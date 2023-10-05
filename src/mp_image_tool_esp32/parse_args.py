# MIT License: Copyright (c) 2023 @glenn20

import argparse
from itertools import takewhile

MB = 0x100_000  # 1 Megabyte
KB = 0x400  # 1 Kilobyte
B = 0x1_000  # 1 Block (4096 bytes)
SIZE_UNITS = {"M": MB, "K": KB, "B": B}

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


# arguments is a multiline string of the form:
# progname
# Description paragraph
#
# argument1               | help string     | action
# argument2               | help string     | action
# -a --option1            | help string     | action
# -b --option2 NAME       | help string     | action
# ...
# Where action is a key from actions dict above.
def parser(arguments: str) -> argparse.ArgumentParser:
    # Split the arguments string up into lines for processing
    lines = (s.strip() for s in arguments.strip().splitlines())
    prog = next(lines)
    description = " ".join(takewhile(lambda s: s, lines))
    parser = argparse.ArgumentParser(prog=prog, description=description)

    # Lines of cmd_args are like: "arguments | help | action"
    # "filename | filename for output | T" # T means action="store_true"
    # "-i --input FILE | read input from FILE"
    # "-q --quiet | suppress normal output | T"  # action="store_true"
    # opts holds all the arguments starting with "-"
    # metavars holds all the other arguments
    for opts, metavars, help, action in [
        [
            [s for s in args.split() if s[0] == "-"],  # args starting with "-"
            [s for s in args.split() if s[0] != "-"],  # other args
            help,
            action,
        ]
        for args, help, action, *_ in [  # Split each line at "|" boundaries
            [s.strip() for s in (line + "||").split("|")] for line in lines
        ]
    ]:
        if not opts:  # No options - use metavars as list of options
            opts = metavars
            metavars = []
        kwargs = {
            k: v
            for k, v in {
                "nargs": len(metavars) if len(metavars) > 1 else 0,
                "metavar": metavars[0] if len(metavars) == 1 else metavars,
                "help": help,
                "action": actions.get(action, action),
            }.items()
            if v  # Only use keywords if they have values
        }
        parser.add_argument(*opts, **kwargs)

    return parser
