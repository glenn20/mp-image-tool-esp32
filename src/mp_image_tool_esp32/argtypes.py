# MIT License: Copyright (c) 2023 @glenn20
"""
Provides helper functions and types to process and convert some command line
arguments.

Includes some argument type conversion helper functions and classes:
- `numeric_arg(arg)`: Convert a string to an integer number of bytes.
- `ArgList(arg)`: Split a string into a list of lists of strings.
- `PartList(arg)`: Split a string into a list of tuples describing a Partition.
- `unsplit(arglist)`: Join a list of lists of strings or ints back into a single
  string.
"""

from __future__ import annotations

import re
from typing import List, Tuple  # Need List & Tuple for py3.8

MB = 0x100_000  # 1 Megabyte
KB = 0x400  # 1 Kilobyte
B = 0x1_000  # 1 Block (4096 bytes)

# Convert suffixes to multipliers for convenient units of size.
SIZE_UNITS = {"M": MB, "MB": MB, "K": KB, "KB": KB, "B": B}

# Delimiters for splitting up and stripping values of command arguments
# First level split is on "," and then on "=" or ":"
DELIMITERS = [r"\s*,\s*", r"\s*[=:]\s*"]


class IntArg(int):
    """Convert a string to an integer number of bytes.
    The string may contain a decimal or hex number and an optional unit suffix:
    "M"=megabytes, "K"=kilobyte or "B"=blocks (4096=0x1000).

    Eg: `"8M"` (8 megabytes), `"0x1fB"` (31 disk blocks = 0x1f000), `"4k"` (4
    kilobytes).
    """

    def __new__(cls, arg: str) -> IntArg:
        if not arg:
            arg = "0"
        unit = 1
        for k, v in SIZE_UNITS.items():
            if arg.upper().endswith(k.upper()):
                arg, unit = arg[: -len(k)], v
                break
        return super().__new__(cls, (float(arg) if "." in arg else int(arg, 0)) * unit)


class ArgList(List[List[str]]):
    """Split command line arguments into a list of list of strings.
    The string is delimited first by "," and then by "=", ":"
    eg: `"nvs=nvs.bin,vfs=vfs.bin"` -> `[["nvs", "nvs.bin"], ["vfs", "vfs.bin"]]`
    """

    def __init__(self, arg: str) -> None:
        super().__init__(
            [re.split(DELIMITERS[1], s) for s in re.split(DELIMITERS[0], arg.strip())]
        )

    def __str__(self) -> str:
        """Reconstruct the argument list as a string."""
        return ",".join("=".join(str(s) for s in x if s) for x in self)


class PartList(List[Tuple[str, str, int, int]]):
    """Split a command line argument into a list of tuples describing a
    Partition: `[(name, subtype_name, offset, size),...]`.

    The string is delimited first by "," and then by "=", or ":". Offset,
    subtype_name and size may be omitted (in that order).

    Eg: `"factory=factory:7B:2M,vfs=1M"` -> `[("factory", "factory", 0x7000,
    0x200000),("vfs", "", 0, 0x100000)]`.
    """

    def __init__(self, arg: str) -> None:
        super().__init__(
            [
                (
                    name,
                    rest[0] if len(rest) >= 2 else "",
                    IntArg(rest[1]) if len(rest) >= 3 else 0,
                    IntArg(rest[-1]) if len(rest) >= 1 else 0,
                )
                for (name, *rest) in ArgList(arg)
            ]
        )

    def __str__(self) -> str:
        """Reconstruct the partition list as a string."""
        return ",".join("=".join(str(s) for s in x if s) for x in self)
