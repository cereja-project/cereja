"""Streaming download command backed by :mod:`cereja.transfers`."""

from __future__ import annotations

import argparse
from pathlib import Path
import ssl
import sys
from typing import Optional, Sequence
from urllib.parse import unquote, urlsplit

from cereja.http import Client, HTTPError
from cereja.transfers import download


class DownloadCliError(Exception):
    """Expected download command usage or execution error."""


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cereja download",
        description="Download a URL with streaming and atomic file replacement.",
    )
    parser.add_argument("url", help="HTTP or HTTPS URL to download.")
    parser.add_argument("-o", "--output", help="Destination file. Defaults to the URL filename.")
    parser.add_argument("--timeout", type=_positive_float, default=10.0, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--chunk-size", type=_positive_int, default=64 * 1024,
        help="Streaming chunk size in bytes.",
    )
    parser.add_argument("--force", action="store_true", help="Replace an existing destination file.")
    parser.add_argument("--quiet", action="store_true", help="Disable progress and completion output.")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate and hostname verification.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    try:
        destination = _destination(args.url, args.output)
        if destination.exists() and not args.force:
            raise DownloadCliError(f"Destination already exists: {destination}")
        progress = None if args.quiet else _Progress(destination)
        with Client(timeout=args.timeout, ssl_context=_ssl_context(args.insecure)) as client:
            result = download(
                args.url,
                destination,
                client=client,
                progress=progress,
                chunk_size=args.chunk_size,
                timeout=args.timeout,
            )
        if not args.quiet:
            progress.finish(result.bytes_transferred)
        return 0
    except (DownloadCliError, HTTPError, OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _destination(url: str, output: str | None) -> Path:
    if output:
        return Path(output)
    name = Path(unquote(urlsplit(url).path)).name
    if not name:
        raise DownloadCliError("Cannot infer destination filename from URL; use -o/--output")
    return Path(name)


def _ssl_context(insecure: bool):
    if not insecure:
        return None
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


class _Progress:
    def __init__(self, destination: Path):
        self.destination = destination
        self._last = None

    def __call__(self, event):
        if event.total_bytes:
            percent = event.bytes_transferred * 100 / event.total_bytes
            message = f"Downloading {event.bytes_transferred}/{event.total_bytes} bytes ({percent:.1f}%)"
        else:
            message = f"Downloading {event.bytes_transferred} bytes"
        if message != self._last:
            print("\r" + message, end="", file=sys.stderr, flush=True)
            self._last = message

    def finish(self, transferred: int):
        if self._last is not None:
            print(file=sys.stderr)
        print(f"Downloaded {transferred} bytes -> {self.destination}", file=sys.stderr)


def _positive_int(value):
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def _positive_float(value):
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed
