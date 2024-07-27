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
from functools import cached_property

from . import logger as log
from .argtypes import MB
from .espdeviceio import ESPDeviceIO
from .image_header import BLOCKSIZE, BOOTLOADER_OFFSET, ImageFormat
from .partition_table import BOOTLOADER_SIZE, Part, PartitionTable


def is_device(filename: str) -> bool:
    """Return `True` if `filename` is a serial device, else `False`."""
    return filename.startswith("/dev/") or filename.startswith("COM")


class FirmwareFileWithOffset(io.BufferedRandom):
    """A class to wrap a file object and add an offset to the seek and tell.
    On esp32 and s2, firmware files start at the bootloader offset (0x1000
    bytes)."""

    BLOCKSIZE = BLOCKSIZE

    def __init__(self, name: str):
        # Detach the raw base file from `file` and attach it to this object
        f = open(name, "r+b")
        hdr = ImageFormat.from_file(f)
        self.chip_name = hdr.chip_name
        self.flash_size = hdr.flash_size
        self.flash_size_str = f"{hdr.flash_size//MB}MB"
        self.bootloader = BOOTLOADER_OFFSET[hdr.chip_name]
        self.offset = self.bootloader  # Offset to add to seek and tell
        self.app_size = f.seek(0, 2) - PartitionTable.APP_PART_OFFSET
        f.seek(self.bootloader)
        super().__init__(f.detach())

    def seek(self, pos: int, whence: int = 0):
        if whence == 0:  # If seek from start of file, adjust for offset
            pos -= self.offset  # Adjust pos for offset
            if pos < 0:
                raise OSError(f"Attempt to seek before offset ({self.offset:#x}).")
        return super().seek(pos, whence) + self.offset

    def tell(self) -> int:
        return super().tell() + self.offset


class Esp32Image:
    """A class to represent an open esp32 firmware: in an open file or
    flash storage on a serial-attached device. Includes a `File` object to read
    and write to the device or file. `esptool.py` is used to read and write to
    flash storage on serial-attached devices.

    Provides methods to read/write and manipulate esp32 firmware and partition
    tables."""

    def __init__(
        self,
        filename: str,
        baud: int = 0,
        /,
        esptool_method: str = "",
        reset_on_close: bool = True,
    ) -> None:
        self.file = (
            ESPDeviceIO(
                filename,
                baud,
                reset_on_close=reset_on_close,
                esptool_method=esptool_method,
            )
            if is_device(filename)
            else FirmwareFileWithOffset(filename)
        )
        self.filename = filename
        self.chip_name = self.file.chip_name
        self.flash_size = self.file.flash_size
        self.app_size = self.file.app_size
        self.bootloader = self.file.bootloader
        self.BLOCKSIZE = BLOCKSIZE
        self.is_device = is_device(filename)

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
        try:
            header = ImageFormat(data)
        except ValueError:
            return False
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
        if isinstance(f, ESPDeviceIO):
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
        pad = self.BLOCKSIZE - (((len(data) - 1) % self.BLOCKSIZE) + 1)
        n = f.write(bytes(data) + b"\xff" * pad)
        if n < len(data) + pad:
            raise ValueError(f"Failed to write {len(data)} bytes to '{part.name}'.")
        if n < part.size:
            log.action("Erasing remainder of partition...")
            if isinstance(f, ESPDeviceIO):
                f.erase(part.size - n)  # Bypass write() to erase the flash
            else:
                f.write(b"\xff" * (part.size - n))
        return n - pad

    def check_app_partitions(self, new_table: PartitionTable) -> None:
        """Check that the app partitions contain valid app image signatures."""
        f = self.file
        for part in (
            p for p in new_table if p.type_name == "app" and p.offset < self.size
        ):
            # Check there is an app at the start of the partition
            f.seek(part.offset)
            if not self._check_app_image(f.read(self.BLOCKSIZE), part.name):
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
                self.erase_part(newp, min(newp.size, 4 * self.BLOCKSIZE))

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

    def update_bootloader(self, *, flash_size: int) -> None:
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
