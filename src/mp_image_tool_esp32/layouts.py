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

# Return the recommended OTA app part size (depends on flash_size)
def ota_part_size(flash_size: int) -> int:
    return next(part_size for fsize, part_size in OTA_PART_SIZES if flash_size > fsize)


# Build a new partition table from the provided layout.
# If subtype is "", infer subtype from name (label).
def new_table(
    table: PartitionTable,
    table_layout: Iterable[tuple[str, str, int]],
) -> PartitionTable:
    table.clear()  # Empty the partition table
    for name, *subtype, size in table_layout:
        subtype = (
            subtype[0] if subtype and subtype[0] else default_subtype.get(name, name)
        )
        table.add_part(name, subtype, size)
    return table


# Build a new OTA-enabled partition table for the given flash size and app
# partition size.
def make_ota_layout(
    table: PartitionTable,
    app_part_size: int = 0,  # Size of the partition to hold the app (bytes)
) -> str:
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


# Provide a detailed printout of the partition table
def print_table(table: PartitionTable) -> None:
    colors = dict(c=Fore.CYAN, r=Fore.RED, _=Fore.RESET)

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
