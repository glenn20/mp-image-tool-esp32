from __future__ import annotations

import math
from functools import cached_property
from typing import BinaryIO

MB = 0x100_000  # 1 Megabyte

BLOCKSIZE = (
    0x1_000  # Default block size for erasing/writing regions of the flash storage
)

# Fields in the image bootloader header
BOOTLOADER_OFFSET = {
    "esp32": 0x1_000,  # 0x1000 bytes
    "esp32s2": 0x1_000,  # 0x1000 bytes
    "esp32s3": 0,
    "esp32c2": 0,
    "esp32c3": 0,
    "esp32c6": 0,
    "esp32h2": 0,
}


class ImageHeader:
    """A class to represent the esp32 firmware image format. Provides methods to
    read and write the image header."""

    # See https://docs.espressif.com/projects/esptool/en/latest/esp32
    # /advanced-topics/firmware-image-format.html

    HEADER_SIZE = 8 + 16  # Size of the image file headers
    APP_IMAGE_MAGIC = b"\xe9"  # Starting bytes for firmware files
    MAGIC_OFFSET = 0  # Offset of the magic byte in the image file
    NUM_SEGMENTS_OFFSET = 1  # Number of segments in the image file
    FLASH_SIZE_OFFSET = 3  # Flash size is in high 4 bits of byte 3 in file
    CHIP_ID_OFFSET = 12  # Chip-type is in bytes 12 and 13 of file
    HASH_APPENDED_OFFSET = 23  # Offset of flag that hash is appended to end of image
    CHIP_IDS = {  # Map from chip ids in the image file header to esp32 chip names.
        0: "esp32",
        2: "esp32s2",
        9: "esp32s3",
        12: "esp32c2",
        5: "esp32c3",
        13: "esp32c6",
        16: "esp32h2",
    }
    data: bytes

    def __init__(self, data: bytes) -> None:
        self.data = data
        if not self.data[self.MAGIC_OFFSET] == self.APP_IMAGE_MAGIC[0]:
            raise ValueError("Invalid image file: magic bytes not found.")

    @cached_property
    def chip_name(self) -> str:
        """Return the chip name from the bootloader header."""
        chip_id = self.data[self.CHIP_ID_OFFSET] | (
            self.data[self.CHIP_ID_OFFSET + 1] << 8
        )
        return self.CHIP_IDS.get(chip_id, str(chip_id))

    @cached_property
    def flash_size(self) -> int:
        """Return the flash size from the bootloader header."""
        flash_id = self.data[self.FLASH_SIZE_OFFSET] >> 4
        return (2**flash_id) * MB

    @cached_property
    def hash_appended(self) -> bool:
        """Return True if the image has a SHA256 hash appended."""
        return self.data[self.HASH_APPENDED_OFFSET] == 1

    @cached_property
    def num_segments(self) -> int:
        """Return the number of segments in this image."""
        return self.data[self.NUM_SEGMENTS_OFFSET]

    def copy(self, flash_size: int = 0) -> ImageHeader:
        """Return a new bootloader header with the `flash_size` updated."""
        if flash_size == 0:
            return ImageHeader(self.data)
        size_MB = flash_size // MB
        if not (0 <= size_MB <= 128):
            raise ValueError(f"Invalid flash size: {flash_size:#x}.")
        # Flash size tag is written into top 4 bits of 4th byte of file
        new_header = bytearray(self.data)
        new_header[self.FLASH_SIZE_OFFSET] = (round(math.log2(size_MB)) << 4) | (
            self.data[self.FLASH_SIZE_OFFSET] & 0xF
        )
        return ImageHeader(bytes(new_header))

    @classmethod
    def from_file(cls, f: BinaryIO) -> ImageHeader:
        """Read the bootloader header from the firmware file or serial device."""
        return cls(f.read(cls.HEADER_SIZE))
