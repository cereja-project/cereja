"""Defensive static security analysis CLI command."""

import argparse
import sys
from pathlib import Path

from cereja.security._analysis import analyze_file
from cereja.security._reporting import report_to_json, report_to_markdown

from ._common import non_negative_int


def _configure_analyze(parser) -> None:
    parser.add_argument("input", help="File to inspect statically.")
    parser.add_argument(
        "--max-depth",
        type=non_negative_int,
        default=2,
        help="Maximum archive recursion depth.",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Report format.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write the report to this path instead of stdout.",
    )
    parser.set_defaults(handler=_handle_analyze)


def register_security_parser(subparsers) -> None:
    """Compatibility registration hook for callers of the historical API."""
    security = subparsers.add_parser(
        "security",
        help="Inspect untrusted files without executing them.",
    )
    security_subparsers = security.add_subparsers(
        dest="security_command",
        required=True,
    )
    analyze = security_subparsers.add_parser(
        "analyze",
        help="Run defensive static analysis.",
    )
    _configure_analyze(analyze)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cereja security",
        description="Inspect untrusted files without executing them.",
    )
    subparsers = parser.add_subparsers(dest="security_command", required=True)
    analyze = subparsers.add_parser("analyze", help="Run defensive static analysis.")
    _configure_analyze(analyze)
    return parser


def main(argv=None) -> int:
    args = create_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (FileNotFoundError, PermissionError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _handle_analyze(args) -> int:
    report = analyze_file(args.input, max_depth=args.max_depth)
    rendered = report_to_json(report) if args.format == "json" else report_to_markdown(report)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="" if rendered.endswith("\n") else "\n")
    return 0
