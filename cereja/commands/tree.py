"""Repository tree CLI command."""

import argparse
import sys

from cereja.system import render_repository_tree

from ._common import non_negative_int, run_handler


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cereja tree",
        description="Draw a repository tree.",
    )
    parser.add_argument("path", nargs="?", default=".", help="Root directory.")
    parser.add_argument("--depth", type=non_negative_int, help="Maximum depth.")
    return parser


def main(argv=None) -> int:
    return run_handler(create_parser(), argv, _handle)


def _handle(args) -> int:
    _print_tree(render_repository_tree(args.path, depth=args.depth))
    return 0


def _print_tree(tree: str) -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass
    print(tree)
