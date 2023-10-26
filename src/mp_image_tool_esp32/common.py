# MIT License: Copyright (c) 2023 @glenn20

from enum import IntEnum
from typing import Any

from colorama import Fore

MB = 0x100_000  # 1 Megabyte
KB = 0x400  # 1 Kilobyte
B = 0x1_000  # 1 Block (4096 bytes)


class Levels(IntEnum):
    """Logging levels for the `log` function."""

    DEBUG = 10
    INFO = 20
    ACTION = 25
    WARN = 30
    ERROR = 40
    CRITICAL = 50


colours = {
    Levels.DEBUG.value: Fore.YELLOW,
    Levels.INFO.value: "",
    Levels.ACTION.value: Fore.GREEN,
    Levels.WARN.value: Fore.YELLOW,
    Levels.ERROR.value: Fore.RED,
    Levels.CRITICAL.value: Fore.RED,
}

debug_level: int = Levels.INFO


def verbosity(level: int) -> bool:
    """Check the debug level."""
    return debug_level <= level


def set_verbosity(level: int) -> None:
    """Set the debug level."""
    global debug_level
    debug_level = level


def colour_print(level: int, *args: Any, **kwargs: Any) -> None:
    """Print with a colour prefix."""
    if verbosity(level):
        print(colours.get(level, ""), end="")
        print(*args, Fore.RESET, **kwargs)


def debug(*args: Any, **kwargs: Any) -> None:
    colour_print(Levels.DEBUG, *args, **kwargs)


def info(*args: Any, **kwargs: Any) -> None:
    colour_print(Levels.INFO, *args, **kwargs)


def action(*args: Any, **kwargs: Any) -> None:
    colour_print(Levels.ACTION, *args, **kwargs)


def warning(*args: Any, **kwargs: Any) -> None:
    colour_print(Levels.WARN, "Warning:", *args, **kwargs)


def error(*args: Any, **kwargs: Any) -> None:
    colour_print(Levels.ERROR, *args, **kwargs)
