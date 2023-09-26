# MIT License: Copyright (c) 2023 @glenn20

import io
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

MB = 0x100_000  # 1 megabyte
KB = 0x400  # 1 kilobyte


@dataclass
class Esp32Image:
    file: io.IOBase
    chip_name: str
    flash_size: int
    offset: int
    app_size: int


debug = False


# Use shell commands to run esptool.py to read and write from flash storage on
# esp32 devices.
def shell(command: str) -> bytes:
    try:
        if debug:
            print("$", command)
        result = subprocess.run(command, capture_output=True, check=True, shell=True)
        if debug:
            print(result.stdout.decode())
            print(result.stderr.decode())
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.cmd} returns error {e.returncode}.")
        if e.stderr:
            print(e.stderr.decode())
        if e.stdout:
            print(e.stdout.decode())
        sys.exit(e.returncode)
    return result.stdout


# Read bytes from the device flash storage using esptool.py
# Offset should be a multiple of 0x1000 (4096), the device block size
def read_flash(filename: str, offset: int, size: int, args="") -> bytes:
    esptool = f"esptool.py {args} --port {filename}"
    with tempfile.NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
        shell(f"{esptool} read_flash {offset:#x} {size:#x} {f.name}")
        return Path(f.name).read_bytes()


# Write bytes to the device flash storage using esptool.py
# Offset should be a multiple of 0x1000 (4096), the device block size
def write_flash(filename: str, offset: int, data: bytes, args="") -> int:
    esptool = f"esptool.py {args} --port {filename}"
    with tempfile.NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
        Path(f.name).write_bytes(data)
        shell(f"{esptool} write_flash {offset:#x} {f.name}")
    return len(data)


# Write bytes to the device flash storage using esptool.py
# Offset should be a multiple of 0x1000 (4096), the device block size
def erase_flash_region(filename: str, offset: int, size=4 * KB, args="") -> bool:
    esptool = f"esptool.py {args} --port {filename}"
    shell(f"{esptool} erase_region {offset:#x} {size:#x}")
    return True


# A virtual file-like wrapper around the flash storage on an esp32 device
class EspDeviceFileWrapper(io.RawIOBase):
    def __init__(self, name: str, args=""):
        self.port = name
        self.args = args
        self.pos = 0

    def read(self, nbytes: int = 0x1000) -> bytes:
        return read_flash(self.port, self.pos, nbytes, self.args)

    def readinto(self, data: bytearray | memoryview) -> int:
        mv = memoryview(data)
        b = read_flash(self.port, self.pos, len(data), self.args)
        mv[: len(b)] = b
        return len(b)

    def write(self, data: bytes) -> int:
        return write_flash(self.port, self.pos, data, self.args)

    def seek(self, pos: int, whence: int = 0):
        self.pos = [0, self.pos, 0][whence] + pos
        return self.pos

    def tell(self) -> int:
        return self.pos

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True


def open_image_device(filename: str) -> Esp32Image:
    output = shell(f"esptool.py --port {filename} flash_id").decode()
    match = re.search(r"^Detecting chip type[. ]*(ESP.*)$", output, re.MULTILINE)
    chip_name: str = match.group(1).lower().replace("_", "") if match else ""
    match = re.search(r"^Detected flash size: *([0-9]*)MB$", output, re.MULTILINE)
    flash_size = int(match.group(1)) * MB if match else 0
    app_size = 0  # Unknown app size
    offset = 0  # No offset required for dev files
    f = io.BufferedReader(EspDeviceFileWrapper(filename, f"--chip {chip_name}"), 0x1000)
    return Esp32Image(f, chip_name, flash_size, offset, app_size)
