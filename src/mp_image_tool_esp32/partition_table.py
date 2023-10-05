# MIT License: Copyright (c) 2023 @glenn20

from __future__ import annotations

import csv
import hashlib
import struct
from functools import cached_property
from typing import NamedTuple, SupportsIndex

MB = 0x100_000  # 1 megabyte
KB = 0x400  # 1 kilobyte

# The default layout in flash storage on device
FLASH_SIZE = 0x400_000  # Defaults size of flash storage (4 Megabytes)
BOOTLOADER_OFFSET = 0x1_000  # Offset of Bootloader in flash storage (bytes)
BOOTLOADER_SIZE = 0x7_000  # Size allowed for Bootloader in flash
PART_TABLE_OFFSET = 0x8_000  # Offset of the partition table in flash
PART_TABLE_SIZE = 0x1_000  # Size of the partition table
FIRST_PART_OFFSET = 0x9_000  # Offset of the first partition in flash
APP_PART_OFFSET = 0x10_000  # Expected offset of application in flash
OTADATA_SIZE = 0x2_000  # Required size of the otadata partition for OTA images

# Map from partition subtype names to (type, subtype)
# Partition subtype names are unique across app and data types
SUBTYPES: dict[str, tuple[int, int]] = {
    "factory": (0, 0),
    "ota": (1, 0),
    "phy": (1, 1),
    "nvs": (1, 2),
    "fat": (1, 129),
} | {f"ota_{i}": (0, i + 16) for i in range(16)}
TYPE_TO_NAME = {0: "app", 1: "data"}
NAME_TO_TYPE = {type: name for name, type in TYPE_TO_NAME.items()}
SUBTYPE_TO_NAME = {types: name for name, types in SUBTYPES.items()}

# Partition table offsets and sizes
PART_FMT = b"<2sBBLL16sL"  # Struct format to read a partition from partition table
PART_LEN = 32  # Size of one entry in partition table (32 bytes)
PART_MAGIC = b"\xaa\x50"  # Magic bytes present at start of each partition
PART_CHKSUM_MAGIC = b"\xeb\xeb"  # If these bytes at end of table, a checksum is present


class PartError(Exception):
    "Raised if an error occurs while reading or building a PartitionTable."

    def __init__(self, msg: str = "Error in partition table."):
        super().__init__(f"Partition Error: {msg}")


class PartTuple(NamedTuple):
    magic: bytes
    type: int
    subtype: int
    offset: int
    size: int
    label: bytes
    flags: int


# My convenient form of itertools.takewhile()
def while_true(iterable):
    for x in iterable:
        if not x:
            break
        yield x


class Part(PartTuple):
    @staticmethod
    def from_bytes(data: bytes) -> Part | None:
        tuple = list(struct.unpack(PART_FMT, data))
        return Part(*tuple) if tuple[0] == PART_MAGIC else None

    def to_bytes(self) -> bytes:
        return struct.pack(PART_FMT, *self)

    # Return the partition type name
    @cached_property
    def name(self) -> str:
        return self.label.rstrip(b"\x00").decode()

    # Return the partition type name
    @cached_property
    def type_name(self) -> str:
        return TYPE_TO_NAME.get(self.type, str(self.type))

    # Return the partition subtype name (or the subtype number as a str)
    @cached_property
    def subtype_name(self) -> str:
        return SUBTYPE_TO_NAME.get((self.type, self.subtype), str(self.subtype))


class PartitionTable(list[Part]):
    # Copy the default flash layout values (may be overridden by instances if
    # required)
    BOOTLOADER_OFFSET = BOOTLOADER_OFFSET
    BOOTLOADER_SIZE = BOOTLOADER_SIZE
    PART_TABLE_OFFSET = PART_TABLE_OFFSET
    PART_TABLE_SIZE = PART_TABLE_SIZE
    FIRST_PART_OFFSET = FIRST_PART_OFFSET
    APP_PART_OFFSET = APP_PART_OFFSET  # type: ignore
    OTADATA_SIZE = OTADATA_SIZE

    def __init__(self, flash_size: int = 0, chip_name: str = ""):
        self.flash_size = flash_size
        self.chip_name = chip_name
        self.app_size = 0
        self.offset = 0

    # Can index by name (str) as well as by position in list (int)
    def __getitem__(self, key: int | str) -> Part:
        if not isinstance(key, str):
            return super().__getitem__(key)  # Delegate to list method
        if (p := next(p for p in self if p.name == key)) is None:
            raise PartError(f"Partition {key} not found.", self)
        return p

    def __setitem__(self, key: SupportsIndex | str, part: Part):
        index = (
            next((i for i, p in enumerate(self) if p.name == key), None)
            if isinstance(key, str)
            else key
        )
        if index is None:
            raise PartError(f"Partition {key} not found.", self)
        super().__setitem__(index, part)

    def print(self) -> None:
        print(
            "# Name             Type     SubType      Offset"
            "       Size      (End)  Flags"
        )
        for p in self:
            total = p.offset + p.size
            size_str = (
                f"({p.size / KB:0.1f} kB)"
                if p.size < 0.5 * MB
                else f"({p.size / MB:0.1f} MB)"
            )
            print(
                f"  {p.name:16s} {p.type_name:8s} {p.subtype_name:8}"
                f" {p.offset:#10x} {p.size:#10x} {total:>#10x} {p.flags:#4x}"
                f" {size_str:>10s}"
            )

    def from_bytes(self, data: bytes) -> PartitionTable:
        # Build the partition table from the records in "data"
        size = min(len(data), PART_TABLE_SIZE) - PART_LEN
        self.extend(
            while_true(
                Part.from_bytes(data[i : i + PART_LEN])
                for i in range(0, size, PART_LEN)
            )
        )
        if len(self) == 0:
            raise PartError("No partition table found.")
        n = len(self) * PART_LEN
        # Check if there is a checksum record at the end of the partition table
        if data[n : n + 2] == PART_CHKSUM_MAGIC:
            chksum = data[n + 16 : n + PART_LEN]
            md5 = hashlib.md5(data[:n]).digest()
            if md5 != chksum:  # Verify the checksum
                raise PartError(f"Checksum: expected {chksum.hex()}, got {md5.hex()}.")
            n += PART_LEN
        # Check that there is at least one empty row next in partition table
        if data[n : n + PART_LEN] != b"\xff" * PART_LEN:
            raise PartError("Partition table does not end with an empty row.")
        self.sort(key=lambda p: p.offset)
        if not self.flash_size:  # Infer flash size from partition table
            self.flash_size = self[-1].offset + self[-1].size
            self.offset = self.flash_size
        if self.app_part:
            self.APP_PART_OFFSET = self.app_part.offset
        self.check()
        return self

    def to_bytes(self) -> bytes:
        data = b"".join((p.to_bytes() for p in self))
        md5 = hashlib.md5(data).digest()
        data = b"".join(
            (
                data,
                PART_CHKSUM_MAGIC.ljust(16, b"\xff"),
                md5,
                (b"\xff" * (self.PART_TABLE_SIZE - len(data) - PART_LEN)),
            )
        )
        assert len(data) == self.PART_TABLE_SIZE
        return data

    def from_csv(self, filename: str) -> PartitionTable:
        self.clear()
        with open(filename, newline="") as f:
            reader = csv.reader((s for s in f if s[0] != "#"), skipinitialspace=True)
            for name, type, subtype, offset, size, flags in reader:
                self.add_part(name, subtype, int(size, 0), int(offset, 0))
        self.check()
        return self

    # Find the first app partition offset.
    @property
    def app_part(self) -> Part:
        part = next(
            filter(lambda p: p.subtype_name in ("factory", "ota_0"), self),
            None,
        )
        if not part:
            self.print()
            raise PartError('No "factory" or "ota_" partition found in table.')
        return part

    # Add a partition to the table
    def add_part(
        self,
        name: str,
        subtype_name: str,
        size: int,  # If size==0, use all space left in the flash
        offset: int = 0,
        flags: int = 0,
    ) -> None:
        if not self.offset:
            self.offset = self.FIRST_PART_OFFSET
        offset = offset or self.offset
        if offset + size > self.flash_size:
            self.print()
            raise PartError(f"No room on flash for partition {name} ({size:#x} bytes).")
        size = size or (self.flash_size - offset)
        type, subtype = SUBTYPES[subtype_name]
        self.append(
            Part(PART_MAGIC, type, subtype, self.offset, size, name.encode(), flags)
        )
        self.offset += size
        self.sort(key=lambda p: p.offset)
        self.check()

    # Change size of partition (and adjusting offsets of following parts if necessary)
    def resize_part(self, name: str, new_size: int) -> None:
        i = self.index(self[name])
        if new_size == 0:  # Exapnd to fill available space
            upper_limit = self[i + 1].offset if i + 1 < len(self) else self.flash_size
            new_size = upper_limit - self[i].offset
        self[i] = self[i]._replace(size=new_size)
        print(f"Resizing {name} partition to {new_size:#x} bytes.")
        for j in range(i + 1, len(self)):
            offset = self[j - 1].offset + self[j - 1].size
            if offset > self[j].offset:  # Shift other partitions to make room
                self[j] = self[j]._replace(offset=offset)
            if self.flash_size < self[j].offset + self[j].size:
                # Shrink other partitions if they overflow the flash storage
                self[j] = self[j]._replace(size=self.flash_size - self[j].offset)

    # Check the partition table for consistency
    # Raises PartError if any inconsistencies found.
    def check(self) -> None:
        offset = self.FIRST_PART_OFFSET
        names: set[str] = set()
        for p in self:
            if p.name in names:
                raise PartError(f'Partition name, "{p.name}" is repeated.')
            names.add(p.name)
            if p.offset < offset:
                raise PartError(
                    f'Partition "{p.name}" overlaps with previous partition.'
                )
            if p.offset > offset:
                print(f'Warning: Gap before partition "{p.name}".')
            if p.offset % 0x1_000:
                raise PartError(
                    f"Partition offset {p.offset:#x} is not multiple of 0x1000."
                )
            if p.size % 0x1_000:
                raise PartError(
                    f"Partition size {p.size:#x} is not multiple of 0x1000."
                )
            if p.type_name == "app" and p.offset % 0x10_000:
                raise PartError(
                    f"App partition offset {p.offset:#x} is not multiple of 0x10000."
                )
            offset += p.size
        if offset > self.flash_size:
            raise PartError(
                f"End of last partition ({offset:#x})"
                f" is greater than flash size ({self.flash_size:#x})."
            )
        if offset != self.flash_size:
            print(
                f"Warning: End of last partition ({offset:#x})"
                f" < flash size ({self.flash_size:#x})."
            )
        if self.app_part.offset != self.APP_PART_OFFSET:
            raise PartError(
                f"Micropython app at offset={self.app_part.offset}"
                f" (expected {self.APP_PART_OFFSET})."
            )
        if self.app_size and self.app_part.size < self.app_size:
            raise PartError(
                f'App partition "{self.app_part.name}"'
                f" is too small for micropython app ({self.app_size:#x} bytes)."
            )

    def clear(self) -> None:
        super().clear()
        self.offset = 0
