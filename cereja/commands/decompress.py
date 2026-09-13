"""Decompression CLI command."""

import argparse
import getpass
from pathlib import Path

from cereja.hashtools import (
    CompressionError,
    decompress_dir,
    decompress_file,
    is_encrypted_archive,
)

from ._common import ensure_output_available, run_handler


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cereja decompress",
        description="Decompress a file or directory archive.",
    )
    parser.add_argument("input", help="Compressed file or directory archive.")
    parser.add_argument("-o", "--output", help="Output path.")
    parser.add_argument(
        "--archive-type",
        choices=("auto", "file", "dir"),
        default="auto",
        help="Archive type to decompress.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing output.")
    parser.add_argument("--quiet", action="store_true", help="Disable progress output.")
    return parser


def main(argv=None) -> int:
    parser = create_parser()
    return run_handler(parser, argv, _handle, errors=(CompressionError,))


def _handle(args) -> int:
    verbose = not args.quiet
    if args.archive_type == "file":
        output_path = _file_output(args.input, args.output)
        ensure_output_available(output_path, args.force)
        result_path = _decompress_file(args.input, output_path, verbose)
    elif args.archive_type == "dir":
        output_path = _dir_output(args.input, args.output)
        ensure_output_available(output_path, args.force)
        result_path = _decompress_dir(args.input, output_path, verbose)
    else:
        result_path = _decompress_auto(args)

    print(f"Decompressed: {result_path}")
    return 0


def _password(input_path: str):
    if not is_encrypted_archive(input_path):
        return None
    return getpass.getpass("Password: ")


def _decompress_file(input_path: str, output_path: Path, verbose: bool):
    password = _password(input_path)
    if password is None:
        return decompress_file(input_path, str(output_path), verbose=verbose)
    return decompress_file(
        input_path,
        str(output_path),
        verbose=verbose,
        password=password,
    )


def _decompress_dir(input_path: str, output_path: Path, verbose: bool):
    password = _password(input_path)
    if password is None:
        return decompress_dir(input_path, str(output_path), verbose=verbose)
    return decompress_dir(
        input_path,
        str(output_path),
        verbose=verbose,
        password=password,
    )


def _decompress_auto(args, password=None):
    file_output = _file_output(args.input, args.output)
    ensure_output_available(file_output, args.force)
    verbose = not args.quiet
    if password is None:
        password = _password(args.input)

    try:
        if password is None:
            return decompress_file(args.input, str(file_output), verbose=verbose)
        return decompress_file(
            args.input,
            str(file_output),
            verbose=verbose,
            password=password,
        )
    except CompressionError:
        dir_output = _dir_output(args.input, args.output)
        ensure_output_available(dir_output, args.force)
        if password is None:
            return decompress_dir(args.input, str(dir_output), verbose=verbose)
        return decompress_dir(
            args.input,
            str(dir_output),
            verbose=verbose,
            password=password,
        )


def _file_output(input_path: str, output_path) -> Path:
    if output_path:
        return Path(output_path)
    if input_path.endswith(".cjz"):
        return Path(input_path[:-4])
    return Path(input_path + ".decompressed")


def _dir_output(input_path: str, output_path) -> Path:
    if output_path:
        return Path(output_path)
    if input_path.endswith(".cjz"):
        return Path(input_path[:-4])
    return Path(input_path + "_extracted")
