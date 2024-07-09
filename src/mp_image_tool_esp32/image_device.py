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

import os
import re
from subprocess import PIPE, CalledProcessError, Popen
from tempfile import NamedTemporaryFile
from typing import IO, Any, BinaryIO

import tqdm
from colorama import Fore

from .common import KB, MB, B, Levels, debug, error, info, verbosity

BAUDRATES = (115200, 230400, 460800, 921600, 1500000, 2000000, 3000000)

BLOCKSIZE = B  # Default block size for erasing/writing regions of the flash storage

baudrate = 460800  # Default baudrate for esptool.py

esptool_args: str = ""  # Default arguments for the esptool.py commands

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
    info(f"Using baudrate {baudrate}")
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


def esptool(port: str, command: str, size: int = 0) -> str:
    """Run the `esptool.py` command and return the output as a string.
    A tqdm progress bar is shown for read/write greater than 16KB.
    Errors in the `esptool.py` command are raised as a `CalledProcessError`."""
    cmd = f"esptool.py {esptool_args} --baud {baudrate} --port {port} {command}"
    debug("$", cmd)  # Use Popen() so we can monitor progress messages in the output
    p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE, text=True, bufsize=0)
    output, stderr = "", ""
    if verbosity(Levels.INFO) and size > 32 * KB and p.stdout:
        output = esptool_progress_bar(p.stdout, size)  # Show a progress bar
        debug(output)
    elif p.stdout:
        while s := p.stdout.readline():
            output += s
            debug(s, end="")  # Show output as it happens if debug==True
    output = output.strip()
    if p.stderr and (stderr := p.stderr.read().strip()):
        error(stderr)
    err = p.poll()
    if err and not (err == 1 and output.endswith("set --after option to 'no_reset'.")):
        # Ignore the "set --after" warning message and ercode for esp32s2.
        # If we add "--after no_reset", reconnects to the device fail repeatedly
        error(f"Error: {cmd} returns error {err}.")
        if stderr:
            print(stderr)
        if output:
            print(output)
        raise CalledProcessError(p.returncode, cmd, output, stderr)
    return output


class Esp32DeviceFileWrapper(BinaryIO):
    """A virtual file-like wrapper around the flash storage on an esp32 device.
    This allows the device to be used as a file-like object for reading and
    writing. Uses `esptool.py` to read and write data to/from the attached
    device."""

    def __init__(self, name: str):
        if not os.path.exists(name):
            raise FileNotFoundError(f"No such device: '{name}'")
        self.port, self.pos, self.end = name, 0, 0

    def read(self, nbytes: int | None = None) -> bytes:
        with NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
            cmd = f"read_flash {self.pos:#x} {nbytes:#x} {f.name}"
            esptool(self.port, cmd, size=nbytes or 0x1000)
            data = f.read()
            if len(data) != nbytes:
                raise ValueError(
                    f"Read {len(data)} bytes from device, expected {nbytes}."
                )
            self.pos += len(data)
            return data

    def write(self, data: bytes) -> int:  # type: ignore
        with NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
            f.write(data)
            f.flush()
            esptool(self.port, f"write_flash -z {self.pos:#x} {f.name}", size=len(data))
            self.pos += len(data)
            return len(data)

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
        esptool(self.port, f"erase_region {self.pos:#x} {size:#x}")
        self.pos += size

    def autodetect(self) -> tuple[str, int]:
        """Auto detect and return (as a tuple) the `chip_name` and `flash_size`
        attached to the serial device."""
        output = esptool(self.port, "flash_id")
        match = re.search(r"^Detecting chip type[. ]*(ESP.*)$", output, re.MULTILINE)
        chip_name: str = match.group(1).lower().replace("-", "") if match else ""
        match = re.search(r"^Detected flash size: *([0-9]*)MB$", output, re.MULTILINE)
        flash_size = int(match.group(1)) * MB if match else 0
        if chip_name:
            global esptool_args
            esptool_args = " ".join((esptool_args, "--chip", chip_name))
        return chip_name, flash_size
