# MIT License: Copyright (c) 2023 @glenn20

import logging
from typing import Any

import colorlog

ACTION = logging.INFO + 1
logging.addLevelName(ACTION, "ACTION")

handler = logging.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s%(message)s",
        log_colors={
            "DEBUG": "yellow",
            "INFO": "reset",
            "ACTION": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    ),
)
log = logging.getLogger()
log.addHandler(handler)
log.setLevel(logging.INFO)
levels = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "ACTION": ACTION,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
}


def setLevel(level: str) -> None:
    log.setLevel(levels.get(level.upper(), logging.NOTSET))


def isloglevel(level: str) -> bool:
    return levels.get(level.upper(), logging.ERROR) >= log.getEffectiveLevel()


def debug(msg: str, *args: Any, **kwargs: Any) -> None:
    log.debug(msg, *args, **kwargs)


def info(msg: str, *args: Any, **kwargs: Any) -> None:
    log.info(msg, *args, **kwargs)


def action(msg: str, *args: Any, **kwargs: Any) -> None:
    log.log(ACTION, msg, *args, **kwargs)


def warning(msg: str, *args: Any, **kwargs: Any) -> None:
    log.warning(msg, *args, **kwargs)


def error(msg: str, *args: Any, **kwargs: Any) -> None:
    log.error(msg, *args, **kwargs)
