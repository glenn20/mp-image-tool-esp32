import os
from typing import BinaryIO

from typing_extensions import Buffer

from . import logger as log
from .esptool_ops import BLOCKSIZE, esptool_wrapper
from .image_header import BOOTLOADER_OFFSET, ImageFormat


class ESPDeviceIO(BinaryIO):
    """A virtual file-like IO wrapper around the flash storage on an esp32 device.
    This allows the device to be used as a file-like object for reading and
    writing. Uses `esptool.py` to read and write data to/from the attached
    device."""

    BLOCKSIZE = BLOCKSIZE

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
        self.esptool = esptool_wrapper(port, baud, method=esptool_method)
        self.chip_name = self.esptool.chip_name
        self.flash_size = self.esptool.flash_size
        self.reset_on_close = not reset_on_close
        self.pos = 0
        self.end = self.flash_size
        self.bootloader = BOOTLOADER_OFFSET[self.chip_name]
        self.seek(BOOTLOADER_OFFSET[self.chip_name])
        hdr = ImageFormat.from_file(self)
        self.app_size = 0  # Unknown app size
        if self.chip_name and self.chip_name != hdr.chip_name:
            log.warning(
                f"Detected device chip type ({self.chip_name}) is different "
                f"from firmware bootloader ({hdr.chip_name})."
            )
        if self.flash_size and self.flash_size != hdr.flash_size:
            log.warning(
                f"Detected flash size ({self.flash_size}) is different "
                f"from firmware bootloader ({hdr.flash_size})."
            )

    def read(self, size: int | None = None) -> bytes:
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

        self.esptool.close()  # type: ignore - esptool does not close the port
        self.pos = 0
        self.end = 0

    # Some additional convenience methods
    def erase(self, size: int) -> None:
        """Erase a region of the device flash storage using `esptool.py`.
        Size should be a multiple of `0x1000 (4096)`, the device block size"""
        log.debug(f"Erasing {size:#x} bytes at position {self.pos:#x}...")
        self.esptool.erase_flash(self.pos, size)
        self.pos += size
