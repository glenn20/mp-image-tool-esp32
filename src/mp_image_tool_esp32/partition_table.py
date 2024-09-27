# MIT License: Copyright (c) 2023 @glenn20
"""Provides classes and methods to read, write, construct and manipulate
partition tables in ESP32 firmware files and flash storage on ESP32 devices.

Provides the:
- `PartitionTable` class to represent a partition table and the
- `Part` class to represent a partition in the table.

Both classes include `from_bytes()` and `to_bytes()` methods to read and
write from binary partiton tables in firmware files and devices.
"""

from __future__ import annotations

import hashlib
import struct
from functools import cached_property
from itertools import takewhile
from typing import List, NamedTuple

from . import logger
from .argtypes import KB, MB, B
from .data_table import TableTuple, plain_table

log = logger.getLogger(__name__)

# The default layout in flash storage on device
FLASH_SIZE = 0x400_000  # Default size of flash storage (4 Megabytes)
BOOTLOADER_SIZE = 0x7_000  # Size allowed for Bootloader in flash
PART_TABLE_OFFSET = 0x8_000  # Offset of the partition table in flash
PART_TABLE_SIZE = 0x1_000  # Size of the partition table
FIRST_PART_OFFSET = 0x9_000  # Offset of the first partition in flash
APP_PART_OFFSET = 0x10_000  # Expected offset of application in flash
OTADATA_SIZE = 0x2_000  # Required size of the otadata partition for OTA images

# Map between partition types/subtypes and names
# Partition subtype names are unique across app and data types
TYPE_TO_NAME = {0: "app", 1: "data"}
NAME_TO_TYPE = {name: typ for typ, name in TYPE_TO_NAME.items()}
SUBTYPES: dict[str, tuple[int, int]] = {
    "factory": (0, 0),
    "ota": (1, 0),
    "phy": (1, 1),
    "nvs": (1, 2),
    "fat": (1, 129),
}
SUBTYPES.update({f"ota_{i}": (int(0), i + 16) for i in range(16)})
SUBTYPE_TO_NAME = {typ: name for name, typ in SUBTYPES.items()}

# Partition table offsets and sizes
PART_FMT = b"<2sBBLL16sL"  # Struct format to read a partition from partition table
PART_LEN = 32  # Size of one entry in partition table (32 bytes)
PART_MAGIC = b"\xaa\x50"  # Magic bytes present at start of each partition
PART_CHKSUM_MAGIC = b"\xeb\xeb"  # If these bytes at end of table, a checksum is present
PART_NAME_LEN = 16  # Length of the Partition label


class PartitionError(Exception):
    "Raised if an error occurs while reading or building a PartitionTable."

    def __init__(self, msg: str, table: PartitionTable | None = None) -> None:
        super().__init__(msg or "Error in partition table.")
        self.table = table

    def __str__(self) -> str:
        return super().__str__() + (f"\n{self.table}" if self.table else "")


class PartTuple(NamedTuple):
    """An entry in the partition table."""

    magic: bytes
    type: int
    subtype: int
    offset: int
    size: int
    label: bytes
    flags: int


# Return a number of bytes in a human readable format
def _human(size: int) -> str:
    return (
        f"({size:0.1f} B)" if size < 0.5 * KB else
        f"({size / KB:0.1f} kB)" if size < 0.5 * MB else
        f"({size / MB:0.1f} MB)"
    )  # fmt: skip


class PartitionEntry(PartTuple):
    @staticmethod
    def from_bytes(data: bytes) -> PartitionEntry:
        """Return a `Part` built from `data`, which is an entry in the partition
        table."""
        return PartitionEntry(*struct.unpack(PART_FMT, data))

    def is_valid(self) -> bool:
        """Check if the partition is valid."""
        return self.magic == PART_MAGIC

    def to_bytes(self) -> bytes:
        """Save the partition as an entry in a partition table in firmware."""
        return struct.pack(PART_FMT, *self)

    @cached_property
    def name(self) -> str:
        """Return the partition name as a string."""
        return self.label.rstrip(b"\x00").decode()

    @cached_property
    def type_name(self) -> str:
        """Return the name of the partition type (`"app"` or `"data"`)."""
        return TYPE_TO_NAME.get(self.type, str(self.type))

    # Return the partition subtype name (or the subtype number as a str)
    @cached_property
    def subtype_name(self) -> str:
        """Return the name of the partition subtype as a string."""
        return SUBTYPE_TO_NAME.get((self.type, self.subtype), str(self.subtype))


class PartitionTable(List[PartitionEntry]):
    """A class to hold a list of partitions (`Part`) in a partition table."""

    max_size: int

    # Copy the default flash layout values
    BOOTLOADER_SIZE = BOOTLOADER_SIZE
    PART_TABLE_OFFSET = PART_TABLE_OFFSET
    PART_TABLE_SIZE = PART_TABLE_SIZE
    FIRST_PART_OFFSET = FIRST_PART_OFFSET
    APP_PART_OFFSET = APP_PART_OFFSET
    OTADATA_SIZE = OTADATA_SIZE
    APP_TYPE = NAME_TO_TYPE["app"]
    DATA_TYPE = NAME_TO_TYPE["data"]

    def __init__(self, max_size: int = 0) -> None:
        self.max_size = max_size

    def find(self, name: str) -> PartitionEntry | None:
        return next((p for p in self if p.name == name), None)

    def by_name(self, name: str) -> PartitionEntry:
        if (p := self.find(name)) is None:
            raise PartitionError(f"Partition '{name}' not found.", self)
        return p

    def by_subtype(self, subtype_name: str) -> PartitionEntry:
        p = next((p for p in self if p.subtype_name == subtype_name), None)
        if not p:
            raise PartitionError(f"Partition '{subtype_name}' not found.", self)
        return p

    def table_data(self) -> TableTuple:
        title = f"Partition table (flash size: [red]{self.max_size // MB}MB[/red]):"
        format = "  {:16s} {:8s} {:8s} {:>#10x} {:>#10x} {:>#10x} {:>#5x} {:>10s}"
        header = "Name Type SubType Offset Size End Flags ''"
        data = [
            (
                p.name,
                p.type_name,
                p.subtype_name,
                p.offset,
                p.size,
                p.offset + p.size,
                p.flags,
                _human(p.size),
            )
            for p in self
        ]
        return TableTuple(title, format, header, data)

    def __str__(self) -> str:
        return plain_table(self.table_data())

    @staticmethod
    def from_bytes(data: bytes, max_size: int = 0) -> PartitionTable:
        """Build the partition table from the records in `data` where `data`
        is a partition table from an ESP32 firmware file or device."""
        table = PartitionTable(max_size)
        parts = takewhile(
            PartitionEntry.is_valid,
            (
                PartitionEntry.from_bytes(part)
                for part in (
                    data[i : i + PART_LEN] for i in range(0, len(data), PART_LEN)
                )
            ),
        )
        table.extend(parts)
        if len(table) == 0:
            raise PartitionError("No partition table found.", table)
        n = len(table) * PART_LEN
        chksum_part = data[n : n + PART_LEN]
        # Check if there is a checksum record at the end of the partition table
        if chksum_part.startswith(PART_CHKSUM_MAGIC):
            chksum = chksum_part[-16:]  # Last 16 bytes are the checksum
            md5 = hashlib.md5(data[:n]).digest()
            if md5 != chksum:  # Verify the checksum
                raise PartitionError(
                    f"Checksum: expected {chksum.hex()}, got {md5.hex()}.", table
                )
            n += PART_LEN
        # Check that there is at least one empty row next in partition table
        if data[n : n + PART_LEN] != b"\xff" * PART_LEN:
            raise PartitionError(
                "Partition table does not end with an empty row.", table
            )
        table.sort(key=lambda p: p.offset)
        if not table.max_size:  # Infer flash size from partition table
            table.max_size = table[-1].offset + table[-1].size
        try:
            table.check()
        except PartitionError as e:
            log.warning(f"Warning: {e}")
        return table

    def to_bytes(self) -> bytes:
        """Save the partition table in firmware format."""
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

    @property
    def app_part(self) -> PartitionEntry:
        """Find the first app partition in the table."""
        part = next(filter(lambda p: p.type_name == "app", self), None)
        if not part:
            raise PartitionError("No app partition found in table.", self)
        return part

    def next_part_offset(self) -> int:
        """Return the offset of the next available free space in flash storage."""
        return max([p.offset + p.size for p in self] + [self.FIRST_PART_OFFSET])

    def add_part(
        self,
        name: str,
        subtype_name: str,
        size: int,
        offset: int = 0,
        flags: int = 0,
    ) -> None:
        """Add a new partition to the partition table.

        If `offset` is 0, set offset to first available free space. If `size` is
        0 expand the size to fill the available free space.

        Args:
            name (str): The name (label) of the partition.
            subtype_name (str): Name of the subtype of the partition.
            size (int): Size of the partition in bytes.
            offset (int, optional): Offset of the partition in bytes. Defaults to 0.
            flags (int, optional): Flags of the partition. Defaults to 0.

        Raises:
            PartitionError: If the partition overlaps with another partition or
                there is no room on the flash storage.
        """
        if any(p for p in self if p.name == name):
            raise PartitionError(f"Partition '{name}' already exists in table.")
        offset = offset or self.next_part_offset()
        if offset + size > self.max_size:
            raise PartitionError(
                f"No room on flash for partition {name} ({size:#x} bytes).", self
            )
        size = size or (self.max_size - offset)
        type, subtype = SUBTYPES[subtype_name]
        label = name.encode().ljust(PART_NAME_LEN, b"\x00")
        self.append(
            PartitionEntry(PART_MAGIC, type, subtype, offset, size, label, flags)
        )
        self.sort(key=lambda p: p.offset)

    def resize_part(self, name: str, new_size: int) -> int:
        """Change size of partition (and adjusting offsets of following parts if
        necessary). If new_size is 0, expand to fill available space.

        Returns the new size of the partition."""
        i = self.index(self.by_name(name))
        i = [p.name for p in self].index(name)
        if new_size == 0:  # Expand to fill available space
            upper_limit = self[i + 1].offset if i + 1 < len(self) else self.max_size
            new_size = upper_limit - self[i].offset
        self[i] = self[i]._replace(size=new_size)
        for j in range(i + 1, len(self)):
            offset = self[j - 1].offset + self[j - 1].size
            if offset > self[j].offset:  # Shift other partitions to make room
                self[j] = self[j]._replace(offset=offset)
            if self.max_size < self[j].offset + self[j].size:
                # Shrink other partitions if they overflow the flash storage
                self[j] = self[j]._replace(size=self.max_size - self[j].offset)
        return new_size

    def check(self, app_size: int = 0) -> None:
        """Check the partition table for consistency.
        Raises `PartError` if any inconsistencies found."""
        offset = self.FIRST_PART_OFFSET
        names: set[str] = set()
        self.sort(key=lambda p: p.offset)
        for p in self:
            if p.name in names:
                raise PartitionError(f"'{p.name}' is repeated.", self)
            names.add(p.name)
            if p.offset < offset:
                raise PartitionError(
                    f"'{p.name}' overlaps with previous partition.", self
                )
            if p.offset > offset:
                log.warning(
                    f"Warning: Free space before '{p.name}' "
                    f"({p.offset - offset:#x} bytes).",
                )
            if p.offset % (1 * B):
                raise PartitionError(
                    f"'{p.name}' offset {p.offset:#x} is not multiple of 0x1000.", self
                )
            if p.size % (1 * B):
                raise PartitionError(
                    f"'{p.name}' size {p.size:#x} is not multiple of 0x1000.", self
                )
            if p.type_name == "app" and p.offset % (0x10 * B):
                raise PartitionError(
                    f"App partition '{p.name}' offset {p.offset:#x}"
                    f" is not multiple of 0x10000.",
                    self,
                )
            offset = p.offset + p.size
        if offset > self.max_size:
            raise PartitionError(
                f"End of last partition ({offset:#x})"
                f" is greater than flash size ({self.max_size:#x}).",
                self,
            )
        if offset != self.max_size:
            log.warning(
                f"Warning: End of last partition ({offset:#x})"
                f" < flash size ({self.max_size:#x})."
            )
        if self.app_part.offset != self.APP_PART_OFFSET:
            log.warning(
                f"Warning: First app at offset={self.app_part.offset:#x}"
                f" (expected {self.APP_PART_OFFSET:#x})."
            )
        if app_size and self.app_part.size < app_size:
            raise PartitionError(
                f"App partition '{self.app_part.name}' is too small for "
                f"micropython app "
                f"({self.app_part.size:#x} < {app_size:#x} bytes).\n"
                "Use the '-a' option to set a larger app partition size.",
                self,
            )
