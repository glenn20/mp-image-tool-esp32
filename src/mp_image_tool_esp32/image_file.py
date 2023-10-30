# MIT License: Copyright (c) 2023 @glenn20
"""A collection of functions to read/write and manipulate esp32 firmware on
local disk files or flash storage of serial-attached devices, including:
- Read/write partition tables
- Read/write and erase partitions
- Read/write bootloader headers (including the flash_size field)

`open_esp32_image(filename)` returns an `Esp32Image` object, which holds
information about an esp32 firmware, including a File object to read/write from
the firmware (on local file or serial-attached esp32 device).

Uses the `image_device.Esp32FileWrapper` class to provide uniform methods to
read/write flash storage on serial-attached esp32 devices as well as esp32
firmware files.
"""

import io
import math
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import IO

from .common import MB, B, action, info, warning
from .image_device import EspDeviceFileWrapper, esp32_device_detect
from .partition_table import BOOTLOADER_SIZE, Part, PartitionTable

# Fields in the image bootloader header
APP_IMAGE_MAGIC = b"\xe9"  # Starting bytes for firmware files
HEADER_SIZE = 8 + 16  # Size of the image file headers
FLASH_SIZE_OFFSET = 3  # Flash size is in high 4 bits of byte 3 in file
CHIP_ID_OFFSET = 12  # Chip-type is in bytes 12 and 13 of file
CHIP_IDS = {  # Map from chip ids in the image file header to esp32 chip names.
    0: "esp32",
    2: "esp32s2",
    9: "esp32s3",
    12: "esp32c2",
    5: "esp32c3",
    13: "esp32c6",
    16: "esp32h2",
}
BOOTLOADER_OFFSET = {
    "esp32": 0x1000,  # 0x1000 bytes
    "esp32s2": 0x1000,  # 0x1000 bytes
    "esp32s3": 0,
    "esp32c2": 0,
    "esp32c3": 0,
    "esp32c6": 0,
    "esp32h2": 0,
}

ByteString = bytes | bytearray | memoryview


def is_device(filename: str) -> bool:
    """Return `True` if `filename` is a serial device, else `False`."""
    return filename.startswith("/dev/") or filename.startswith("COM")


def _chip_flash_size(data: ByteString) -> tuple[str, int]:
    """Read the `chip_name` and `flash_size` from the given image header."""
    header = bytes(data[:HEADER_SIZE])
    if not header.startswith(APP_IMAGE_MAGIC):
        # warn(f"Firmware magic byte ({APP_IMAGE_MAGIC}) not found in image header.")
        return "", 0
    chip_id = header[CHIP_ID_OFFSET] | (header[CHIP_ID_OFFSET + 1] << 8)
    chip_name = CHIP_IDS.get(chip_id, str(chip_id))
    flash_id = header[FLASH_SIZE_OFFSET] >> 4
    flash_size = (2**flash_id) * MB
    return chip_name, flash_size


def _load_bootloader_header(f: io.IOBase) -> tuple[str, int]:
    """Load the bootloader header from the firmware file or serial device  and
    return the `chip_name` and `flash_size`."""
    header: bytes = f.read(HEADER_SIZE)
    if (details := _chip_flash_size(header)) == ("", 0):
        raise ValueError("Invalid firmware header.")
    return details


def _set_header_flash_size(header: bytearray, flash_size: int = 0) -> None:
    """Set the `flash_size` field in the supplied image bootloader `header`."""
    if flash_size == 0:
        return
    size_MB = flash_size // MB
    if not (0 <= size_MB <= 128):
        raise ValueError(f"Invalid flash size: {flash_size:#x}.")
    # Flash size tag is written into top 4 bits of 4th byte of file
    header[FLASH_SIZE_OFFSET] = (round(math.log2(size_MB)) << 4) | (
        header[FLASH_SIZE_OFFSET] & 0xF
    )


@dataclass(frozen=True)
class Esp32Params:
    filename: str  # The name of the firmware file or device
    file: IO[bytes]  # The file object to read/write the firmware
    chip_name: str  # esp32, esp32s2, esp32s3, esp32c2, esp32c3 or esp32c6
    flash_size: int  # Size of flash storage in bytes (from firmware header)
    app_size: int  # Size of app partition in bytes
    bootloader: int  # Offset of bootloader (0x1000 bytes for esp32/s2 else 0)
    is_device: bool


class FirmwareFileWithOffset(io.BufferedRandom):
    """A class to wrap a file object and add an offset to the seek and tell.
    On esp32 and s2, firmware files start at the bootloader offset (0x1000
    bytes)."""

    def __init__(self, file: io.BufferedRandom, offset: int = 0):
        # Detach the raw base file from `file` and attach it to this object
        super().__init__(file.detach())
        self.offset = offset  # Offset to add to seek and tell

    def seek(self, pos: int, whence: int = 0):
        if whence == 0:  # If seek from start of file, adjust for offset
            pos -= self.offset  # Adjust pos for offset
            if pos < 0:
                raise OSError(f"Attempt to seek before offset ({self.offset:#x}).")
        return super().seek(pos, whence) + self.offset

    def tell(self) -> int:
        return super().tell() + self.offset


def open_image_file(filename: str) -> Esp32Params:
    """Open a firmware file and return an `Esp32Image` object, which includes a
    File object for reading from the firmware file."""
    f = open(filename, "r+b")
    chip_name, flash_size = _load_bootloader_header(f)
    info(f"Chip type: {chip_name}")
    info(f"Flash size: {flash_size // MB}MB")
    bootloader = BOOTLOADER_OFFSET[chip_name]
    if bootloader != 0:  # Is non-zero for esp32 and esp32s2 firmware files
        f = FirmwareFileWithOffset(f, bootloader)
    # Get app size from the size of the file. TODO: Should use app_part.offset
    app_size = f.seek(0, 2) - PartitionTable.APP_PART_OFFSET
    f.seek(bootloader)
    return Esp32Params(filename, f, chip_name, flash_size, app_size, bootloader, False)


def open_image_device(filename: str) -> Esp32Params:
    """Open a serial device and return an `Esp32Image` object, which includes a
    File object wrapper around `esptool.py` to read and write to the device."""
    f = EspDeviceFileWrapper(filename)
    detected_chip_name, detected_flash_size = esp32_device_detect(filename)
    f.seek(BOOTLOADER_OFFSET[detected_chip_name])
    chip_name, flash_size = _load_bootloader_header(f)
    info(f"Chip type: {detected_chip_name}")
    info(f"Flash size: {detected_flash_size // MB}MB")
    bootloader = BOOTLOADER_OFFSET[chip_name]  # Use the chip type in the bootloader
    f.end = flash_size
    app_size = 0  # Unknown app size

    def check_boot(det: str | int, boot: str | int, what: str):
        if det and det != boot:
            warning(f"Detected {what} ({det}) is different from bootloader ({boot}).")

    check_boot(detected_chip_name, chip_name, "chip")
    check_boot(detected_flash_size // MB, flash_size // MB, "flash size")
    return Esp32Params(filename, f, chip_name, flash_size, app_size, bootloader, True)  # type: ignore


def open_esp32_image(filename: str) -> Esp32Params:
    """Open an esp32 firmware file or serial-attached device and
    return an `Esp32Image` object, which includes a `File` object to read and
    write to the device or file. `esptool.py` is used to read and write to
    flash storage on serial-attached devices."""
    if is_device(filename):
        return open_image_device(filename)
    else:
        return open_image_file(filename)


class Esp32Image(Esp32Params):
    """A class to represent an open esp32 firmware: in an open file or
    flash storage on a serial-attached device. Includes a `File` object to read
    and write to the device or file. `esptool.py` is used to read and write to
    flash storage on serial-attached devices.

    Provides methods to read/write and manipulate esp32 firmware and partition
    tables."""

    def __init__(self, filename: str) -> None:
        super().__init__(**vars(open_esp32_image(filename)))

    @cached_property
    def size(self) -> int:
        """Return the size of the firmware file or device."""
        return self.file.seek(0, 2)

    @cached_property
    def table(self) -> PartitionTable:
        """Load, check and return a `PartitionTable` from an `ESP32Image` object."""
        fin = self.file
        fin.seek(PartitionTable.PART_TABLE_OFFSET)
        data = fin.read(PartitionTable.PART_TABLE_SIZE)
        table = PartitionTable(self.flash_size, self.chip_name)
        table.from_bytes(data)
        table.app_size = self.app_size
        return table

    def _get_part(self, part: Part | str) -> Part:
        if part == "bootloader":
            return Part(b"", 0, -1, self.bootloader, BOOTLOADER_SIZE, b"bootloader", 0)
        return part if isinstance(part, Part) else self.table.by_name(part)

    def _check_app_image(self, data: ByteString, name: str) -> bool:
        """Check that the `data` is a valid app image for this device/firmware."""
        chip_name, flash_size = _chip_flash_size(data)
        if not chip_name:  # `data` is not an app image
            return False
        if chip_name != (y := self.chip_name):
            raise ValueError(
                f"'{name}': App image chip type ({chip_name}) "
                f"does not match firmware ({y})."
            )
        if name == "bootloader" and flash_size != (y := self.flash_size):
            warning(f"'{name}': App {flash_size=} does not match bootloader ({y}).")
        return True

    def save_app_image(self, output: str) -> int:
        """Read the app image from the device and write it to a file."""
        with open(output, "wb") as fout:
            fin = self.file
            fin.seek(self.table.app_part.offset)
            fout.write(fin.read())
            return fout.tell()

    def erase_part(self, part: Part | str, size: int = 0) -> None:
        """Erase blocks on partition `part`. Erase whole partition if
        `size` == 0."""
        part = self._get_part(part)
        if part.offset >= self.size:
            return
        f = self.file
        f.seek(part.offset)
        size = min(size, part.size) if size else part.size
        if isinstance(f, EspDeviceFileWrapper):
            f.erase(size)  # Bypass write() to erase the flash
        else:
            f.write(b"\xff" * size)

    def read_part(self, part: Part | str) -> bytes:
        """Return the contents of the `part` partition from `image` as `bytes"""
        part = self._get_part(part)
        if part.offset >= self.size:
            raise ValueError(f"Partition '{part.name}' is outside image.")
        f = self.file
        f.seek(part.offset)
        return f.read(part.size)

    def read_part_to_file(self, part: Part | str, output: str) -> int:
        """Read contents of the `part` partition from `image` into a file"""
        data = self.read_part(self._get_part(part))  # Read data before creating file
        with open(output, "wb") as fout:
            return fout.write(data)

    def write_part(self, part: Part | str, data: ByteString) -> int:
        """Write contents of `data` into the `part` partition in `image`."""
        part = self._get_part(part)
        if part.type_name == "app" and not self._check_app_image(data, part.name):
            raise ValueError(f"Attempt to write invalid app image to '{part.name}'.")
        if part.offset >= self.size:
            raise ValueError(f"Partition '{part.name}' is outside image.")
        if part.size < len(data):
            raise ValueError(
                f"Partition '{part.name}' ({part.size:#x} bytes)"
                f" is too small for data ({len(data):#x} bytes)."
            )
        f = self.file
        f.seek(part.offset)
        pad = B - (((len(data) - 1) % B) + 1)  # Pad to block size
        n = f.write(bytes(data) + b"\xff" * pad)
        if n < len(data) + pad:
            raise ValueError(f"Failed to write {len(data)} bytes to '{part.name}'.")
        if n < part.size:
            action("Erasing remainder of partition...")
            if isinstance(f, EspDeviceFileWrapper):
                f.erase(part.size - n)  # Bypass write() to erase the flash
            else:
                f.write(b"\xff" * (part.size - n))
        return n - pad

    def write_part_from_file(self, part: Part | str, input: str) -> int:
        """Write contents of `input` file into the `part` partition in `image`."""
        return self.write_part(self._get_part(part), Path(input).read_bytes())

    def check_app_partitions(self, new_table: PartitionTable) -> None:
        """Check that the app partitions contain valid app image signatures."""
        f = self.file
        for part in (
            p for p in new_table if p.type_name == "app" and p.offset < self.size
        ):
            # Check there is an app at the start of the partition
            f.seek(part.offset)
            if not self._check_app_image(f.read(1 * B), part.name):
                warning(f"Partition '{part.name}': App image signature not found.")
            else:
                action(f"Partition '{part.name}' App image signature found.")

    def check_data_partitions(self, new_table: PartitionTable) -> None:
        """Erase any data partitions in `new_table` which have been moved or resized."""
        old_table = self.table
        oldparts, newparts = (p for p in old_table or (None,)), (p for p in new_table)
        oldp = next(oldparts)
        for newp in newparts:
            while oldp and oldp.offset < newp.offset:
                oldp = next(oldparts, None)
            if not oldp:
                continue
            if newp.type_name == "data" and oldp != newp and newp.offset < self.size:
                action(f"Erasing data partition: {newp.name}...")
                self.erase_part(newp, min(newp.size, 4 * B))

    def update_flash_size(self, flash_size: int) -> None:
        """Update the bootloader header with the `flash_size`, if it has changed."""
        f = self.file
        f.seek(self.bootloader)  # Bootloader is offset from start
        header = bytearray(f.read(1 * B))  # Need to write whole blocks
        _set_header_flash_size(header, flash_size)
        f.seek(self.bootloader)
        f.write(header)

    def write_table(self, table: PartitionTable) -> None:
        """Write a new `PartitionTable` to the flash storage or firmware file."""
        f = self.file
        f.seek(table.PART_TABLE_OFFSET)
        f.write(table.to_bytes())

    def update_table(self, table: PartitionTable) -> None:
        """Update `image` with a new `PartitionTable` from `table`. Will:
        - write the new `table` to `image`
        - update the `flash_size` in the bootloader header (if it has changed) and
        - erase any data partitions which have changed from `initial_table`."""
        action("Writing partition table...")
        self.write_table(table)
        if table.flash_size != self.flash_size:
            action(f"Setting flash_size in bootloader to {table.flash_size//MB}MB...")
            self.update_flash_size(table.flash_size)
        self.check_app_partitions(table)  # Check app parts for valid app signatures
        self.check_data_partitions(table)  # Erase data partitions which have changed
        self.table = table
