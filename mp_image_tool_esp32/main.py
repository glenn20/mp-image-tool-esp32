#!/usr/bin/env python3

# MIT License: Copyright (c) 2023 @glenn20

from __future__ import annotations

import argparse
import copy
import os

from colorama import Fore
from colorama import init as colorama_init

from . import image_device, image_file
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

debug = False


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


# Provide a detailed printout of the partition table
def print_table(table: PartitionTable) -> None:
    colors = dict(g=Fore.GREEN, r=Fore.RED, _=Fore.RESET)

    print(
        "{g}Partition table (flash size: {r}{size}MB{g}):".format(
            size=table.flash_size // MB, **colors
        )
    )
    print(Fore.CYAN, end="")
    table.print()
    print(Fore.RESET, end="")
    table.check()
    if table.app_part:
        print(
            "Micropython app fills {used:0.1f}% of {app} partition "
            "({rem} kB unused)".format(
                used=100 * table.app_size / table.app_part.size,
                app=table.app_part.label_name,
                rem=(table.app_part.size - table.app_size) // KB,
            )
        )
    vfs = table[-1] if table[-1].label_name in ("vfs", "ffat") else None
    if vfs:
        print(f"Filesystem partition '{vfs.label_name}' is {vfs.size / MB:0.1f} MB.")


def print_action(*args) -> None:
    print(Fore.GREEN, end="")
    print(*args, Fore.RESET)


def print_error(*args) -> None:
    print(Fore.RED, end="")
    print(*args, Fore.RESET)


colorama_init()

parser = argparse.ArgumentParser()
parser.add_argument("filename", help="the esp32 image file name")
parser.add_argument("-q", "--quiet", help="mute program output", action="store_true")
parser.add_argument("-n", "--dummy", help="no output file", action="store_true")
parser.add_argument("-d", "--debug", help="print additional info", action="store_true")
parser.add_argument("--ota", help="build an OTA partition table", action="store_true")
parser.add_argument("-f", "--flash-size", help="size of flash for new partition table")
parser.add_argument("-a", "--app-size", help="size of factory and ota app partitions")
parser.add_argument("--erase-fs", help="erase first 4 blocks of the named fs partition")
parser.add_argument("--from-csv", help="load new partition table from CSV file")
parser.add_argument("--erase-part", help="erase the named partition on an esp32 device")
parser.add_argument("--write-part", help="write a file into a partition", nargs=2)
parser.add_argument(
    "--read-part", help="save a partition from an esp32 device to a file", nargs=2
)
parser.add_argument(
    "-x", "--extract-app", help="extract .app-bin from firmware", action="store_true"
)
parser.add_argument(
    "-r",
    "--resize",
    help="resize specific partitions by label, eg. --resize factory=0x2M,vfs=0x400K",
)


def process_args(args: argparse.Namespace) -> None:
    image_device.debug = args.debug  # print esptool.py commands and output
    input: str = args.filename  # the input firmware filename
    verbose = not args.quiet  # verbose is True by default
    extension = ""  # Each operarion that changes table adds identifier to extension

    # Open the input firmware file or esp32 device
    if verbose:
        desc = "esp32 device at" if image_file.is_device(input) else "image file"
        print_action(f"Opening {desc}: {input}...")
    table = image_file.load_partition_table(input)
    if verbose:
        print(f"Chip type: {table.chip_name}")
        print(f"Flash size: {table.flash_size // MB}MB")
        print(
            f"Micropython App size: {table.app_size:#x} bytes "
            f"({table.app_size // KB:,d} KB)"
        )
        print_table(table)

    # Extract the micropython app image from the firmware file
    if args.extract_app:
        basename: str = os.path.basename(input)
        output = basename[:-4] if basename.endswith(".bin") else basename
        output += ".app-bin"
        if verbose:
            print_action(f"Writing micropython app image file: {output}...")
        image_file.save_app_image(input, output, table)

    # Commands to modify the partition table
    if args.flash_size:
        flash_size = numeric_arg(args.flash_size)
        if flash_size and flash_size != table.flash_size:
            table.resize_flash(flash_size)
        extension += f"-{flash_size // MB}MB"

    if args.ota:
        app_part_size = numeric_arg(args.app_size)
        table = new_ota_table(table, app_part_size)
        extension += "-OTA"

    if args.from_csv:
        filename = args.from_csv
        table.from_csv(filename)
        extension += "-CSV"

    if args.app_size:
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

    # Write the modified partition table to a new file or flash storage on device
    if not args.dummy and extension:
        if not image_file.is_device(input):
            basename: str = os.path.basename(input)
            part_name, suffix = basename.rsplit(".", 1)
            output = f"{part_name}{extension}.{suffix}"
            if verbose:
                print_action(f"Writing output file: {output}...")
                print_table(table)
            image_file.copy_with_new_table(input, output, table)
        else:
            if verbose:
                print_action(f"Writing new table to flash storage at {input}...")
                print_table(table)
            image_device.write_table(input, table)
            # Erase all the partitions before the first app partition
            # This typically includes any nvs, otadata and phy_init partitions
            parts = [p for p in table if p.offset < table.app_part.offset]
            if verbose:
                part_names = ", ".join(f'"{p.label_name}"' for p in parts)
                print_action(f"Erasing partitions: {part_names}...")
            for p in parts:
                image_device.erase_part(input, p)

    # For erasing flash storage partitions
    if args.erase_part:
        part_names: str = args.erase_part
        if not image_file.is_device(input):
            raise ValueError("--erase-region requires an esp32 device")
        for part_name in part_names.split(","):
            part = table.by_name(part_name)
            if not part:
                raise ValueError(f'partition not found "{part_name}".')
            if not args.dummy:
                image_device.erase_part(input, part)

    if args.erase_fs:
        part_names: str = args.erase_fs
        if not image_file.is_device(input):
            raise ValueError("--erase-fs requires an esp32 device")
        for part_name in part_names.split(","):
            part = table.by_name(part_name)
            if not part:
                raise PartError(f'partition not found: "{part_name}".')
            if part.label_name not in ("vfs", "ffat"):
                raise PartError(f'partition "{part_name}" is not a fs partition.')
            print_action(f'Erasing filesystem on partition "{part.label_name}"...')
            if not args.dummy:
                image_device.erase_part(input, part, 4 * B)

    if args.read_part:
        part_name, filename = args.read_part
        if (part := table.by_name(part_name)) is None:
            raise PartError(f"No partition '{part_name}' found.")
        if verbose:
            print_action(f"Saving partition '{part_name}' into '{filename}'...")
        n = image_device.read_part(input, part, filename)
        if verbose:
            print(f"Wrote {n:#x} bytes to '{filename}'.")

    if args.write_part:
        part_name, filename = args.write_part
        if (part := table.by_name(part_name)) is None:
            raise PartError(f"No partition '{part_name}' found.")
        if verbose:
            print_action(f"Writing partition '{part_name}' from '{filename}'...")
        n = image_device.write_part(input, part, filename)
        if verbose:
            print(f"Wrote {n:#x} bytes to '{part_name}'.")


def main() -> int:
    args = parser.parse_args()
    try:
        process_args(args)
    except (PartError, ValueError) as err:
        print_error(err)
        if args.debug:
            raise err
        return 1
    return 0


if __name__ == "__main__":
    main()
