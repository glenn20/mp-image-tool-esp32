#!/usr/bin/env python3
# MIT License: Copyright (c) 2023 @glenn20
"""Provides utility functions to build, read and print partition table layouts
for ESP32 firmware, including OTA layouts.

Provides:
- `new_table(table, layout)`: Replace the partitions in table with new
  partitions generated from the provided layout.
- `ota_layout(table, app_part_size=0)`: Return an OTA partition table
  layout
- `from_csv(table, filename)`: Replace the partitions in table with new
  partitions from a CSV file.
- `print_table(table)`: Print a detailed description of the partition table.
"""


import csv

from . import logger as log
from .argtypes import KB, MB, PartList
from .partition_table import PartitionError, PartitionTable

# Recommended size for OTA app partitions (depends on flash_size).
# These choices match OTA partition sizes in ports/esp32/partition-*-ota.csv.
OTA_PART_SIZES = (
    (8 * MB, 0x270_000),  # if flash size > 8MB
    (4 * MB, 0x200_000),  # else if flash size > 4MB
    (0 * MB, 0x180_000),  # else if flash size > 0MB
)
DEFAULT_TABLE_LAYOUT = """
nvs     : nvs       : 0x7000,
factory : factory   : 0x1f0000,
vfs     : fat       : 0
"""
OTA_TABLE_LAYOUT = """
nvs     : nvs       : {nvs},
otadata : ota       : {otadata},
ota_0   : ota_0     : {ota_0},
ota_1   : ota_1     : {ota_1},
vfs     : fat       : 0
"""
# Mapping of partition names to default subtypes
# Don't need to include where name==subtype as will fall back name.
default_subtype = {
    "otadata": "ota",
    "vfs": "fat",
    "phy_init": "phy",
}


def ota_part_size(flash_size: int) -> int:
    """Calculate and return the recommended OTA app part size (in bytes) for the
    given flash_size."""
    return next(part_size for fsize, part_size in OTA_PART_SIZES if flash_size > fsize)


def get_subtype(name: str, subtype: str) -> str:
    """Return subtype if it is not empty, else infer subtype from name."""
    return subtype or default_subtype.get(name, name)


# PartList is a list of tuples which specify a Partition:
#   [(name, subtype, offset, size), ...]
def new_table(
    table: PartitionTable,
    table_layout: PartList,
    app_size: int = 0,  # Size of the firmware app (bytes)
) -> PartitionTable:
    """Build a new partition table from the provided layout.
    For each tuple, if subtype is `""`, infer `subtype` from name."""
    table.clear()  # Empty the partition table
    for name, *subtype, offset, size in table_layout:
        subtype = get_subtype(name, subtype[0] if subtype else "")
        table.add_part(name, subtype, size, offset)
    if table.app_part and table.app_part.size < app_size:
        raise PartitionError(
            f"App size ({app_size}) exceeds '{table.app_part.name}' "
            f"partition size ({table.app_part.size}):\n"
            "  Use the '-a' option to set the app partition size.",
            table,
        )
    return table


def ota_layout(
    table: PartitionTable,
    app_part_size: int = 0,  # Size of the partition to hold the app (bytes)
) -> str:
    """Build a layout string for a new OTA-enabled partition table, given
    `flash_size` and `app_part_size`. If `app_part_size` is 0, use the
    recommended size for the flash size."""
    flash_size = table.max_size
    if not app_part_size:
        app_part_size = ota_part_size(flash_size)
    nvs_part_size = table.app_part.offset - table.FIRST_PART_OFFSET - table.OTADATA_SIZE
    return OTA_TABLE_LAYOUT.format(
        nvs=nvs_part_size,
        otadata=table.OTADATA_SIZE,
        ota_0=app_part_size,
        ota_1=app_part_size,
    )


def from_csv(table: PartitionTable, filename: str) -> PartitionTable:
    """Load the partiton table from a CSV file."""
    table.clear()
    with open(filename, newline="") as f:
        reader = csv.reader((s for s in f if s[0] != "#"), skipinitialspace=True)
        for name, _, subtype, offset, size, flags in reader:
            table.add_part(name, subtype, int(size, 0), int(offset, 0), int(flags, 0))
    table.check()
    return table


def print_table(table: PartitionTable, app_size: int = 0) -> None:
    """Print a detailed description of the partition table."""
    colors = dict(c=log.CYAN, r=log.RED)

    print(log.CYAN, end="")
    print(
        "{c}Partition table (flash size: {r}{size}MB{c}):".format(
            size=table.max_size // MB, **colors
        )
    )
    print(table)
    print(log.RESET, end="")
    if table.app_part and app_size:
        print(
            "Micropython app fills {used:0.1f}% of {app} partition "
            "({rem} kB free)".format(
                used=100 * app_size / table.app_part.size,
                app=table.app_part.name,
                rem=(table.app_part.size - app_size) // KB,
            )
        )
