"""Metadata-only large-file search CLI."""

import argparse
from dataclasses import asdict
import json

from cereja.system.file_sizes import find_large_files
from ._common import CliError, non_negative_int, positive_int, run_handler


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='cereja large-files',
        description=('Find large regular files recursively using metadata only. Include hidden and binary files; '
                     'no repository filters, content reads or link/reparse traversal.'),
        epilog=('Exit codes: 0 complete scan, 1 root validation failure, 2 usage error, '
                '3 incomplete scan (including enumeration errors).'),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument('root', help='Explicit root directory (linked ancestors unsupported).')
    parser.add_argument('--min-size-bytes', type=non_negative_int, default=0, help='Minimum logical file size, inclusive.')
    parser.add_argument('--max-results', type=positive_int, default=20, help='Maximum retained largest files.')
    parser.add_argument('--max-entries', type=positive_int, default=1_000_000, help='Maximum examined directory entries.')
    parser.add_argument('--max-depth', type=non_negative_int, default=64, help='Maximum directory descent below root.')
    parser.add_argument('--max-errors', type=non_negative_int, default=32, help='Maximum retained error details.')
    parser.add_argument('--format', choices=('text', 'json'), default='text', help='Output format.')
    return parser


def main(argv=None) -> int:
    return run_handler(create_parser(), argv, _handle)


def _handle(args) -> int:
    try:
        report = find_large_files(args.root, min_size_bytes=args.min_size_bytes, max_results=args.max_results,
                                  max_entries=args.max_entries, max_depth=args.max_depth, max_errors=args.max_errors)
    except (OSError, ValueError) as error:
        raise CliError(json.dumps(str(error), ensure_ascii=True)) from None
    if args.format == 'json':
        print(json.dumps(asdict(report), ensure_ascii=True, indent=2))
    else:
        # Filesystem names remain data, including terminal control characters.
        print('root: ' + json.dumps(report.root, ensure_ascii=True))
        print('size_bytes\tpath (JSON quoted)')
        for file in report.files:
            print(f'{file.size_bytes}\t' + json.dumps(file.path, ensure_ascii=True))
        for field in ('complete', 'results_truncated', 'examined_entries', 'scanned_files', 'matched_files',
                      'skipped_links', 'skipped_special', 'error_count', 'errors_truncated'):
            print(f'{field}: {getattr(report, field)}')
        print('reasons: ' + ', '.join(report.reasons))
        for error in report.errors:
            print('error: ' + json.dumps(asdict(error), ensure_ascii=True))
    return 0 if report.complete else 3
