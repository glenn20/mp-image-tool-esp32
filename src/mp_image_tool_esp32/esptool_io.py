# MIT License: Copyright (c) 2023 @glenn20
"""Provides an interface to the flash storage on a serial-attached ESP32
device (ESP32/S2/S3/C2/C3).

Defines the `EspTool` abstract base class which provides methods for reading and
writing flash storage on an ESP32 device.

Also provides three different implementations of the `ESPTool` interface:

- `ESPToolSubprocess` performs operations by running `esptool.py` as a shell
  command in a subprocess using `Popen()`.

- `ESPToolModuleMain` performs operations through the `esptool.main()` command
  processor in the `esptool` module (from the `esptool.py` python package).

- `ESPToolCommandDirect` performs operations by calling lower-level methods in
  the `esptool` module. Generally, this is the most efficient method for
  performing operations on the ESP32 device.

All esptool.py commands and output are logged to the DEBUG facility.
"""

from __future__ import annotations

import io
import re
import shlex
import sys
from abc import ABC, abstractmethod
from subprocess import PIPE, CalledProcessError, Popen
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Dict, Sequence

import esptool
import esptool.cmds
import esptool.util
from typing_extensions import Buffer

from . import logger
from .argtypes import MB, B
from .progress_bar import EsptoolMonitor, ProgressBar

log = logger.getLogger(__name__)

BAUDRATES = (115200, 230400, 460800, 921600, 1500000, 2000000, 3000000)
BAUDRATE = 921600  # Default baudrate for esptool.py
BLOCKSIZE = B  # Block size for erasing/writing regions of the flash storage


def set_baudrate(baud: int) -> int:
    """Set the baudrate for `esptool.py` to the highest value <= `baud`."""
    return max(filter(lambda x: x <= baud, BAUDRATES))


class ESPTool(ABC):
    """Base class for classes which provide an interface to an ESP32 device
    using `esptool.py`. The protocol defines the methods required to configure,
    read and write data to the device.
    """

    port: str
    baud: int
    chip_name: str
    flash_size: int
    esptool_args: str = "--after no_reset"

    @abstractmethod
    def __init__(self, port: str, baud: int) -> None:
        """Execute an `esptool.py` command and return the output as a string."""
        ...

    @abstractmethod
    def esptool_cmd(self, command: str, *, size: int = 0) -> str:
        """Execute an `esptool.py` command and return the output as a string."""
        ...

    @abstractmethod
    def write_flash(self, pos: int, data: Buffer) -> int:
        """Write `data` to the device flash storage at position `pos`."""
        ...

    @abstractmethod
    def read_flash(self, pos: int, size: int) -> bytes:
        """Read `size` bytes from the device flash storage at position `pos`."""
        ...

    @abstractmethod
    def erase_flash(self, pos: int, size: int) -> None:
        """Erase a region of the device flash storage starting at `pos`."""
        ...

    @abstractmethod
    def hard_reset(self) -> None:
        """Perform a hard reset of the device using the RTS pin."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Close the connection to the device."""
        ...


def check_alignment(func: Callable[..., Any]) -> Callable[..., Any]:
    """Raise a ValueError if any of the arguments are integers that are not
    aligned to the `BLOCKSIZE`."""

    def inner(self: Any, *args: Sequence[Any]) -> Callable[..., Any]:
        for arg in args:
            if isinstance(arg, int):
                if arg % BLOCKSIZE:
                    raise ValueError(
                        f"{func.__name__}: {arg:#x} is not aligned to "
                        f"blocksize ({BLOCKSIZE:#x} bytes)."
                    )
        return func(self, *args)  # type: ignore

    return inner


class ESPToolSubprocess(ESPTool):
    """An ESPTool class which runs esptool commands in a `esptool.py`
    subprocess."""

    def __init__(self, port: str, baud: int = 0):
        self.port = port
        self.baud = set_baudrate(baud or BAUDRATE)
        output = self.esptool_cmd("flash_id")
        match = re.search(r"^Detecting chip type[. ]*(ESP.*)$", output, re.MULTILINE)
        self.chip_name = match.group(1).lower().replace("-", "") if match else ""
        match = re.search(r"^Detected flash size: *([0-9]*)MB$", output, re.MULTILINE)
        self.flash_size = int(match.group(1)) * MB if match else 0
        if self.chip_name:
            self.esptool_args = " ".join((self.esptool_args, "--chip", self.chip_name))
        log.debug(
            f"Detected {self.chip_name} with flash size {self.flash_size / MB}MB."
        )

    def esptool_run(self, cmd: str) -> None:
        """Run an esptool command in a subprocess and echo output to sys.stdout."""
        # subprocess.run() will not redirect the output if we have redirected
        # sys.stdout, so we use Popen() to capture the esptool read_flash and
        # write_flash progress messages and echo them to sys.stdout and sys.stderr
        # (which may then be redirected for capture).
        #
        # Progress messages are not terminated with a newline, so we can't use line
        # buffered output (bufsize=1) to get progress messages from esptool.py.
        # Either use unbuffered (=0) or a small buffer size for responsiveness.
        cmd = f"{sys.executable} -m esptool {cmd}"  # python -m esptool ...
        p = Popen(shlex.split(cmd), stdout=PIPE, stderr=PIPE, text=True, bufsize=20)
        if p.stdout:  # Read stdout first to capture progress messages
            while s := p.stdout.read(1):  # Cant use readline() to read messages
                sys.stdout.write(s)
        if p.stderr:
            sys.stderr.write(p.stderr.read())
        if err := p.wait():
            raise CalledProcessError(err, cmd)

    def esptool_cmd(self, command: str, *, size: int = 0) -> str:
        cmd = f"{self.esptool_args} --baud {self.baud} --port {self.port} {command}"
        name = command.split()[0]  # Get the command name for the progress bar
        name = " ".join(s.capitalize() for s in name.split("_", 1))
        with EsptoolMonitor(size, name=name) as monitor:
            self.esptool_run(cmd)
        return monitor.output

    @check_alignment
    def write_flash(self, pos: int, data: Buffer) -> int:
        data = memoryview(data)
        with NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
            f.write(data)
            f.flush()
            self.esptool_cmd(f"write_flash {pos:#x} {f.name}", size=len(data))
            return len(data)

    def read_flash(self, pos: int, size: int) -> bytes:
        with NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
            self.esptool_cmd(f"read_flash {pos:#x} {size:#x} {f.name}", size=size)
            f.seek(0)
            return f.read()

    @check_alignment
    def erase_flash(self, pos: int, size: int) -> None:
        self.esptool_cmd(f"erase_region {pos:#x} {size:#x}")

    def hard_reset(self) -> None:
        if "--after no_reset" in self.esptool_args:
            self.esptool_cmd("--after hard_reset chip_id")

    def close(self) -> None:
        pass


class ESPToolModuleMain(ESPToolSubprocess):
    esp_maybe: esptool.ESPLoader | None

    """An ESPTool class which calls `esptool.main()` from the esptool module.
    Overrides the esptool_run() method to run the esptool commands using
    `esptool.main()` in this python process (instead of a subprocess)."""

    def __init__(self, port: str, baud: int = 0):
        self.esp_maybe = None
        super().__init__(port, baud)

    def esptool_run(self, cmd: str) -> None:
        esptool.main(shlex.split(cmd), self.esp_maybe)


class ESPToolModuleDirect(ESPToolModuleMain):
    """Call undocumented methods in the esptool modules directly to perform
    read_flash/write_flash/erase_flash operations on the ESP32 device, instead
    of invoking through the `esptool.main()` command interface. This is more
    efficient and allows us to initialise the device once and keep the
    connection open for all.

    Calls `esptool.main()` on initialisation to ensure the connection to the
    device is correctly established.
    """

    esp: esptool.ESPLoader

    def __init__(self, port: str, baud: int = 0):
        self.port = port
        self.baud = set_baudrate(baud or BAUDRATE)
        with EsptoolMonitor(name="detect_chip"):  # Suppress esptool output
            esp = esptool.cmds.detect_chip(port)
            esp = esp.run_stub()  # Load the stub flasher for better performance

        self.esp = esp
        self.esp_maybe = esp
        self.esptool_args = "--after no_reset_stub --no-stub"
        # Initialize the device and detect the flash size
        self.esptool_cmd("flash_id")
        log.debug(f"Connected to ESP32 device on {port} at {baud} baud.")
        self.chip_name = esp.CHIP_NAME.lower().replace("-", "")
        size_str = esptool.cmds.detect_flash_size(esp) or ""
        log.debug(f"Detected flash size: {size_str}")
        self.flash_size = esptool.util.flash_size_bytes(size_str) or 0
        log.debug(f"Detected {self.chip_name} with flash size {size_str}.")
        if not size_str or not self.flash_size:
            raise ValueError("Could not detect flash size.")

    @check_alignment
    def write_flash(self, pos: int, data: Buffer) -> int:
        # esptool cmds require an argparse-like args object. We use the Dictargs
        # class to mockup the required arguments for `write_flash()`
        # Unfortunately esptool doesn't provide a lower-level API for writing
        # the flash that takes care of all the setup needed.
        class Dictargs(Dict[str, Any]):
            __getattr__: Callable[[str], Any] = dict.get  # type: ignore

        args = Dictargs(
            flash_mode="keep",
            flash_size="keep",
            flash_frequency="keep",
            compress=True,
            addr_filename=((pos, io.BytesIO(data)),),
        )
        size = len(memoryview(data))
        with EsptoolMonitor(size, name="Write Flash"):  # Show a progress bar
            esptool.cmds.write_flash(self.esp, args)
        return size

    def read_flash(self, pos: int, size: int) -> bytes:
        with ProgressBar(total=size, name="Read Flash") as pbar:  # Show a progress bar
            return self.esp.read_flash(pos, size, pbar.update)

    @check_alignment
    def erase_flash(self, pos: int, size: int) -> None:
        self.esp.erase_region(pos, size)

    def hard_reset(self) -> None:
        with EsptoolMonitor(name="esptool_hard_reset"):  # Suppress esptool output
            self.esp.hard_reset()

    def close(self) -> None:
        if self.esp:
            self.esp._port.close()


# We have three different implementations of the ESPTool interface
# A map to select implementation by name
esptool_methods: dict[str, type[ESPTool]] = {
    "subprocess": ESPToolSubprocess,
    "command": ESPToolModuleMain,
    "direct": ESPToolModuleDirect,
}


def get_esptool(port: str, baud: int = 0, *, method: str = "direct") -> ESPTool:
    """Return an `ESPTool` object which can be used to read and write to the
    device. The `method` parameter can be used to select the method used to
    connect to the device. The default is the `direct` method which is more
    efficient."""
    esptool = esptool_methods[method or "direct"]
    return esptool(port, baud)
