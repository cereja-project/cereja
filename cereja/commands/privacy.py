"""Process-scoped privacy policies for third-party AI tooling."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from typing import Optional, Sequence

from cereja.privacy import huggingface, openhands


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

    oh = providers.add_parser(
        "openhands",
        help="Control OpenHands process environment and telemetry.",
    )
    oh_actions = oh.add_subparsers(dest="action", required=True)

    oh_status = oh_actions.add_parser("status", help="Show current OpenHands privacy state.")
    oh_status.add_argument(
        "--component",
        required=True,
        choices=["agent-server", "canvas-build", "canvas-static"],
        help="OpenHands component to inspect.",
    )
    oh_status.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    oh_run = oh_actions.add_parser("run", help="Run a command under an OpenHands privacy profile.")
    oh_run.add_argument(
        "--component",
        required=True,
        choices=["agent-server", "canvas-build", "canvas-static"],
        help="OpenHands component profile to apply.",
    )
    oh_run.add_argument("--cwd", help="Working directory for the child process.")
    oh_run.add_argument("command", nargs=argparse.REMAINDER, help="Command to execute after --.")
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


def _render_openhands_status(payload: dict) -> str:
    lines = [
        "OpenHands privacy",
        f"  Component                   {payload['component']}",
        f"  Inspection source           {payload['inspection_source']}",
        f"  Coverage scope              {payload['coverage_scope']}",
        f"  Runtime behavior            {payload['runtime_behavior']}",
        f"  Network isolation           {payload['network_isolation']}",
        f"  Outbound content filtering  {payload['outbound_content_filtering']}",
        f"  Model routing               {payload['model_routing']}",
        f"  Critic                      {payload['critic']}",
        f"  Webhooks                    {payload['webhooks']}",
        f"  Local content logging       {payload['local_content_logging']}",
        "",
        "Flags:",
    ]
    for name, state in sorted(payload.get("flags", {}).items()):
        lines.append(f"  {name}: {state}")
    removable = payload.get("removable_variables", {})
    if removable:
        lines.append("")
        lines.append("Removable variables:")
        for name, state in sorted(removable.items()):
            lines.append(f"  {name}: {state}")
    return "\n".join(lines) + "\n"


def _handle_openhands(args: argparse.Namespace) -> int:
    if args.action == "status":
        try:
            payload = openhands.status(component=args.component)
        except (ValueError, TypeError):
            print("Error: invalid argument for openhands status", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(_render_openhands_status(payload), end="")
        return 0

    if args.action == "run":
        try:
            command = _command(args.command)
            result = openhands.run(
                command,
                component=args.component,
                cwd=args.cwd,
            )
            return int(result.returncode)
        except (ValueError, TypeError) as exc:
            msg = str(exc)
            if "a child command is required" in msg:
                print("Error: a child command is required after --", file=sys.stderr)
            elif "unsupported OpenHands component" in msg:
                print("Error: unsupported OpenHands component", file=sys.stderr)
            else:
                print("Error: invalid command or arguments for openhands execution", file=sys.stderr)
            return 1
        except OSError:
            print("Error: failed to launch OpenHands child process", file=sys.stderr)
            return 1

    raise ValueError(f"unsupported OpenHands privacy action: {args.action}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = create_parser()
    try:
        args = parser.parse_args(argv)
        if args.provider == "huggingface":
            return _handle_huggingface(args)
        if args.provider == "openhands":
            return _handle_openhands(args)
        parser.error(f"unsupported privacy provider: {args.provider}")
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0
