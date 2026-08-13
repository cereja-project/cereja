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
import json
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
    is_encrypted_archive,
)
from cereja.system import (
    clear_context_cache,
    context_response_to_dict,
    get_context_cache_info,
    list_text_context,
    render_repository_tree,
    search_text_context,
)
from cereja.system._context.cache_db import CacheDatabaseError

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
    except (
        CliError,
        CompressionError,
        CryptoError,
        FileNotFoundError,
        NotADirectoryError,
        PermissionError,
    ) as exc:
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
    compress_parser.add_argument("--encrypt", action="store_true", help="Encrypt the compressed archive.")
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

    tree_parser = subparsers.add_parser("tree", help="Draw a repository tree.")
    tree_parser.add_argument("path", nargs="?", default=".", help="Root directory.")
    tree_parser.add_argument("--depth", type=_non_negative_int, help="Maximum depth.")
    tree_parser.set_defaults(handler=_handle_tree)

    context_parser = subparsers.add_parser(
        "context", help="Search or list bounded textual context."
    )
    context_subparsers = context_parser.add_subparsers(
        dest="context_command", required=True
    )
    context_search_parser = context_subparsers.add_parser(
        "search", help="Search textual context."
    )
    _add_context_common_options(context_search_parser)
    context_search_parser.add_argument("--query", required=True, help="Search terms.")
    context_search_parser.add_argument(
        "--max-snippets", type=_positive_int, default=2,
        help="Maximum snippets per result."
    )
    context_search_parser.add_argument(
        "--max-snippet-chars", type=_positive_int, default=240,
        help="Maximum characters per snippet."
    )
    context_search_parser.set_defaults(handler=_handle_context_search)

    context_list_parser = context_subparsers.add_parser(
        "list", help="List textual file metadata."
    )
    _add_context_common_options(context_list_parser)
    context_list_parser.set_defaults(handler=_handle_context_list)

    context_cache_parser = context_subparsers.add_parser(
        "cache", help="Manage the textual context cache."
    )
    context_cache_subparsers = context_cache_parser.add_subparsers(
        dest="context_cache_command", required=True
    )
    context_cache_info_parser = context_cache_subparsers.add_parser(
        "info", help="Show textual context cache information."
    )
    _add_context_cache_format_option(context_cache_info_parser)
    context_cache_info_parser.set_defaults(handler=_handle_context_cache_info)

    context_cache_clear_parser = context_cache_subparsers.add_parser(
        "clear", help="Clear the textual context cache."
    )
    _add_context_cache_format_option(context_cache_clear_parser)
    context_cache_clear_parser.set_defaults(handler=_handle_context_cache_clear)

    return parser


def _handle_compress(args: argparse.Namespace) -> int:
    input_path = Path(args.input)
    verbose = not args.quiet
    password = _prompt_new_password() if args.encrypt else None
    if input_path.is_dir():
        output_path = _compressed_dir_output(input_path, args.output)
        _ensure_output_available(output_path, args.force)
        if password is None:
            result_path, stats = compress_dir(str(input_path), str(output_path), strategy=args.strategy, verbose=verbose)
        else:
            result_path, stats = compress_dir(
                str(input_path),
                str(output_path),
                strategy=args.strategy,
                verbose=verbose,
                password=password,
            )
    else:
        output_path = _compressed_file_output(input_path, args.output)
        _ensure_output_available(output_path, args.force)
        if password is None:
            result_path, stats = compress_file(str(input_path), str(output_path), strategy=args.strategy, verbose=verbose)
        else:
            result_path, stats = compress_file(
                str(input_path),
                str(output_path),
                strategy=args.strategy,
                verbose=verbose,
                password=password,
            )

    _print_compression_result(result_path, stats)
    return 0


def _handle_decompress(args: argparse.Namespace) -> int:
    verbose = not args.quiet
    if args.archive_type == "file":
        output_path = _decompressed_file_output(args.input, args.output)
        _ensure_output_available(output_path, args.force)
        password = _prompt_existing_password(args.input)
        if password is None:
            result_path = decompress_file(args.input, str(output_path), verbose=verbose)
        else:
            result_path = decompress_file(args.input, str(output_path), verbose=verbose, password=password)
    elif args.archive_type == "dir":
        output_path = _decompressed_dir_output(args.input, args.output)
        _ensure_output_available(output_path, args.force)
        password = _prompt_existing_password(args.input)
        if password is None:
            result_path = decompress_dir(args.input, str(output_path), verbose=verbose)
        else:
            result_path = decompress_dir(args.input, str(output_path), verbose=verbose, password=password)
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


def _handle_tree(args: argparse.Namespace) -> int:
    _print_tree(render_repository_tree(args.path, depth=args.depth))
    return 0


def _add_context_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root", action="append", required=True, help="Explicit root directory."
    )
    parser.add_argument(
        "--extension", action="append", help="File suffix to include; repeatable."
    )
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format."
    )
    parser.add_argument(
        "--max-results", type=_positive_int, default=10,
        help="Maximum returned files."
    )
    parser.add_argument(
        "--max-file-bytes", type=_positive_int, default=1_048_576,
        help="Maximum bytes read from each file."
    )
    parser.add_argument(
        "--cache", action="store_true", help="Use the persistent context cache."
    )
    parser.add_argument(
        "--refresh-cache", action="store_true",
        help="Refresh cached file content before querying."
    )


def _add_context_cache_format_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format", choices=("text", "json"), default="text", help="Output format."
    )


def _handle_context_search(args: argparse.Namespace) -> int:
    try:
        response = search_text_context(
            args.root,
            args.query,
            extensions=args.extension,
            max_results=args.max_results,
            max_snippets=args.max_snippets,
            max_snippet_chars=args.max_snippet_chars,
            max_file_bytes=args.max_file_bytes,
            cache=args.cache,
            refresh_cache=args.refresh_cache,
        )
    except (ValueError, CacheDatabaseError) as exc:
        raise CliError(str(exc)) from exc
    _print_context_response(response, args.format)
    return 0


def _handle_context_list(args: argparse.Namespace) -> int:
    try:
        response = list_text_context(
            args.root,
            extensions=args.extension,
            max_results=args.max_results,
            max_file_bytes=args.max_file_bytes,
            cache=args.cache,
            refresh_cache=args.refresh_cache,
        )
    except (ValueError, CacheDatabaseError) as exc:
        raise CliError(str(exc)) from exc
    _print_context_response(response, args.format)
    return 0


def _handle_context_cache_info(args: argparse.Namespace) -> int:
    try:
        info = get_context_cache_info()
    except (ValueError, CacheDatabaseError) as exc:
        raise CliError(str(exc)) from exc
    _print_context_cache_info(info, args.format)
    return 0


def _handle_context_cache_clear(args: argparse.Namespace) -> int:
    try:
        report = clear_context_cache()
    except (ValueError, CacheDatabaseError) as exc:
        raise CliError(str(exc)) from exc
    _print_context_cache_clear_report(report, args.format)
    return 0


def _print_context_response(response, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(context_response_to_dict(response), ensure_ascii=False, indent=2))
        return
    for result in response.results:
        if response.mode == "search":
            print(
                f"{result.path} ({result.size_bytes} bytes, score={result.score}, "
                f"matches={result.match_count})"
            )
            for snippet in result.snippets:
                print(f"  {snippet.line}: {snippet.text}")
        else:
            print(f"{result.path} ({result.size_bytes} bytes)")
    for skipped in response.skipped:
        print(f"Skipped: {skipped.path} ({skipped.reason})")
    if response.truncated:
        print("Results truncated.")


def _print_context_cache_info(info, output_format: str) -> None:
    payload = _context_cache_info_to_dict(info)
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def _print_context_cache_clear_report(report, output_format: str) -> None:
    payload = _context_cache_clear_report_to_dict(report)
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def _context_cache_info_to_dict(info) -> dict:
    return {
        "path": info.path,
        "schema_version": info.schema_version,
        "namespace": info.namespace,
        "database_bytes": info.database_bytes,
        "wal_bytes": info.wal_bytes,
        "shm_bytes": info.shm_bytes,
        "roots": info.roots,
        "files": info.files,
        "text_files": info.text_files,
        "skipped_files": info.skipped_files,
        "last_access_ns": info.last_access_ns,
    }


def _context_cache_clear_report_to_dict(report) -> dict:
    return {
        "associations_removed": report.associations_removed,
        "roots_removed": report.roots_removed,
        "files_removed": report.files_removed,
        "before_bytes": report.before_bytes,
        "after_bytes": report.after_bytes,
    }


def _print_tree(tree: str) -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass
    print(tree)


def _decompress_auto(args: argparse.Namespace, password: Optional[str] = None) -> str:
    file_output = _decompressed_file_output(args.input, args.output)
    _ensure_output_available(file_output, args.force)
    verbose = not args.quiet
    if password is None:
        password = _prompt_existing_password(args.input)

    try:
        if password is None:
            return decompress_file(args.input, str(file_output), verbose=verbose)
        return decompress_file(args.input, str(file_output), verbose=verbose, password=password)
    except CompressionError:
        dir_output = _decompressed_dir_output(args.input, args.output)
        _ensure_output_available(dir_output, args.force)
        if password is None:
            return decompress_dir(args.input, str(dir_output), verbose=verbose)
        return decompress_dir(args.input, str(dir_output), verbose=verbose, password=password)


def _prompt_new_password() -> str:
    password = getpass.getpass("Password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise CliError("Password confirmation does not match.")
    return password


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _prompt_existing_password(input_path: str) -> Optional[str]:
    if not is_encrypted_archive(input_path):
        return None
    return getpass.getpass("Password: ")


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
