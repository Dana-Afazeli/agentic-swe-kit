"""The console as an output boundary: the only place in the sample that writes to stdout."""

import sys


def write(line: str) -> None:
    sys.stdout.write(line + "\n")
