from typing import Callable, Sequence

import serial

class StubFlasher: ...

class ESPLoader:
    CHIP_NAME: str
    _port: serial.Serial

    def read_flash(
        self,
        offset: int,
        size: int,
        progress_fn: Callable[[int, int], None] | None = None,
    ) -> bytes: ...
    def erase_region(self, offset: int, size: int) -> None: ...
    def run_stub(self, stub: StubFlasher | None = None) -> "ESPLoader": ...
    def hard_reset(self) -> None: ...

def main(argv: Sequence[str], esp: ESPLoader | None) -> None: ...
