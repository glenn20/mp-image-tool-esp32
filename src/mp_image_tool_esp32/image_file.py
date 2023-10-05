# MIT License: Copyright (c) 2023 @glenn20

from __future__ import annotations

import math
from contextlib import contextmanager
from typing import Generator

from .image_device import Esp32Image, open_image_device
from .partition_table import PartitionTable

MB = 0x100_000  # 1 megabyte
KB = 0x400  # 1 kilobyte

# Fields in the image header
HEADER_SIZE = 8 + 16  # Size of the image file headers
FLASH_SIZE_OFFSET = 3  # Flash size is in high 4 bits of byte 3 in file
CHIP_ID_OFFSET = 12  # Chip-type is in bytes 12 and 13 of file

APP_IMAGE_MAGIC = b"\xe9"  # Starting bytes for firmware files
IMAGE_OFFSET = 0x1000  # Offset in flash to write firmware (set to 0 on S3 and C2)

# Map from chip ids in the image file header to esp32 chip names.
CHIP_IDS = {
    0: "esp32",
    2: "esp32s2",
    9: "esp32s3",
    12: "esp32c2",
    5: "esp32c3",
    13: "esp32c6",
}


def is_device(filename: str) -> bool:
    return filename.startswith("/dev/") or filename.startswith("COM")


# Get the chip type name, flash size and image file offset from the image file
# header:
# - chip_type: "esp32", "esp32s2", "esp32s3", "esp32c2" or "esp32c6"
# - flash_size: 4*MB, 8*MB, 16*MB, 32*MB, 64*MB or 128*MB
# - offset:
#   - 0x1000 (if esp32 or esp32s2)
#   - 0 (if esp32s3 or esp32c2)
def open_image_file(filename: str) -> Esp32Image:
    f = open(filename, "rb")
    header = f.read(HEADER_SIZE)
    if header[: len(APP_IMAGE_MAGIC)] != APP_IMAGE_MAGIC:
        raise ValueError(f"Firmware magic byte ({APP_IMAGE_MAGIC}) not found at byte 0")
    flash_id = header[FLASH_SIZE_OFFSET] >> 4
    flash_size = (2**flash_id) * MB
    chip_id = header[CHIP_ID_OFFSET] | (header[CHIP_ID_OFFSET + 1] << 8)
    chip_name = CHIP_IDS.get(chip_id, str(chip_id))
    # S3 and C2 image files are written to flash starting at offset 0
    offset = 0 if chip_name in ("esp32s3", "esp32c3") else IMAGE_OFFSET
    # Get app size from the size of the file. TODO: Should use app_part.offset
    app_size = f.seek(0, 2) - PartitionTable.APP_PART_OFFSET + offset
    f.seek(0)
    return Esp32Image(f, chip_name, flash_size, offset, app_size)


@contextmanager
def open_image(filename: str) -> Generator[Esp32Image, None, None]:
    openfun = open_image_device if is_device(filename) else open_image_file
    image: Esp32Image | None = None
    try:
        yield (image := openfun(filename))
    finally:
        if image:
            image.file.close()


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


# Load an image file and check the partition table
def load_partition_table(filename: str) -> PartitionTable:
    with open_image(filename) as image:
        fin = image.file
        fin.seek(PartitionTable.PART_TABLE_OFFSET - image.offset)
        data = fin.read(PartitionTable.PART_TABLE_SIZE)
        table = PartitionTable(image.flash_size, image.chip_name)
        table.from_bytes(data)
        table.app_size = image.app_size
    return table


def save_app_image(input: str, output: str, table: PartitionTable) -> int:
    with open_image(input) as image, open(output, "wb") as fout:
        fin = image.file
        fin.seek(table.app_part.offset - image.offset)
        fout.write(fin.read())
        return fout.tell()


def copy_with_new_table(input: str, output: str, table: PartitionTable) -> int:
    with open_image(input) as image, open(output, "wb") as fout:
        fin = image.file
        header = bytearray(fin.read(HEADER_SIZE))
        # Update the flash size in the image file header
        set_header_flash_size(header, table.flash_size)
        # Write header of new image file
        fout.write(header)
        assert fin.tell() == fout.tell()
        # Copy the bootloader section from input to output
        fout.write(fin.read(table.PART_TABLE_OFFSET - image.offset - len(header)))
        assert fin.tell() == fout.tell()
        # Write the new partition table to the output
        fout.write(table.to_bytes())
        fin.seek(table.PART_TABLE_SIZE, 1)
        assert fin.tell() == fout.tell()
        # Copy the initial data partitions from input to output (should be empty)
        fout.write(fin.read(table.app_part.offset - table.FIRST_PART_OFFSET))
        assert fin.tell() == fout.tell()
        # Copy the app image from the input to the output
        size = table.app_size or table.app_part.size
        while size > 0 and (n := fout.write(fin.read(size))):
            size -= n
        assert fin.tell() == fout.tell()
        return fout.tell()
