"""Curl-like HTTP command backed by :mod:`cereja.http`."""

from __future__ import annotations

import argparse
import json
import ssl
import sys
from typing import Optional, Sequence

from cereja.http import Client, HTTPError
from cereja.transfers.sinks import AtomicFileSink

_SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "api-key",
}


class HttpCliError(Exception):
    """Expected HTTP command usage or execution error."""


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cereja http",
        description="Make HTTP/1.1 requests using Cereja's zero-dependency client.",
    )
    parser.add_argument("request", nargs="+", metavar="URL|METHOD URL")
    parser.add_argument("-X", "--method", help="HTTP method.")
    parser.add_argument("-H", "--header", action="append", default=[], help="Request header; repeatable.")
    parser.add_argument("-q", "--query", action="append", default=[], help="Query parameter KEY=VALUE; repeatable.")
    body = parser.add_mutually_exclusive_group()
    body.add_argument("-d", "--data", help="Raw UTF-8 request body.")
    body.add_argument("--json", dest="json_body", help="JSON request body.")
    parser.add_argument("-I", "--head", action="store_true", help="Send HEAD and print response headers.")
    parser.add_argument("-i", "--include", action="store_true", help="Include response headers in stdout.")
    parser.add_argument("-L", "--follow", action="store_true", help="Follow redirects.")
    parser.add_argument("-o", "--output", help="Write the response body atomically to a file.")
    parser.add_argument("--timeout", type=_positive_float, default=5.0, help="Timeout for HTTP phases in seconds.")
    parser.add_argument(
        "--max-body", type=_positive_int, default=16 * 1024 * 1024,
        help="Maximum materialized response body bytes.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Write request/response diagnostics to stderr.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print a JSON response body.")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate and hostname verification.")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    try:
        method, url = _resolve_target(args)
        headers = _parse_pairs(args.header, header=True)
        params = _parse_pairs(args.query, header=False)
        request_kwargs = {
            "params": params or None,
            "headers": headers or None,
        }
        if args.json_body is not None:
            request_kwargs["json"] = _parse_json(args.json_body)
        elif args.data is not None:
            request_kwargs["content"] = args.data

        with Client(
            timeout=args.timeout,
            follow_redirects=args.follow,
            max_body_bytes=args.max_body,
            ssl_context=_ssl_context(args.insecure),
        ) as client:
            response = client.request(method, url, **request_kwargs)

        if args.verbose:
            _write_verbose(response)
        if args.include or args.head:
            _write_response_head(response)
        if not args.head:
            body = _render_body(response, args.pretty)
            if args.output:
                _write_file(args.output, body)
            else:
                _write_stdout(body)
        return 0
    except (HttpCliError, HTTPError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _resolve_target(args):
    parts = args.request
    if len(parts) == 1:
        method, url = args.method or "GET", parts[0]
    elif len(parts) == 2:
        if args.method:
            raise HttpCliError("Use either METHOD URL or --method, not both")
        method, url = parts
    else:
        raise HttpCliError("Expected URL or METHOD URL")
    method = method.upper()
    if args.head:
        if args.data is not None or args.json_body is not None:
            raise HttpCliError("HEAD does not accept a request body")
        method = "HEAD"
    return method, url


def _parse_pairs(values, *, header):
    result = []
    separator = ":" if header else "="
    label = "Header" if header else "Query parameter"
    for raw in values:
        if separator not in raw:
            expected = "Name: value" if header else "KEY=VALUE"
            raise HttpCliError(f"{label} must use '{expected}'")
        name, value = raw.split(separator, 1)
        name = name.strip()
        value = value.strip() if header else value
        if not name:
            raise HttpCliError(f"{label} name cannot be empty")
        result.append((name, value))
    return result


def _parse_json(value):
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise HttpCliError(f"Invalid JSON: {exc.msg}") from exc


def _ssl_context(insecure):
    if not insecure:
        return None
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def _render_body(response, pretty):
    if not pretty:
        return response.content
    try:
        value = response.json()
    except Exception as exc:
        raise HttpCliError("--pretty requires a JSON response") from exc
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def _write_file(path, data):
    sink = AtomicFileSink(path)
    try:
        handle = sink.open()
        handle.write(data)
        sink.commit()
    except BaseException:
        sink.abort()
        raise


def _write_stdout(data):
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is not None:
        buffer.write(data)
        buffer.flush()
        return
    sys.stdout.write(data.decode("utf-8", errors="replace"))


def _write_response_head(response):
    print(f"{response.info.http_version} {response.status_code} {response.info.reason}")
    for name, value in response.headers:
        print(f"{name}: {value}")
    print()


def _redacted(name, value):
    return "<redacted>" if name.lower() in _SENSITIVE_HEADERS else value


def _write_verbose(response):
    request = response.request
    print(f"> {request.method} {request.url.target} HTTP/1.1", file=sys.stderr)
    for name, value in request.headers:
        print(f"> {name}: {_redacted(name, value)}", file=sys.stderr)
    print(f"< {response.info.http_version} {response.status_code} {response.info.reason}", file=sys.stderr)
    for name, value in response.headers:
        print(f"< {name}: {_redacted(name, value)}", file=sys.stderr)


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
