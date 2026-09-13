"""System information command backed by :mod:`cereja.system.hardware`."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence

from cereja.system import hardware
from cereja.system.hardware.formatting import render


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cereja system",
        description="Inspect operating system and hardware information.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    info_parser = commands.add_parser("info", help="Show system information.")
    info_parser.add_argument(
        "--full", action="store_true",
        help="Include additional technical details.",
    )
    info_parser.add_argument(
        "--sensitive", action="store_true",
        help="Include unique identifiers such as serial numbers when available.",
    )
    info_parser.add_argument(
        "--json", action="store_true",
        help="Emit deterministic JSON instead of the visual layout.",
    )
    info_parser.add_argument(
        "--section", action="append", choices=sorted(hardware.SECTIONS),
        help="Collect only one section; repeatable.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = create_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    try:
        result = hardware.info(
            detail="full" if args.full else "basic",
            include_sensitive=args.sensitive,
            sections=args.section,
        )
        if args.json:
            print(result.to_json(indent=2))
        else:
            print(render(result), end="")
        return 0
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
