# MIT License: Copyright (c) 2023 @glenn20
"""Provides classes and functions to manage OTA firmware updates over the serial
interface to ESP32 devices.

Provides:
- ota_update(image: Esp32Image, table: PartitionTable, filename: str, no_rollback=False)

If `table` includes `OTA` partitions, write the app firmware in `filename` to the
next available `OTA` partition and set it as the next boot partition.

If `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE` is enabled in the bootloader
on the device, the new firmware must be validated on reboot, or the device will
rollback to the previous firmware. This can be done by calling
`esp32.Partition.mark_app_valid_cancel_rollback()`.
"""

import binascii
import struct
from enum import IntEnum
from functools import cached_property
from pathlib import Path
from typing import List

from . import logger as log
from .firmware import Firmware
from .partition_table import PartitionEntry

OTA_SIZE = 0x20  # The size of an OTA record in bytes (32 bytes)
OTA_OFFSETS = (0, 0x1000)  # The offsets of the OTA records in the otadata partition
OTA_RECORDS = ((i, i + OTA_SIZE) for i in OTA_OFFSETS)  # Offset and size of OTA records
OTA_FMT = b"<L20sLL"  # The format for reading/writing binary OTA records
OTA_LABEL = b"\xff" * OTA_SIZE  # The expected label field in the OTA record
OTA_CRC_INIT = 0xFFFFFFFF  # The initial value for the CRC32 checksum


class OtaState(IntEnum):
    """Allowed values for the `state` field in an OTA record."""

    NEW = 0
    PENDING = 1
    VALID = 2
    INVALID = 3
    ABORTED = 4
    UNDEFINED = 0xFFFFFFFF


def ota_crc(seq: int) -> int:
    """Calculate the CRC32 checksum of an OTA sequence number."""
    return binascii.crc32(seq.to_bytes(4, "little"), OTA_CRC_INIT)


def ota_is_valid(seq: int, state: int, crc: int) -> bool:
    """Check validity of an OTA record."""
    return state == OtaState.VALID and ota_crc(seq) == crc


def ota_sequence_number(data: bytes) -> int:
    """Return the ota sequence number from a binary OTA record in `data` or 0 if
    the record is invalid."""
    seq, _, state, crc = struct.unpack(OTA_FMT, data)
    is_valid = ota_is_valid(seq, state, crc)
    log.debug(f"OTA record: seq={seq}, state={state}, crc={crc}, valid={is_valid}")
    return seq if is_valid else 0


def ota_record(seq: int, state: int) -> bytes:
    """Return a byte string containing a binary OTA record for sequence number
    `seq` and state `state`."""
    return (
        struct.pack(OTA_FMT, seq, OTA_LABEL, state, ota_crc(seq))
        if 1 <= seq <= 0xFFFFFFFF
        else b"\xff" * OTA_SIZE
    )


class OTAUpdater:
    """A class to manage ESP32 *OTA* updates to a serial attached device."""

    def __init__(
        self,
        image: Firmware,
        no_rollback: bool = False,
    ):
        self.image = image
        self.no_rollback = no_rollback
        self.otadata_part = self.image.table.by_subtype("ota")

        data = self.image.read_part(self.otadata_part)
        self.ota_sequence_number = max(
            ota_sequence_number(buf) for buf in (data[i:j] for i, j in OTA_RECORDS)
        )

    @cached_property
    def _ota_app_parts(self) -> List[PartitionEntry]:
        """Return a list of all the `ota` app partitions sorted by subtype."""
        parts = sorted(  # "ota_0", "ota_1", ... partitions
            (p for p in self.image.table if p.type == 0 and 0x10 <= p.subtype < 0x20),
            key=lambda p: p.subtype,
        )
        if len(parts) < 2:
            raise ValueError("Require at least 2 ota partitions: 'ota_0' and 'ota_1.")
        # Check ota app parts are sequential in number, starting from 0
        for i, p in enumerate(parts):
            if p.subtype - 0x10 != i:
                raise ValueError("OTA partition subtypes must be sequential.")
        return parts

    def _ota_app_part(self, seq: int) -> PartitionEntry:
        """Return the `ota` app partition for a given sequence number."""
        ota_num = (seq - 1) % len(self._ota_app_parts) if seq > 0 else 0
        return self._ota_app_parts[ota_num]

    def current(self) -> PartitionEntry:
        """Return the current `ota` app firmware boot partition."""
        return self._ota_app_part(self.ota_sequence_number)

    def get_next_update(self) -> PartitionEntry:
        """Return the next available `ota` app firmware partition to be updated."""
        return self._ota_app_part(self.ota_sequence_number + 1)

    def set_boot(self, part: PartitionEntry) -> None:
        """Set `part` as the next boot partition. `part` must an `ota` partition."""
        seq = (start := self.ota_sequence_number)  # Start with current sequence number
        while part != self._ota_app_part(seq):  # look for part in ota_parts
            seq += 1
            if seq - start > len(self._ota_app_parts):
                raise ValueError(f"'{part.name}' not found in 'ota' partitions")
        if seq == start:
            log.warning(f"'{part.name}' is already set for booting.")
            return
        data = (
            ota_record(seq, OtaState.UNDEFINED if self.no_rollback else OtaState.NEW)
            + b"\xff" * (0x1000 - OTA_SIZE)
            + ota_record(self.ota_sequence_number, OtaState.VALID)
            + b"\xff" * (0x1000 - OTA_SIZE)
        )
        if self.image.write_part(self.otadata_part, data) != len(data):
            raise ValueError("Failed to write OTA data to otadata partition.")


def ota_update(image: Firmware, firmware: str, no_rollback: bool = False) -> None:
    """Update the app firmware on an OTA-enabled esp32 device over the serial
    interface.

    If `image` includes `OTA` partitions, write the app firmware in `filename`
    to the next available `OTA` partition and set it as the next boot partition.

    If `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE` is enabled in the bootloader on
    the device (default since micropython v1.21.0), you must call
    `esp32.Partition.mark_app_valid_cancel_rollback()` to validate the new
    firmware on reboot, or the device will rollback to the previous firmware.
    """
    if not image.is_device:
        raise ValueError("Device is not a serial device.")

    ota = OTAUpdater(image, no_rollback)

    new_part = ota.get_next_update()  # Get the next available OTA update partition
    log.action(f"Writing firmware to OTA partition {new_part.name}...")
    image.write_part(new_part, Path(firmware).read_bytes())

    log.action("Updating otadata partition...")
    ota.set_boot(new_part)
