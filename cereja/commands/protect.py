"""Build import-compatible protected Python code."""

import argparse
import getpass
import os

from cereja.protect import (
    DEFAULT_KEY_ENV,
    ProtectionError,
    protect_path,
)

from ._common import CliError, run_handler


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cereja protect",
        description=(
            "Encrypt a Python module or package while "
            "preserving normal import syntax."
        ),
    )
    parser.add_argument(
        "input",
        help=(
            "Python module file or regular package "
            "directory to protect."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        default="cereja-protected",
        help=(
            "Destination import root. "
            "Default: cereja-protected."
        ),
    )
    parser.add_argument(
        "--key-env",
        default=DEFAULT_KEY_ENV,
        help=(
            "Environment variable used to obtain the "
            "runtime decryption key."
        ),
    )
    parser.add_argument(
        "--include-extension",
        action="append",
        default=[],
        metavar="EXT",
        help=(
            "Additional static extension to encrypt. "
            "May be repeated."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing protected output.",
    )
    return parser


def main(argv=None) -> int:
    return run_handler(
        create_parser(),
        argv,
        _handle,
        errors=(ProtectionError, OSError),
    )


def _handle(args) -> int:
    password = os.environ.get(args.key_env)
    if not password:
        password = getpass.getpass(
            "Protection password: "
        )
        confirmation = getpass.getpass(
            "Confirm password: "
        )
        if password != confirmation:
            raise CliError(
                "Password confirmation does not match."
            )
        if not password:
            raise CliError(
                "Protection password cannot be empty."
            )

    result = protect_path(
        args.input,
        args.output,
        password,
        key_env=args.key_env,
        static_extensions=args.include_extension,
        force=args.force,
    )
    print(f"Protected: {result}")
    print(
        "Runtime key source: "
        f"environment variable {args.key_env}"
    )
    return 0
