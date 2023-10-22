# MIT License: Copyright (c) 2023 @glenn20

from typing import Any

from colorama import Fore

MB = 0x100_000  # 1 Megabyte
KB = 0x400  # 1 Kilobyte
B = 0x1_000  # 1 Block (4096 bytes)


debug: bool = False
verbose: bool = True


def colour_print(colour: str, *args: Any, **kwargs: Any) -> None:
    """Print with a colour prefix."""
    print(colour, end="")
    print(*args, Fore.RESET, **kwargs)


def warn(*args: Any, **kwargs: Any) -> None:
    colour_print(Fore.YELLOW, "Warning:", *args, **kwargs)


def error(*args: Any, **kwargs: Any) -> None:
    colour_print(Fore.RED, *args, **kwargs)


def info(*args: Any, **kwargs: Any) -> None:
    if verbose or debug:
        colour_print(Fore.GREEN, *args, **kwargs)


def vprint(*args: Any, **kwargs: Any) -> None:
    if verbose or debug:
        print(*args, **kwargs)


def dprint(*args: Any, **kwargs: Any) -> None:
    if debug:
        colour_print(Fore.YELLOW, *args, **kwargs)
