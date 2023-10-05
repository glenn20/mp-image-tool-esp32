#!/usr/bin/env python3

# MIT License: Copyright (c) 2023 @glenn20

from __future__ import annotations

import copy
import os
import re

from colorama import Fore
from colorama import init as colorama_init

from . import image_device, image_file, parse_args
from .partition_table import NAME_TO_TYPE, PartError, PartitionTable

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
nvs       nvs        0x7000
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
# Mapping of partition names to default subtypes
# Don't need to include where name==subtype as will fall back name.
default_subtype: dict[str, str] = {"otadata": "ota", "vfs": "fat", "phy_init": "phy"}
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
    table = copy.copy(old_table)
    table.clear()  # Empty the partition table
    if not app_part_size:
        app_part_size = ota_part_size(flash_size)
    nvs_part_size = (
        old_table.app_part.offset - table.FIRST_PART_OFFSET - table.OTADATA_SIZE
    )
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
    colors = dict(c=Fore.CYAN, r=Fore.RED, _=Fore.RESET)

    print(Fore.CYAN, end="")
    print(
        "{c}Partition table (flash size: {r}{size}MB{c}):".format(
            size=table.flash_size // MB, **colors
        )
    )
    table.print()
    print(Fore.RESET, end="")
    table.check()
    if table.app_part and table.app_size:
        print(
            "Micropython app fills {used:0.1f}% of {app} partition "
            "({rem} kB unused)".format(
                used=100 * table.app_size / table.app_part.size,
                app=table.app_part.name,
                rem=(table.app_part.size - table.app_size) // KB,
            )
        )
    vfs = table[-1] if table[-1].name in ("vfs", "ffat") else None
    if vfs:
        print(f"Filesystem partition '{vfs.name}' is {vfs.size / MB:0.1f} MB.")


def print_action(*args, **kwargs) -> None:
    print(Fore.GREEN, end="")
    print(*args, Fore.RESET, **kwargs)


def print_error(*args, **kwargs) -> None:
    print(Fore.RED, end="")
    print(*args, Fore.RESET, **kwargs)


arguments = """
    mp-image-tool-esp32
    Tool for manipulating MicroPython esp32 firmware image files and flash storage on
    esp32 devices.

    filename                    | the esp32 firmware image filename or serial device
    -q --quiet                  | mute program output | T
    -n --dummy                  | no output file | T
    -d --debug                  | print additional info | T
    -x --extract-app            | extract .app-bin from firmware | T
    -f --flash-size SIZE        | size of flash for new partition table
    -a --app-size SIZE          | size of factory and ota app partitions
    --from-csv FILE             | load new partition table from CSV file
    --table NAME1,SUBTYPE,SIZE[/NAME2,...] \
                                | create new partition table. SUBTYPE is optional \
                                  in most cases. Eg. --table nvs,7B/factory,2M/vfs,0
    --ota                       | build an OTA partition table | T
    --delete NAME1[,NAME2]      | delete the named partitions
    --add NAME1,SUBTYPE,OFFSET,SIZE[/NAME2,...] \
                                | add new partitions to table
    --resize NAME1=SIZE1[,NAME2=SIZE2] \
                                | resize partitions eg. --resize \
                                  factory=2M,nvs=5B,vfs=0. if SIZE is 0, \
                                  expand partition to use available space.
    --erase NAME1[,NAME2]       | erase the named partitions on device flash storage
    --erase-fs NAME1[,NAME2]    | erase first 4 blocks of a partition on flash \
                                  storage. Micropython will initialise fs on next boot.
    --read NAME1=FILE1[,NAME2=FILE2] \
                                | copy partition contents to file
    --write NAME1=FILE1[,NAME2=FILE2] \
                                | write file contents into partitions on the \
                                  device flash storage.

    Where SIZE is a decimal or hex number with an optional suffix (M=megabytes,
    K=kilobytes, B=blocks (0x1000=4096 bytes)).
"""


def process_args() -> None:
    parser = parse_args.parser(arguments)
    options = parser.parse_args()
    global debug
    debug = options.debug
    image_device.debug = options.debug  # print esptool.py commands and output
    input: str = options.filename  # the input firmware filename
    verbose = not options.quiet  # verbose is True by default
    extension = ""  # Each operation that changes table adds identifier to extension

    # Use u0, a0, and c0 as aliases for /dev/ttyUSB0. /dev/ttyACM0 and COM0
    input = re.sub(r"^u([0-9]+)$", r"/dev/ttyUSB\1", input)
    input = re.sub(r"^a([0-9]+)$", r"/dev/ttyACM\1", input)
    input = re.sub(r"^c([0-9]+)$", r"COM\1", input)

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

    arg: str
    # -x --extract-app : Extract the micropython app image from the firmware file
    if options.extract_app:
        basename: str = os.path.basename(input)
        output = basename[:-4] if basename.endswith(".bin") else basename
        output += ".app-bin"
        if verbose:
            print_action(f"Writing micropython app image file: {output}...")
        image_file.save_app_image(input, output, table)

    ## Commands to modify the partition table

    # -f --flash-size SIZE : Set the size of the flash storage
    if arg := options.flash_size:
        flash_size = numeric_arg(arg)
        if flash_size and flash_size != table.flash_size:
            table.flash_size = flash_size
        extension += f"-{flash_size // MB}MB"

    # --from-csv FILE : Replace partition table with one loaded from CSV file.
    if arg := options.from_csv:
        table.from_csv(arg)
        extension += "-CSV"

    # --table nvs,,7B/factory,,2M/vfs,,0
    if arg := options.table:
        table.clear()
        for name, *rest in (s.split(",") for s in arg.split("/")):
            subtype = (
                rest[0]
                if len(rest) == 2 and rest[0]
                else default_subtype.get(name, name)
            )
            size = numeric_arg(rest[-1])
            table.add_part(name.strip(), subtype.strip(), size)
        table.check()
        extension += "-TABLE"

    # --ota : Replace partition table with an OTA-enabled table.
    if options.ota:
        app_part_size = numeric_arg(options.app_size)
        table = new_ota_table(table, app_part_size)
        extension += "-OTA"

    # -a --app-size SIZE : Resize all the APP partitions
    if arg := options.app_size:
        app_part_size = numeric_arg(arg)
        app_parts = filter(lambda p: p.type == NAME_TO_TYPE["app"], table)
        for p in app_parts:
            table.resize_part(p.name, app_part_size)
        extension += f"-APP={arg}"

    # --delete name1[,name2,..] : Delete a partition from table
    if arg := options.delete:
        for name in arg.split(","):
            table.remove(table[name])
        extension += f"-delete={arg}"

    # --add NAME1,SUBTYPE,OFFSET,SIZE[:NAME2,..] : Add a new partition to table
    if arg := options.add:
        for name, subtype, offset, size in (s.split(",") for s in arg.split("/")):
            table.add_part(name, subtype, numeric_arg(size), numeric_arg(offset))
        extension += f"-add={arg}"

    # --resize NAME1=SIZE[,NAME2=...] : Resize partitions
    if arg := options.resize:
        for name, size in (s.split("=", 1) for s in arg.split(",")):
            table.resize_part(name, numeric_arg(size))
        table.check()
        extension += f"-{arg}"

    ## Write the modified partition table to a new file or flash storage on device

    if not options.dummy and extension:
        if not image_file.is_device(input):
            # Make a copy of the firmware file with new partition table
            basename: str = os.path.basename(input)
            name, suffix = basename.rsplit(".", 1)
            output = f"{name}{extension}.{suffix}"
            if verbose:
                print_action(f"Writing output file: {output}...")
                print_table(table)
            image_file.copy_with_new_table(input, output, table)
        else:
            # Write the new partition table to the ESP32 device
            if verbose:
                print_action(f"Writing new table to flash storage at {input}...")
                print_table(table)
            image_device.write_table(input, table)
            # Erase all the partitions before the first app partition
            # This typically includes any nvs, otadata and phy_init partitions
            parts = [p for p in table if p.offset < table.app_part.offset]
            if verbose:
                part_names = ", ".join(f"'{p.name}'" for p in parts)
                print_action(f"Erasing partitions: {part_names}...")
            for p in parts:
                image_device.erase_part(input, p)

    # For erasing/reading/writing flash storage partitions

    # --erase NAME1[,NAME2,...] : Erase the partitions on the flash storage
    if arg := options.erase:
        if not image_file.is_device(input):
            raise ValueError("--erase requires an esp32 device")
        for name in arg.split(","):
            if not options.dummy:
                image_device.erase_part(input, table[name])

    # --erase-fs NAME1[,NAME2,...] : Erase the first 4 blocks of partitions
    # Micropython will automatically re-initialise the filesystem on boot.
    if arg := options.erase_fs:
        if not image_file.is_device(input):
            raise ValueError("--erase-fs requires an esp32 device")
        for name in arg.split(","):
            part = table[name]
            if part.name not in ("vfs", "ffat"):
                raise PartError(f'partition "{part.name}" is not a fs partition.')
            print_action(f'Erasing filesystem on partition "{part.name}"...')
            if not options.dummy:
                image_device.erase_part(input, part, 4 * B)

    # --read NAME1=FILE1[,NAME2=...] : Read contents of partition NAME1 into FILE
    if arg := options.read:
        if not image_file.is_device(input):
            raise ValueError("--read requires an esp32 device")
        for name, filename in (s.split("=", 1) for s in arg.split(",")):
            part = table[name]
            if verbose:
                print_action(f"Saving partition '{name}' into '{filename}'...")
            if not options.dummy:
                n = image_device.read_part(input, part, filename)
                if verbose:
                    print(f"Wrote {n:#x} bytes to '{filename}'.")

    # --write NAME1=FILE1[,NAME2=...] : Write contents of FILE into partition NAME1
    if arg := options.write:
        if not image_file.is_device(input):
            raise ValueError("--write requires an esp32 device")
        for name, filename in (s.split("=", 1) for s in arg.split(",")):
            part = table[name]
            if verbose:
                print_action(f"Writing partition '{name}' from '{filename}'...")
            if not options.dummy:
                n = image_device.write_part(input, part, filename)
                if verbose:
                    print(f"Wrote {n:#x} bytes to partition '{name}'.")


def main() -> int:
    colorama_init()
    try:
        process_args()
    except (PartError, ValueError, FileNotFoundError) as err:
        print_error(f"{type(err).__name__}: {err}")
        if isinstance(err, PartError) and err.table:
            err.table.print()
        if debug:
            raise err
        return 1
    return 0


if __name__ == "__main__":
    main()
