# MIT License: Copyright (c) 2023 @glenn20
"""Provides a File-like interface to the flash storage on a serial-attached
ESP32 device (ESP32/S2/S3/C2/C3).

Provides the `Esp32FileWrapper` class which extends the `io.RawIOBase` class to
provided a File-like interface to the flash storage on the ESP32 device. Uses
`esptool.py` to read and write data to/from the attached device.

If `common.debug` is set True, all esptool.py commands and output are printed to
stdout.
"""

import io
import os
import re
from subprocess import PIPE, CalledProcessError, Popen
from tempfile import NamedTemporaryFile
from typing import IO

import tqdm
from colorama import Fore

from .common import KB, MB, Levels, debug, error, verbosity

esptool_args: str = "--baud 460800"  # Default arguments for the esptool.py commands

tqdm_args = {
    "ascii": " =",
    "bar_format": (
        Fore.GREEN
        + "{l_bar}{bar}| "
        + Fore.CYAN
        + "{n:,}/{total:,}kB {rate_fmt}"
        + Fore.RESET
    ),
}

# Regexp to match progress messages printed out by esptool.py
# match[2] is the number of bytes read/written, match[1] is "" for reads
# Matches: "Writing at 0x0002030... (2 %)\r" and "1375 (1 %)\r" at end of output
PROGRESS_MESSAGE_REGEXP = re.compile(
    r"(Writing at )?((0x)?[0-9a-f]+)[.]* *\([0-9]+ *%\)[\n\r\x08]$"
)


def esptool_progress_bar(stdout: IO[str], size: int) -> str:
    """Use a tqdm progress bar to show progress of esptool.py reads and writes.
    Monitors command output from `stdout` and updates the progress bar
    when progress updates are received."""
    offset, output = 0, ""
    with tqdm.trange(0, size // KB, unit="kB", **tqdm_args) as pbar:  # type: ignore
        while stdout and (s := stdout.read(1)):
            output += s
            if (
                s in ("\n", "\r", "\x08")  # If we have a whole new line
                and (match := re.search(PROGRESS_MESSAGE_REGEXP, output))  # and a match
                and (n := int(match[2], 0) // KB) > pbar.n  # and number has increased
            ):
                # On writes, the first number is an offset - need to subtract
                offset = offset or (n if match[1] else 0)
                pbar.update((n - offset - pbar.n))  # Update the progress bar
        pbar.update((size // KB) - pbar.n)  # A final update to make sure we hit 100%
        return output


def exec_esptool(cmd: str, size: int = 0) -> str:
    """Run the esptool.py command `cmd` and return the output as a string.
    A tqdm progress bar is shown for read/write greater than 16KB.
    Errors in the esptool.py command are raised as a CalledProcessError."""
    debug("$", cmd)  # Use Popen() so we can monitor progress messages in the output
    p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE, text=True, bufsize=0)
    output, stderr = "", ""
    if verbosity(Levels.INFO) and size > 16 * KB and p.stdout:
        output = esptool_progress_bar(p.stdout, size)  # Show a progress bar
        debug(output)
    elif p.stdout:
        while s := p.stdout.readline():
            output += s
            debug(s, end="")  # Show output as it happens if debug==True
    output = output.strip()
    if p.stderr and (stderr := p.stderr.read().strip()):
        error(stderr, end="")
    err = p.poll()
    if err and not (err == 1 and output.endswith("set --after option to 'no_reset'.")):
        # Ignore the "set --after" warning message and ercode for esp32s2.
        # If we add "--after no_reset", reconnects to the device fail repeatedly
        raise CalledProcessError(p.returncode, cmd, output, stderr)
    return output


def esptool(port: str, command: str, size: int = 0) -> str:
    """Convenience function for calling an esptool.py command."""
    global esptool_args
    try:
        cmd = f"esptool.py {esptool_args} --port {port} {command}"
        return exec_esptool(cmd, size)
    except CalledProcessError as err:
        error(f"Error: {err.cmd} returns error {err.returncode}.")
        if err.stderr:
            print(err.stderr)
        if err.stdout:
            print(err.stdout)
        raise err
    return ""


def erase_flash(filename: str, offset: int, size: int) -> None:
    """Read bytes from the device flash storage using `esptool.py`.
    Offset should be a multiple of 0x1000 (4096), the device block size"""
    esptool(filename, f"erase_region {offset:#x} {size:#x}")


def read_flash(filename: str, offset: int, size: int) -> bytes:
    """Read bytes from the device flash storage using esptool.py
    Offset should be a multiple of 0x1000 (4096), the device block size"""
    with NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
        esptool(filename, f"read_flash {offset:#x} {size:#x} {f.name}", size=size)
        return f.read()


def write_flash(filename: str, offset: int, data: bytes) -> int:
    """Write bytes to the device flash storage using `esptool.py`
    Offset should be a multiple of 0x1000 (4096), the device block size"""
    mv = memoryview(data)
    with NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
        f.write(data)
        f.flush()
        esptool(filename, f"write_flash -z {offset:#x} {f.name}", size=len(data))
    return len(mv)


class EspDeviceFileWrapper(io.RawIOBase):
    """A virtual file-like wrapper around the flash storage on an esp32 device.
    This allows the device to be used as a file-like object for reading and
    writing."""

    def __init__(self, name: str):
        self.port = name
        self.pos = 0
        self.end = 0

    def read(self, nbytes: int = 0x1000) -> bytes:
        return read_flash(self.port, self.pos, nbytes)

    def readinto(self, data: bytes) -> int:  # type: ignore
        mv = memoryview(data)
        b = read_flash(self.port, self.pos, len(mv))
        mv[: len(b)] = b
        return len(b)

    def write(self, data: bytes) -> int:  # type: ignore
        return write_flash(self.port, self.pos, data)

    def seek(self, pos: int, whence: int = 0):
        self.pos = [0, self.pos, self.end][whence] + pos
        return self.pos

    def tell(self) -> int:
        return self.pos

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def erase(self, offset: int, size: int) -> None:
        erase_flash(self.port, offset, size)


def esp32_device_detect(device: str) -> tuple[str, int]:
    """Auto detect and return (as a tuple) the `chip_name` and `flash_size`
    attached to `device`."""
    if not os.path.exists(device):
        raise FileNotFoundError(f"No such device: '{device}'")
    output = esptool(device, "flash_id")
    match = re.search(r"^Detecting chip type[. ]*(ESP.*)$", output, re.MULTILINE)
    chip_name: str = match.group(1).lower().replace("-", "") if match else ""
    match = re.search(r"^Detected flash size: *([0-9]*)MB$", output, re.MULTILINE)
    flash_size = int(match.group(1)) * MB if match else 0
    if chip_name:
        global esptool_args
        esptool_args = " ".join((esptool_args, "--chip", chip_name))
    return chip_name, flash_size
