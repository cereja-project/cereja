"""Process-scoped privacy policies for third-party AI tooling."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from typing import Optional, Sequence

from cereja.privacy import huggingface


def _command(value: Sequence[str]) -> list[str]:
    command = list(value)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("a child command is required after --")
    return command


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cereja privacy",
        description=(
            "Run third-party tools with explicit process-scoped privacy policies. "
            "These policies are not an operating-system network sandbox."
        ),
    )
    providers = parser.add_subparsers(dest="provider", required=True)
    hf = providers.add_parser("huggingface", help="Control Hugging Face Hub access and telemetry.")
    actions = hf.add_subparsers(dest="action", required=True)

    status = actions.add_parser("status", help="Show current Hugging Face privacy state.")
    status.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    run = actions.add_parser("run", help="Run a command with Hugging Face offline.")
    run.add_argument("--cwd", help="Working directory for the child process.")
    run.add_argument("command", nargs=argparse.REMAINDER, help="Command to execute after --.")

    shell = actions.add_parser("shell", help="Open a child shell with Hugging Face offline.")
    shell.add_argument("--cwd", help="Working directory for the child shell.")
    shell.add_argument("--shell", dest="shell_executable", help="Shell executable to launch.")

    download = actions.add_parser(
        "download",
        help="Run one explicit online download while telemetry remains disabled.",
    )
    download.add_argument("--cwd", help="Working directory for the child process.")
    authentication = download.add_mutually_exclusive_group()
    authentication.add_argument(
        "--no-token",
        action="store_true",
        help="Do not provide an authentication token to the child process.",
    )
    authentication.add_argument(
        "--token-env",
        metavar="NAME",
        help="Read the token explicitly from environment variable NAME.",
    )
    download.add_argument("command", nargs=argparse.REMAINDER, help="Download command to execute after --.")
    return parser


def _render_status(payload: dict) -> str:
    environment = payload["environment"]
    lines = [
        "Hugging Face privacy",
        f"  Hub mode            {payload['mode'].upper()}",
        f"  Telemetry           {'DISABLED' if payload['telemetry_disabled'] else 'NOT FULLY DISABLED'}",
        f"  Implicit token      {'DISABLED' if payload['implicit_token_disabled'] else 'ENABLED OR UNSET'}",
        f"  HF token            {'PRESENT' if payload['token_present'] else 'NOT EXPOSED'}",
        "  Network isolation   NOT ENFORCED",
        "",
        "Environment:",
    ]
    for name, value in environment.items():
        lines.append(f"  {name}={value if value is not None else '<unset>'}")
    return "\n".join(lines) + "\n"


def _handle_huggingface(args: argparse.Namespace) -> int:
    if args.action == "status":
        payload = huggingface.status()
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(_render_status(payload), end="")
        return 0

    if args.action == "run":
        result = huggingface.run(_command(args.command), offline=True, cwd=args.cwd)
        return int(result.returncode)

    if args.action == "shell":
        result = huggingface.shell(executable=args.shell_executable, cwd=args.cwd)
        return int(result.returncode)

    if args.action == "download":
        token = None
        if args.token_env:
            token = os.environ.get(args.token_env)
            if not token:
                raise ValueError(f"environment variable {args.token_env!r} is not set")
        elif not args.no_token:
            token = getpass.getpass("Hugging Face token (hidden, not persisted): ").strip()
            if not token:
                raise ValueError("empty token; use --no-token for public downloads")
        result = huggingface.run(
            _command(args.command),
            offline=False,
            token=token,
            cwd=args.cwd,
        )
        return int(result.returncode)

    raise ValueError(f"unsupported Hugging Face privacy action: {args.action}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = create_parser()
    try:
        args = parser.parse_args(argv)
        if args.provider == "huggingface":
            return _handle_huggingface(args)
        parser.error(f"unsupported privacy provider: {args.provider}")
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0
