# MIT License: Copyright (c) 2023 @glenn20

import re
import typing
from argparse import ArgumentParser, Namespace
from itertools import takewhile
from typing import Any, Iterable

from .common import KB, MB, B

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


def arglist(arg: str) -> list[list[str]]:
    """Split command line arguments into a list of list of strings.
    The string is delimited first by "," and then by "=", ":" or "-".
    eg: `"nvs=nvs.bin,vfs=vfs.bin"` -> `[["nvs", "nvs.bin"], ["vfs", "vfs.bin"]]`
    """
    return [re.split(DELIMITERS[1], s) for s in re.split(DELIMITERS[0], arg.strip())]


def partlist(arg: str) -> list[tuple[str, str, int, int]]:
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
# Where action is a key from actions dict above (optional).
# dataclass is a class containing the type hints for the arguments.
# It should have one field for each argument name provided in arguments.
def parser(usage: str, typed_namespace: Namespace | None = None) -> ArgumentParser:
    """Create an argparse.ArgumentParser from a string containing the prog name,
    description, arguments and epilog.

    The names, metavars and help strings for each argument are extracted from
    `arguments`. The type hints and conversion functions for each argument are
    extracted from `typed_namespace`.

    Args:
        usage (str): a single string containing the progname, description, \
            arguments and epilog for the ArgumentParser as separate paragraphs.
        typed_namespace (argparse.Namespace): contains the type hints for the \
            arguments.
    """
    # Split the arguments string up into sections: preamble, body, epilog
    prog, description, arguments, epilog = (
        paragraph.strip() for paragraph in f"{usage}\n\n".split("\n\n", 3)
    )
    parser = ArgumentParser(
        prog=prog,
        description=description,
        epilog=epilog,
    )

    # Mapping of argument name to type - from the typed_namespace type info
    type_list = typing.get_type_hints(typed_namespace) if typed_namespace else {}
    # Mapping from types to functions which convert strings to that type
    type_mapper = getattr(typed_namespace, "type_mapper", {})

    # For each line of arguments, split into fields and add to the parser.
    for args, help, action in [  # list[str], str, str
        (argstr.split(), help, action)
        for argstr, help, action, *_ in (
            (s.strip() for s in (line + "||").split("|"))  # split into fields
            for line in arguments.splitlines()
        )
    ]:
        # opts contains args starting with "-" if any, else all args.
        # metavars contains trailing args not in opts.
        # "-i --input FILE" -> opts = ["-i", "--input"], metavars = ["FILE"]
        # "filename" -> opts = ["filename"], metavars = []
        opts = list(takewhile(lambda s: s.startswith("-"), args)) or args
        metavars = args[len(opts) :]

        # Construct the keyword arguments for parser.add_argument...
        kwargs: dict[str, Any] = {}
        if len(metavars) > 1:
            kwargs["metavar"] = metavars
            kwargs["nargs"] = len(metavars)
        elif len(metavars) == 1:
            kwargs["metavar"] = metavars[0]

        # Use type information in the typed_namespace to get the arg type
        name: str = opts[-1].lstrip("-").replace("-", "_")
        typ: type | None = type_list.get(name)  # Get type from typed_namespace
        if fun := type_mapper.get(typ):
            # A type conversion function was provided in type_mapper
            kwargs["type"] = fun
        elif typ and typ not in (bool, str):
            # If no function given in type_mapper, use type constructor itself
            kwargs["type"] = typ
        elif typ == bool and not action:
            # default for bool, unless action or fun have been set
            action = "store_true"
        if action:
            # Convert from aliases in actions dict to full name
            kwargs["action"] = actions.get(action, action)
        if help:
            kwargs["help"] = help

        parser.add_argument(*opts, **kwargs)

    return parser
