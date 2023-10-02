# MIT License: Copyright (c) 2023 @glenn20

import argparse

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


def parse_args(cmd_args: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    # Lines of cmd_args are like: "arguments | help | action"
    # "filename | filename for output | T" # T means action="store_true"
    # "-i --input FILE | read input from FILE"
    # "-q --quiet | suppress normal output | T"  # action="store_true"
    # opts holds all the arguments starting with "-"
    # args holds all the other arguments
    for opts, args, help, action in [
        [
            [s for s in args.split() if s[0] == "-"],  # args starting with "-"
            [s for s in args.split() if s[0] != "-"],  # other args
            help,
            action,
        ]
        for args, help, action, *_ in [  # Split each line at "|" boundaries
            [s.strip() for s in (line + "|").split("|")]
            for line in (s for s in cmd_args.strip().splitlines() if s.strip())
        ]
    ]:
        metavars = args if opts else []
        args = opts or args
        kwargs = {
            k: v
            for k, v in {
                "nargs": len(metavars) if len(metavars) > 1 else 0,
                "metavar": metavars,
                "help": help,
                "action": actions.get(action, action),
            }.items()
            if v  # Only use keywords if they have values
        }
        parser.add_argument(*args, **kwargs)

    return parser.parse_args()
