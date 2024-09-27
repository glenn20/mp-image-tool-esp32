# MIT License: Copyright (c) 2023 @glenn20
"""A wrapper module to provide a consistent interface for logging to console."""

import logging
import typing
from typing import Any

import esptool
import littlefs
import serial
from rich.console import Console, ConsoleRenderable
from rich.highlighter import NullHighlighter
from rich.logging import RichHandler
from rich.theme import Theme

FORMAT = "%(message)s"  # Just print the message
ACTION = logging.INFO + 1  # Add a new level for logging ACTIONs

log_styles = {  # Colours used by the different log level themes
    "debug": "magenta",
    "info": "",
    "action": "green",
    "warning": "yellow",
    "error": "red",
    "critical": "red",
}
console = Console(
    theme=Theme(  # Set the themes for the different log levels
        {f"logging.level.{level}": colour for level, colour in log_styles.items()}
    ),
    highlight=False,
    soft_wrap=True,
)


class Handler(RichHandler):
    # Override the render_message method to add color to the log messages
    def render_message(
        self, record: logging.LogRecord, message: str
    ) -> ConsoleRenderable:
        return super().render_message(
            record, f"[logging.level.{record.levelname.lower()}]{message}"
        )


# Create a RichHandler with a custom themed console
richhandler = Handler(
    console=console,
    highlighter=NullHighlighter(),
    markup=True,
    show_time=False,  # Don't show the timem level or path in log messages
    show_level=False,
    show_path=False,
    rich_tracebacks=True,
    tracebacks_suppress=[esptool, serial, littlefs],
)
richhandler.setFormatter(logging.Formatter(FORMAT))


# Extend the Logger class to add a new level for logging ACTIONs
# This class is never instantiated, but is used to satisfy the type checker
# for the patching we do to the Logger objects. The action method is also
# patched into the Logger class below.
class ExtendedLogger(logging.Logger):
    def action(self, message: str, *args: Any, **kwargs: Any) -> None:
        if self.isEnabledFor(ACTION):
            self._log(ACTION, message, args, **kwargs)


logging.addLevelName(ACTION, "ACTION")
# Patch the ACTION constant into the logging module
setattr(logging, "ACTION", ACTION)  # Add logging.ACTION to the logging module
# Patch an `action()` method into the Logger class
setattr(logging.getLoggerClass(), "action", ExtendedLogger.action)


def getLogger(name: str) -> ExtendedLogger:
    """Wrapper around logging.getLogger() to satisfy the type checker.
    Returns an ExtendedLogger object with an additional `action()` method.
    """
    logger = logging.getLogger(name)
    return typing.cast(ExtendedLogger, logger)


def set_logging(config: str) -> None:
    """Set the logging level for the loggers specified in `config`.
    If `config` is "show", "list", or "help", list the available loggers.
    """
    if config in ("show", "list", "help"):
        print(f"Available loggers: {list(logging.root.manager.loggerDict.keys())}")
    else:
        for name, level in (s.split("=", 1) for s in config.split(",")):
            logging.getLogger(name).setLevel(level.upper())
