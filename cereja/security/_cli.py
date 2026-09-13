"""Compatibility facade for the defensive security CLI."""


def main(argv=None) -> int:
    from cereja.commands.security import main as command_main

    return command_main(argv)


def register_security_parser(subparsers) -> None:
    from cereja.commands.security import register_security_parser as register

    register(subparsers)
