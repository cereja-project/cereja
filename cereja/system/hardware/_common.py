"""Small helpers shared by system inventory backends."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess


def to_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def clean(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return None


def run_text(args, *, timeout=5.0):
    try:
        result = subprocess.run(
            list(args), capture_output=True, text=True, check=False,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def run_json(args, *, timeout=8.0):
    output = run_text(args, timeout=timeout)
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return None


def selected(sections, name):
    return name in sections
