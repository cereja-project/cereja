"""CLI integration for defensive static security analysis."""
import argparse
import sys
from pathlib import Path

from ._analysis import analyze_file
from ._reporting import report_to_json, report_to_markdown


def register_security_parser(subparsers) -> None:
    security_parser = subparsers.add_parser(
        "security", help="Inspect untrusted files without executing them."
    )
    security_subparsers = security_parser.add_subparsers(
        dest="security_command", required=True
    )
    analyze_parser = security_subparsers.add_parser(
        "analyze", help="Run defensive static analysis."
    )
    _configure_analyze_parser(analyze_parser)
    analyze_parser.set_defaults(handler=_handle_analyze)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="cereja security")
    subparsers = parser.add_subparsers(dest="security_command", required=True)
    analyze_parser = subparsers.add_parser("analyze", help="Run defensive static analysis.")
    _configure_analyze_parser(analyze_parser)
    analyze_parser.set_defaults(handler=_handle_analyze)
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (FileNotFoundError, PermissionError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _configure_analyze_parser(parser) -> None:
    parser.add_argument("input", help="File to inspect statically.")
    parser.add_argument(
        "--max-depth", type=_non_negative_int, default=2,
        help="Maximum archive recursion depth."
    )
    parser.add_argument(
        "--format", choices=("json", "markdown"), default="markdown",
        help="Report format."
    )
    parser.add_argument("-o", "--output", help="Write the report to this path instead of stdout.")


def _handle_analyze(args) -> int:
    report = analyze_file(args.input, max_depth=args.max_depth)
    rendered = report_to_json(report) if args.format == "json" else report_to_markdown(report)
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="" if rendered.endswith("\n") else "\n")
    return 0


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be non-negative")
    return parsed
