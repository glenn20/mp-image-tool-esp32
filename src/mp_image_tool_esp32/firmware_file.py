import io
import os
from collections import defaultdict
from typing import IO, Union

from typing_extensions import Buffer

from . import logger as log
from .esptool_io import BLOCKSIZE, get_esptool
from .image_header import ImageHeader

# Bootloader offsets for esp32 devices, indexed by chip name
# Offset is zero for all devices except esp32 and esp32s2
BOOTLOADER_OFFSET = defaultdict(int, esp32=0x1_000, esp32s2=0x1_000)


def is_device(filename: str) -> bool:
    """Return `True` if `filename` is a serial device, else `False`."""
    return filename.startswith("/dev/") or filename.startswith("COM")


class FirmwareFile(io.BufferedRandom):
    """A virtual file-like IO wrapper around an esp32 firmware file object which
    provides an offset to the seek and tell. On esp32 and esp32s2 devices,
    firmware files start at the bootloader offset (0x1000 bytes)."""

    header: ImageHeader
    BLOCKSIZE: int = BLOCKSIZE

    def __init__(self, name: str):
        # Detach the raw base file from `file` and attach it to this object
        f = open(name, "r+b")
        self.header = ImageHeader.from_file(f)
        f.seek(0)  # Reset file position
        self.offset = BOOTLOADER_OFFSET[self.header.chip_name]
        super().__init__(f.detach())

    def seek(self, pos: int, whence: int = 0):
        if whence == 0:  # If seek from start of file, adjust for offset
            pos -= self.offset  # Adjust pos for offset
            if pos < 0:
                raise OSError(f"Attempt to seek before offset ({self.offset:#x}).")
        return super().seek(pos, whence) + self.offset

    def tell(self) -> int:
        return super().tell() + self.offset

    # Some additional convenience methods
    def erase(self, size: int) -> None:
        """Erase a region of the device flash storage using `esptool.py`.
        Size should be a multiple of `0x1000 (4096)`, the device block size"""
        log.debug("Erase is a no-op for firmware files...")
        self.write(b"\xff" * size)


class FirmwareDevice(IO[bytes]):
    """A virtual file-like IO wrapper around the flash storage on an esp32
    device. This allows the device to be used as a file-like object for reading
    and writing. Uses `esptool.py` to read and write data to/from the attached
    device."""

    header: ImageHeader
    BLOCKSIZE: int = BLOCKSIZE

    def __init__(
        self,
        port: str,
        baud: int = 0,
        *,
        esptool_method: str = "subprocess",
        reset_on_close: bool = True,
    ):
        if not os.path.exists(port):
            raise FileNotFoundError(f"No such device: '{port}'")
        self.esptool = get_esptool(port, baud, method=esptool_method)
        self.baud = self.esptool.baud
        self.reset_on_close = reset_on_close
        chip_name = self.esptool.chip_name
        flash_size = self.esptool.flash_size
        self.pos = 0
        self.end = flash_size
        self.seek(BOOTLOADER_OFFSET[chip_name])
        # Check the bootloader header matches the detected device
        self.header = ImageHeader.from_file(self)
        self.seek(BOOTLOADER_OFFSET[chip_name])
        if chip_name and chip_name != self.header.chip_name:
            log.error(
                f"Detected device chip type ({chip_name}) is different "
                f"from firmware bootloader ({self.header.chip_name})."
            )
        if flash_size and flash_size != self.header.flash_size:
            log.error(
                f"Detected flash size ({flash_size}) is different "
                f"from firmware bootloader ({self.header.flash_size})."
            )

    def read(self, size: Union[int, None] = None) -> bytes:
        log.debug(f"Reading {size:#x} bytes from {self.pos:#x}...")
        size = size if size is not None else self.end - self.pos
        data = self.esptool.read_flash(self.pos, size)
        if len(data) != size:
            raise ValueError(f"Read {len(data)} bytes from device, expected {size}.")
        self.pos += len(data)
        return data

    def write(self, data: Buffer) -> int:
        data = memoryview(data).tobytes()
        log.debug(f"Writing {len(data):#x} bytes at position {self.pos:#x}...")
        size = self.esptool.write_flash(self.pos, data)
        self.pos += size
        return size

    def seek(self, pos: int, whence: int = 0):
        self.pos = (0, self.pos, self.end)[whence] + pos
        return self.pos

    def tell(self) -> int:
        return self.pos

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def close(self) -> None:
        if self.reset_on_close:
            log.action("Resetting out of bootloader mode using RTS pin...")
            self.esptool.hard_reset()
        else:
            log.action("Leaving device in bootloader mode...")

        self.esptool.close()  # esptool does not close the port
        self.pos = 0
        self.end = 0

    # Some additional convenience methods
    def erase(self, size: int) -> None:
        """Erase a region of the device flash storage using `esptool.py`.
        Size should be a multiple of `0x1000 (4096)`, the device block size"""
        log.debug(f"Erasing {size:#x} bytes at position {self.pos:#x}...")
        self.esptool.erase_flash(self.pos, size)
        self.pos += size


class Firmware:
    """A class to represent a firmware file. Provides methods to read and write
    the firmware file."""

    filename: str
    file: Union[FirmwareFile, FirmwareDevice]
    header: ImageHeader
    bootloader: int
    is_device: bool
    BLOCKSIZE: int = BLOCKSIZE

    def __init__(
        self,
        filename: str,
        baud: int = 0,
        *,
        esptool_method: str = "direct",
        reset_on_close: bool = True,
    ):
        self.filename = filename
        self.file = (
            FirmwareDevice(
                filename,
                baud,
                esptool_method=esptool_method,
                reset_on_close=reset_on_close,
            )
            if is_device(filename)
            else FirmwareFile(filename)
        )
        hdr = self.file.header
        self.bootloader = BOOTLOADER_OFFSET[hdr.chip_name]
        self.is_device = is_device(filename)
        self.file.seek(self.bootloader)
        self.header = hdr
        self.baud = 0
