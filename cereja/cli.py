"""
Command-line interface for Cereja.

Copyright (c) 2019 The Cereja Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import argparse
import getpass
import sys
from pathlib import Path
from typing import Optional, Sequence

from cereja import get_version_pep440_compliant
from cereja.config import BASE_DIR
from cereja.file import FileIO
from cereja.hashtools import (
    CompressionError,
    CryptoError,
    compress_dir,
    compress_file,
    decompress_dir,
    decompress_file,
    decrypt_file,
    encrypt_file,
)

COMPRESSION_STRATEGIES = (
    "auto",
    "dict",
    "rle",
    "delta",
    "bitpack",
    "zlib",
    "bz2",
    "lzma",
    "hybrid",
)


class CliError(Exception):
    """Raised for expected command-line usage errors."""


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the Cereja command-line interface."""
    parser = create_parser()
    args = parser.parse_args(argv)

    try:
        if args.startmodule:
            return _start_module(args.startmodule)

        command = getattr(args, "command", None)
        if command is None:
            parser.print_help()
            return 0

        return args.handler(args)
    except (CliError, CompressionError, CryptoError, FileNotFoundError, NotADirectoryError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser used by the CLI."""
    parser = argparse.ArgumentParser(prog="cereja", description="Cereja Tools.")
    parser.add_argument("--version", action="version", version=get_version_pep440_compliant())
    parser.add_argument("--startmodule", type=str, help="Scaffold a new Cereja module.")

    subparsers = parser.add_subparsers(dest="command")

    compress_parser = subparsers.add_parser("compress", help="Compress a file or directory.")
    compress_parser.add_argument("input", help="File or directory to compress.")
    compress_parser.add_argument("-o", "--output", help="Output path.")
    compress_parser.add_argument(
        "--strategy",
        choices=COMPRESSION_STRATEGIES,
        default="auto",
        help="Compression strategy.",
    )
    compress_parser.add_argument("--force", action="store_true", help="Overwrite existing output.")
    compress_parser.add_argument("--quiet", action="store_true", help="Disable progress output.")
    compress_parser.set_defaults(handler=_handle_compress)

    decompress_parser = subparsers.add_parser("decompress", help="Decompress a file or directory archive.")
    decompress_parser.add_argument("input", help="Compressed file or directory archive.")
    decompress_parser.add_argument("-o", "--output", help="Output path.")
    decompress_parser.add_argument(
        "--archive-type",
        choices=("auto", "file", "dir"),
        default="auto",
        help="Archive type to decompress.",
    )
    decompress_parser.add_argument("--force", action="store_true", help="Overwrite existing output.")
    decompress_parser.add_argument("--quiet", action="store_true", help="Disable progress output.")
    decompress_parser.set_defaults(handler=_handle_decompress)

    encrypt_parser = subparsers.add_parser("encrypt", help="Encrypt a file.")
    encrypt_parser.add_argument("input", help="File to encrypt.")
    encrypt_parser.add_argument("-o", "--output", help="Output path.")
    encrypt_parser.add_argument("--force", action="store_true", help="Overwrite existing output.")
    encrypt_parser.set_defaults(handler=_handle_encrypt)

    decrypt_parser = subparsers.add_parser("decrypt", help="Decrypt a file.")
    decrypt_parser.add_argument("input", help="File to decrypt.")
    decrypt_parser.add_argument("-o", "--output", help="Output path.")
    decrypt_parser.add_argument("--force", action="store_true", help="Overwrite existing output.")
    decrypt_parser.set_defaults(handler=_handle_decrypt)

    return parser


def _handle_compress(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    verbose = not args.quiet
    if input_path.is_dir():
        output_path = _compressed_dir_output(input_path, args.output)
        _ensure_output_available(output_path, args.force)
        result_path, stats = compress_dir(str(input_path), str(output_path), strategy=args.strategy, verbose=verbose)
    else:
        output_path = _compressed_file_output(input_path, args.output)
        _ensure_output_available(output_path, args.force)
        result_path, stats = compress_file(str(input_path), str(output_path), strategy=args.strategy, verbose=verbose)

    _print_compression_result(result_path, stats)
    return 0


def _handle_decompress(args: argparse.Namespace) -> int:
    verbose = not args.quiet
    if args.archive_type == "file":
        output_path = _decompressed_file_output(args.input, args.output)
        _ensure_output_available(output_path, args.force)
        result_path = decompress_file(args.input, str(output_path), verbose=verbose)
    elif args.archive_type == "dir":
        output_path = _decompressed_dir_output(args.input, args.output)
        _ensure_output_available(output_path, args.force)
        result_path = decompress_dir(args.input, str(output_path), verbose=verbose)
    else:
        result_path = _decompress_auto(args)

    print(f"Decompressed: {result_path}")
    return 0


def _handle_encrypt(args: argparse.Namespace) -> int:
    output_path = Path(args.output) if args.output else Path(args.input + ".enc")
    _ensure_output_available(output_path, args.force)

    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise CliError("Password confirmation does not match.")

    result_path = encrypt_file(args.input, password, str(output_path))
    print(f"Encrypted: {result_path}")
    return 0


def _handle_decrypt(args: argparse.Namespace) -> int:
    output_path = _decrypted_file_output(args.input, args.output)
    _ensure_output_available(output_path, args.force)

    password = getpass.getpass("Password: ")
    result_path = decrypt_file(args.input, password, str(output_path))
    print(f"Decrypted: {result_path}")
    return 0


def _decompress_auto(args: argparse.Namespace) -> str:
    file_output = _decompressed_file_output(args.input, args.output)
    _ensure_output_available(file_output, args.force)
    verbose = not args.quiet

    try:
        return decompress_file(args.input, str(file_output), verbose=verbose)
    except CompressionError:
        dir_output = _decompressed_dir_output(args.input, args.output)
        _ensure_output_available(dir_output, args.force)
        return decompress_dir(args.input, str(dir_output), verbose=verbose)


def _ensure_cjz_suffix(output_path: Path) -> Path:
    if output_path.suffix:
        return output_path
    return output_path.with_name(output_path.name + ".cjz")


def _compressed_dir_output(input_path: Path, output_path: Optional[str]) -> Path:
    if output_path:
        return _ensure_cjz_suffix(Path(output_path))

    if str(input_path) in (".", ""):
        return Path(input_path.resolve().name + ".cjz")

    return Path(str(input_path).rstrip("/\\") + ".cjz")


def _compressed_file_output(input_path: Path, output_path: Optional[str]) -> Path:
    if output_path:
        return _ensure_cjz_suffix(Path(output_path))
    return Path(str(input_path) + ".cjz")


def _decompressed_file_output(input_path: str, output_path: Optional[str]) -> Path:
    if output_path:
        return Path(output_path)
    if input_path.endswith(".cjz"):
        return Path(input_path[:-4])
    return Path(input_path + ".decompressed")


def _decompressed_dir_output(input_path: str, output_path: Optional[str]) -> Path:
    if output_path:
        return Path(output_path)
    if input_path.endswith(".cjz"):
        return Path(input_path[:-4])
    return Path(input_path + "_extracted")


def _decrypted_file_output(input_path: str, output_path: Optional[str]) -> Path:
    if output_path:
        return Path(output_path)
    if input_path.endswith(".enc"):
        return Path(input_path[:-4])
    return Path(input_path + ".dec")


def _ensure_output_available(output_path: Path, force: bool) -> None:
    if output_path.exists() and not force:
        raise CliError(f"Output already exists: {output_path}. Use --force to overwrite.")


def _print_compression_result(result_path: str, stats) -> None:
    print(f"Compressed: {result_path}")
    print(f"Strategy: {stats.strategy.value}")
    print(f"Original size: {stats.original_size} bytes")
    print(f"Compressed size: {stats.compressed_size} bytes")
    print(f"Ratio: {stats.ratio:.2f}x")
    print(f"Savings: {stats.savings_percent:.2f}%")


def _start_module(module_path: str) -> int:
    base_dir = Path(BASE_DIR)
    license_text = b"".join(FileIO.load(base_dir.parent / "LICENSE").data).decode()
    license_text = '"""\n' + license_text + '"""'
    new_module_path = base_dir.joinpath(*module_path.split("/"))

    if new_module_path.parent.exists() and new_module_path.parent.is_dir():
        FileIO.create(new_module_path, license_text).save()
        return 0

    raise CliError(f"{new_module_path} is not valid.")
