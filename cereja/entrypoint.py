"""Top-level command dispatcher for Cereja."""

import argparse
import importlib
import sys
from typing import Optional, Sequence

from cereja._version import __version__
from cereja.commands.registry import COMMANDS, get_command


def create_parser() -> argparse.ArgumentParser:
    """Create the lightweight root parser without importing commands."""
    parser = argparse.ArgumentParser(prog="cereja", description="Cereja Tools.")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--startmodule",
        metavar="PATH",
        help="Legacy alias for `cereja module create PATH`.",
    )
    subparsers = parser.add_subparsers(dest="command")
    for command in COMMANDS:
        subparsers.add_parser(command.name, help=command.help, add_help=False)
    return parser


def _dispatch(command_name: str, argv: Sequence[str]) -> int:
    command = get_command(command_name)
    module = importlib.import_module(command.module)
    return module.main(list(argv))


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Dispatch one command while keeping unrelated implementations unloaded."""
    args = list(sys.argv[1:] if argv is None else argv)
    parser = create_parser()
    namespace, remaining = parser.parse_known_args(args)

    if namespace.startmodule is not None:
        if namespace.command is not None or remaining:
            parser.error("--startmodule cannot be combined with another command")
        return _dispatch("module", ["create", namespace.startmodule])

    if namespace.command is None:
        parser.print_help()
        return 0

    return _dispatch(namespace.command, remaining)
