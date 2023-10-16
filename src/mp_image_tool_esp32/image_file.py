# MIT License: Copyright (c) 2023 @glenn20

import io
import math
import os
from pathlib import Path

from .common import MB, B, info, warn
from .image_device import Esp32Image, EspDeviceFileWrapper, esp32_device_detect
from .partition_table import BOOTLOADER_OFFSET, IMAGE_OFFSET, Part, PartitionTable

# Fields in the image bootloader header
APP_IMAGE_MAGIC = b"\xe9"  # Starting bytes for firmware files
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
    """Load the bootloader header from the firmware file or serial device  and
    return the `chip_name` and `flash_size`."""
    header: bytes = f.read(HEADER_SIZE)
    if not header.startswith(APP_IMAGE_MAGIC):
        raise ValueError(f"Firmware magic byte ({APP_IMAGE_MAGIC}) not found at byte 0")
    chip_id = header[CHIP_ID_OFFSET] | (header[CHIP_ID_OFFSET + 1] << 8)
    chip_name = CHIP_IDS.get(chip_id, str(chip_id))
    flash_id = header[FLASH_SIZE_OFFSET] >> 4
    flash_size = (2**flash_id) * MB
    return chip_name, flash_size


def set_header_flash_size(header: bytearray | memoryview, flash_size: int = 0) -> None:
    """Set the `flash_size` field in the supplied image bootloader `header`."""
    if flash_size == 0:
        return
    size_MB = flash_size // MB
    if not (0 <= size_MB <= 128):
        raise ValueError(f"Invalid flash size: {flash_size:#x}.")
    # Flash size tag is written into top 4 bits of 4th byte of file
    header[FLASH_SIZE_OFFSET] = (round(math.log2(size_MB)) << 4) | (
        header[FLASH_SIZE_OFFSET] & 0xF
    )


def update_bootloader_header(image: Esp32Image, flash_size: int) -> None:
    """Update the bootloader header with the `flash_size`, if it has changed."""
    f = image.file
    f.seek(image.bootloader_offset)
    header = bytearray(f.read(1 * B))  # Need to write whole blocks
    set_header_flash_size(header, flash_size)
    f.seek(image.bootloader_offset)
    f.write(header)


def open_image_device(filename: str) -> Esp32Image:
    """Open a serial device and return an `Esp32Image` object, which includes a
    File object wrapper around `esptool.py` to read and write to the device."""
    f = EspDeviceFileWrapper(filename)
    detected_chip_name, detected_flash_size = esp32_device_detect(filename)
    bootloader_offset = BOOTLOADER_OFFSETS[detected_chip_name]
    f.seek(bootloader_offset)
    chip_name, flash_size = load_bootloader_header(f)
    f.end = flash_size
    offset = 0  # No offset required for device files
    app_size = 0  # Unknown app size
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
    return Esp32Image(
        f, chip_name, flash_size, app_size, offset, bootloader_offset, True
    )


def open_image_file(filename: str) -> Esp32Image:
    """Open a firmware file and return an `Esp32Image` object, which includes a
    File object for reading from the firmware file."""
    bootloader_offset = 0
    f = open(filename, "r+b")
    f.seek(bootloader_offset)
    chip_name, flash_size = load_bootloader_header(f)
    offset = IMAGE_OFFSETS[chip_name]
    # Get app size from the size of the file. TODO: Should use app_part.offset
    app_size = f.seek(0, 2) - PartitionTable.APP_PART_OFFSET + offset
    f.seek(0)
    return Esp32Image(
        f, chip_name, flash_size, app_size, offset, bootloader_offset, False
    )


def open_esp32_image(filename: str) -> Esp32Image:
    """Open an esp32 firmware file or serial-attached device and
    return an `Esp32Image` object, which includes a `File` object to read and
    write to the device or file. `esptool.py` is used to read and write to
    flash storage on serial-attached devices."""
    if is_device(filename):
        return open_image_device(filename)
    else:
        return open_image_file(filename)


def load_partition_table(image: Esp32Image) -> PartitionTable:
    """Load, check and return a `PartitionTable` from an `ESP32Image` object."""
    fin = image.file
    fin.seek(PartitionTable.PART_TABLE_OFFSET - image.offset)
    data = fin.read(PartitionTable.PART_TABLE_SIZE)
    table = PartitionTable(image.flash_size, image.chip_name)
    table.from_bytes(data)
    table.app_size = image.app_size
    return table


def save_app_image(image: Esp32Image, output: str, table: PartitionTable) -> int:
    """Read the app image from the device and write it to a file."""
    with open(output, "wb") as fout:
        fin = image.file
        fin.seek(table.app_part.offset - image.offset)
        fout.write(fin.read())
        return fout.tell()


def write_table(image: Esp32Image, table: PartitionTable) -> None:
    """Write a new `PartitionTable` to the flash storage or firmware file."""
    f = image.file
    f.seek(table.PART_TABLE_OFFSET - image.offset)
    f.write(table.to_bytes())


def erase_part(image: Esp32Image, part: Part, size: int = 0) -> None:
    """Erase blocks on partition `part`. Erase whole partition if `size`==0."""
    f = image.file
    if isinstance(f, EspDeviceFileWrapper):
        f.erase(part.offset, (size or part.size))
    else:
        f.seek(part.offset - image.offset)
        f.write(b"\xff" * (size or part.size))


def read_part(image: Esp32Image, part: Part, output: str) -> int:
    """Read contents of the `part` partition from `image` into a file"""
    with open(output, "wb") as fout:
        f = image.file
        f.seek(part.offset - image.offset)
        return fout.write(f.read(part.size))


def write_part(image: Esp32Image, part: Part, input: str) -> int:
    """Write contents of `input` file into the `part` partition in `image`."""
    if part.size < os.path.getsize(input):
        raise ValueError(
            f"Partition {part.name} ({part.size} bytes)"
            f" is too small for data ({os.path.getsize(input)} bytes)."
        )
    f = image.file
    f.seek(part.offset - image.offset)
    return f.write(Path(input).read_bytes())


def write_bootloader(image: Esp32Image, input: str) -> int:
    """Write contents of `input` file into the bootloader of `image`."""
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
) -> None:
    """Erase any data partitions in `image` which have been moved or resized
    between `old_table` and `new_table`.

    Also warns if any `"app"` partitions don't start with an app image
    signature."""
    f = image.file
    f.seek(0, 2)
    end_of_file = f.tell()
    oldparts, newparts = (p for p in old_table), (p for p in new_table)
    oldp = next(oldparts)
    for newp in newparts:
        while oldp and oldp.offset < newp.offset:
            oldp = next(oldparts, None)
        if newp.type_name == "data" and oldp != newp and newp.offset < end_of_file:
            info(f"Erasing data partition: {newp.name}...")
            erase_part(image, newp, min(newp.size, 4 * B))
        if newp.type_name == "app" and newp.offset < end_of_file:
            # Check there is an app at the start of the partition
            f.seek(newp.offset - image.offset)
            data: bytes = f.read(1 * B)
            if not data.startswith(APP_IMAGE_MAGIC):
                warn(f"app partition '{newp.name}' does not contain app image.")


def update_image(
    image: Esp32Image,
    table: PartitionTable,
    initial_table: PartitionTable,
) -> None:
    """Update `image` with a new `PartitionTable` from `table`. Will:
    - write the new `table` to `image`
    - update the `flash_size` in the bootloader header (if it has changed) and
    - erase any data partitions which have changed from `initial_table`."""
    info("Writing partition table...")
    write_table(image, table)
    if table.flash_size != image.flash_size:
        info(f"Setting flash_size in bootloader to {table.flash_size//MB}MB...")
        update_bootloader_header(image, table.flash_size)
    update_partitions(image, table, initial_table)
