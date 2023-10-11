# MIT License: Copyright (c) 2023 @glenn20

from __future__ import annotations

import io
import math
import os
from pathlib import Path

from .common import APP_IMAGE_MAGIC, MB, B, print_action
from .image_device import Esp32Image, EspDeviceFileWrapper, image_device_detect
from .partition_table import BOOTLOADER_OFFSET, IMAGE_OFFSET, Part, PartitionTable

# Fields in the image header
HEADER_SIZE = 8 + 16  # Size of the image file headers
FLASH_SIZE_OFFSET = 3  # Flash size is in high 4 bits of byte 3 in file
CHIP_ID_OFFSET = 12  # Chip-type is in bytes 12 and 13 of file
CHIP_IDS = {  # Map from chip ids in the image file header to esp32 chip names.
    0: "esp32",
    2: "esp32s2",
    9: "esp32s3",
    12: "esp32c2",
    5: "esp32c3",
    13: "esp32c6",
}
IMAGE_OFFSETS = {
    "esp32": IMAGE_OFFSET,  # 0x1000 bytes
    "esp32s2": IMAGE_OFFSET,  # 0x1000 bytes
    "esp32s3": 0,
    "esp32c2": 0,
    "esp32c3": 0,
    "esp32c6": 0,
}
BOOTLOADER_OFFSETS = {
    "esp32": BOOTLOADER_OFFSET,  # 0x1000 bytes
    "esp32s2": BOOTLOADER_OFFSET,  # 0x1000 bytes
    "esp32s3": 0,
    "esp32c2": 0,
    "esp32c3": 0,
    "esp32c6": 0,
}


def is_device(filename: str) -> bool:
    return filename.startswith("/dev/") or filename.startswith("COM")


def load_bootloader_header(f: io.IOBase) -> tuple[str, int]:
    header = f.read(HEADER_SIZE)
    if not header.startswith(APP_IMAGE_MAGIC):
        raise ValueError(f"Firmware magic byte ({APP_IMAGE_MAGIC}) not found at byte 0")
    chip_id = header[CHIP_ID_OFFSET] | (header[CHIP_ID_OFFSET + 1] << 8)
    chip_name = CHIP_IDS.get(chip_id, str(chip_id))
    flash_id = header[FLASH_SIZE_OFFSET] >> 4
    flash_size = (2**flash_id) * MB
    return chip_name, flash_size


# Set the flash size in the supplied image file header
def set_header_flash_size(header: bytearray | memoryview, flash_size: int = 0) -> None:
    if flash_size == 0:
        return
    size_MB = flash_size // MB
    if not (0 <= size_MB <= 128):
        raise ValueError(f"Invalid flash size: {flash_size:#x}.")
    # Flash size tag is written into top 4 bits of 4th byte of file
    header[FLASH_SIZE_OFFSET] = (round(math.log2(size_MB)) << 4) | (
        header[FLASH_SIZE_OFFSET] & 0xF
    )


# Update the bootloader header with the flash_size, if it has changed.
def update_bootloader_header(image: Esp32Image, flash_size: int) -> None:
    f = image.file
    f.seek(image.bootloader_offset)
    header = bytearray(f.read(1 * B))  # Need to write whole blocks
    set_header_flash_size(header, flash_size)
    f.seek(image.bootloader_offset)
    f.write(header)


def open_image(filename: str) -> Esp32Image:
    if is_device(filename):
        f = EspDeviceFileWrapper(filename)
    else:
        f = open(filename, "r+b")
    detected_chip_name, detected_flash_size, bootloader_offset = "", 0, 0
    if is_device(filename):
        detected_chip_name, detected_flash_size = image_device_detect(filename)
        bootloader_offset = BOOTLOADER_OFFSETS[detected_chip_name]
    f.seek(bootloader_offset)
    chip_name, flash_size = load_bootloader_header(f)
    if isinstance(f, EspDeviceFileWrapper):
        if detected_chip_name and detected_chip_name != chip_name:
            print(
                f"Warning: Detected chip ({detected_chip_name})"
                f" is different from bootloader ({chip_name})."
            )
        if detected_flash_size and detected_flash_size != flash_size:
            print(
                f"Warning: Detected flash size ({detected_flash_size // MB}MB)"
                f" is different from bootloader ({flash_size // MB}MB)."
            )
        f.end = flash_size
        offset = 0  # No offset required for device files
        app_size = 0  # Unknown app size
    else:
        offset = IMAGE_OFFSETS[chip_name]
        # Get app size from the size of the file. TODO: Should use app_part.offset
        app_size = f.seek(0, 2) - PartitionTable.APP_PART_OFFSET + offset
    f.seek(0)
    return Esp32Image(
        f,
        chip_name,
        flash_size,
        app_size,
        offset,
        bootloader_offset,
        is_device(filename),
    )


# Load an image file and check the partition table
def load_partition_table(image: Esp32Image) -> PartitionTable:
    fin = image.file
    fin.seek(PartitionTable.PART_TABLE_OFFSET - image.offset)
    data = fin.read(PartitionTable.PART_TABLE_SIZE)
    table = PartitionTable(image.flash_size, image.chip_name)
    table.from_bytes(data)
    table.app_size = image.app_size
    return table


def save_app_image(image: Esp32Image, output: str, table: PartitionTable) -> int:
    with open(output, "wb") as fout:
        fin = image.file
        fin.seek(table.app_part.offset - image.offset)
        fout.write(fin.read())
        return fout.tell()


# Write changes to the flash storage on the device
def write_table(image: Esp32Image, table: PartitionTable) -> None:
    f = image.file
    f.seek(table.PART_TABLE_OFFSET - image.offset)
    f.write(table.to_bytes())


# Erase blocks on a partition. Erase whole partition if size == 0
def erase_part(image: Esp32Image, part: Part, size: int = 0) -> None:
    f = image.file
    if isinstance(f, EspDeviceFileWrapper):
        f.erase(part.offset, part.size)
    else:
        f.seek(part.offset - image.offset)
        f.write(b"\xff" * (size or part.size))


# Read a partition from device into a file
def read_part(image: Esp32Image, part: Part, output: str) -> int:
    with open(output, "wb") as fout:
        f = image.file
        f.seek(part.offset - image.offset)
        return fout.write(f.read(part.size))


# Write data from a file to a partition on device
def write_part(image: Esp32Image, part: Part, input: str) -> int:
    if part.size < os.path.getsize(input):
        raise ValueError(
            f"Partition {part.name} ({part.size} bytes)"
            f" is too small for data ({os.path.getsize(input)} bytes)."
        )
    f = image.file
    f.seek(part.offset - image.offset)
    return f.write(Path(input).read_bytes())


# Write data from a file to a partition on device
def write_bootloader(image: Esp32Image, input: str) -> int:
    size, max_size = os.path.getsize(input), PartitionTable.BOOTLOADER_SIZE
    if max_size < size:
        raise ValueError(
            f"File ({size} bytes) is too big for bootloader ({max_size} bytes)."
        )
    f = image.file
    f.seek(image.bootloader_offset)
    return f.write(Path(input).read_bytes())


def update_partitions(
    image: Esp32Image,
    new_table: PartitionTable,
    old_table: PartitionTable,
    verbose: bool = True,
) -> None:
    # Erase any data partitions which have been moved or resized
    oldparts, newparts = (p for p in old_table), (p for p in new_table)
    oldp = next(oldparts)
    f = image.file
    f.seek(0, 2)
    end_of_file = f.tell()
    for newp in newparts:
        while oldp and oldp.offset < newp.offset:
            oldp = next(oldparts, None)
        if newp.type_name == "data" and oldp != newp and newp.offset < end_of_file:
            if verbose:
                print_action(f"Erasing data partition: {newp.name}...")
            erase_part(image, newp, min(newp.size, 4 * B))
        if newp.type_name == "app" and newp.offset < end_of_file:
            # Check there is an app at the start of the partition
            f.seek(newp.offset - image.offset)
            data: bytes = f.read(1 * B)
            if not data.startswith(APP_IMAGE_MAGIC):
                print(
                    f"Warning: app partition '{newp.name}' "
                    f"does not contain app image."
                )


def update_image(
    image: Esp32Image,
    table: PartitionTable,
    initial_table: PartitionTable,
    verbose: bool = True,
) -> None:
    if verbose:
        print_action("Writing partition table...")
    write_table(image, table)
    if table.flash_size != image.flash_size:
        if verbose:
            print_action(f"Writing flash_size={table.flash_size} to bootloader...")
        update_bootloader_header(image, table.flash_size)
    update_partitions(image, table, initial_table, verbose)
