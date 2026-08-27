"""Top-level command dispatcher for Cereja."""
import sys
from typing import Optional, Sequence

from cereja.cli import main as legacy_main
from cereja.security._cli import main as security_main


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Dispatch security commands while preserving the existing CLI."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "security":
        return security_main(args[1:])
    return legacy_main(args)
