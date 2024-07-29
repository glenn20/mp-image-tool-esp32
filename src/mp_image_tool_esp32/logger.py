# MIT License: Copyright (c) 2023 @glenn20
"""A wrapper module to provide a consistent interface for logging to console.
"""

import logging
from logging import CRITICAL, DEBUG, ERROR, INFO, NOTSET, WARNING
from typing import Any

import colorama

FORMAT = "%(message)s"
ACTION = INFO + 1
RESET = "\033[0m"
BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, GREY = (
    f"\033[3{i};20m" for i in range(8)
)
log_color = {
    DEBUG: MAGENTA,
    INFO: RESET,
    ACTION: GREEN,
    WARNING: YELLOW,
    ERROR: RED,
    CRITICAL: RED,
}
log_levels = {
    "DEBUG": DEBUG,
    "INFO": INFO,
    "ACTION": ACTION,
    "WARNING": WARNING,
    "ERROR": ERROR,
}


colorama.init()
logging.addLevelName(ACTION, "ACTION")
logging.basicConfig(format=FORMAT)
logger = logging.getLogger()  # Use the root logger
logger.setLevel(logging.INFO)


def colour(msg: str, level: int) -> str:
    return f"{log_color[level]}{msg}{RESET}"


def setLevel(level: str) -> None:
    logger.setLevel(log_levels.get(level.upper(), NOTSET))


def isloglevel(level: str) -> bool:
    return log_levels.get(level.upper(), ERROR) >= logger.getEffectiveLevel()


def _dolog(level: int, msg: str, *args: Any, **kwargs: Any) -> None:
    if msg:
        logger.log(level, colour(msg, level), *args, **kwargs)


def debug(msg: str, *args: Any, **kwargs: Any) -> None:
    _dolog(DEBUG, msg, *args, **kwargs)


def info(msg: str, *args: Any, **kwargs: Any) -> None:
    _dolog(INFO, msg, *args, **kwargs)


def action(msg: str, *args: Any, **kwargs: Any) -> None:
    _dolog(ACTION, msg, *args, **kwargs)


def warning(msg: str, *args: Any, **kwargs: Any) -> None:
    _dolog(WARNING, msg, *args, **kwargs)


def error(msg: str, *args: Any, **kwargs: Any) -> None:
    _dolog(ERROR, msg, *args, **kwargs)
