#!/usr/bin/env python3

# MIT License: Copyright (c) 2023 @glenn20

from __future__ import annotations

import copy
import os
import re
import shutil
from dataclasses import dataclass

from colorama import init as colorama_init

from . import image_device, image_file, layouts, parse_args
from .common import KB, MB, B, print_action, print_error
from .partition_table import NAME_TO_TYPE, PartitionError, PartitionTable

SIZE_UNITS = {"M": MB, "K": KB, "B": B}
debug = False

# Delimiters for splitting up values of command arguments
# First level split is on "," and then on "=" or ":" or "-"
DELIMITERS = [r"\s*,\s*", r"\s*[=:-]\s*"]


# Split arguments into a list of list of strings
# eg: "nvs=7M,factory=2M" -> [["nvs", "7M"], ["factory", "2M"]]
# eg: "nvs=nvs:7M factory-2M" -> [["nvs", nvs, "7M"], ["factory", "2M"]]
def split_values(arg: str) -> list[list[str]]:
    """Break up arg into a list of list of strings."""
    return [re.split(DELIMITERS[1], s) for s in re.split(DELIMITERS[0], arg.strip())]


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


arguments = """
    mp-image-tool-esp32
    Tool for manipulating MicroPython esp32 firmware files and flash storage
    on esp32 devices.

    filename            | the esp32 firmware image filename or serial device
    -o --output         | output filename
    -q --quiet          | mute program output | T
    -n --dummy          | no output file | T
    -d --debug          | print additional info | T
    -x --extract-app    | extract .app-bin from firmware | T
    -f --flash-size SIZE| size of flash for new partition table
    -a --app-size SIZE  | size of factory and ota app partitions
    --from-csv FILE     | load new partition table from CSV file
    --table ota/default/NAME1=SUBTYPE:SIZE[,NAME2,...] \
                        | create new partition table, eg: \
                          "--table ota" (install an OTA-enabled partition table), \
                          "--table default" (default (non-OTA) partition table), \
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


# Static type checking for the return value of argparse.parse_args()
# Must include a field for each argparse option above.
@dataclass
class ProgramArgs:
    filename: str
    output: str
    quiet: bool
    dummy: bool
    debug: bool
    extract_app: bool
    flash_size: str
    app_size: str
    from_csv: str
    table: str
    delete: str
    add: str
    resize: str
    erase: str
    erase_fs: str
    read: str
    write: str
    bootloader: str


def process_arguments(arguments: str) -> None:
    parser = parse_args.parser(arguments)
    # Add static type checking to parser.parse_args() (from argparse).
    args = ProgramArgs(**vars(parser.parse_args()))
    global debug
    debug = args.debug
    image_device.debug = args.debug  # print esptool.py commands and output
    input: str = args.filename  # the input firmware filename
    verbose = not args.quiet  # verbose is True by default
    extension = ""  # Each operation that changes table adds identifier to extension

    # Use u0, a0, and c0 as aliases for /dev/ttyUSB0. /dev/ttyACM0 and COM0
    input = re.sub(r"^u([0-9]+)$", r"/dev/ttyUSB\1", input)
    input = re.sub(r"^a([0-9]+)$", r"/dev/ttyACM\1", input)
    input = re.sub(r"^c([0-9]+)$", r"COM\1", input)

    # Open the input firmware file or esp32 device
    if verbose:
        desc = "esp32 device at" if image_file.is_device(input) else "image file"
        print_action(f"Opening {desc}: {input}...")
    image = image_file.open_image(input)
    table: PartitionTable = image_file.load_partition_table(image)
    if verbose:
        print(f"Chip type: {table.chip_name}")
        print(f"Flash size: {table.flash_size // MB}MB")
        if table.app_size:
            print(
                f"Micropython App size: {table.app_size:#x} bytes "
                f"({table.app_size // KB:,d} KB)"
            )
        layouts.print_table(table)
    copy.copy(image)
    initial_table = copy.copy(table)  # Preserve a deep copy of the original table

    value: str
    # -x --extract-app : Extract the micropython app image from the firmware file
    if args.extract_app:
        basename: str = os.path.basename(input)
        output = basename[:-4] if basename.endswith(".bin") else basename
        output += ".app-bin"
        if verbose:
            print_action(f"Writing micropython app image file: {output}...")
        image_file.save_app_image(image, output, table)

    ## Commands to modify the partition table

    # -f --flash-size SIZE : Set the size of the flash storage
    if value := args.flash_size:
        flash_size = numeric_arg(value)
        if flash_size and flash_size != table.flash_size:
            table.flash_size = flash_size
        extension += f"-{flash_size // MB}MB"

    # --from-csv FILE : Replace partition table with one loaded from CSV file.
    if value := args.from_csv:
        table.from_csv(value)
        extension += "-CSV"

    # --table nvs=7B,factory=2M,vfs=0
    if value := args.table:
        if value == "ota":
            value = layouts.make_ota_layout(table)
            extension += "-OTA"
        elif value == "default":
            value = layouts.DEFAULT_TABLE_LAYOUT
            extension += "-DEFAULT"
        else:
            extension += "-TABLE"
        # Break up the value string into a partition table layout
        layout = (
            (name, (subtype or [""])[0], numeric_arg(size))
            for (name, *subtype, size) in split_values(value)
        )
        table = layouts.new_table(table, layout)
        table.check()

    # -a --app-size SIZE : Resize all the APP partitions
    if value := args.app_size:
        app_part_size = numeric_arg(value)
        app_parts = filter(lambda p: p.type == NAME_TO_TYPE["app"], table)
        for p in app_parts:
            table.resize_part(p.name, app_part_size)
        extension += f"-APP={value}"

    # --delete name1[,name2,..] : Delete a partition from table
    if value := args.delete:
        for name, *_ in split_values(value):
            table.remove(table[name])
        extension += f"-delete={value}"

    # --add NAME1=SUBTYPE:OFFSET:SIZE[,NAME2=..] : Add a new partition to table
    if value := args.add:
        for name, subtype, header_offset, size in split_values(value):
            table.add_part(name, subtype, numeric_arg(size), numeric_arg(header_offset))
        extension += f"-add={value}"

    # --resize NAME1=SIZE[,NAME2=...] : Resize partitions
    if value := args.resize:
        for name, size in split_values(value):
            new_size = table.resize_part(name, numeric_arg(size))
            print_action(f"Resizing {name} partition to {new_size:#x} bytes...")
        table.check()
        extension += f"-{value}"

    ## Write the modified partition table to a new file or flash storage on device

    if not args.dummy and extension:
        # Write the new partition table to the ESP32 device
        if initial_table.app_part.offset != table.app_part.offset:
            raise PartitionError("first app partition offset has changed", table)
        # Make a copy of the firmware file with new partition table
        output = args.output
        if image.is_device:
            output = input  # Write table back to esp32 device flash storage.
        if not output:
            basename: str = os.path.basename(input)
            name, *suffix = basename.rsplit(".", 1)
            output = f"{name}{extension}.{(suffix or ['bin'])[0]}"
        if verbose:
            what = f"{image.chip_name} device" if image.is_device else "firmware file"
            print_action(f"Writing to {what}: {output}...")
            layouts.print_table(table)
        if not image.is_device:  # If input is a firmware file, make a copy and open it
            shutil.copy(input, output)
            image.file.close()
            image = image_file.open_image(output)
        # Write the new values to the firmware...
        image_file.update_image(image, table, initial_table, verbose)

    # For erasing/reading/writing flash storage partitions

    # --erase NAME1[,NAME2,...] : Erase the partitions on the flash storage
    if value := args.erase:
        if not image.is_device:
            raise ValueError("--erase requires an esp32 device")
        for name, *_ in split_values(value):
            if verbose:
                print_action(f"Erasing partition '{name}'...")
            if not args.dummy:
                image_file.erase_part(image, table[name])

    # --erase-fs NAME1[,NAME2,...] : Erase the first 4 blocks of partitions
    # Micropython will automatically re-initialise the filesystem on boot.
    if value := args.erase_fs:
        if not image.is_device:
            raise ValueError("--erase-fs requires an esp32 device")
        for name, *_ in split_values(value):
            part = table[name]
            if part.subtype_name not in ("fat",):
                raise PartitionError(f"partition '{part.name}' is not a fs partition.")
            print_action(f"Erasing filesystem on partition '{part.name}'...")
            if not args.dummy:
                image_file.erase_part(image, part, 4 * B)

    # --read NAME1=FILE1[,NAME2=...] : Read contents of partition NAME1 into FILE
    if value := args.read:
        if not image.is_device:
            raise ValueError("--read requires an esp32 device")
        for name, filename in split_values(value):
            part = table[name]
            if verbose:
                print_action(f"Saving partition '{name}' into '{filename}'...")
            if not args.dummy:
                n = image_file.read_part(image, part, filename)
                if verbose:
                    print(f"Wrote {n:#x} bytes to '{filename}'.")

    # --write NAME1=FILE1[,NAME2=...] : Write contents of FILE into partition NAME1
    if value := args.write:
        if not image.is_device:
            raise ValueError("--write requires an esp32 device")
        for name, filename in split_values(value):
            part = table[name]
            if verbose:
                print_action(f"Writing partition '{name}' from '{filename}'...")
            if not args.dummy:
                n = image_file.write_part(image, part, filename)
                if verbose:
                    print(f"Wrote {n:#x} bytes to partition '{name}'.")

    # --bootloader FILE: load a new bootloader from FILE
    if value := args.bootloader:
        if not image.is_device:
            raise ValueError("--write requires an esp32 device")
        if verbose:
            print_action(f"Writing bootloader from '{value}'...")
        if not args.dummy:
            n = image_file.write_bootloader(image, value)
            if verbose:
                print(f"Wrote {n:#x} bytes to bootloader.")


def main() -> int:
    colorama_init()
    try:
        process_arguments(arguments)
    except (PartitionError, ValueError, FileNotFoundError) as err:
        print_error(f"{type(err).__name__}: {err}")
        if isinstance(err, PartitionError) and err.table:
            err.table.print()
        if debug:
            raise err
        return 1
    return 0


if __name__ == "__main__":
    main()
