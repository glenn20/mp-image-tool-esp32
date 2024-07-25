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
import os
import re
import shlex
import sys
from contextlib import contextmanager
from tempfile import NamedTemporaryFile
from typing import IO, Any, BinaryIO, Generator

import esptool  # type: ignore
import tqdm
from colorama import Fore

from . import logger as log
from .argtypes import KB, B, numeric_arg

BAUDRATES = (115200, 230400, 460800, 921600, 1500000, 2000000, 3000000)

BLOCKSIZE = B  # Default block size for erasing/writing regions of the flash storage

baudrate = 460800  # Default baudrate for esptool.py

reset_on_close = True  # Reset the device on close

# These arguments are necessary for esptool.py to connect to the device
# These prevent esptool.main() from resetting the device on finish
esptool_args: str = "--after no_reset_stub --no-stub"

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


def set_baudrate(baud: int) -> int:
    """Set the baudrate for `esptool.py` to the highest value <= `baud`."""
    global baudrate
    baudrate = max(filter(lambda x: x <= baud, BAUDRATES))
    return baudrate


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


# A context manager to redirect stdout and stderr to a buffer
# Will print stderr to stdout if an error occurs
@contextmanager
def redirect_stdout_stderr(
    name: str = "esptool",
) -> Generator[io.StringIO, None, None]:
    """A contect manager to redirect stdout and stderr to StringIO buffers.
    If an exception occurs, stderr will be printed to output.
    The `stdout` StringIO buffer is returned.
    """
    sys.stdout = io.StringIO()  # Redirect stdout to a buffer
    sys.stderr = io.StringIO()  # Redirect stderr to a buffer
    try:
        yield sys.stdout
    except Exception as err:
        output = sys.stdout.getvalue()
        stderr = sys.stderr.getvalue()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        log.error(f"Error: {name} returns {type(err).__name__}: {err}")
        if stderr:
            log.warning(stderr)
        log.warning(output)
    else:
        output = sys.stdout.getvalue()
        stderr = sys.stderr.getvalue()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__


def esptool_run(command: str, esp: esptool.ESPLoader) -> str:
    """Run the `esptool.py` command and return the output as a string."""
    cmd = f"{esptool_args} {command}"
    log.debug(f"$ {cmd}")
    with redirect_stdout_stderr() as output:
        esptool.main(shlex.split(cmd), esp)  # type: ignore
    return output.getvalue()


def esptool_connect(port: str) -> tuple[esptool.ESPLoader, str, int]:
    """Connect to the ESP32 device on the specified serial `port`.
    Returns a tuple of the `esp` object, `chip_name` and `flash_size`.
    """
    with redirect_stdout_stderr():
        esp = esptool.cmds.detect_chip(port)  # type: ignore
        esp = esp.run_stub()  # type: ignore
    if esp is None or not isinstance(esp, esptool.ESPLoader):
        raise ValueError(f"Failed to connect to device on port {port}.")

    # Initialize the device and detect the flash size
    esptool_run(f"--baud {baudrate} flash_id", esp)
    chip_name: str = esp.CHIP_NAME.lower().replace("-", "")
    size_str: str = esptool.cmds.detect_flash_size(esp)  # type: ignore
    if not isinstance(size_str, str):
        raise ValueError(f"Failed to detect flash size on device {chip_name}.")
    flash_size: int = numeric_arg(size_str.rstrip("B"))
    log.debug(f"Detected {chip_name} with flash size {flash_size}.")
    return esp, chip_name, flash_size


class Esp32DeviceFileWrapper(BinaryIO):
    """A virtual file-like wrapper around the flash storage on an esp32 device.
    This allows the device to be used as a file-like object for reading and
    writing. Uses `esptool.py` to read and write data to/from the attached
    device."""

    def __init__(self, name: str):
        if not os.path.exists(name):
            raise FileNotFoundError(f"No such device: '{name}'")
        self.esp, self.chip_name, self.flash_size = esptool_connect(name)
        self.pos = 0
        self.end = 0

    def read(self, nbytes: int | None = None) -> bytes:
        log.debug(f"Reading {nbytes:#x} bytes from {self.pos:#x}...")
        data = self.esp.read_flash(self.pos, nbytes or self.end - self.pos, None)  # type: ignore
        if len(data) != nbytes:
            raise ValueError(f"Read {len(data)} bytes from device, expected {nbytes}.")
        self.pos += len(data)
        return data

    def write(self, data: bytes) -> int:  # type: ignore
        if len(data) % BLOCKSIZE:
            raise ValueError(
                f"Write of {len(data):#x} is not aligned to "
                f"blocksize ({BLOCKSIZE:#x} bytes)."
            )
        if self.pos % BLOCKSIZE:
            raise ValueError(
                f"Write at position {self.pos:#x} is not multiple of "
                f"blocksize ({BLOCKSIZE:#x} bytes)."
            )
        with NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
            f.write(data)
            f.flush()
            esptool_run(f"write_flash -z {self.pos:#x} {f.name}", self.esp)
            size = len(data)
            self.pos += size
            return size

    def seek(self, pos: int, whence: int = 0):
        self.pos = (0, self.pos, self.end)[whence] + pos
        return self.pos

    def tell(self) -> int:
        return self.pos

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    # Some additional convenience methods
    def erase(self, size: int) -> None:
        """Erase a region of the device flash storage using `esptool.py`.
        Size should be a multiple of `0x1000 (4096)`, the device block size"""
        esptool_run(f"erase_region {self.pos:#x} {size:#x}", self.esp)
        self.pos += size

    def close(self) -> None:
        if reset_on_close:
            self.esp.hard_reset()
        self.esp._port.close()  # type: ignore
        self.pos = 0
        self.end = 0
