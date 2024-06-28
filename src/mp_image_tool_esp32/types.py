# MIT License: Copyright (c) 2023 @glenn20
"""Common type definitions and functions for the ESP32 image tool."""

from __future__ import annotations

import sys

if sys.version_info >= (3, 10):
    # Convenient type aliases for static type checking of arguments
    ArgList = list[list[str]]
    # List of Partition tuples: [(name, subtype, offset, size), ...]
    PartList = list[tuple[str, str, int, int]]
    # Types we can use for binary data
    ByteString = bytes | bytearray | memoryview
else:
    from typing import List, Tuple, Union

    # Convenient type aliases for static type checking of arguments
    ArgList = List[List[str]]
    # List of Partition tuples: [(name, subtype, offset, size), ...]
    PartList = List[Tuple[str, str, int, int]]
    # Types we can use for binary data
    ByteString = Union[bytes, bytearray, memoryview]
