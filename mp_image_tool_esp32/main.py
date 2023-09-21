#!/usr/bin/env python3

# MIT License: Copyright (c) 2023 @glenn20

from __future__ import annotations

import argparse
import copy
import os

from colorama import init as colorama_init

from . import image_file
from .partition_table import PartError, PartitionTable

MB = 0x100_000  # 1 Megabyte
KB = 0x400  # 1 Kilobyte
B = 0x1_000  # 1 Block (4096 bytes)
SIZE_UNITS = {"M": MB, "K": KB, "B": B}

# Recommended size for OTA app partitions (depends on flash_size).
OTA_PART_SIZES = (
    (8 * MB, 0x270_000),  # if flash size > 8MB
    (4 * MB, 0x200_000),  # else if flash size > 4MB
    (0 * MB, 0x180_000),  # else if flash size > 0MB
)

DEFAULT_TABLE_FMT = """
nvs       nvs        0x6000
phy_init  phy        0x1000
factory   factory  0x1f0000
vfs       fat             0
"""
OTA_TABLE_FMT = """
nvs       nvs         {nvs}
otadata   ota     {otadata}
ota_0     ota_0     {ota_0}
ota_1     ota_1     {ota_1}
vfs       fat             0
"""


# Return the recommended OTA app part size (depends on flash_size)
def ota_part_size(flash_size: int) -> int:
    return next(part_size for fsize, part_size in OTA_PART_SIZES if flash_size > fsize)


# Convert a partition table format string to build a partition table
def table_spec(fmt: str, **kwargs) -> list[tuple[str, str, int]]:
    return [
        (name, type, int(size))
        for name, type, size in [
            line.split() for line in fmt.strip().format(**kwargs).split("\n")
        ]
    ]


# Process a string containing a number with an optional unit suffix
# eg. "8M" (8 megabytes), "0x10B" (16 disk blocks), "4K" (4 kilobytes)
def numeric_arg(arg: str) -> int:
    if not arg:
        return 0
    unit = 1
    if arg[-1].upper() in SIZE_UNITS.keys():
        unit = SIZE_UNITS[arg[-1].upper()]
        arg = arg[:-1]
    return int(arg, 0) * unit


# Build a new OTA-enabled partition table for the given flash size and app
# partition size. Will check can accommodate given app_size.
def new_ota_table(
    old_table: PartitionTable,
    app_part_size: int = 0,  # Size of the partition to hold the app (bytes)
) -> PartitionTable:
    flash_size = old_table.flash_size
    # if flash_size < 4 * MB:
    #     raise ValueError(f"Flash size ({flash_size:#x}) is < 4MB.")

    table = copy.copy(old_table)
    table.clear()  # Empty the partition table
    if not app_part_size:
        app_part_size = ota_part_size(flash_size)
    nvs_part_size = table.APP_PART_OFFSET - table.FIRST_PART_OFFSET - table.OTADATA_SIZE
    spec = table_spec(
        OTA_TABLE_FMT,
        nvs=nvs_part_size,
        otadata=table.OTADATA_SIZE,
        ota_0=app_part_size,
        ota_1=app_part_size,
    )
    for p in spec:
        table.add_part(*p)
    table.check()
    return table


colorama_init()

parser = argparse.ArgumentParser()
parser.add_argument("filename", help="the esp32 image file name")
parser.add_argument("-q", "--quiet", help="mute program output", action="store_true")
parser.add_argument("-n", "--dummy", help="no output file", action="store_true")
parser.add_argument(
    "-d", "--debug", help="print additional diagnostics", action="store_true"
)
parser.add_argument("--ota", help="build an OTA partition table", action="store_true")
parser.add_argument(
    "-x", "--extract-app", help="extract the micropython .app-bin", action="store_true"
)
parser.add_argument("-f", "--flash-size", help="size of flash for new partition table")
parser.add_argument("-a", "--app-size", help="size of factory and ota app partitions")
parser.add_argument(
    "-r",
    "--resize",
    help="resize specific partitions by label, eg. --resize factory=0x2M,vfs=0x400K",
)


def main() -> int:
    args = parser.parse_args()
    input: str = args.filename
    filename: str = os.path.basename(input)
    verbose = not args.quiet
    extension = ""

    try:
        table = image_file.load_partition_table(input, verbose)

        if args.extract_app:
            output = filename[:-4] if filename.endswith(".bin") else filename
            output += ".app-bin"
            image_file.save_app_image(input, output, table, verbose)

        if args.flash_size:
            flash_size = numeric_arg(args.flash_size)
            if flash_size and flash_size != table.flash_size:
                table.resize_flash(flash_size)
            extension += f"-{flash_size // MB}MB"

        if args.ota:
            app_part_size = numeric_arg(args.app_size)
            table = new_ota_table(table, app_part_size)
            extension += "-OTA"
        elif args.app_size:
            app_part_size = numeric_arg(args.app_size)
            app_parts = filter(lambda p: p.type == 0, table)
            for p in app_parts:
                table.resize_part(p.label_name, app_part_size)
            extension += f"-APP={args.app_size}"

        if args.resize:
            for spec in args.resize.split(","):
                part_name, size = spec.split("=", 1)
                table.resize_part(part_name, numeric_arg(size))
            extension += f"-{args.resize}"

        if not args.dummy and extension:
            name, suffix = filename.rsplit(".", 1)
            output = f"{name}{extension}.{suffix}"
            image_file.copy_with_new_table(input, output, table, verbose)
    except PartError as err:
        if args.debug:
            raise err
        print(err)
        return 1
    return 0


if __name__ == "__main__":
    main()
