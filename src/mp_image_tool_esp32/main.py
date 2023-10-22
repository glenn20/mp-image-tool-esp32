#!/usr/bin/env python3
# MIT License: Copyright (c) 2023 @glenn20
"""Main program module for mp-image-tool-esp32: a tool for manipulating ESP32
firmware files and flash storage on ESP32 devices.

After importing, call `main.main()` to execute the program.

Dependencies:
- `colorama` for colour terminal support,
- `esptool.py` for access to flash storage on serial-attached ESP32 devices.
"""

import argparse
import copy
import os
import re
import shutil

from colorama import init as colorama_init

from . import common, image_file, layouts, ota_update, parse_args
from .common import KB, MB, B, error, info, vprint
from .image_file import Esp32Image
from .partition_table import NAME_TO_TYPE, PartitionError, PartitionTable

# Convenient type aliases for static type checking of arguments
ArgList = list[list[str]]
# List of Partition tuples: [(name, subtype, offset, size), ...]
PartList = list[tuple[str, str, int, int]]


# `TypedNamespace` and the `usage` string together provide three things:
# 1. static type checking for the fields in the namespace returned by
#    `argparse.parse_args()`.
# 2. *automatic* conversion of string arguments to the correct type (using the
#    `type=` keyword of `argparse.add_argument()`).
# 3. an overly-elaborate method for avoiding the boilerplate of
#    `argparse.add_argument()` which also makes the command usage much easier
#    for humans to parse from the code.
#
# `TypedNamespace` must include a field for each (non-`str`) optional argument
# (prefixed with "-") provided in the `usage` string.
#
# The `type_mapper` field is used to provide type conversion functions that
# override the default type constructor. bool arguments are handled with
# `action="store_true"` unless overridden in `type_mapper`.
class TypedNamespace(argparse.Namespace):
    filename: str
    output: str
    quiet: bool
    debug: bool
    extract_app: bool
    flash_size: int
    app_size: int
    no_rollback: bool
    ota_update: str
    from_csv: str
    table: PartList
    delete: ArgList
    add: PartList
    resize: PartList
    erase: ArgList
    erase_fs: ArgList
    read: ArgList
    write: ArgList
    bootloader: str
    type_mapper = {  # Map types to funcs which return type from a string arg.
        int: parse_args.numeric_arg,  # Convert arg to an integer.
        PartList: parse_args.partlist,  # Convert arg to a list of Part tuples.
        ArgList: parse_args.arglist,  # Convert arg to a list[list[str]].
    }


# Remember to add any new arguments here to TypedNamespace above as well.
usage = """
    mp-image-tool-esp32

    Tool for manipulating MicroPython esp32 firmware files and flash storage
    on esp32 devices.

    filename            | the esp32 firmware image filename or serial device
    -o --output         | output filename
    -q --quiet          | mute program output
    -d --debug          | print additional info
    -x --extract-app    | extract .app-bin from firmware
    -f --flash-size SIZE| size of flash for new partition table
    -a --app-size SIZE  | size of factory and ota app partitions
    --no-rollback       | disable app rollback after OTA update
    --ota-update FILE   | perform an OTA firmware updgrade over the serial port
    --from-csv FILE     | load new partition table from CSV file
    --table ota/default/NAME1=SUBTYPE:SIZE[,NAME2,...] \
                        | create new partition table, eg: \
                            "--table ota" (install an OTA-enabled partition table),\
                            "--table default" (default (non-OTA) partition table),\
                            "--table nvs=7B,factory=2M,vfs=0". \
                            SUBTYPE is optional in most cases (inferred from name).
    --delete NAME1[,NAME2] | delete the named partitions
    --add NAME1:SUBTYPE:OFFSET:SIZE[,NAME2,...] \
                        | add new partitions to table
    --resize NAME1=SIZE1[,NAME2=SIZE2] \
                        | resize partitions \
                            eg. --resize factory=2M,nvs=5B,vfs=0. \
                            If SIZE is 0, expand partition to available space
    --erase NAME1[,NAME2] | erase the named partitions on device flash storage
    --erase-fs NAME1[,NAME2] \
                        | erase first 4 blocks of a partition on flash storage.\
                            Micropython will initialise filesystem on next boot.
    --read NAME1=FILE1[,NAME2=FILE2] \
                        | copy partition contents to file
    --write NAME1=FILE1[,NAME2=FILE2] \
                        | write file contents into partitions on the \
                            device flash storage.
    --bootloader FILE   | load a new bootloader from FILE

    Where SIZE is a decimal or hex number with an optional suffix (M=megabytes,
    K=kilobytes, B=blocks (0x1000=4096 bytes)).

    Options --erase, --erase-fs, --read, --write and --bootloader can only be
    used when operating on serial-attached devices (not firmware files).
"""


def process_arguments() -> None:
    namespace: TypedNamespace = TypedNamespace()
    parser = parse_args.parser(usage, namespace)
    args = parser.parse_args(namespace=namespace)

    common.debug = args.debug
    common.verbose = not args.quiet  # verbose is True by default

    # Use u0, a0, and c0 as aliases for /dev/ttyUSB0. /dev/ttyACM0 and COM0
    input: str = args.filename  # the input firmware filename
    input = re.sub(r"^u([0-9]+)$", r"/dev/ttyUSB\1", input)
    input = re.sub(r"^a([0-9]+)$", r"/dev/ttyACM\1", input)
    input = re.sub(r"^c([0-9]+)$", r"COM\1", input)
    basename: str = os.path.basename(input)
    what: str = "esp32 device" if image_file.is_device(input) else "image file"

    # Open input (args.filename) from firmware file or esp32 device
    info(f"Opening {what}: {input}...")
    image: Esp32Image = image_file.open_esp32_image(input)
    if image.app_size:
        x = image.app_size
        vprint(f"Micropython App size: {x:#x} bytes ({x // KB:,d} KB)")
    table: PartitionTable = image_file.load_partition_table(image)
    if common.verbose:
        layouts.print_table(table)
    initial_table = copy.copy(table)  # Preserve deep copy of original table
    extension = ""  # Each op that changes table adds identifier to extension

    if args.extract_app:  # -x --extract-app : Extract app image from firmware
        output = args.output or re.sub(r"(.bin)?$", ".app-bin", basename, 1)
        info(f"Writing micropython app image file: {output}...")
        image_file.save_app_image(image, output, table)

    if args.flash_size:  # -f --flash-size SIZE : Set size of the flash storage
        if args.flash_size and args.flash_size != table.flash_size:
            table.flash_size = args.flash_size
        extension += f"-{args.flash_size // MB}MB"

    if args.ota_update:  # --ota-update FILE : Perform an OTA firmware upgrade
        if not image.is_device:
            raise ValueError("--ota requires an esp32 device")
        info(f"Performing OTA firmware upgrade from '{args.ota_update}'...")
        ota_update.ota_update(image, table, args.ota_update, args.no_rollback)

    if args.from_csv:  # --from-csv FILE : Replace part table from CSV file.
        table = layouts.from_csv(table, args.from_csv)
        extension += "-CSV"

    if args.table:  # --table nvs=7B,factory=2M,vfs=0
        if args.table == [("ota", "", 0, 0)]:
            args.table = parse_args.partlist(layouts.ota_layout(table, args.app_size))
            extension += "-OTA"
        elif args.table == [("default", "", 0, 0)]:
            args.table = parse_args.partlist(layouts.DEFAULT_TABLE_LAYOUT)
            extension += "-DEFAULT"
        else:
            extension += "-TABLE"
        # Break up the value string into a partition table layout
        table = layouts.new_table(table, args.table)
        table.check()

    if args.app_size:  # -a --app-size SIZE : Resize all the APP partitions
        app_parts = filter(lambda p: p.type == NAME_TO_TYPE["app"], table)
        for p in app_parts:
            table.resize_part(p.name, args.app_size)
        extension += f"-appsize={args.app_size}"

    if args.delete:  # --delete name1[,name2,..] : Delete partition from table
        for name, *_ in args.delete:
            table.remove(table.by_name(name))
        extension += f"-delete={parse_args.unsplit(args.delete)}"

    if args.resize:  # --resize NAME1=SIZE[,NAME2=...] : Resize partitions
        for name, *_, new_size in args.resize:
            info(f"Resizing {name} partition to {new_size:#x} bytes...")
            table.resize_part(name, new_size)
        table.check()
        extension += f"-resize={parse_args.unsplit(args.resize)}"

    if args.add:  # --add NAME1=SUBTYPE:OFFSET:SIZE[,..] : Add new partitions
        for name, subtype, offset, size in args.add:
            subtype = layouts.get_subtype(name, subtype)
            table.add_part(name, subtype, size, offset)
        extension += f"-add={parse_args.unsplit(args.add)}"

    ## Write modified partition table to a new file or back to flash storage

    if extension:  # A change has been made to the partition table
        layouts.print_table(table)
        if initial_table.app_part.offset != table.app_part.offset:
            raise PartitionError("first app partition offset has changed", table)
        # Make a copy of the firmware file with new partition table
        output = (
            input
            if image.is_device  # Write table back to esp32 device flash storage.
            else args.output or re.sub(r"([.][^.]+)?$", f"{extension}\\1", basename, 1)
        )
        info(f"Writing to {what}: {output}...")
        if not image.is_device:  # If input is a firmware file, make a copy
            shutil.copy(input, output)
            image.file.close()
            image = image_file.open_esp32_image(output)
        # Write the new values to the firmware...
        image_file.update_image(image, table, initial_table)

    ## For erasing/reading/writing flash storage partitions

    if args.erase:  # --erase NAME1[,NAME2,...] : Erase partition
        if not image.is_device:
            raise ValueError("--erase requires an esp32 device")
        for name, *_ in args.erase:
            info(f"Erasing partition '{name}'...")
            image_file.erase_part(image, table.by_name(name))

    if args.erase_fs:  # --erase-fs NAME1[,...] : Erase first 4 blocks of parts
        if not image.is_device:
            raise ValueError("--erase-fs requires an esp32 device")
        # Micropython will automatically re-initialise the filesystem on boot.
        for name, *_ in args.erase_fs:
            part = table.by_name(name)
            if part.subtype_name not in ("fat",):
                raise PartitionError(f"partition '{part.name}' is not a fs partition.")
            info(f"Erasing filesystem on partition '{part.name}'...")
            image_file.erase_part(image, part, 4 * B)

    if args.read:  # --read NAME1=FILE1[,...]: Read contents of parts into FILES
        if not image.is_device:
            raise ValueError("--read requires an esp32 device")
        for name, filename in args.read:
            part = table.by_name(name)
            info(f"Saving partition '{name}' into '{filename}'...")
            n = image_file.read_part_to_file(image, part, filename)
            vprint(f"Wrote {n:#x} bytes to '{filename}'.")

    if args.write:  # --write NAME1=FILE1[,...] : Write FILES into partitions
        if not image.is_device:
            raise ValueError("--write requires an esp32 device")
        for name, filename in args.write:
            part = table.by_name(name)
            info(f"Writing partition '{name}' from '{filename}'...")
            n = image_file.write_part_from_file(image, part, filename)
            vprint(f"Wrote {n:#x} bytes to partition '{name}'.")

    if args.bootloader:  # --bootloader FILE: load a new bootloader from FILE
        if not image.is_device:
            raise ValueError("--bootloader requires an esp32 device")
        info(f"Writing bootloader from '{args.bootloader}'...")
        n = image_file.write_bootloader(image, args.bootloader)
        vprint(f"Wrote {n:#x} bytes to bootloader.")

    image.file.close()


def main() -> int:
    colorama_init()
    try:
        process_arguments()
    except (PartitionError, ValueError, FileNotFoundError) as err:
        error(f"{type(err).__name__}: {err}")
        if isinstance(err, PartitionError) and err.table:
            err.table.print()
        if common.debug:
            raise err
        return 1
    return 0


if __name__ == "__main__":
    main()
