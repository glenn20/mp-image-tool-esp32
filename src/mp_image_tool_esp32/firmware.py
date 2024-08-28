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

from . import logger as log
from .argtypes import MB, B
from .firmware_fileio import FirmwareDeviceIO, FirmwareFileIO, Partition
from .image_header import ImageHeader
from .partition_table import PartitionEntry, PartitionTable

BLOCKSIZE = B  # Block size for erasing/writing regions of the flash storage


def is_device(filename: str) -> bool:
    """Return `True` if `filename` is a serial device, else `False`."""
    return filename.startswith("/dev/") or filename.startswith("COM")


class Firmware:
    """A class to represent an open esp32 firmware: in an open file or
    flash storage on a serial-attached device. Includes a `File` object to read
    and write to the device or file. `esptool.py` is used to read and write to
    flash storage on serial-attached devices.

    Provides methods to read/write and manipulate esp32 firmware and partition
    tables."""

    filename: str
    file: FirmwareFileIO | FirmwareDeviceIO
    header: ImageHeader
    bootloader: int
    is_device: bool
    BLOCKSIZE: int = BLOCKSIZE

    def __init__(
        self,
        filename: str,
        baud: int = 0,
        /,
        esptool_method: str = "",
        reset_on_close: bool = True,
        check: bool = True,
    ) -> None:
        self.filename = filename
        self.file = (
            FirmwareDeviceIO(
                filename,
                baud,
                esptool_method=esptool_method,
                reset_on_close=reset_on_close,
                check=check,
            )
            if is_device(filename)
            else FirmwareFileIO(filename)
        )
        self.is_device = isinstance(self.file, FirmwareDeviceIO)
        self.header = self.file.header
        self.bootloader = self.file.bootloader

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
        table = PartitionTable.from_bytes(data, self.header.flash_size)
        return table

    def _get_part(self, part: PartitionEntry | str) -> PartitionEntry:
        if part == "bootloader":
            return PartitionEntry(
                b"",
                0,
                -1,
                self.bootloader,
                PartitionTable.BOOTLOADER_SIZE,
                b"bootloader",
                0,
            )
        return part if isinstance(part, PartitionEntry) else self.table.by_name(part)

    def partition(self, part: PartitionEntry | str) -> Partition:
        """Return a `Partition` object for the partition `part`."""
        return Partition(self._get_part(part), self.file)

    def check_app_image_header(self, data: bytes, name: str) -> bool:
        """Check that `data` is a valid app image for this device/firmware."""
        try:
            header = ImageHeader.from_bytes(data)
            header.check()
        except ValueError:
            return False
        if not header.chip_name:  # `data` is not an app image
            return False
        if header.chip_name != self.header.chip_name:
            log.warning(
                f"'{name}': App image chip type ({header.chip_name}) "
                f"does not match bootloader ({self.header.chip_name})."
            )
            return False
        if name == "bootloader" and header.flash_size != self.header.flash_size:
            log.warning(
                f"'{name}': image flash size ({header.flash_size}) "
                f"does not match bootloader ({self.header.flash_size})."
            )
        return True

    def save_app_image(self, output: str) -> int:
        """Read the first app image from the device and write it to a file."""
        with self.partition(self.table.app_part) as p:
            with open(output, "wb") as fout:
                return fout.write(p.read().rstrip(b"\xff"))  # Remove trailing padding

    def read_firmware(self) -> bytes:
        """Return the entire firmware from this image as `bytes"""
        f = self.file
        f.seek(self.bootloader)
        return f.read()

    def write_firmware(self, image: Firmware) -> int:
        """Write firmware from `image` into this image."""
        if not isinstance(self.file, FirmwareDeviceIO):
            raise ValueError("Must flash firmware to a device.")
        src, dst = image.header, self.header
        if src.flash_size != dst.flash_size:
            log.warning(
                f"Destination flash size ({dst.flash_size // MB}MB) is "
                f"different from source flash_size ({src.flash_size // MB}MB)."
            )
        f = self.file
        f.seek(self.bootloader)
        data = image.read_firmware()
        pad = self.BLOCKSIZE - (((len(data) - 1) % self.BLOCKSIZE) + 1)
        size = f.write(data + b"\xff" * pad)
        if size < len(data) + pad:
            raise ValueError(f"Failed to write {len(data)} bytes to '{self.filename}'.")
        if p := next((p for p in image.table if p.offset + p.size >= size), None):
            log.action(f"Erasing remainder of partition '{p.name}'...")
            f.erase(p.offset + p.size - size)
        return size

    def check_app_partitions(
        self, new_table: PartitionTable, check_hash: bool = False
    ) -> None:
        """Check that the app partitions contain valid app image signatures."""
        app_parts = [
            p for p in new_table if p.type_name == "app" and p.offset < self.size
        ]
        app_parts = [self._get_part("bootloader")] + app_parts
        for part in app_parts:
            # Check there is an app at the start of the partition
            with self.partition(part) as p:
                data = p.read(self.BLOCKSIZE)
                if not self.check_app_image_header(data, part.name):
                    log.warning(
                        f"Partition '{part.name}': App image signature not found."
                    )
                    continue
                log.info(f"Partition '{part.name}': App image signature found.")
                if not check_hash:
                    continue
                data += p.read()  # Read the rest of the partition
            header = ImageHeader.from_bytes(data)
            size, calc_sha, stored_sha = header.check_image_hash(data)
            size += len(stored_sha)  # Include the stored hash in the size
            sha, stored = calc_sha.hex(), stored_sha.hex()
            log.debug(f"{part.name}: {size=}\n       {sha=}\n    {stored=})")
            if sha != stored:
                log.warning(
                    f"Partition '{part.name}': Hash mismatch ({size=} {sha=} {stored=})"
                )
            else:
                log.info(f"Partition '{part.name}': Hash confirmed ({size=}).")

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
                with self.partition(newp) as p:
                    p.erase(min(newp.size, 4 * self.BLOCKSIZE))

    def _get_block(
        self,
        offset: int,
        data: bytes | bytearray,
        blocksize: int,
        pad_byte: bytes = b"\xff",
    ) -> tuple[bytes, int]:
        """Return the block of data containing `offset`."""
        start = (offset // blocksize) * blocksize
        end = min(start + blocksize, len(data))
        data = data[start:end]
        data += pad_byte[:1] * (blocksize - len(data))
        assert len(data) == blocksize, f"Block size {len(data):#x} != {blocksize:#x}"
        return bytes(data), start

    def update_bootloader(self) -> None:
        """Update the bootloader header and hash, if it has changed."""
        with self.partition("bootloader") as p:
            data = p.read()  # Read the whole bootloader
            data, _new_hash_offset = self.header.update_image(data)
            # Instead of writing a whole new bootloader image, just update the
            # block containing the header and the block containing the hash
            p.seek(0)
            p.write(data)  # Write the block with the new header
            # p.write(data[: self.BLOCKSIZE])  # Write the block with the new header
            # if new_hash_offset:  # If a new hash was written
            #     block, start = self._get_block(new_hash_offset, data, self.BLOCKSIZE)
            #     p.seek(start)
            #     p.write(block)  # Write the block with the new hash

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
