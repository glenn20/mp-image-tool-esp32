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

from functools import cached_property
from typing import Tuple

from . import logger as log
from .argtypes import MB
from .firmware_file import Firmware
from .image_header import ImageHeader, update_image
from .partition_table import BOOTLOADER_SIZE, Part, PartitionTable


class Esp32Image(Firmware):
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
        super().__init__(
            filename,
            baud,
            esptool_method=esptool_method,
            reset_on_close=reset_on_close,
        )
        self.app_size = 0  # TODO: Calculate this correctly
        self.app_part_size = 0  # TODO: Calculate this correctly

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
        table = PartitionTable.from_bytes(
            data, self.header.flash_size, self.header.chip_name
        )
        table.app_size = self.app_size
        return table

    def _get_part(self, part: Part | str) -> Part:
        if part == "bootloader":
            return Part(b"", 0, -1, self.bootloader, BOOTLOADER_SIZE, b"bootloader", 0)
        return part if isinstance(part, Part) else self.table.by_name(part)

    def _check_app_image(self, data: bytes, name: str) -> bool:
        """Check that `data` is a valid app image for this device/firmware."""
        try:
            header = ImageHeader.from_bytes(data)
        except ValueError:
            return False
        if not header.chip_name:  # `data` is not an app image
            return False
        if header.chip_name != self.header.chip_name:
            raise ValueError(
                f"'{name}': App image chip type ({header.chip_name}) "
                f"does not match bootloader ({self.header.chip_name})."
            )
        if name == "bootloader" and header.flash_size != self.header.flash_size:
            log.warning(
                f"'{name}': App {header.flash_size=} "
                f"does not match bootloader ({self.header.flash_size})."
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
        f.erase(size)  # Bypass write() to erase the flash

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
            f.erase(part.size - n)  # Bypass write() to erase the flash
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

    def get_block(
        self,
        offset: int,
        data: bytes | bytearray,
        blocksize: int,
        pad_byte: bytes = b"\xff",
    ) -> Tuple[bytes, int]:
        """Return the block of data containing `offset`."""
        start = (offset // blocksize) * blocksize
        end = min(start + blocksize, len(data))
        data = data[start:end]
        data += pad_byte[:1] * (blocksize - len(data))
        assert len(data) == blocksize, f"Block size {len(data):#x} != {blocksize:#x}"
        return bytes(data), start

    def update_bootloader(self) -> None:
        """Update the bootloader header and hash, if it has changed."""
        f = self.file
        f.seek(self.bootloader)
        data = f.read(BOOTLOADER_SIZE)  # Read the whole bootloader image
        data, new_hash_offset = update_image(self.header, data)
        # Instead of writing a whole new bootloader image, just update the
        # block containing the header and the block caontaining the hash
        f.seek(self.bootloader)
        f.write(data[: self.BLOCKSIZE])  # Write the block with the new header
        if new_hash_offset:  # If a new hash was written
            block, start = self.get_block(new_hash_offset, data, self.BLOCKSIZE)
            f.seek(self.bootloader + start)
            f.write(block)  # Write the block with the new hash

    def write_table(self, table: PartitionTable) -> None:
        """Write a new `PartitionTable` to the flash storage or firmware file."""
        f = self.file
        f.seek(table.PART_TABLE_OFFSET)
        f.write(table.to_bytes())

    def update_image(self, table: PartitionTable, header: ImageHeader) -> None:
        """Update `image` with a new `PartitionTable` from `table`. Will:
        - write the new `table` to `image`
        - update the `flash_size` in the bootloader header (if it has changed) and
        - erase any data partitions which have changed from `initial_table`."""
        log.action("Writing partition table...")
        if header.ismodified():
            size = header.flash_size // MB
            log.action(f"Updating flash size ({size}MB) in bootloader header...")
            self.header = header
            self.update_bootloader()
        self.write_table(table)
        self.check_app_partitions(table)  # Check app parts for valid app signatures
        self.check_data_partitions(table)  # Erase data partitions which have changed
        self.table = table
