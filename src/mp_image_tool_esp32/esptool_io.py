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
import logging
import re
import shlex
import sys
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from subprocess import PIPE, CalledProcessError, Popen
from tempfile import NamedTemporaryFile
from threading import Lock, Thread
from typing import IO, Any, Callable, Dict, Generator, Sequence

import esptool
import esptool.cmds
import esptool.util
import tqdm
from typing_extensions import Buffer

from . import logger
from .argtypes import KB, MB, B

log = logger.getLogger(__name__)

BAUDRATES = (115200, 230400, 460800, 921600, 1500000, 2000000, 3000000)
BAUDRATE = 921600  # Default baudrate for esptool.py
BLOCKSIZE = B  # Block size for erasing/writing regions of the flash storage


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


# Arguments for the tqdm progress bar
tqdm_args: dict[str, Any] = dict(
    delay=0,
    file=sys.__stderr__,
    dynamic_ncols=True,
)

# Regexp to match progress messages printed out by esptool.py
# match[1] is "" for reads and "Writing at " for writes
# match[2] is the number of bytes read/written,
# match[3] is the percentage complete
# Matches: "Writing at 0x0002030... (2 %)\x08" and "1375 (1 %)\x08" at end of output
PROGRESS_BAR_MESSAGE_REGEXP = re.compile(
    r"(Writing at )?((0x)?[0-9a-f]+)[.]* *\(([0-9]+) *%\)[\n\r\x08]$"
)


def set_baudrate(baud: int) -> int:
    """Set the baudrate for `esptool.py` to the highest value <= `baud`."""
    return max(filter(lambda x: x <= baud, BAUDRATES))


class ESPToolProgressBar:
    """Show a progress bar for `esptool.py` reads and writes.

    Monitors the `input` IO stream for progress messages and updates a
    progress bar accordingly. `size` is the expected size of the read/write
    operation. If used as a context manager, the progress bar is run in a
    separate thread while executing the body of the `with` block. If the `run()`
    method is used, the progress bar is run in the current thread.

    The progress bar is shown using the `tqdm` module.
    """

    MIN_SIZE = 64 * KB

    def __init__(self, input: IO[str], size: int = 0):
        self.input = input  # The input stream to monitor
        self.size: int = size  # The expected size of the read/write operation
        self.output: str = ""  # Save the output for later
        self.thread: Thread | None = None  # The thread to run the progress bar

    def run(self) -> str:
        """Use a tqdm progress bar to show progress of `esptool.py` reads and
        writes. Monitors command output from `stdout` and updates the progress bar
        when progress updates are received."""
        if self.size < self.MIN_SIZE:
            return self.input.read()
        n, offset, line = 0, 0, ""
        with tqdm.trange(0, self.size // KB, unit="kB", **tqdm_args) as pbar:
            while n < self.size and (s := self.input.read(1)):
                line += s
                self.output += s
                if s in ("\n", "\r", "\x08") and (  # If we have a whole new line
                    match := re.search(PROGRESS_BAR_MESSAGE_REGEXP, line)  # and a match
                ):
                    n = int(match[2], 0)
                    # On writes, the first number is a starting value - need to subtract
                    offset = offset or (n if match[1] else 0)
                    pbar.update((n - offset) // KB - pbar.n)  # Update the progress bar
                    line = ""
            pbar.update((self.size // KB) - pbar.n)  # Make sure we hit 100%
        self.output += self.input.read()
        return self.output

    def __enter__(self) -> ESPToolProgressBar:
        if self.size >= self.MIN_SIZE:
            self.thread = Thread(target=self.run)
            self.thread.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any):
        if self.thread:
            self.input.close()
            self.thread.join()
        self.output += self.input.read()


class StringIO_RW(io.StringIO):
    """A thread-safe StringIO buffer which can be read from and written to."""

    def __init__(self, s: str = ""):
        super().__init__()
        self.buf = s
        self.lock = Lock()

    def read(self, size: int | None = None) -> str:
        while not self.closed and len(self.buf) < (size or 1):
            time.sleep(0.1)
        with self.lock:
            n = size or len(self.buf)
            s = self.buf[:n]
            self.buf = self.buf[n:]
            return s

    def write(self, s: str) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed file.")
        with self.lock:
            self.buf += s
            return len(s)


# A context manager to redirect stdout and stderr to a buffer
# Will print stderr to stdout if an error occurs
# This is used to wrap calls to esptool module functions directly
@contextmanager
def redirect_stdout_stderr(name: str = "esptool") -> Generator[IO[str], None, None]:
    """A contect manager to redirect stdout and stderr to StringIO buffers.
    If an exception occurs, stderr will be printed to output.
    The `stdout` StringIO buffer is returned.
    """
    # Redirect stdout and stderr to StringIO buffers
    backupio = sys.stdout, sys.stderr
    out, err = StringIO_RW(), StringIO_RW()
    sys.stdout, sys.stderr = out, err

    error = None
    try:
        yield out  # Pass the output as value of the contextmanager
    except KeyboardInterrupt as e:
        error = e
    except Exception as e:
        error = e
    finally:
        sys.stdout, sys.stderr = backupio
        stdout = "" if out.closed else out.getvalue()
        stderr = "" if err.closed else err.getvalue()
        if error:
            log.error(f"Error: {name} raises {type(err).__name__}")
            if stderr:
                log.warning(stderr)
            if stdout:
                log.warning(stdout)
            raise error
        else:
            if stderr:
                log.warning(stderr)
            if stdout:
                log.debug(stdout)


# This is used to run esptool.py commands in a subprocess
def esptool_subprocess(command: str, *, size: int = 0) -> str:
    """Run the `esptool.py` command and return the output as a string.
    A tqdm progress bar is shown for read/write greater than 16KB.
    Errors in the `esptool.py` command are raised as a `CalledProcessError`."""
    args = shlex.split(command)
    log.debug(f"$ {command}")
    # Use Popen() to monitor progress messages in the output
    p = Popen(args, stdout=PIPE, stderr=PIPE, text=True, bufsize=0)
    output, stderr = "", ""
    if (
        log.isEnabledFor(logging.INFO)
        and size > ESPToolProgressBar.MIN_SIZE
        and p.stdout
    ):
        output = ESPToolProgressBar(p.stdout, size).run()  # Show a progress bar
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
        return func(self, *args)

    return inner


class ESPToolSubprocess(ESPTool):
    """An ESPTool class which runs esptool commands in a `esptool.py`
    subprocess."""

    def __init__(self, port: str, baud: int = 0):
        self.port = port
        self.baud = set_baudrate(baud or BAUDRATE)
        output = self.esptool_cmd("flash_id")
        match = re.search(r"^Detecting chip type[. ]*(ESP.*)$", output, re.MULTILINE)
        self.chip_name: str = match.group(1).lower().replace("-", "") if match else ""
        match = re.search(r"^Detected flash size: *([0-9]*)MB$", output, re.MULTILINE)
        self.flash_size = int(match.group(1)) * MB if match else 0
        if self.chip_name:
            self.esptool_args = " ".join((self.esptool_args, "--chip", self.chip_name))
        log.debug(f"Detected {self.chip_name} with flash size {self.flash_size/MB}MB.")

    def esptool_cmd(self, command: str, *, size: int = 0) -> str:
        """Run the `esptool.py` command and return the output as a string.
        Calls the `main()` function in the `esptool` module with the command."""
        cmd = (
            f"{sys.executable} -m esptool {self.esptool_args} "
            f"--baud {self.baud} --port {self.port} {command}"
        )
        return esptool_subprocess(cmd, size=size)

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
        """Reset the ESP32 device using the RTS pin."""
        if "--after no_reset" in self.esptool_args:
            self.esptool_cmd("--after hard_reset chip_id")

    def close(self) -> None:
        pass


class ESPToolModuleMain(ESPToolSubprocess):
    """An ESPTool class which calls `esptool.main()` from the esptool module.
    Overrides the esptool_cmd() method to run the esptool commands using
    `esptool.main()` in this python process (instead of a subprocess)."""

    def __init__(self, port: str, baud: int = 0):
        """Connect to the ESP32 device on the specified serial `port`.
        Returns a tuple of the `esp` object, `chip_name` and `flash_size`.
        """
        self.esp = None
        super().__init__(port, baud)

    def esptool_cmd(self, command: str, *, size: int = 0) -> str:
        """Run the `esptool.py` command and return the output as a string.
        Calls the `main()` function in the `esptool` module with the command."""
        cmd = f"{self.esptool_args} --baud {self.baud} --port {self.port} {command}"
        log.debug(f"$ esptool.py {cmd}")
        with redirect_stdout_stderr(command) as stdout:
            with ESPToolProgressBar(stdout, size) as pbar:
                esptool.main(shlex.split(cmd), self.esp)
        log.debug(pbar.output)
        return pbar.output


class ESPToolModuleDirect(ESPToolModuleMain):
    """Call undocumented methods in the esptool modules directly to perform
    operations on the ESP32 device, instead of invoking through the
    `esptool.main()` command interface. This is more efficient and allows us to
    initialise the device once and keep the connection open for all.

    Calls `esptool.main()` on initialisation to ensure the connection to the
    device is correctly initialised.
    """

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
        # the flash that takes care of all the initialisation needed.
        class Dictargs(Dict[str, Any]):
            __getattr__: Callable[[str], Any] = dict.get  # type: ignore

        args = Dictargs(
            flash_mode="keep",
            flash_size="keep",
            flash_frequency="keep",
            compress=True,
            addr_filename=((pos, io.BytesIO(data)),),
        )
        data = memoryview(data)
        with redirect_stdout_stderr("esptool_write_flash") as output:
            with ESPToolProgressBar(output, len(data)) as pbar:
                esptool.cmds.write_flash(self.esp, args)
        log.debug(pbar.output)
        return len(data)

    def read_flash(self, pos: int, size: int) -> bytes:
        if size < ESPToolProgressBar.MIN_SIZE:
            return self.esp.read_flash(pos, size, None)
        with tqdm.trange(0, size // KB, unit="kB", **tqdm_args) as pbar:

            def progress(x: int, size: int) -> None:
                pbar.update(x // KB - pbar.n)

            return self.esp.read_flash(pos, size, progress)

    @check_alignment
    def erase_flash(self, pos: int, size: int) -> None:
        self.esp.erase_region(pos, size)

    def hard_reset(self) -> None:
        """Reset the ESP32 device using the RTS pin."""
        with redirect_stdout_stderr("esptool_hard_reset"):
            self.esp.hard_reset()

    def close(self) -> None:
        if self.esp:
            self.esp._port.close()  # type: ignore - esptool does not close the port


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
