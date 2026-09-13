"""Encryption CLI command."""

import argparse
import getpass
from pathlib import Path

from cereja.hashtools import CryptoError, encrypt_file

from ._common import CliError, ensure_output_available, run_handler


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cereja encrypt",
        description="Encrypt a file.",
    )
    parser.add_argument("input", help="File to encrypt.")
    parser.add_argument("-o", "--output", help="Output path.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output.")
    return parser


def main(argv=None) -> int:
    return run_handler(create_parser(), argv, _handle, errors=(CryptoError,))


def _handle(args) -> int:
    output_path = Path(args.output) if args.output else Path(args.input + ".enc")
    ensure_output_available(output_path, args.force)

    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise CliError("Password confirmation does not match.")

    result_path = encrypt_file(args.input, password, str(output_path))
    print(f"Encrypted: {result_path}")
    return 0
