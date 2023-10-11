# MIT License: Copyright (c) 2023 @glenn20

from colorama import Fore

MB = 0x100_000  # 1 Megabyte
KB = 0x400  # 1 Kilobyte
B = 0x1_000  # 1 Block (4096 bytes)

APP_IMAGE_MAGIC = b"\xe9"  # Starting bytes for firmware files


def print_action(*args, **kwargs) -> None:
    print(Fore.GREEN, end="")
    print(*args, Fore.RESET, **kwargs)


def print_error(*args, **kwargs) -> None:
    print(Fore.RED, end="")
    print(*args, Fore.RESET, **kwargs)
