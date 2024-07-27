from typing import Any

import esptool

def detect_chip(
    port: str = ...,
    baud: int = ...,
    connect_mode: str = ...,
    trace_enabled: bool = ...,
    connect_attempts: int = ...,
) -> esptool.ESPLoader: ...
def detect_flash_size(
    esp: esptool.ESPLoader, args: Any | None = None
) -> str | None: ...
def write_flash(esp: esptool.ESPLoader, args: Any) -> None: ...
