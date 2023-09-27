# MIT License: Copyright (c) 2023 @glenn20

import io
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from colorama import Fore

from .partition_table import Part, PartitionTable

MB = 0x100_000  # 1 megabyte
KB = 0x400  # 1 kilobyte

debug = False  # If True, print the esptool.py commands and output
esptool_args = "--baud 460800"  # Default arguments for the esptool.py commands


# A class to hold information about an esp32 firmware file or device
@dataclass
class Esp32Image:
    file: io.IOBase
    chip_name: str
    flash_size: int
    offset: int
    app_size: int


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
        print(f"{Fore.RED}Error: {e.cmd} returns error {e.returncode}.{Fore.RESET}")
        if e.stderr:
            print(e.stderr.decode())
        if e.stdout:
            print(e.stdout.decode())
        sys.exit(e.returncode)
    return result.stdout


# Convenience function for calling an esptool.py command.
def esptool(port: str, command: str) -> bytes:
    return shell(f"esptool.py {esptool_args} --port {port} {command}")


# Read bytes from the device flash storage using esptool.py
# Offset should be a multiple of 0x1000 (4096), the device block size
def read_flash(filename: str, offset: int, size: int) -> bytes:
    with NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
        esptool(filename, f"read_flash {offset:#x} {size:#x} {f.name}")
        return Path(f.name).read_bytes()


# Write bytes to the device flash storage using esptool.py
# Offset should be a multiple of 0x1000 (4096), the device block size
def write_flash(filename: str, offset: int, data: bytes) -> int:
    with NamedTemporaryFile("w+b", prefix="mp-image-tool-esp32-") as f:
        Path(f.name).write_bytes(data)
        esptool(filename, f"write_flash {offset:#x} {f.name}")
    return len(data)


# A virtual file-like wrapper around the flash storage on an esp32 device
class EspDeviceFileWrapper(io.RawIOBase):
    def __init__(self, name: str):
        self.port = name
        self.pos = 0

    def read(self, nbytes: int = 0x1000) -> bytes:
        return read_flash(self.port, self.pos, nbytes)

    def readinto(self, data: bytearray | memoryview) -> int:
        mv = memoryview(data)
        b = read_flash(self.port, self.pos, len(data))
        mv[: len(b)] = b
        return len(b)

    def write(self, data: bytes) -> int:
        return write_flash(self.port, self.pos, data)

    def seek(self, pos: int, whence: int = 0):
        self.pos = [0, self.pos, 0][whence] + pos
        return self.pos

    def tell(self) -> int:
        return self.pos

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True


# Open a wrapper around the serial port for an esp32 device and return
def open_image_device(filename: str) -> Esp32Image:
    output = esptool(filename, "flash_id").decode()
    match = re.search(r"^Detecting chip type[. ]*(ESP.*)$", output, re.MULTILINE)
    chip_name: str = match.group(1).lower().replace("_", "") if match else ""
    match = re.search(r"^Detected flash size: *([0-9]*)MB$", output, re.MULTILINE)
    flash_size = int(match.group(1)) * MB if match else 0
    app_size = 0  # Unknown app size
    offset = 0  # No offset required for dev files
    f = EspDeviceFileWrapper(filename)
    if chip_name:
        global esptool_args
        esptool_args = " ".join((esptool_args, "--chip", chip_name))
    return Esp32Image(f, chip_name, flash_size, offset, app_size)


# Write changes to the flash storage on the device
def write_table(device: str, table: PartitionTable) -> None:
    with open_image_device(device).file as f:
        f.seek(table.PART_TABLE_OFFSET)
        f.write(table.to_bytes())


# Erase blocks on a partition. Erase whole partition if size == 0
def erase_part(device: str, part: Part, size: int = 0) -> None:
    esptool(device, f"erase_region {part.offset:#x} {size or part.size:#x}")


# Read a partition from device into a file
def read_part(device: str, part: Part, output: str) -> int:
    esptool(device, f"read_flash {part.offset:#x} {part.size:#x} {output}")
    return os.path.getsize(output)


# Write data from a file to a partition on device
def write_part(device: str, part: Part, input: str) -> int:
    if part.size < os.path.getsize(input):
        raise ValueError(
            f"Partition {part.name} ({part.size} bytes)"
            f" is too small for data ({os.path.getsize(input)} bytes)."
        )
    esptool(device, f"write_flash {part.offset:#x} {input}")
    return os.path.getsize(input)
