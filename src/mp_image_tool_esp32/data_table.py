from __future__ import annotations

import re
import shlex
from itertools import zip_longest
from typing import Any, Iterable, List, NamedTuple

from rich.table import Table

from . import logger

use_rich_table: bool = True


class TableTuple(NamedTuple):
    """A tuple containing the data for a table."""

    title: str  # A title/caption for the table
    format: str  # Format string for the table fields
    header: str  # Header fields for the table
    data: Iterable[Iterable[Any]]  # The rows of the table


# Return a formatted data table as a string
def plain_table(table: TableTuple, **kwargs: Any) -> str:
    # Make a format string for the header fields, which are all strings.
    hdr_format = re.sub(
        r":([^#}0-9.,]*)#?,?(\d*)[.]?(\d*),?\w}", r":\1\2s}", table.format
    )
    if hdr_format.startswith(" "):
        hdr_format = f"#{hdr_format[1:]}"
    content: List[str] = []
    if table.title:
        content.append(table.title)
    if table.header:
        content.append(hdr_format.format(*shlex.split(table.header)))
    if table.data:
        for line in table.data:
            content.append(table.format.format(*line))
    style = (style := kwargs.get("style", "")) and f"[{style}]"
    return style + "\n".join(content)


# Return a formatted data table as a string
def rich_table(table: TableTuple, **kwargs: Any) -> Table:
    # Make a format string for the header fields, which are all strings.
    rich_table = Table(title=table.title or None, **kwargs)
    # Strip out the field width specs from the format string
    format = re.sub(r"({[^}:]*:[^0-9}]*)[0-9]*", r"\1", table.format)
    fmt = shlex.split(format)  # Split the format string into fields
    for hdr, f in zip_longest(shlex.split(table.header), fmt):
        rich_table.add_column(
            hdr or "",
            justify="right" if ">" in f else "center" if "^" in f else "left",
        )
    for line in table.data:
        rich_table.add_row(*(f.format(d) for f, d in zip_longest(fmt, line)))
    return rich_table


def print_table(table: TableTuple, rich: bool | None = None, **kwargs: Any) -> None:
    rich = rich if rich is not None else use_rich_table
    logger.console.print(
        rich_table(table, **kwargs) if rich else plain_table(table, **kwargs),
        style=kwargs.get("style"),
    )
