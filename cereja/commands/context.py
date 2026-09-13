"""Bounded textual context CLI command."""

import argparse
import json

from cereja.system import (
    clear_context_cache,
    context_response_to_dict,
    get_context_cache_info,
    list_text_context,
    search_text_context,
)
from cereja.system._context.cache_db import CacheDatabaseError

from ._common import CliError, positive_int, run_handler


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cereja context",
        description=(
            "Search or list bounded textual context. These operations open "
            "source files read-only; the optional cache does not modify "
            "searched files."
        ),
    )
    subparsers = parser.add_subparsers(dest="context_command", required=True)

    search = subparsers.add_parser("search", help="Search textual context.")
    _add_common_options(search)
    search.add_argument("--query", required=True, help="Search terms.")
    search.add_argument(
        "--max-snippets",
        type=positive_int,
        default=2,
        help="Maximum snippets per result.",
    )
    search.add_argument(
        "--max-snippet-chars",
        type=positive_int,
        default=240,
        help="Maximum characters per snippet.",
    )
    search.set_defaults(handler=_handle_search)

    listing = subparsers.add_parser("list", help="List textual file metadata.")
    _add_common_options(listing)
    listing.set_defaults(handler=_handle_list)

    cache = subparsers.add_parser(
        "cache",
        help="Manage the textual context cache.",
        description="Inspect or clear the global per-user context cache.",
        epilog="Example: cereja context cache info --format json",
    )
    cache_subparsers = cache.add_subparsers(dest="context_cache_command", required=True)

    cache_info = cache_subparsers.add_parser(
        "info",
        help="Show cache metadata and physical sizes.",
    )
    _add_cache_format(cache_info)
    cache_info.set_defaults(handler=_handle_cache_info)

    cache_clear = cache_subparsers.add_parser(
        "clear",
        help="Clear the default context-cache namespace.",
    )
    _add_cache_format(cache_clear)
    cache_clear.set_defaults(handler=_handle_cache_clear)
    return parser


def main(argv=None) -> int:
    return run_handler(create_parser(), argv, lambda args: args.handler(args))


def _add_common_options(parser) -> None:
    parser.add_argument(
        "--root",
        action="append",
        required=True,
        help="Explicit root directory.",
    )
    parser.add_argument(
        "--extension",
        action="append",
        help="File suffix to include; repeatable.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--max-results",
        type=positive_int,
        default=10,
        help="Maximum returned files.",
    )
    parser.add_argument(
        "--max-file-bytes",
        type=positive_int,
        default=1_048_576,
        help="Maximum bytes read from each file.",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Use and write the global per-user cache.",
    )
    parser.add_argument(
        "--refresh-cache",
        action="store_true",
        help="Reprocess the current roots and extensions; requires --cache.",
    )


def _add_cache_format(parser) -> None:
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )


def _translate(operation):
    try:
        return operation()
    except (ValueError, CacheDatabaseError) as exc:
        raise CliError(str(exc)) from exc


def _handle_search(args) -> int:
    response = _translate(
        lambda: search_text_context(
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
    )
    _print_response(response, args.format)
    return 0


def _handle_list(args) -> int:
    response = _translate(
        lambda: list_text_context(
            args.root,
            extensions=args.extension,
            max_results=args.max_results,
            max_file_bytes=args.max_file_bytes,
            cache=args.cache,
            refresh_cache=args.refresh_cache,
        )
    )
    _print_response(response, args.format)
    return 0


def _handle_cache_info(args) -> int:
    info = _translate(get_context_cache_info)
    _print_mapping(_cache_info_to_dict(info), args.format)
    return 0


def _handle_cache_clear(args) -> int:
    report = _translate(clear_context_cache)
    _print_mapping(_cache_clear_to_dict(report), args.format)
    return 0


def _print_response(response, output_format: str) -> None:
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


def _print_mapping(payload: dict, output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def _cache_info_to_dict(info) -> dict:
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


def _cache_clear_to_dict(report) -> dict:
    return {
        "associations_removed": report.associations_removed,
        "roots_removed": report.roots_removed,
        "files_removed": report.files_removed,
        "before_bytes": report.before_bytes,
        "after_bytes": report.after_bytes,
    }
