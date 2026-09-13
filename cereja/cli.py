"""Compatibility facade for the Cereja command-line interface.

New CLI implementation lives in :mod:`cereja.entrypoint` and
:mod:`cereja.commands`. Importing this module intentionally stays lightweight.
"""

from typing import Optional, Sequence


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Delegate legacy ``cereja.cli.main`` calls to the root dispatcher."""
    from cereja.entrypoint import main as entrypoint_main

    return entrypoint_main(argv)
