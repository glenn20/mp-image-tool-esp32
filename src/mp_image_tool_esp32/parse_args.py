# MIT License: Copyright (c) 2023 @glenn20
"""
Provides functions to streamline and enhance the use of `argparse` to process
command line arguments.

Provides the `parser(usage, typed_namespace)` function which returns an
`ArgumentParser`.

`parser()` uses the `usage` string and `typed_namespace` together to provide:

1. static type checking for the fields in namespace returned by
   `argparse.parse_args()`.
2. automatic conversion of string arguments to the correct type (using the
   `type=` keyword of `argparse.add_argument()`).
3. an overly-elaborate method for avoiding the boilerplate of
   `argparse.add_argument()` which also makes the command usage easier for
   humans to parse from the code.

Also includes some argument type conversion helper functions:
- `numeric_arg(arg)`: Convert a string to an integer number of bytes.
- `arglist(arg)`: Split a string into a list of lists of strings.
- `partlist(arg)`: Split a string into a list of tuples describing a Partition.
- `unsplit(arglist)`: Join a list of lists of strings or ints back into a single
  string.
"""
from __future__ import annotations

import re
import typing
from argparse import ArgumentParser, Namespace
from itertools import takewhile
from typing import Any, Iterable

from .common import KB, MB, B
from .types import ArgList, PartList

actions = {
    "S": "store",
    "T": "store_true",
    "SC": "store_const",
    "A": "append",
    "AC": "append_const",
    "C": "count",
    "H": "help",
    "V": "version",
}

# Convert suffixes to multipliers for convenient units of size.
SIZE_UNITS = {"M": MB, "K": KB, "B": B}

# Delimiters for splitting up and stripping values of command arguments
# First level split is on "," and then on "=" or ":" or "-"
DELIMITERS = [r"\s*,\s*", r"\s*[=:-]\s*"]


# Process a string containing a number with an optional unit suffix
# eg. "8M" (8 megabytes), "0x10B" (16 disk blocks), "4K" (4 kilobytes)
def numeric_arg(arg: str) -> int:
    """Convert a string to an integer number of bytes.
    The string may contain a decimal or hex number and an optional unit suffix:
    "M"=megabytes, "K"=kilobyte or "B"=blocks (4096=0x1000).

    Eg: `"8M"` (8 megabytes), `"0x1fB"` (31 disk blocks = 0x1f000), `"4k"` (4
    kilobytes).
    """
    if not arg:
        return 0
    if (unit := SIZE_UNITS.get(arg[-1].upper(), 1)) != 1:
        arg = arg[:-1]
    return int(arg, 0) * unit  # Allow numbers in decimal or hex


def arglist(arg: str) -> ArgList:
    """Split command line arguments into a list of list of strings.
    The string is delimited first by "," and then by "=", ":" or "-".
    eg: `"nvs=nvs.bin,vfs=vfs.bin"` -> `[["nvs", "nvs.bin"], ["vfs", "vfs.bin"]]`
    """
    return [re.split(DELIMITERS[1], s) for s in re.split(DELIMITERS[0], arg.strip())]


def partlist(arg: str) -> PartList:
    """Split a command line argument into a list of tuples describing a
    Partition: `[(name, subtype_name, offset, size),...]`.

    The string is delimited first by "," and then by "=", ":" or "-". Offset,
    subtype_name and size may be omitted (in that order).

    Eg: `"factory=factory:7B:2M,vfs=1M"` -> `[("factory", "factory", 0x7000,
    0x200000),("vfs", "", 0, 0x100000)]`.
    """
    return [
        (
            name,
            rest[0] if len(rest) >= 2 else "",
            numeric_arg(rest[1]) if len(rest) >= 3 else 0,
            numeric_arg(rest[-1]) if len(rest) >= 1 else 0,
        )
        for (name, *rest) in arglist(arg)
    ]


def unsplit(arglist: Iterable[Iterable[str | int]]) -> str:
    """Join a list of lists of strings or ints into a single string
    delimited by "," and then "="."""
    return ",".join("=".join(str(s) for s in x if s) for x in arglist)


# A wrapper class for ArgumentParser that uses type hints from a namespace
class TypedArgumentParser:
    def __init__(self, parser: ArgumentParser, typed_namespace: Namespace | None):
        self.parser = parser
        self.typed_namespace = typed_namespace
        # The type hints for the arguments are in the `typed_namespace`
        self.argument_types = typing.get_type_hints(typed_namespace)
        # `typed_namespace` may also contain a type conversion function for some types
        self.type_mapper = getattr(typed_namespace, "_type_mapper", {})

    def _get_argument_type(self, name: str) -> Any:
        # Get the field name by replacing "-" with "_" in the last word of options
        name = name.lstrip("-").replace("-", "_")
        argtype = self.argument_types.get(name)  # Get the argument type hint
        if not argtype:
            raise ValueError(f"Argument `{name}` not found in {self.typed_namespace}")
        # The type_mapper may contain a function to convert the argument type
        return self.type_mapper.get(argtype, argtype)

    def add_argument(self, line: str) -> None:
        argstr, help, action, *_ = (s.strip() for s in f"{line}|||".split("|", 3))

        # options contains leading words starting with "-" if any, else all words.
        # eg. "-i --input FILE" -> opts = ["-i", "--input"], metavars = ["FILE"]
        # eg. "filename" -> opts = ["filename"], metavars = []
        words = argstr.split()
        options = list(takewhile(lambda s: s.startswith("-"), words)) or words
        metavars = words[len(options) :]  # trailing words not in options.
        kwargs: dict[str, Any] = {}
        if len(metavars) > 1:
            kwargs.update({"metavar": metavars, "nargs": len(metavars)})
        elif len(metavars) == 1:
            kwargs.update({"metavar": metavars[0]})

        # Get the type hint for the argument from the typed_namespace
        argtype = self._get_argument_type(options[-1])
        if argtype and argtype not in (bool, str):
            kwargs["type"] = argtype
        elif argtype == bool and not action:
            # default for bool, unless action or fun have been set
            action = "store_true"

        if action:
            # Convert from aliases in actions dict to full name
            kwargs["action"] = actions.get(action, action)
        if help:
            kwargs["help"] = help

        self.parser.add_argument(*options, **kwargs)


# usage is a multiline string of the form:
# """
# progname
#
# Description paragraph
#
# argument1                | help string     | action
# argument2                | help string
# -a --option1             | help string     | action
# -b --option2 NAME        | help string
# -c --option3 NAME1,NAME2 | help string
# ...
# """

# Where `action` is an argparse action or an abbreviationfrom actions dict above
# (optional). `typed_namespace` is a class containing the type hints for the
# arguments. It should have one field for each argument name provided in
# arguments.
def parser(usage: str, typed_namespace: Namespace | None = None) -> ArgumentParser:
    """Construct an argparse.ArgumentParser from a string containing the prog name,
    description, arguments and epilog.

    The names, metavars and help strings for each argument are extracted from
    `usage`. The type hints and conversion functions for each argument are
    extracted from `typed_namespace`.

    Args:
        usage (str): a single multi-line string containing the progname, \
            description, arguments and epilog for the ArgumentParser as \
            separate paragraphs.
        typed_namespace (argparse.Namespace): contains the type hints for the \
            arguments.

    Returns:
        ArgumentParser: an argparse.ArgumentParser object with the arguments added.
    """
    # Split the usage string up into sections: program, description, body, epilog
    prog, description, arguments, epilog = (
        paragraph.strip() for paragraph in f"{usage}\n\n".split("\n\n", 3)
    )
    parser = TypedArgumentParser(
        ArgumentParser(prog=prog, description=description, epilog=epilog),
        typed_namespace,
    )

    # Process each of the arguments in the `arguments` string (one per line)
    for line in arguments.splitlines():
        parser.add_argument(line)

    return parser.parser
