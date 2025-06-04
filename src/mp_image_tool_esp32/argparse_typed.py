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
"""

from __future__ import annotations

from argparse import ArgumentParser, Namespace
from itertools import takewhile
from typing import Any, Sequence, get_type_hints

action_aliases = {
    "S": "store",
    "T": "store_true",
    "SC": "store_const",
    "A": "append",
    "AC": "append_const",
    "C": "count",
    "H": "help",
    "V": "version",
}


# A wrapper class for argparse.ArgumentParser that uses type hints from a namespace
class TypedArgumentParser:
    def __init__(self, parser: ArgumentParser, typed_namespace: Namespace | None):
        self.parser = parser
        self.typed_namespace = typed_namespace
        # The type hints for the arguments are in the `typed_namespace`
        globalns = getattr(typed_namespace, "_globals", {})
        self.argument_types = get_type_hints(typed_namespace, globalns)
        # `typed_namespace` may also contain a type conversion function for some types
        self.type_conversions = getattr(typed_namespace, "_type_conversions", {})

    def _get_argument_type(self, argument_name: str) -> Any:
        # Get the argument type hint from the typed_namespace
        argument_type = self.argument_types.get(argument_name)
        if not argument_type:
            raise ValueError(
                f"Argument `{argument_name}` not found in {self.typed_namespace}"
            )
        # The type_conversions map may contain a function to convert the argument type
        return self.type_conversions.get(argument_type, argument_type)

    def add_argument(
        self, arguments: Sequence[str], metavars: Sequence[str], action: str, help: str
    ) -> None:
        kwargs: dict[str, Any] = {}
        # Sort out the metavar options first
        if len(metavars) > 1:
            if metavars[-1] == "...":
                kwargs["metavar"] = metavars[0]
                kwargs["nargs"] = "+"
            else:
                kwargs["metavar"] = metavars
                kwargs["nargs"] = len(metavars)
        elif len(metavars) == 1:
            kwargs["metavar"] = metavars[0]

        # Get the type hint for the argument from the typed_namespace
        argument_name = arguments[-1].lstrip("-").replace("-", "_")
        argument_type = self._get_argument_type(argument_name)
        if argument_type and argument_type not in (bool, str) and len(metavars) == 1:
            kwargs["type"] = argument_type
        elif argument_type is bool and not action:
            # default for bool, unless action or fun have been set
            action = "store_true"

        if action:  # Expand any aliases in the action name
            kwargs["action"] = action_aliases.get(action, action)
        if help:
            kwargs["help"] = help

        self.parser.add_argument(*arguments, **kwargs)


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

    # Construct a regular argparse ArgumentParser
    argparser = ArgumentParser(prog=prog, description=description, epilog=epilog)
    # Construct a TypedArgumentParser using the regular parser and the typed_namespace
    typed_parser = TypedArgumentParser(argparser, typed_namespace)

    # Process each of the arguments in the `arguments` string (one per line)
    for line in arguments.splitlines():
        # Split the line into parts: ARGUMENTS | HELP STRING | ACTION
        # eg.  "-i --ignore          | Ignore file    | T"
        argstr, help, action, *_ = (s.strip() for s in f"{line}|||".split("|", 3))

        # options contains leading words starting with "-" if any, else all words.
        # eg. "-i --input FILE" -> options = ["-i", "--input"], metavars = ["FILE"]
        # eg. "filename" -> options = ["filename"], metavars = []
        argument_names = argstr.split()
        option_names = list(takewhile(lambda s: s.startswith("-"), argument_names))
        if not option_names:
            # There are no options, so all words are argument names.
            typed_parser.add_argument(argument_names, [], action, help)
        else:
            # If an option is provided, the metavars are the rest of the words.
            metavars = argument_names[len(option_names) :]
            typed_parser.add_argument(option_names, metavars, action, help)

    return typed_parser.parser
