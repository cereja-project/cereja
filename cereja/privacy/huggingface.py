"""Hugging Face privacy policies for child processes.

The policy is intentionally process-scoped. Cereja never persists Hugging Face
credentials or edits shell/profile configuration. Offline mode disables Hub
access for libraries that honor the standard Hugging Face environment flags,
but it is not a network sandbox for arbitrary Python code.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

TELEMETRY_POLICY = {
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "DO_NOT_TRACK": "1",
}

OFFLINE_POLICY = {
    **TELEMETRY_POLICY,
    "HF_HUB_OFFLINE": "1",
    "HF_DATASETS_OFFLINE": "1",
    "TRANSFORMERS_OFFLINE": "1",
    "HF_HUB_DISABLE_IMPLICIT_TOKEN": "1",
}

DOWNLOAD_POLICY = {
    **TELEMETRY_POLICY,
    "HF_HUB_OFFLINE": "0",
    "HF_DATASETS_OFFLINE": "0",
    "TRANSFORMERS_OFFLINE": "0",
}

_TOKEN_VARIABLES = ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN")


def _copy_environment(base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    return dict(os.environ if base_env is None else base_env)


def _without_tokens(environment: dict[str, str]) -> dict[str, str]:
    for name in _TOKEN_VARIABLES:
        environment.pop(name, None)
    return environment


def offline_environment(base_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return an environment for offline Hugging Face execution.

    Authentication tokens inherited from the parent process are deliberately
    removed from the child environment.
    """
    environment = _without_tokens(_copy_environment(base_env))
    environment.update(OFFLINE_POLICY)
    return environment


def download_environment(
    *,
    token: str | None = None,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return an environment for an explicit model-download process.

    Telemetry remains disabled. A token is included only when supplied
    explicitly to this function. The token is never written to disk by Cereja.
    """
    environment = _without_tokens(_copy_environment(base_env))
    environment.update(DOWNLOAD_POLICY)
    environment["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "0" if token else "1"
    if token:
        environment["HF_TOKEN"] = token
    return environment


def status(environment: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Inspect Hugging Face privacy-related environment state without secrets."""
    env = os.environ if environment is None else environment
    values = {
        name: env.get(name)
        for name in (
            "HF_HUB_DISABLE_TELEMETRY",
            "DO_NOT_TRACK",
            "HF_HUB_OFFLINE",
            "HF_DATASETS_OFFLINE",
            "TRANSFORMERS_OFFLINE",
            "HF_HUB_DISABLE_IMPLICIT_TOKEN",
        )
    }
    offline = all(values[name] == "1" for name in (
        "HF_HUB_OFFLINE",
        "HF_DATASETS_OFFLINE",
        "TRANSFORMERS_OFFLINE",
    ))
    telemetry_disabled = all(values[name] == "1" for name in (
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
    ))
    return {
        "provider": "huggingface",
        "mode": "offline" if offline else "online_or_mixed",
        "offline": offline,
        "telemetry_disabled": telemetry_disabled,
        "implicit_token_disabled": values["HF_HUB_DISABLE_IMPLICIT_TOKEN"] == "1",
        "token_present": any(bool(env.get(name)) for name in _TOKEN_VARIABLES),
        "network_isolation": "not_enforced",
        "environment": values,
    }


def run(
    command: Sequence[str],
    *,
    offline: bool = True,
    token: str | None = None,
    cwd: str | os.PathLike[str] | None = None,
    base_env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run a command under the selected Hugging Face privacy policy."""
    if not command:
        raise ValueError("command must not be empty")
    if offline and token is not None:
        raise ValueError("token cannot be supplied while offline=True")
    env = (
        offline_environment(base_env)
        if offline
        else download_environment(token=token, base_env=base_env)
    )
    return subprocess.run(
        list(command),
        cwd=None if cwd is None else Path(cwd),
        env=env,
        check=False,
    )


def shell(
    *,
    executable: str | None = None,
    cwd: str | os.PathLike[str] | None = None,
    base_env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Open a child shell with the offline Hugging Face privacy policy."""
    if executable is None:
        if os.name == "nt":
            executable = (base_env or os.environ).get("COMSPEC", "cmd.exe")
        else:
            executable = (base_env or os.environ).get("SHELL", "/bin/sh")
    return run([executable], offline=True, cwd=cwd, base_env=base_env)
