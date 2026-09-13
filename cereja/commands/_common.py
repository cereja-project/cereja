"""Shared primitives for command-line modules."""

import argparse
import sys
from pathlib import Path
from typing import Iterable, Type


class CliError(Exception):
    """Raised for expected command-line usage or operation errors."""


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def ensure_output_available(output_path: Path, force: bool) -> None:
    if output_path.exists() and not force:
        raise CliError(
            f"Output already exists: {output_path}. Use --force to overwrite."
        )


def run_handler(parser, argv, handler, errors: Iterable[Type[BaseException]] = ()) -> int:
    """Parse argv, run one handler and translate expected operational errors."""
    args = parser.parse_args(argv)
    caught = (
        CliError,
        FileNotFoundError,
        NotADirectoryError,
        PermissionError,
        *tuple(errors),
    )
    try:
        return handler(args)
    except caught as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
