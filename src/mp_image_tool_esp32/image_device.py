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
import time
from subprocess import PIPE, CalledProcessError, Popen
from tempfile import NamedTemporaryFile

import tqdm
from colorama import Fore

from .common import KB, MB, dprint, error

esptool_args: str = "--baud 460800"  # Default arguments for the esptool.py commands

tqdm_args = dict(
    ascii=" =",
    bar_format=(
        Fore.GREEN
        + "{l_bar}{bar}| "
        + Fore.CYAN
        + "{n:,}/{total:,}kB {rate_fmt}"
        + Fore.RESET
    ),
)


def esptool_progress_bar(stdout: io.TextIOWrapper, size: int) -> str:
    """Use a tqdm progress bar to show progress of esptool.py reads and writes.
    Monitors command output from `stdout` and updates the progress bar
    when progress updates are received."""
    offset, output = 0, ""
    # Matches: "Writing at 0x0002030... (2 %)\r" and "1375 (1 %)\r" at end of output
    regexp = r"(Writing at )?((0x)?[0-9a-f]+)[.]* *\([0-9]+ *%\)[\n\r\x08]$"
    with tqdm.trange(0, size // KB, unit="kB", **tqdm_args) as pbar:  # type: ignore
        while stdout and (s := stdout.read(1)):
            output += s
            if (
                s in ("\n", "\r", "\x08")  # If we have a whole new line
                and (match := re.search(regexp, output))  # and is progress update
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
    dprint("$", cmd)
    p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE, text=True, bufsize=0)
    output, stderr = "", ""
    if size > 16 * KB and p.stdout:  # Show a progress bar for large reads/writes
        output = esptool_progress_bar(p.stdout, size)  # type: ignore
        dprint(output)
    elif p.stdout:
        while s := p.stdout.readline():
            output += s
            dprint(s, end="")  # Show output as it happens if debug==True
    if p.stderr and (stderr := p.stderr.read()):
        error(stderr, end="")
    err = p.poll()
    if err and not (err == 1 and "set --after option to 'no_reset'" in output):
        raise CalledProcessError(p.returncode, cmd, output, stderr)
    return output


def esptool(port: str, command: str, size: int = 0) -> str:
    """Convenience function for calling an esptool.py command."""
    # Keep trying for up to 5 seconds. On some devices, we need to wait up to
    # 0.6 seconds for serial port to be ready after previous commands (eg.
    # esp32s2).
    global esptool_args
    for i in range(50, -1, -1):
        try:
            cmd = f"esptool.py {esptool_args} --port {port} {command}"
            return exec_esptool(cmd, size)
        except CalledProcessError as err:
            if "set --after option to 'no_reset'" in err.stdout:
                esptool_args += " --after no_reset"
            if i == 0:
                error(f"Error: {err.cmd} returns error {err.returncode}.")
                if err.stderr:
                    print(err.stderr)
                if err.stdout:
                    print(err.stdout)
                raise err
            time.sleep(0.1)
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
