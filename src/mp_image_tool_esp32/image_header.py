from __future__ import annotations

import binascii
import hashlib
import math
from ctypes import (
    Array,
    LittleEndianStructure,
    Structure,
    c_uint8,
    c_uint16,
    c_uint32,
    sizeof,
)
from functools import cached_property
from typing import IO, Any, Tuple

MB = 1024 * 1024


# See https://docs.espressif.com/projects/esptool/en/latest/esp32
# /advanced-topics/firmware-image-format.html
class ImageHeaderStruct(LittleEndianStructure):
    """A ctypes structure to represent the fields in the esp32 firmware image
    header."""

    _pack_ = 1
    _fields_ = [
        ("magic", c_uint8),
        ("num_segments", c_uint8),
        ("spi_flash_mode", c_uint8),
        ("flash_frequency_id", c_uint8, 4),
        ("flash_size_id", c_uint8, 4),
        ("entry_point_address", c_uint32),
        ("spi_rom_pins", c_uint8 * 4),
        ("chip_id", c_uint16),
        ("deprecated", c_uint8),
        ("min_chip_revision", c_uint16),
        ("max_chip_revision", c_uint16),
        ("_reserved", c_uint8 * 4),
        ("hash_appended", c_uint8),
    ]
    magic: int
    num_segments: int
    spi_flash_mode: int
    flash_frequency_id: int
    flash_size_id: int
    entry_point_address: int
    spi_rom_pins: bytes
    chip_id: int
    deprecated: int
    min_chip_revision: int
    max_chip_revision: int
    _reserved: bytes
    hash_appended: int


assert sizeof(ImageHeaderStruct) == 24


def ctypes_repr(x: Any, indent: str = "") -> str:
    """Return a string representation of a ctypes object.
    Will recursively unpack and format nested structures and arrays."""
    if isinstance(x, Array):
        return f"[{', '.join(repr(i) for i in x)}]"
    elif isinstance(x, Structure):
        indent += "  "
        args = "\n".join(
            (
                f"  {f}={ctypes_repr(getattr(x, f), indent)},"
                for f, *_ in x._fields_
                if not f[0].startswith("_")
            )
        )
        return f"{x.__class__.__name__}(\n{args}\n)"
    else:
        return repr(x)


class ImageHeader(ImageHeaderStruct):
    """A class to represent the esp32 firmware image format. Provides methods to
    read and write the image header."""

    APP_IMAGE_MAGIC = 0xE9
    CHIP_IDS = {  # Map from chip ids in the image file header to esp32 chip names.
        0x00: "esp32",
        0x02: "esp32s2",
        0x05: "esp32c3",
        0x09: "esp32s3",
        0x0C: "esp32c2",
        0x0D: "esp32c6",
        0x10: "esp32h2",
        0x12: "esp32p4",
        0xFFFF: "invalid",
    }
    initial_crc32: int  # Checksum of the image header

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.check()

    def check(self) -> ImageHeader:
        if self.magic != self.APP_IMAGE_MAGIC:
            raise ValueError("Invalid image file: magic bytes not found.")
        if self.chip_name == "invalid":
            raise ValueError("Invalid chip id in image header.")
        self.initial_crc32 = binascii.crc32(self)  # Calculate the checksum
        return self

    def ismodified(self) -> bool:
        """Return True if the bootloader header has been modified."""
        return binascii.crc32(self) != self.initial_crc32

    @cached_property
    def chip_name(self) -> str:
        """Return the chip name from the bootloader header."""
        chip_name = self.CHIP_IDS.get(self.chip_id, str(self.chip_id))
        if chip_name == "invalid":
            raise ValueError("Invalid chip id in image header.")
        return chip_name

    @property
    def flash_size(self) -> int:
        """Return the flash size from the bootloader header."""
        return (2**self.flash_size_id) * MB

    @flash_size.setter
    def flash_size(self, flash_size: int) -> None:
        """Set the flash size in the bootloader header."""
        if not (0 <= flash_size <= 256 * MB):
            raise ValueError(f"Invalid flash size: {flash_size:#x}.")
        self.flash_size_id = round(math.log2(flash_size / MB))

    @property
    def size(self) -> int:
        """Return the size of the image header."""
        return sizeof(self)

    def copy(self) -> ImageHeader:
        """Return a copy of the image header."""
        return ImageHeader.from_bytes(bytes(self))

    @classmethod
    def from_bytes(cls, data: bytes) -> ImageHeader:
        """Read the image header from a file."""
        return cls.from_buffer_copy(data).check()

    @classmethod
    def from_file(cls, file: IO[bytes]) -> ImageHeader:
        """Read the image header from a file."""
        return cls.from_bytes(file.read(sizeof(cls)))

    def __repr__(self) -> str:
        return ctypes_repr(self) + f", ismodified={self.ismodified()}"


def get_image_size(data: bytes | bytearray) -> int:
    """Return the size of the application or bootloader image in `data`."""
    hdr = ImageHeader.from_buffer(data)
    n = hdr.size
    for _ in range(hdr.num_segments):  # Skip over each segment in the image
        segment_size = int.from_bytes(data[n + 4 : n + 8], "little")
        n += segment_size + 8
    n += 1  # Allow for the checksum byte
    n = (n + 0xF) & ~0xF  # Round up to a multiple of 16 bytes
    return n


def calculate_image_size_and_hash(data: bytes | bytearray) -> tuple[int, bytes]:
    """Check the sha256 hash at the end of the bootloader image data."""
    n = get_image_size(data)
    return n, hashlib.sha256(data[:n]).digest()


def update_image(hdr: ImageHeader, data: bytes | bytearray) -> Tuple[bytearray, int]:
    """Update the bootloader hash, if it has changed."""
    if isinstance(data, bytes):
        data = bytearray(data)
    # Write the updated header to the start of the bootloader
    data[: hdr.size] = bytes(hdr)  # Write the updated header
    size = 0
    if hdr.hash_appended == 1:
        size, sha = calculate_image_size_and_hash(data)
        data[size : size + len(sha)] = sha
    return data, size
