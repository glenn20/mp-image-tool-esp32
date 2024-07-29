# MIT License: Copyright (c) 2023 @glenn20
"""Provides a File-like interface to the flash storage on a serial-attached
ESP32 device (ESP32/S2/S3/C2/C3).

Provides the `Esp32FileWrapper` class which extends the `io.RawIOBase` class to
provided a File-like interface to the flash storage on the ESP32 device. Uses
`esptool.py` to read and write data to/from the attached device.

If `common.debug` is set True, all esptool.py commands and output are printed to
stdout.
"""

from __future__ import annotations

import io
import re
import shlex
import sys
from abc import ABC, abstractmethod
from contextlib import contextmanager
from subprocess import PIPE, CalledProcessError, Popen
from tempfile import NamedTemporaryFile
from typing import IO, Any, Callable, Dict, Generator, Sequence

import esptool
import esptool.cmds
import esptool.util
import tqdm
from colorama import Fore

from . import logger as log
from .argtypes import KB, MB, B

BAUDRATES = (115200, 230400, 460800, 921600, 1500000, 2000000, 3000000)

BAUDRATE = 460800  # Default baudrate for esptool.py

BLOCKSIZE = B  # Block size for erasing/writing regions of the flash storage

tqdm_args: dict[str, Any] = {
    "ascii": " =",
    "bar_format": (
        Fore.CYAN
        + "{l_bar}{bar}| "
        + Fore.GREEN
        + "{n:,}/{total:,}kB {rate_fmt}"
        + Fore.RESET
    ),
}

# Regexp to match progress messages printed out by esptool.py
# match[1] is "" for reads and "Writing at " for writes
# match[2] is the number of bytes read/written,
# match[3] is the percentage complete
# Matches: "Writing at 0x0002030... (2 %)\x08" and "1375 (1 %)\x08" at end of output
PROGRESS_MESSAGE_REGEXP = re.compile(
    r"(Writing at )?((0x)?[0-9a-f]+)[.]* *\(([0-9]+) *%\)[\n\r\x08]$"
)


def esptool_progress_bar(stdout: IO[str], size: int) -> str:
    """Use a tqdm progress bar to show progress of `esptool.py` reads and
    writes. Monitors command output from `stdout` and updates the progress bar
    when progress updates are received."""
    offset, output = 0, ""

    with tqdm.trange(0, size // KB, unit="kB", **tqdm_args) as pbar:
        while stdout and (s := stdout.read(1)):
            output += s
            if (
                s in ("\n", "\r", "\x08")  # If we have a whole new line
                and (match := re.search(PROGRESS_MESSAGE_REGEXP, output))  # and a match
                and (n := int(match[2], 0) // KB) > pbar.n  # and number has increased
            ):
                # On writes, the first number is a starting value - need to subtract
                offset = offset or (n if match[1] else 0)
                pbar.update((n - offset - pbar.n))  # Update the progress bar
        pbar.update((size // KB) - pbar.n)  # A final update to make sure we hit 100%
        return output


def set_baudrate(baud: int) -> int:
    """Set the baudrate for `esptool.py` to the highest value <= `baud`."""
    return max(filter(lambda x: x <= baud, BAUDRATES))


# A context manager to redirect stdout and stderr to a buffer
# Will print stderr to stdout if an error occurs
# This is used to wrap calls to esptool module functions directly
@contextmanager
def redirect_stdout_stderr(
    name: str = "esptool",
) -> Generator[io.StringIO, None, None]:
    """A contect manager to redirect stdout and stderr to StringIO buffers.
    If an exception occurs, stderr will be printed to output.
    The `stdout` StringIO buffer is returned.
    """
    # Redirect stdout and stderr to buffers
    err = None
    sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
    try:
        yield sys.stdout  # Pass the output as value of the contextmanager
    except Exception as e:
        err = e
    finally:
        output, stderr = sys.stdout.getvalue(), sys.stderr.getvalue()
        sys.stdout, sys.stderr = sys.__stdout__, sys.__stderr__

    if err:
        log.error(f"Error: {name} raises {type(err).__name__}")
        log.warning(stderr)
        log.warning(output)
        raise err
    else:
        log.debug(output)


# This is used to run esptool.py commands in a subprocess
def esptool_subprocess(command: str, size: int = 0) -> str:
    """Run the `esptool.py` command and return the output as a string.
    A tqdm progress bar is shown for read/write greater than 16KB.
    Errors in the `esptool.py` command are raised as a `CalledProcessError`."""
    args = shlex.split(command)
    log.debug(f"$ {command}")
    # Use Popen() to monitor progress messages in the output
    p = Popen(args, stdout=PIPE, stderr=PIPE, text=True, bufsize=0)
    output, stderr = "", ""
    if log.isloglevel("info") and size > 32 * KB and p.stdout:
        output = esptool_progress_bar(p.stdout, size)  # Show a progress bar
        log.debug(output)
    elif p.stdout:
        for line in p.stdout:
            output += line
            log.debug(line.strip())  # Show output as it happens if debug==True
    output = output.strip()
    if p.stderr:
        stderr = p.stderr.read().strip()
    err = p.poll()
    if err and not (err == 1 and output.endswith("set --after option to 'no_reset'.")):
        # Ignore the "set --after" warning message and ercode for esp32s2.
        # If we add "--after no_reset", reconnects to the device fail repeatedly
        log.error(f"Error: {command} raises error {err}.")
        if stderr:
            log.error(stderr)
        if output:
            log.error(output)
        raise CalledProcessError(p.returncode, command, output, stderr)
    elif stderr:
        log.warning(stderr)
    return output


def check_alignment(func: Callable[..., Any]) -> Callable[..., Any]:
    def inner(self: Any, *args: Sequence[Any]) -> Callable[..., Any]:
        for arg in args:
            if isinstance(arg, int):
                if arg % BLOCKSIZE:
                    raise ValueError(
                        f"{func.__name__}: {arg:#x} is not aligned to "
                        f"blocksize ({BLOCKSIZE:#x} bytes)."
                    )
        return func(self, *args)

    return inner


class ESPTool(ABC):
    """Protocol for classes which provide an interface to an ESP32 device
    using `esptool.py`. The protocol defines the methods required to configure,
    read and write data to the device.
    """

    name: str
    port: str
    baud: int
    chip_name: str
    flash_size: int
    flash_size_str: str
    esptool_args: str

    @abstractmethod
    def esptool_cmd(self, command: str) -> str:
        """Execute an `esptool.py` command and return the output as a string."""
        ...

    @abstractmethod
    def write_flash(self, pos: int, data: bytes) -> int:
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


class ESPToolSubprocess(ESPTool):
    """An ESPTool class which runs esptool commands in a `esptool.py`
    subprocess."""

    name = "subprocess"

    def __init__(self, port: str, baud: int = 0):
        self.port = port
        self.baud = set_baudrate(baud or BAUDRATE)
        self.esptool_args = "--after no_reset"
        output = self.esptool_cmd("flash_id")
        match = re.search(r"^Detecting chip type[. ]*(ESP.*)$", output, re.MULTILINE)
        self.chip_name: str = match.group(1).lower().replace("-", "") if match else ""
        match = re.search(r"^Detected flash size: *([0-9]*)MB$", output, re.MULTILINE)
        self.flash_size_str = match.group(1) if match else ""
        self.flash_size = int(match.group(1)) * MB if match else 0
        if self.chip_name:
            self.esptool_args = " ".join((self.esptool_args, "--chip", self.chip_name))
        log.debug(f"Detected {self.chip_name} with flash size {self.flash_size}.")

    def esptool_cmd(self, command: str) -> str:
        """Run the `esptool.py` command and return the output as a string.
        Calls the `main()` function in the `esptool` module with the command."""
        cmd = (
            f"{sys.executable} -m esptool {self.esptool_args} "
            f"--baud {self.baud} --port {self.port} {command}"
        )
        return esptool_subprocess(cmd)

    @check_alignment
    def write_flash(self, pos: int, data: bytes) -> int:
        with NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
            f.write(data)
            f.flush()
            self.esptool_cmd(f"write_flash {pos:#x} {f.name}")
            return len(data)

    def read_flash(self, pos: int, size: int) -> bytes:
        with NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
            self.esptool_cmd(f"read_flash {pos:#x} {size:#x} {f.name}")
            f.seek(0)
            return f.read()

    @check_alignment
    def erase_flash(self, pos: int, size: int) -> None:
        self.esptool_cmd(f"erase_region {pos:#x} {size:#x}")

    def hard_reset(self) -> None:
        """Reset the ESP32 device using the RTS pin."""
        if "--after no_reset" in self.esptool_args:
            self.esptool_cmd("--after hard_reset chip_id")

    def close(self) -> None:
        pass


class ESPToolModuleMain(ESPToolSubprocess):
    """An ESPTool class which calls `esptool.main()` from the esptool module."""

    name = "command"

    def __init__(self, port: str, baud: int = 0):
        """Connect to the ESP32 device on the specified serial `port`.
        Returns a tuple of the `esp` object, `chip_name` and `flash_size`.
        """
        self.esp = None
        super().__init__(port, baud)
        self.esptool_args = "--after no_reset"

    def esptool_cmd(self, command: str) -> str:
        """Run the `esptool.py` command and return the output as a string.
        Calls the `main()` function in the `esptool` module with the command."""
        cmd = f"{self.esptool_args} --baud {self.baud} --port {self.port} {command}"
        log.debug(f"$ esptool.py {cmd}")
        with redirect_stdout_stderr(command) as output:
            esptool.main(shlex.split(cmd), self.esp)
        return output.getvalue()


class ESPToolModuleDirect(ESPToolModuleMain):
    """Call undocumented methods in the esptool modules directly to perform
    operations on the ESP32 device, instead of invoking through the
    `esptool.main()` command interface. This is more efficient and allows us to
    initialise the device once and keep the connection open for all.

    Calls `esptool.main()` on initialisation to ensure the connection to the
    device is correctly initialised.
    """

    name = "direct"

    def __init__(self, port: str, baud: int = 0):
        """Connect to the ESP32 device on the specified serial `port`."""
        with redirect_stdout_stderr("detect_chip"):
            esp = esptool.cmds.detect_chip(port)
            esp = esp.run_stub()

        self.esp: esptool.ESPLoader = esp
        self.port = port
        self.baud = set_baudrate(baud or BAUDRATE)
        self.esptool_args = "--after no_reset_stub --no-stub"
        # Initialize the device and detect the flash size
        self.esptool_cmd("flash_id")
        log.debug(f"Connected to ESP32 device on {port} at {baud} baud.")
        self.chip_name = esp.CHIP_NAME.lower().replace("-", "")
        self.flash_size_str = esptool.cmds.detect_flash_size(esp) or ""
        log.debug(f"Detected flash size: {self.flash_size_str}")
        self.flash_size = esptool.util.flash_size_bytes(self.flash_size_str) or 0
        log.debug(f"Detected {self.chip_name} with flash size {self.flash_size}.")
        if not self.flash_size_str or not self.flash_size:
            raise ValueError("Could not detect flash size.")
        log.debug(f"Detected {self.chip_name} with flash size {self.flash_size}.")

    @check_alignment
    def write_flash(self, pos: int, data: bytes) -> int:
        # esptool cmds require an argparse-like args object. We use the Dictargs
        # class to mockup the required arguments for `write_flash()`
        # Unfortunately esptool doesn't provide a lower-level API for writing
        # the flash that takes care of all the initialisation needed.
        class Dictargs(Dict[str, Any]):
            __getattr__: Callable[[str], Any] = dict.get  # type: ignore

        args = Dictargs(
            flash_mode="keep",
            compress=True,
            addr_filename=((pos, io.BytesIO(data)),),
            flash_size=self.flash_size_str,
        )
        with redirect_stdout_stderr("esptool_write_flash"):
            esptool.cmds.write_flash(self.esp, args)
        return len(data)

    def read_flash(self, pos: int, size: int) -> bytes:
        data = self.esp.read_flash(pos, size, None)
        return data

    @check_alignment
    def erase_flash(self, pos: int, size: int) -> None:
        self.esp.erase_region(pos, size)

    def hard_reset(self) -> None:
        """Reset the ESP32 device using the RTS pin."""
        self.esp.hard_reset()

    def close(self) -> None:
        if self.esp:
            self.esp._port.close()  # type: ignore - esptool does not close the port


methods = (ESPToolSubprocess, ESPToolModuleMain, ESPToolModuleDirect)

esptool_methods: dict[str, type[ESPToolSubprocess]] = {
    method.name: method for method in methods
}


def esptool_wrapper(port: str, baud: int = 0, *, method: str = "direct") -> ESPTool:
    """Connect to the ESP32 device on the specified serial `port`.
    Returns an `ESPTool` object which can be used to read and write to the device.
    The `method` parameter can be used to select the method used to connect to the
    device. The default is the `direct` method which is more efficient."""
    meth = esptool_methods[method or "direct"]
    return meth(port, baud)
