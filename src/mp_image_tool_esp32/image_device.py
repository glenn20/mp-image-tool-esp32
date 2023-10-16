# MIT License: Copyright (c) 2023 @glenn20

import io
import os
import re
import subprocess
import time
from dataclasses import dataclass
from tempfile import NamedTemporaryFile

from .common import MB, debug, error

esptool_args = "--baud 460800"  # Default arguments for the esptool.py commands


@dataclass
class Esp32Image:
    """A class to hold information about an esp32 firmware file or device"""

    file: io.IOBase
    chip_name: str
    flash_size: int
    app_size: int
    offset: int  # Esp32 and S2 firmware files have a global offset of 0x1000
    bootloader_offset: int  # Offset of bootloader: esp32/s2=0x1000 else 0
    is_device: bool


def shell(command: str) -> bytes:
    """Use shell commands to run `esptool.py` to read and write from flash
    storage on esp32 devices."""
    if debug:
        print("$", command)
    result = subprocess.run(command, capture_output=True, check=True, shell=True)
    if debug:
        print(result.stdout.decode())
        print(result.stderr.decode())
    return result.stdout


def esptool(port: str, command: str) -> bytes:
    """Convenience function for calling an esptool.py command."""
    # Keep trying for up to 5 seconds. On some devices, we need to wait up to
    # 0.6 seconds for serial port to be ready after previous commands (eg.
    # esp32s2).
    global esptool_args
    for i in range(50, -1, -1):
        try:
            return shell(f"esptool.py {esptool_args} --port {port} {command}")
        except subprocess.CalledProcessError as err:
            if "set --after option to 'no_reset'" in err.stdout.decode():
                esptool_args += " --after no_reset"
            if i == 0:
                error(f"Error: {err.cmd} returns error {err.returncode}.")
                if err.stderr:
                    print(err.stderr.decode())
                if err.stdout:
                    print(err.stdout.decode())
                raise err
            time.sleep(0.1)
    return b""


def erase_flash(filename: str, offset: int, size: int) -> None:
    """Read bytes from the device flash storage using `esptool.py`.
    Offset should be a multiple of 0x1000 (4096), the device block size"""
    esptool(filename, f"erase_region {offset:#x} {size:#x}")


def read_flash(filename: str, offset: int, size: int) -> bytes:
    """Read bytes from the device flash storage using esptool.py
    Offset should be a multiple of 0x1000 (4096), the device block size"""
    with NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
        esptool(filename, f"read_flash {offset:#x} {size:#x} {f.name}")
        return f.read()


def write_flash(filename: str, offset: int, data: bytes) -> int:
    """Write bytes to the device flash storage using `esptool.py`
    Offset should be a multiple of 0x1000 (4096), the device block size"""
    mv = memoryview(data)
    with NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
        f.write(data)
        f.flush()
        esptool(filename, f"write_flash -z {offset:#x} {f.name}")
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
    output = esptool(device, "flash_id").decode()
    match = re.search(r"^Detecting chip type[. ]*(ESP.*)$", output, re.MULTILINE)
    chip_name: str = match.group(1).lower().replace("-", "") if match else ""
    match = re.search(r"^Detected flash size: *([0-9]*)MB$", output, re.MULTILINE)
    flash_size = int(match.group(1)) * MB if match else 0
    if chip_name:
        global esptool_args
        esptool_args = " ".join((esptool_args, "--chip", chip_name))
    return chip_name, flash_size
