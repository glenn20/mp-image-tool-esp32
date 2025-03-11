"""Provides the `FirmwareFile` and `FirmwareDevice` classes which provide a
file-like interface for writing data to/from ESP32 firmware files and devices.

`FirmwareFile` and `FirmwareDevice` implement common file-like interfaces to
ESP32 firmware files on disk AND ESP32 firmware on the flash storage of a
serial-attached ESP32 devices. These classes also provide an additional method:
`erase(size)` to erase a region of the device flash storage.
"""

# It would be nice to define a common interface (for typing purposes) for
# `FirmwareFile` and `FirmwareDevice`, but I encountered difficulty while trying
# to also support the `erase()` method and python versions back to 3.8. So,
# we rely on duck-typing for now.

from __future__ import annotations

import io
import os
from collections import defaultdict
from typing import BinaryIO

from typing_extensions import Buffer

from . import logger
from .argtypes import MB
from .esptool_io import BLOCKSIZE, ESPTool, get_esptool
from .image_header import ImageHeader
from .partition_table import PartitionEntry, PartitionError

log = logger.getLogger(__name__)

# Bootloader offsets for esp32 devices, indexed by chip name
# Offset is zero for all devices except esp32 and esp32s2
BOOTLOADER_OFFSET = defaultdict(int, esp32=0x1_000, esp32s2=0x1_000)


class FirmwareFileIO(io.BufferedRandom):
    """A file-like IO wrapper around an esp32 firmware file object which
    provides an offset to the seek and tell so that we can provide a uniform
    interface for all ESP32 firmware file types.

    On ESP32 and ESP32-S2 devices, firmware files start at the bootloader offset
    (0x1000 bytes)."""

    header: ImageHeader
    bootloader: int
    size: int
    BLOCKSIZE: int = BLOCKSIZE

    def __init__(self, name: str):
        # Detach the raw base file from `file` and attach it to this object
        f = open(name, "r+b")
        self.header = ImageHeader.from_file(f)
        self.header.validate()  # Raise an exception for invalid headers
        self.bootloader = BOOTLOADER_OFFSET[self.header.chip_name]
        self.size = f.seek(0, 2) + self.bootloader
        f.seek(0)  # Reset file position
        super().__init__(f.detach())

    def seek(self, pos: int, whence: int = 0) -> int:
        if whence == 0:  # If seek from start of file, adjust for offset
            pos -= self.bootloader  # Adjust pos for offset
            if pos < 0:
                raise ValueError(
                    f"Attempt to seek before offset ({self.bootloader:#x})."
                )
        return super().seek(pos, whence) + self.bootloader

    def tell(self) -> int:
        return super().tell() + self.bootloader

    # Add an `erase` method
    def erase(self, size: int) -> None:
        """Erase a region of the device flash storage.
        Size should be a multiple of `0x1000 (4096)`, the device block size"""
        log.debug(f"Erasing {size:#x} bytes at position {self.tell():#x}...")
        self.write(b"\xff" * size)


class FirmwareDeviceIO(BinaryIO):
    """A file-like IO wrapper around the flash storage on an esp32 device.
    This allows the device to be used as a file-like object for reading and
    writing. Uses `esptool.py` to read and write data to/from the attached
    device."""

    header: ImageHeader
    bootloader: int
    size: int
    BLOCKSIZE: int = BLOCKSIZE
    esptool: ESPTool

    def __init__(
        self,
        port: str,
        baud: int = 0,
        *,
        esptool_method: str = "subprocess",
        reset_on_close: bool = True,
        check: bool = True,
    ):
        if not os.path.exists(port):
            raise FileNotFoundError(f"No such device: '{port}'")
        self.esptool = get_esptool(port, baud, method=esptool_method)
        self.size = self.esptool.flash_size
        self._pos: int = 0
        self._end: int = self.size
        self._reset_on_close: bool = reset_on_close
        self.bootloader = BOOTLOADER_OFFSET[self.esptool.chip_name]
        self.seek(self.bootloader)
        # Check the bootloader header matches the detected device
        self.header = ImageHeader.from_file(self)
        self.seek(self.bootloader)
        if not check:
            return  # Skip checking the bootloader header

        if self.header.is_erased():
            raise PartitionError(
                "No bootloader found on flash.\n"
                "  Use '--flash' option to flash new firmware."
            )
        self.header.validate()
        if self.esptool.chip_name and self.esptool.chip_name != self.header.chip_name:
            log.error(
                f"Detected device chip type ({self.esptool.chip_name}) is "
                f"different from firmware bootloader ({self.header.chip_name})."
            )
        if (
            self.esptool.flash_size
            and self.esptool.flash_size != self.header.flash_size
        ):
            log.warning(
                f"Detected flash size ({self.esptool.flash_size // MB}MB) is "
                f"different from firmware bootloader "
                f"({self.header.flash_size // MB}MB).\n"
                "  [italic]Use the '-f' option to change the size in the bootloader."
            )

    def __enter__(self) -> FirmwareDeviceIO:
        return self

    def read(self, size: int | None = None) -> bytes:
        size = size if size is not None else self._end - self._pos
        log.debug(f"Reading {size:#x} bytes from {self._pos:#x}...")
        data = self.esptool.read_flash(self._pos, size)
        if len(data) != size:
            raise ValueError(f"Read {len(data)} bytes from device, expected {size}.")
        self._pos += len(data)
        return data

    def write(self, data: Buffer) -> int:
        data = memoryview(data)
        log.debug(f"Writing {len(data):#x} bytes at position {self._pos:#x}...")
        size = self.esptool.write_flash(self._pos, data)
        self._pos += size
        return size

    def seek(self, pos: int, whence: int = 0) -> int:
        self._pos = (0, self._pos, self._end)[whence] + pos
        return self._pos

    def tell(self) -> int:
        return self._pos

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def close(self) -> None:
        if self._reset_on_close:
            log.debug("Resetting out of bootloader mode using RTS pin...")
            self.esptool.hard_reset()
        else:
            log.action("Leaving device in bootloader mode...")

        self.esptool.close()  # esptool does not close the port
        self._pos = 0
        self._end = 0

    # Add an `erase` method
    def erase(self, size: int) -> None:
        """Erase a region of the device flash storage using `esptool.py`.
        Size should be a multiple of `0x1000 (4096)`, the device block size"""
        log.debug(f"Erasing {size:#x} bytes at position {self._pos:#x}...")
        self.esptool.erase_flash(self._pos, size)
        self._pos += size


class Partition(BinaryIO):
    """A file-like IO wrapper around a partition of an esp32 firmware file or
    device. This allows the partition to be used as a file-like object for
    reading and writing."""

    part: PartitionEntry
    file: FirmwareFileIO | FirmwareDeviceIO

    def __init__(self, part: PartitionEntry, file: FirmwareFileIO | FirmwareDeviceIO):
        self.file = file
        self.part = part
        self._pos: int = 0
        if part.offset >= file.size:
            raise ValueError(f"Partition '{part.name}' is not in firmware file.")
        self.seek(0)

    def __enter__(self) -> Partition:
        return self

    def seek(self, pos: int, whence: int = 0) -> int:
        name = self.part.name
        if whence == 0:  # Seek from start of file
            pos += 0
        elif whence == 1:  # Seek from current position...
            pos += self._pos
        elif whence == 2:  # Seek from end of file..
            pos += self.part.size
        else:
            raise ValueError(f"Partition '{name}': Invalid whence value: {whence}")
        if not 0 <= pos <= self.part.size:
            raise ValueError(f"Partition '{name}': Invalid seek: ({pos=:#x}).")
        self._pos = pos
        self.file.seek(self.part.offset + pos)
        return self._pos

    def tell(self) -> int:
        return self._pos

    def read(self, size: int | None = None) -> bytes:
        pos = self._pos
        if size is None or pos + size > self.part.size:
            size = self.part.size - pos
        b = self.file.read(size)
        self._pos += len(b)
        return b

    def write(self, data: Buffer) -> int:
        data = memoryview(data)
        pos, size, name = self._pos, len(data), self.part.name
        if not 0 <= pos + size <= self.part.size:
            raise ValueError(
                f"Partition '{name}': Invalid write ({pos=:#x} {size=:#x})."
            )
        if pos % self.file.BLOCKSIZE != 0:
            raise ValueError(
                f"Partition '{name}': Write not block aligned ({pos=:#x})."
            )
        skip_erase = (
            # If the last partition of a firmware file, dont erase trailing blocks
            isinstance(self.file, FirmwareFileIO)
            and self.part.offset + self.part.size > self.file.size
        )
        pad = 0
        if not skip_erase:
            remainder = len(data) % self.file.BLOCKSIZE
            pad = self.file.BLOCKSIZE - remainder if remainder else 0

        self.seek(pos)
        res = self.file.write(b"" + data + b"\xff" * pad)  # Write data: pad with 0xff
        res -= pad  # Subtract the padding from the write length
        if res != size:
            raise ValueError(f"Partition {name}: Write failed: ({size=:#x} {res=:#x}.")
        self._pos += res
        return res

    def truncate(self, size: int | None = None) -> int:
        size = size if size is not None else self._pos
        if (
            isinstance(self.file, FirmwareFileIO)
            and self.part.offset + self.part.size > self.file.size
        ):
            # If the last partition of a firmware file, dont erase trailing blocks
            self.seek(size)
            self.file.truncate()  # Truncate the file to the new size
            return size
        else:
            nextblock = (size + self.file.BLOCKSIZE - 1) // self.file.BLOCKSIZE
            size = nextblock * self.file.BLOCKSIZE
            self.seek(size)  # Seek to the next block
            log.action(f"Erasing partition '{self.part.name}' from {size:#x}...")
            self.file.erase(self.part.size - size)
            return size

    def close(self) -> None:
        self._pos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    # Add an `erase` method
    def erase(self, size: int | None = None) -> None:
        """Erase a region of the device flash storage using `esptool.py`.
        Size should be a multiple of `0x1000 (4096)`, the device block size"""
        pos = self._pos
        if not size or pos + size > self.part.size:
            size = self.part.size - pos
        if not 0 <= pos + size <= self.part.size:
            raise ValueError(
                f"Attempt to erase outside partition {self.part.name} "
                f"({pos=:#x} {size=:#x})."
            )
        log.debug(f"Erasing {size:#x} bytes at position {pos:#x}...")
        self.file.seek(self.part.offset + pos)
        self.file.erase(size)
        self._pos += size
