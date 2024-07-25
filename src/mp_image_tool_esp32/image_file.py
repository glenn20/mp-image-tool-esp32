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

from __future__ import annotations

import hashlib
import io
import math
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import BinaryIO

from . import logger as log
from .argtypes import MB
from .image_device import BLOCKSIZE, Esp32DeviceFileWrapper
from .partition_table import BOOTLOADER_SIZE, Part, PartitionTable

# Fields in the image bootloader header
BOOTLOADER_OFFSET = {
    "esp32": 0x1000,  # 0x1000 bytes
    "esp32s2": 0x1000,  # 0x1000 bytes
    "esp32s3": 0,
    "esp32c2": 0,
    "esp32c3": 0,
    "esp32c6": 0,
    "esp32h2": 0,
}


def is_device(filename: str) -> bool:
    """Return `True` if `filename` is a serial device, else `False`."""
    return filename.startswith("/dev/") or filename.startswith("COM")


class ImageFormat:
    """A class to represent the esp32 firmware image format. Provides methods to
    read and write the image header."""

    # See https://docs.espressif.com/projects/esptool/en/latest/esp32
    # /advanced-topics/firmware-image-format.html

    HEADER_SIZE = 8 + 16  # Size of the image file headers
    APP_IMAGE_MAGIC = b"\xe9"  # Starting bytes for firmware files
    MAGIC_OFFSET = 0  # Offset of the magic byte in the image file
    NUM_SEGMENTS_OFFSET = 1  # Number of segments in the image file
    FLASH_SIZE_OFFSET = 3  # Flash size is in high 4 bits of byte 3 in file
    CHIP_ID_OFFSET = 12  # Chip-type is in bytes 12 and 13 of file
    HASH_APPENDED_OFFSET = 23  # Offset of flag that hash is appended to end of image
    CHIP_IDS = {  # Map from chip ids in the image file header to esp32 chip names.
        0: "esp32",
        2: "esp32s2",
        9: "esp32s3",
        12: "esp32c2",
        5: "esp32c3",
        13: "esp32c6",
        16: "esp32h2",
    }

    def __init__(self, data: bytes) -> None:
        self.data = data
        if not self.data[self.MAGIC_OFFSET] == self.APP_IMAGE_MAGIC[0]:
            raise ValueError("Invalid image file: magic bytes not found.")

    @cached_property
    def chip_name(self) -> str:
        """Return the chip name from the bootloader header."""
        chip_id = self.data[self.CHIP_ID_OFFSET] | (
            self.data[self.CHIP_ID_OFFSET + 1] << 8
        )
        return self.CHIP_IDS.get(chip_id, str(chip_id))

    @cached_property
    def flash_size(self) -> int:
        """Return the flash size from the bootloader header."""
        flash_id = self.data[self.FLASH_SIZE_OFFSET] >> 4
        return (2**flash_id) * MB

    @cached_property
    def hash_appended(self) -> bool:
        """Return True if the image has a SHA256 hash appended."""
        return self.data[self.HASH_APPENDED_OFFSET] == 1

    @cached_property
    def num_segments(self) -> int:
        """Return the number of segments in this image."""
        return self.data[self.NUM_SEGMENTS_OFFSET]

    def copy(self, flash_size: int = 0) -> ImageFormat:
        """Return a new bootloader header with the `flash_size` updated."""
        if flash_size == 0:
            return ImageFormat(self.data)
        size_MB = flash_size // MB
        if not (0 <= size_MB <= 128):
            raise ValueError(f"Invalid flash size: {flash_size:#x}.")
        # Flash size tag is written into top 4 bits of 4th byte of file
        new_header = bytearray(self.data)
        new_header[self.FLASH_SIZE_OFFSET] = (round(math.log2(size_MB)) << 4) | (
            self.data[self.FLASH_SIZE_OFFSET] & 0xF
        )
        return ImageFormat(bytes(new_header))

    @classmethod
    def from_file(cls, f: BinaryIO) -> ImageFormat:
        """Read the bootloader header from the firmware file or serial device."""
        return cls(f.read(cls.HEADER_SIZE))


@dataclass
class Esp32Params:
    filename: str  # The name of the firmware file or device
    file: BinaryIO  # The file object to read/write the firmware
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
    header = ImageFormat.from_file(f)
    bootloader = BOOTLOADER_OFFSET[header.chip_name]
    if bootloader != 0:  # Is non-zero for esp32 and esp32s2 firmware files
        f = FirmwareFileWithOffset(f, bootloader)
    # Get app size from the size of the file. TODO: Should use app_part.offset
    app_size = f.seek(0, 2) - PartitionTable.APP_PART_OFFSET
    f.seek(bootloader)
    return Esp32Params(
        filename, f, header.chip_name, header.flash_size, app_size, bootloader, False
    )


def open_image_device(filename: str) -> Esp32Params:
    """Open a serial device and return an `Esp32Image` object, which includes a
    File object wrapper around `esptool.py` to read and write to the device."""
    f = Esp32DeviceFileWrapper(filename)
    detected_chip_name, detected_flash_size = f.autodetect()
    f.seek(BOOTLOADER_OFFSET[detected_chip_name])
    header = ImageFormat.from_file(f)
    bootloader = BOOTLOADER_OFFSET[header.chip_name]
    f.end = header.flash_size  # Use the flash size in the bootloader
    app_size = 0  # Unknown app size

    if detected_chip_name and detected_chip_name != header.chip_name:
        log.warning(
            f"Detected device chip type ({detected_chip_name}) is different "
            f"from firmware bootloader ({header.chip_name})."
        )
    if detected_flash_size and detected_flash_size != header.flash_size:
        log.warning(
            f"Detected flash size ({detected_flash_size}) is different "
            f"from firmware bootloader ({header.flash_size})."
        )
    return Esp32Params(
        filename, f, header.chip_name, header.flash_size, app_size, bootloader, True
    )


class Esp32Image(Esp32Params):
    """A class to represent an open esp32 firmware: in an open file or
    flash storage on a serial-attached device. Includes a `File` object to read
    and write to the device or file. `esptool.py` is used to read and write to
    flash storage on serial-attached devices.

    Provides methods to read/write and manipulate esp32 firmware and partition
    tables."""

    def __init__(self, filename: str) -> None:
        params = (
            open_image_device(filename)
            if is_device(filename)
            else open_image_file(filename)
        )
        super().__init__(**vars(params))

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
        table = PartitionTable.from_bytes(data, self.flash_size, self.chip_name)
        table.app_size = self.app_size
        return table

    def _get_part(self, part: Part | str) -> Part:
        if part == "bootloader":
            return Part(b"", 0, -1, self.bootloader, BOOTLOADER_SIZE, b"bootloader", 0)
        return part if isinstance(part, Part) else self.table.by_name(part)

    def _check_app_image(self, data: bytes, name: str) -> bool:
        """Check that `data` is a valid app image for this device/firmware."""
        header = ImageFormat(data)
        if not header.chip_name:  # `data` is not an app image
            return False
        if header.chip_name != self.chip_name:
            raise ValueError(
                f"'{name}': App image chip type ({header.chip_name}) "
                f"does not match bootloader ({self.chip_name})."
            )
        if name == "bootloader" and header.flash_size != self.flash_size:
            log.warning(
                f"'{name}': App {header.flash_size=} "
                f"does not match bootloader ({self.flash_size})."
            )
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
        if isinstance(f, Esp32DeviceFileWrapper):
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

    def write_part(self, part: Part | str, data: bytes) -> int:
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
        pad = BLOCKSIZE - (((len(data) - 1) % BLOCKSIZE) + 1)  # Pad to block size
        n = f.write(bytes(data) + b"\xff" * pad)
        if n < len(data) + pad:
            raise ValueError(f"Failed to write {len(data)} bytes to '{part.name}'.")
        if n < part.size:
            log.action("Erasing remainder of partition...")
            if isinstance(f, Esp32DeviceFileWrapper):
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
            if not self._check_app_image(f.read(BLOCKSIZE), part.name):
                log.warning(f"Partition '{part.name}': App image signature not found.")
            else:
                log.action(f"Partition '{part.name}' App image signature found.")

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
                log.action(f"Erasing data partition: {newp.name}...")
                self.erase_part(newp, min(newp.size, 4 * BLOCKSIZE))

    def check_image_hash(self, image: ImageFormat) -> tuple[int, bytes]:
        """Check the sha256 hash at the end of the bootloader image data."""
        n = image.HEADER_SIZE
        for i in range(image.num_segments):  # Skip over each segment in the image
            segment_size = int.from_bytes(image.data[n + 4 : n + 8], "little")
            log.debug(f"Bootloader Segment {i} size: {segment_size:#x}")
            n += segment_size + 8
        n += 1  # Allow for the checksum byte
        n = (n + 0xF) & ~0xF  # Round up to a multiple of 16 bytes
        return n, hashlib.sha256(image.data[:n]).digest()

    def update_image_hash(self, image: ImageFormat) -> ImageFormat:
        """Update the sha256 hash at the end of the bootloader image data."""
        size, sha = self.check_image_hash(image)
        log.action(f"Updating bootloader sha256 hash: {sha.hex()}")
        return ImageFormat(image.data[:size] + sha + image.data[size + len(sha) :])

    def update_bootloader(self, flash_size: int) -> None:
        """Update the bootloader header with the `flash_size`, if it has changed."""
        f = self.file
        f.seek(self.bootloader)
        # Read the whole bootloader image
        image = ImageFormat(f.read(BOOTLOADER_SIZE))
        new_image = image.copy(flash_size=flash_size)
        # Update the header with the new flash size
        if new_image.hash_appended:
            new_image = self.update_image_hash(new_image)
        f.seek(self.bootloader)
        f.write(new_image.data)
        self.flash_size = flash_size

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
        log.action("Writing partition table...")
        if table.flash_size != self.flash_size:
            log.action(
                f"Setting flash_size in bootloader to {table.flash_size//MB}MB..."
            )
            self.update_bootloader(flash_size=table.flash_size)
        self.write_table(table)
        self.check_app_partitions(table)  # Check app parts for valid app signatures
        self.check_data_partitions(table)  # Erase data partitions which have changed
        self.table = table
