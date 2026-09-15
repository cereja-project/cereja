"""Decryption CLI command."""

import argparse
import getpass
from pathlib import Path

from cereja.hashtools import CryptoError, decrypt_file

from ._common import ensure_output_available, run_handler


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cereja decrypt",
        description="Decrypt a file.",
    )
    parser.add_argument("input", help="File to decrypt.")
    parser.add_argument("-o", "--output", help="Output path.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output.")
    return parser


def main(argv=None) -> int:
    return run_handler(create_parser(), argv, _handle, errors=(CryptoError,))


def _handle(args) -> int:
    output_path = _output(args.input, args.output)
    ensure_output_available(output_path, args.force)
    password = getpass.getpass("Password: ")
    result_path = decrypt_file(args.input, password, str(output_path), overwrite=args.force)
    print(f"Decrypted: {result_path}")
    return 0


def _output(input_path: str, output_path) -> Path:
    if output_path:
        return Path(output_path)
    if input_path.endswith(".enc"):
        return Path(input_path[:-4])
    return Path(input_path + ".dec")
