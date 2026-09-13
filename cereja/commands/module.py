"""Cereja module scaffolding CLI command."""

import argparse
from pathlib import Path

from cereja.config import BASE_DIR
from cereja.file import FileIO

from ._common import CliError, run_handler


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cereja module",
        description="Manage Cereja module scaffolding.",
    )
    subparsers = parser.add_subparsers(dest="module_command", required=True)
    create = subparsers.add_parser("create", help="Scaffold a new Cereja module.")
    create.add_argument("path", help="Module path relative to the Cereja package.")
    create.set_defaults(handler=_handle_create)
    return parser


def main(argv=None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    return run_handler(parser, argv, lambda _args: _args.handler(_args))


def _handle_create(args) -> int:
    base_dir = Path(BASE_DIR)
    license_text = b"".join(FileIO.load(base_dir.parent / "LICENSE").data).decode()
    license_text = '"""\n' + license_text + '"""'
    new_module_path = base_dir.joinpath(*args.path.split("/"))

    if new_module_path.parent.exists() and new_module_path.parent.is_dir():
        FileIO.create(new_module_path, license_text).save()
        return 0

    raise CliError(f"{new_module_path} is not valid.")
