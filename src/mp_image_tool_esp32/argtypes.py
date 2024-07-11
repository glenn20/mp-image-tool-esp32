# MIT License: Copyright (c) 2023 @glenn20
"""
Provides helper functions and types to process and convert some command line
arguments.

Includes some argument type conversion helper functions:
- `numeric_arg(arg)`: Convert a string to an integer number of bytes.
- `arglist(arg)`: Split a string into a list of lists of strings.
- `partlist(arg)`: Split a string into a list of tuples describing a Partition.
- `unsplit(arglist)`: Join a list of lists of strings or ints back into a single
  string.
"""
from __future__ import annotations

import re
import sys
from typing import Iterable

MB = 0x100_000  # 1 Megabyte
KB = 0x400  # 1 Kilobyte
B = 0x1_000  # 1 Block (4096 bytes)

# Convert suffixes to multipliers for convenient units of size.
SIZE_UNITS = {"M": MB, "K": KB, "B": B}

# Delimiters for splitting up and stripping values of command arguments
# First level split is on "," and then on "=" or ":" or "-"
DELIMITERS = [r"\s*,\s*", r"\s*[=:-]\s*"]

if sys.version_info >= (3, 10):
    # Convenient type aliases for static type checking of arguments
    ArgList = list[list[str]]
    # List of Partition tuples: [(name, subtype, offset, size), ...]
    PartList = list[tuple[str, str, int, int]]
else:
    from typing import List, Tuple

    # Convenient type aliases for static type checking of arguments
    ArgList = List[List[str]]
    # List of Partition tuples: [(name, subtype, offset, size), ...]
    PartList = List[Tuple[str, str, int, int]]


# Process a string containing a number with an optional unit suffix
# eg. "8M" (8 megabytes), "0x10B" (16 disk blocks), "4K" (4 kilobytes)
def numeric_arg(arg: str) -> int:
    """Convert a string to an integer number of bytes.
    The string may contain a decimal or hex number and an optional unit suffix:
    "M"=megabytes, "K"=kilobyte or "B"=blocks (4096=0x1000).

    Eg: `"8M"` (8 megabytes), `"0x1fB"` (31 disk blocks = 0x1f000), `"4k"` (4
    kilobytes).
    """
    if not arg:
        return 0
    if (unit := SIZE_UNITS.get(arg[-1].upper(), 1)) != 1:
        arg = arg[:-1]
    return int(arg, 0) * unit  # Allow numbers in decimal or hex


def arglist(arg: str) -> ArgList:
    """Split command line arguments into a list of list of strings.
    The string is delimited first by "," and then by "=", ":" or "-".
    eg: `"nvs=nvs.bin,vfs=vfs.bin"` -> `[["nvs", "nvs.bin"], ["vfs", "vfs.bin"]]`
    """
    return [re.split(DELIMITERS[1], s) for s in re.split(DELIMITERS[0], arg.strip())]


def partlist(arg: str) -> PartList:
    """Split a command line argument into a list of tuples describing a
    Partition: `[(name, subtype_name, offset, size),...]`.

    The string is delimited first by "," and then by "=", ":" or "-". Offset,
    subtype_name and size may be omitted (in that order).

    Eg: `"factory=factory:7B:2M,vfs=1M"` -> `[("factory", "factory", 0x7000,
    0x200000),("vfs", "", 0, 0x100000)]`.
    """
    return [
        (
            name,
            rest[0] if len(rest) >= 2 else "",
            numeric_arg(rest[1]) if len(rest) >= 3 else 0,
            numeric_arg(rest[-1]) if len(rest) >= 1 else 0,
        )
        for (name, *rest) in arglist(arg)
    ]


def unsplit(arglist: Iterable[Iterable[str | int]]) -> str:
    """Join a list of lists of strings or ints into a single string
    delimited by "," and then "="."""
    return ",".join("=".join(str(s) for s in x if s) for x in arglist)
