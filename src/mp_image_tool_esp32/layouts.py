from typing import Iterable

from colorama import Fore

from .common import KB, MB
from .partition_table import PartitionTable

# Recommended size for OTA app partitions (depends on flash_size).
# These choices match OTA partition sizes in ports/esp32/partition-*-ota.csv.
OTA_PART_SIZES = (
    (8 * MB, 0x270_000),  # if flash size > 8MB
    (4 * MB, 0x200_000),  # else if flash size > 4MB
    (0 * MB, 0x180_000),  # else if flash size > 0MB
)
DEFAULT_TABLE_LAYOUT = """
nvs     : nvs       : 0x7000,
factory : factory   : 0x1f0000,
vfs     : fat       : 0
"""
OTA_TABLE_LAYOUT = """
nvs     : nvs       : {nvs},
otadata : ota       : {otadata},
ota_0   : ota_0     : {ota_0},
ota_1   : ota_1     : {ota_1},
vfs     : fat       : 0
"""
# Mapping of partition names to default subtypes
# Don't need to include where name==subtype as will fall back name.
default_subtype: dict[str, str] = {
    "otadata": "ota",
    "vfs": "fat",
    "phy_init": "phy",
}


def ota_part_size(flash_size: int) -> int:
    """Calculate and return the recommended OTA app part size (in bytes) for the
    given flash_size."""
    return next(part_size for fsize, part_size in OTA_PART_SIZES if flash_size > fsize)


def get_subtype(name: str, subtype: str) -> str:
    """Return subtype if it is not empty, else infer subtype from name."""
    return subtype or default_subtype.get(name, name)


def new_table(
    table: PartitionTable,
    table_layout: Iterable[tuple[str, str, int, int]],
) -> PartitionTable:
    """Build a new partition table from the provided layout.
    For each tuple, if subtype is `""`, infer `subtype` from name."""
    table.clear()  # Empty the partition table
    for name, *subtype, offset, size in table_layout:
        subtype = get_subtype(name, subtype[0] if subtype else "")
        table.add_part(name, subtype, size, offset)
    return table


def make_ota_layout(
    table: PartitionTable,
    app_part_size: int = 0,  # Size of the partition to hold the app (bytes)
) -> str:
    """Build a layout for a new OTA-enabled partition table for the given flash
    size and app_part_size. If app_part_size is 0, use the recommended size for
    the flash size."""
    flash_size = table.flash_size
    if not app_part_size:
        app_part_size = ota_part_size(flash_size)
    nvs_part_size = table.app_part.offset - table.FIRST_PART_OFFSET - table.OTADATA_SIZE
    return OTA_TABLE_LAYOUT.format(
        nvs=nvs_part_size,
        otadata=table.OTADATA_SIZE,
        ota_0=app_part_size,
        ota_1=app_part_size,
    )


def print_table(table: PartitionTable) -> None:
    """Print a detailed description of the partition table."""
    colors = dict(c=Fore.CYAN, r=Fore.RED)

    print(Fore.CYAN, end="")
    print(
        "{c}Partition table (flash size: {r}{size}MB{c}):".format(
            size=table.flash_size // MB, **colors
        )
    )
    table.print()
    print(Fore.RESET, end="")
    if table.app_part and table.app_size:
        print(
            "Micropython app fills {used:0.1f}% of {app} partition "
            "({rem} kB free)".format(
                used=100 * table.app_size / table.app_part.size,
                app=table.app_part.name,
                rem=(table.app_part.size - table.app_size) // KB,
            )
        )
