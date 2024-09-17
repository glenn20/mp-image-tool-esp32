#!/usr/bin/env python3
# MIT License: Copyright (c) 2023 @glenn20
"""Main program module for mp-image-tool-esp32: a tool for manipulating ESP32
firmware files and flash storage on ESP32 devices.

After importing, call `main.main()` to execute the program.

Dependencies:
- `esptool.py` for access to flash storage on serial-attached ESP32 devices.
"""

from __future__ import annotations

import argparse
import copy
import logging
import os
import platform
import re
import shutil
import sys
from pathlib import Path
from typing import List, Sequence

from . import __version__, layouts, logger, ota_update
from .argparse_typed import parser as typed_parser
from .argtypes import MB, ArgList, B, IntArg, PartList
from .firmware import Firmware
from .lfs import lfs_cmd
from .partition_table import PartitionError, PartitionTable

log = logger.getLogger(__name__)


# `TypedNamespace` and the `usage` string together provide three things:
# 1. static type checking for the fields in the namespace returned by
#    `argparse.parse_args()`.
# 2. *automatic* conversion of string arguments to the correct type (using the
#    `type=` keyword of `argparse.add_argument()`).
# 3. an overly-elaborate method for avoiding the boilerplate of
#    `argparse.add_argument()` which also makes the command usage easier
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
    log: str
    no_reset: bool
    check_app: bool
    extract_app: bool
    flash_size: IntArg
    app_size: IntArg
    method: str
    no_rollback: bool
    ota_update: str
    baud: IntArg
    from_csv: str
    table: PartList
    delete: ArgList
    add: PartList
    resize: PartList
    erase: ArgList
    erase_fs: ArgList
    read: ArgList
    write: ArgList
    flash: str
    trim: bool
    trimblocks: bool
    fs: List[List[str]]
    _globals = globals()  # Used to access the module's global variables.


# Remember to add any new arguments here to TypedNamespace above as well.
# The argparse.add_argument() boilerplate is parsed from this string
usage = """
    mp-image-tool-esp32

    Tool for manipulating MicroPython esp32 firmware files and flash storage
    on esp32 devices.

    filename            | the esp32 firmware filename or serial device
    -o --output FILE    | output firmware filename (auto-generated if not given)
    -q --quiet          | set debug level to ERROR (default: INFO)
    -n --no-reset       | leave device in bootloader mode afterward
    -x --extract-app    | extract .app-bin from firmware
    -f --flash-size SIZE| change the expected flash size programmed into the \
                          firmware bootloader
    -a --app-size SIZE  | size of factory and ota app partitions
    -m --method METHOD  | esptool method: subprocess, command or direct (default)
    -d --debug          | set debug level to DEBUG (default: INFO)
    --log NAME=LEVEL[,NAME=LEVEL,...] \
                        | set the log level for the named loggers.
    --check-app         | check app partitions and OTA config are valid
    --no-rollback       | disable app rollback after OTA update
    --baud RATE         | baud rate for serial port (default: 921600)
    --ota-update FILE   | perform an OTA firmware upgrade over the serial port
    --from-csv FILE     | load new partition table from CSV file
    --table ota/default/original/NAME1=SUBTYPE:SIZE[,NAME2,...] \
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
    --erase NAME1[,NAME2] | erase the named partitions
    --erase-fs NAME1[,NAME2] \
                        | erase first 4 blocks of a partition on flash storage.\
                            Micropython will initialise filesystem on next boot.
    --read NAME1=FILE1[,NAME2=FILE2,bootloader=FILE,...] \
                        | copy partition contents (or bootloader) to file. \
                          Use --trimblocks or --trim to remove trailing blank blocks.
    --write NAME1=FILE1[,NAME2=FILE2,bootloader=FILE,...] \
                        | write file(s) contents into partitions \
                            (or bootloader) in the firmware.
    --flash DEVICE      | flash new firmware to the serial-attached device.
    --trimblocks        | Remove trailing blank blocks from data returned by \
                          --read and --extract-app. This is useful for reading \
                          app images and filesystems from flash storage.
    --trim              | Like --trimblocks, but trims to 16-byte boundary. This \
                          is appropriate for reading app images from flash \
                          storage.
    --fs CMD ARG1 ARG2 ... | Operate on files in the `vfs` or other filesystem \
                          partitions. | A

    Where SIZE is a decimal or hex number with an optional suffix (M=megabytes,
    K=kilobytes, B=blocks (0x1000=4096 bytes)).

    --fs commands include: ls, get, put, mkdir, rm, rename, cat, info, mkfs,
    df, grow and more.

    Options --erase-fs and --ota-update can only be used when operating on
    serial-attached devices (not firmware files).

    If the --flash option is provided, the firmware (including any changes
    made) will be flashed to the device, eg:

       `mp-image-tool-esp32 firmware.bin --flash u0`

    is a convenient way to flash firmware to a device.
"""


def expand_device_short_names(name: str) -> str:
    """Expand short device names to full device names."""
    name = re.sub(r"^u([0-9]+)$", r"/dev/ttyUSB\1", name)
    name = re.sub(r"^a([0-9]+)$", r"/dev/ttyACM\1", name)
    name = re.sub(r"^c([0-9]+)$", r"COM\1", name)
    return name


def run_commands(argv: Sequence[str] | None = None) -> None:
    namespace = TypedNamespace()
    parser = typed_parser(usage, namespace)
    args = parser.parse_args(args=argv, namespace=namespace)
    progname = os.path.basename(sys.argv[0])

    logging.basicConfig(
        format=logger.FORMAT,
        handlers=[logger.richhandler],
        level=(
            logging.ERROR
            if args.quiet
            else logging.DEBUG if args.debug else logging.INFO
        ),
    )
    if args.log:
        logger.set_logging(args.log)

    log.action(
        f"Running {progname} v{__version__} (Python {platform.python_version()})."
    )

    ## Open the firmware file or esp32 device

    # Use u0, a0, and c0 as aliases for /dev/ttyUSB0. /dev/ttyACM0 and COM0
    filename: str = args.filename  # the input firmware filename
    input: str = expand_device_short_names(filename)
    basename: str = os.path.basename(input)
    log.action(f"Opening {input}...")
    firmware: Firmware = Firmware(
        input,
        args.baud,
        reset_on_close=not args.no_reset,
        esptool_method=args.method,
    )
    input_type: str = "device" if firmware.is_device else "firmware file"
    log.info(
        f"Found {firmware.header.chip_name} {input_type} "
        f"({firmware.header.flash_size // MB}MB flash)."
    )
    app_size = 0
    if not firmware.is_device:
        app_size = firmware.file.seek(0, 2) - firmware.table.app_part.offset
        firmware.file.seek(firmware.bootloader)
    if log.isEnabledFor(logging.INFO):
        layouts.print_partition_table(firmware.table, app_size)
        if firmware.is_device and not args.fs:
            lfs_cmd(firmware, "df")  # Display filesystem usage information

    ## Process requested changes to the firmware file (esp. partition table)

    # Make a copy of the partition table and image header for modification
    new_table: PartitionTable = copy.copy(firmware.table)
    new_header = firmware.file.header.copy()
    extension = ""  # Each op that changes table adds identifier to extension

    if args.extract_app:  # -x --extract-app : Extract app image from firmware
        output = args.output or re.sub(r"(.bin)?$", ".app-bin", basename, 1)
        log.action(f"Writing micropython app image file: {output}...")
        firmware.save_app_image(output)
        firmware.file.close()
        return

    if args.flash_size:  # -f --flash-size SIZE : Set size of the flash storage
        max_flash_size = getattr(firmware.file, "flash_size", 1024 * MB)
        if args.flash_size > max_flash_size:
            raise ValueError(
                "Selected flash size is larger than device flash size "
                f"({args.flash_size // MB}MB > {max_flash_size // MB}MB).",
            )
        if args.flash_size != new_header.flash_size:
            new_table.max_size = args.flash_size
            new_header.flash_size = args.flash_size
            assert new_header.ismodified(), "Image header not modified!"
        extension += f"-{args.flash_size // MB}MB"

    if args.from_csv:  # --from-csv FILE : Replace part table from CSV file.
        new_table = layouts.from_csv(new_table, args.from_csv)
        extension += "-CSV"

    if args.table:  # --table default|ota|nvs=7B,factory=2M,vfs=0
        if str(args.table) == "ota":
            # ota_layout returns a string, so parse it into a PartList
            args.table = PartList(layouts.ota_layout(new_table, args.app_size))
            extension += "-OTA"
        elif str(args.table) == "default":
            # DEFAULT_TABLE_LAYOUT is a string, so parse it into a PartList
            args.table = PartList(layouts.DEFAULT_TABLE_LAYOUT)
            extension += "-DEFAULT"
        elif str(args.table) == "original":
            # DEFAULT_TABLE_LAYOUT is a string, so parse it into a PartList
            args.table = PartList(layouts.ORIGINAL_TABLE_LAYOUT)
            extension += "-ORIGINAL"
        else:
            extension += "-TABLE"
        # Build a partition table from the PartList
        new_table = layouts.new_table(new_table, args.table, app_size)
        new_table.check()

    if args.app_size:  # -a --app-size SIZE : Resize all the APP partitions
        app_parts = filter(lambda p: p.type == new_table.APP_TYPE, new_table)
        for e in app_parts:
            new_table.resize_part(e.name, args.app_size)
        extension += f"-appsize={args.app_size // B}B"

    if args.delete:  # --delete name1[,name2,..] : Delete partition from table
        for name, *_ in args.delete:
            new_table.remove(new_table.by_name(name))
        extension += f"-delete={args.delete}"

    if args.resize:  # --resize NAME1=SIZE[,NAME2=...] : Resize partitions
        for name, *_, new_size in args.resize:
            log.action(f"Resizing {name} partition to {new_size:#x} bytes...")
            new_table.resize_part(name, new_size)
        new_table.check()
        extension += f"-resize={args.resize}"

    if args.add:  # --add NAME1=SUBTYPE:OFFSET:SIZE[,..] : Add new partitions
        for name, subtype, offset, size in args.add:
            subtype = layouts.get_subtype(name, subtype)
            new_table.add_part(name, subtype, size, offset)
        extension += f"-add={args.add}"

    ## We have performed all the changes to the partition table...
    ## Write modified partition table to a new file or back to flash storage

    if args.erase and not firmware.is_device:
        extension += f"-erase={args.erase}"
    if args.write and not firmware.is_device:
        extension += f"-write={args.write}"

    if extension or args.output:  # A change has been made to the partition table
        if new_table.app_part.offset != firmware.table.app_part.offset:
            raise PartitionError("first app partition offset has changed", new_table)
        if log.isEnabledFor(logging.INFO):
            layouts.print_partition_table(new_table, app_size)
        if not firmware.is_device:  # If input is a firmware file, make a copy
            # Make a copy of the firmware file and open the new firmware...
            output_filename = args.output or re.sub(
                r"([.][^.]+)?$", f"{extension}\\1", basename, 1
            )
            firmware.file.close()
            shutil.copy(input, output_filename)
            firmware = Firmware(output_filename)

        # Update the firmware with the new partition table and bootloader header...
        log.action(
            f"Writing to {firmware.header.chip_name} {input_type}: {firmware.filename}..."
        )
        firmware.update_image(new_table, new_header)

    ## For erasing/reading/writing flash storage partitions

    if args.erase:  # --erase NAME1[,NAME2,...] : Erase partition
        for name, *_ in args.erase:
            log.action(f"Erasing partition '{name}'...")
            with firmware.partition(name) as p:
                p.truncate()

    if args.erase_fs:  # --erase-fs NAME1[,...] : Erase first 4 blocks of parts
        if not firmware.is_device:
            raise ValueError("--erase-fs requires an esp32 device")
        # Micropython will automatically re-initialise the filesystem on boot.
        for name, *_ in args.erase_fs:
            part = firmware.table.by_name(name)
            if part.subtype_name not in ("fat",):
                raise PartitionError(f"partition '{part.name}' is not a fs partition.")
            log.action(f"Erasing filesystem on partition '{part.name}'...")
            with firmware.partition(part) as p:
                p.erase(4 * 0x1000)

    if args.read:  # --read NAME1=FILE1[,...]: Read contents of parts into FILES
        for name, filename in args.read:
            log.action(f"Saving partition '{name}' into '{filename}'...")
            data = firmware.partition(name).read()
            if args.trimblocks:  # Trim trailing blank 4096-byte blocks from data
                data = firmware.trimblocks(data)
            if args.trim:  # Trim trailing blank 16-byte blocks from data
                data = firmware.trimblocks(data, 16)
            n = Path(filename).write_bytes(data)
            log.info(f"Wrote {n:,} bytes to '{filename}'.")

    if args.write:  # --write NAME1=FILE1[,...] : Write FILES into partitions
        for name, filename in args.write:
            log.action(f"Writing partition '{name}' from '{filename}'...")
            data = Path(filename).read_bytes()
            with firmware.partition(name) as p:
                if p.part.type_name == "app" and not firmware.check_app_image_header(
                    data, p.part.name
                ):
                    raise ValueError(
                        f"Attempt to write invalid app image to '{p.part.name}'."
                    )
                n = p.write(data)
                p.truncate()
            log.info(f"Wrote {n:#x} bytes to partition '{name}'.")

    if args.ota_update:  # --ota-update FILE : Perform an OTA firmware upgrade
        if not firmware.is_device:
            raise ValueError("--ota-update requires an esp32 device")
        log.action(f"Performing OTA firmware upgrade from '{args.ota_update}'...")
        ota_update.ota_update(firmware, args.ota_update, args.no_rollback)

    if args.check_app:  # --check-app : Check the partition table and app images
        firmware.check_app_partitions(firmware.table, check_hash=True)
        try:
            ota = ota_update.OTAUpdater(firmware)
            log.info(f"Current OTA boot partition: {ota.current().name}")
            log.info(f"Next OTA boot partition: {ota.get_next_update().name}")
        except PartitionError:
            pass  # No OTA partitions

    if args.fs:  # --fs CMD NAME1[,NAME2,...] : Perform a filesystem command
        # Process any littlefs filesystem commands
        for command, *fs_args in args.fs:
            lfs_cmd(firmware, command, fs_args)

    if args.flash:  # --flash DEVICE : Flash firmware to the device
        filename = expand_device_short_names(args.flash)
        device = None
        log.action(f"Opening device '{filename}' for flashing...")
        try:
            device = Firmware(
                filename,
                args.baud,
                reset_on_close=not args.no_reset,
                esptool_method=args.method,
                check=False,  # Bootloader on device may be missing or broken
            )
            if not device.is_device:
                raise ValueError("Flashing requires a device, not a firmware file.")
            log.info(
                f"Found {device.header.chip_name} device "
                f"({device.header.flash_size // MB}MB flash)."
            )
            log.action(f"Flashing firmware to device: {filename}...")
            device.write_firmware(firmware)
        finally:
            if device:
                device.file.close()

    firmware.file.close()


def main(argv: Sequence[str] | None = None) -> int:
    try:
        log.setLevel("DEBUG" if "-d" in sys.argv or "--debug" in sys.argv else "INFO")
        run_commands(argv)
    except (KeyboardInterrupt, Exception) as err:
        if not log.isEnabledFor(logging.DEBUG):
            log.error(f"{type(err).__name__}: {err}")  # Just log the error
        else:
            log.exception("Error:")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
