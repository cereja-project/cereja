"""Compression CLI command."""

import argparse
import getpass
from pathlib import Path

from cereja.hashtools import CompressionError, compress_dir, compress_file

from ._common import CliError, ensure_output_available, run_handler

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


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cereja compress",
        description="Compress a file or directory.",
    )
    parser.add_argument("input", help="File or directory to compress.")
    parser.add_argument("-o", "--output", help="Output path.")
    parser.add_argument(
        "--strategy",
        choices=COMPRESSION_STRATEGIES,
        default="auto",
        help="Compression strategy.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing output.")
    parser.add_argument("--quiet", action="store_true", help="Disable progress output.")
    parser.add_argument(
        "--encrypt",
        action="store_true",
        help="Encrypt the compressed archive.",
    )
    return parser


def main(argv=None) -> int:
    parser = create_parser()
    return run_handler(parser, argv, _handle, errors=(CompressionError,))


def _handle(args) -> int:
    input_path = Path(args.input)
    verbose = not args.quiet
    password = _prompt_new_password() if args.encrypt else None

    if input_path.is_dir():
        output_path = _compressed_dir_output(input_path, args.output)
        ensure_output_available(output_path, args.force)
        kwargs = {"strategy": args.strategy, "verbose": verbose}
        if password is not None:
            kwargs["password"] = password
        result_path, stats = compress_dir(
            str(input_path),
            str(output_path),
            **kwargs,
        )
    else:
        output_path = _compressed_file_output(input_path, args.output)
        ensure_output_available(output_path, args.force)
        kwargs = {"strategy": args.strategy, "verbose": verbose}
        if password is not None:
            kwargs["password"] = password
        result_path, stats = compress_file(
            str(input_path),
            str(output_path),
            **kwargs,
        )

    _print_result(result_path, stats)
    return 0


def _prompt_new_password() -> str:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise CliError("Password confirmation does not match.")
    return password


def _ensure_cjz_suffix(output_path: Path) -> Path:
    if output_path.suffix:
        return output_path
    return output_path.with_name(output_path.name + ".cjz")


def _compressed_dir_output(input_path: Path, output_path) -> Path:
    if output_path:
        return _ensure_cjz_suffix(Path(output_path))
    if str(input_path) in (".", ""):
        return Path(input_path.resolve().name + ".cjz")
    return Path(str(input_path).rstrip("/\\") + ".cjz")


def _compressed_file_output(input_path: Path, output_path) -> Path:
    if output_path:
        return _ensure_cjz_suffix(Path(output_path))
    return Path(str(input_path) + ".cjz")


def _print_result(result_path: str, stats) -> None:
    print(f"Compressed: {result_path}")
    print(f"Strategy: {stats.strategy.value}")
    print(f"Original size: {stats.original_size} bytes")
    print(f"Compressed size: {stats.compressed_size} bytes")
    print(f"Ratio: {stats.ratio:.2f}x")
    print(f"Savings: {stats.savings_percent:.2f}%")
