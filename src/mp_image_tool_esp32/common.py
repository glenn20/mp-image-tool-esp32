# MIT License: Copyright (c) 2023 @glenn20

from typing import Any

from colorama import Fore

MB = 0x100_000  # 1 Megabyte
KB = 0x400  # 1 Kilobyte
B = 0x1_000  # 1 Block (4096 bytes)


debug: bool = False
verbose: bool = True


def warn(*args: Any, **kwargs: Any) -> None:
    print(Fore.YELLOW, end="")
    print("Warning:", *args, Fore.RESET, **kwargs)


def error(*args: Any, **kwargs: Any) -> None:
    print(Fore.RED, end="")
    print(*args, Fore.RESET, **kwargs)


def info(*args: Any, **kwargs: Any) -> None:
    if verbose or debug:
        print(Fore.GREEN, end="")
        print(*args, Fore.RESET, **kwargs)


def vprint(*args: Any, **kwargs: Any) -> None:
    if verbose or debug:
        print(*args, **kwargs)
