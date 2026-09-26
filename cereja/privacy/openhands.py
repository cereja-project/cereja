"""OpenHands process-scoped privacy profiles.

This module configures child-process environments with documented telemetry
and tracing controls for OpenHands components.

The policy is process-scoped and environment-only. Cereja never persists
credentials, modifies shell profiles, or alters user configuration. These
policies do not provide an operating-system network sandbox, traffic capture,
or outbound content filtering.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SUPPORTED_COMPONENTS = ("agent-server", "canvas-build", "canvas-static")

AGENT_SERVER_APPLIED = {
    "DO_NOT_TRACK": "1",
    "OH_TELEMETRY_EXPORTER": "none",
}

CANVAS_BUILD_APPLIED = {
    "DO_NOT_TRACK": "1",
    "VITE_DO_NOT_TRACK": "1",
}

CANVAS_STATIC_APPLIED = {
    "DO_NOT_TRACK": "1",
    "AGENT_CANVAS_DISABLE_TELEMETRY": "1",
}

AGENT_SERVER_REMOVED = (
    "OH_TELEMETRY_POSTHOG_API_KEY",
    "OH_TELEMETRY_POSTHOG_HOST",
    "OH_TELEMETRY_HTTP_ENDPOINT",
    "OH_TELEMETRY_HTTP_TOKEN",
    "LMNR_PROJECT_API_KEY",
    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_ENDPOINT",
    "OTEL_EXPORTER_OTLP_TRACES_HEADERS",
    "OTEL_EXPORTER_OTLP_HEADERS",
)


def _validate_component(component: Any) -> str:
    if not isinstance(component, str):
        raise TypeError("component must be a string")
    if component not in SUPPORTED_COMPONENTS:
        raise ValueError(
            f"unsupported OpenHands component: {component!r}; "
            f"must be one of {list(SUPPORTED_COMPONENTS)}"
        )
    return component


def environment(
    component: str,
    base_env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return a new copy of the environment with OpenHands profile applied.

    Parameters
    ----------
    component:
        Target component: 'agent-server', 'canvas-build', or 'canvas-static'.
    base_env:
        Base environment mapping. When None, defaults to os.environ.
        An empty mapping remains empty without falling back to os.environ.
    """
    comp = _validate_component(component)
    env = dict(os.environ if base_env is None else base_env)

    if comp == "agent-server":
        for var in AGENT_SERVER_REMOVED:
            env.pop(var, None)
        env.update(AGENT_SERVER_APPLIED)
    elif comp == "canvas-build":
        env.update(CANVAS_BUILD_APPLIED)
    elif comp == "canvas-static":
        env.update(CANVAS_STATIC_APPLIED)

    return env


def status(
    environment: Mapping[str, str] | str | None = None,
    *,
    component: str | None = None,
) -> dict[str, Any]:
    """Inspect OpenHands privacy-related environment state without secrets.

    Inspects exclusively the supplied environment mapping (or os.environ if
    omitted). Never modifies processes or queries external services.
    """
    if component is None:
        if isinstance(environment, str):
            component = environment
            environment = None
        else:
            raise TypeError("status() missing required argument: 'component'")

    comp = _validate_component(component)
    env = os.environ if environment is None else environment

    if comp == "agent-server":
        expected_flags = AGENT_SERVER_APPLIED
        removable_names = AGENT_SERVER_REMOVED
    elif comp == "canvas-build":
        expected_flags = CANVAS_BUILD_APPLIED
        removable_names = ()
    else:
        expected_flags = CANVAS_STATIC_APPLIED
        removable_names = ()

    flags: dict[str, str] = {}
    for name, expected_val in expected_flags.items():
        if name not in env:
            flags[name] = "unset"
        elif env[name] == expected_val:
            flags[name] = "set"
        else:
            flags[name] = "conflicting"

    removable_vars: dict[str, str] = {
        name: "present" if name in env else "absent"
        for name in removable_names
    }

    return {
        "provider": "openhands",
        "component": comp,
        "source": "environment_only",
        "inspection_source": "environment_only",
        "coverage_scope": "child_environment_only",
        "runtime_behavior": "not_verified",
        "network_isolation": "not_enforced",
        "outbound_content_filtering": "not_enforced",
        "model_routing": "not_checked",
        "critic": "not_checked",
        "webhooks": "not_checked",
        "local_content_logging": "not_checked",
        "flags": flags,
        "removable_variables": removable_vars,
    }


def run(
    command: Sequence[str],
    component: str | None = None,
    *,
    cwd: str | os.PathLike[str] | None = None,
    base_env: Mapping[str, str] | None = None,
    **subprocess_kwargs: Any,
) -> subprocess.CompletedProcess:
    """Run a command under the selected OpenHands privacy profile.

    Arguments must be a sequence of strings. Shell interpretation is not
    enabled. Propagates the child return code.
    """
    if component is None:
        raise TypeError("run() missing required argument: 'component'")
    comp = _validate_component(component)

    if isinstance(command, (str, bytes)):
        raise TypeError(
            "command must be a sequence of arguments, not a string or bytes"
        )
    if not isinstance(command, Sequence):
        raise TypeError("command must be a sequence of arguments")
    if len(command) == 0:
        raise ValueError("command must not be empty")
    if any(not isinstance(arg, str) for arg in command):
        raise TypeError("all command elements must be strings")
    if not command[0] or not command[0].strip():
        raise ValueError("executable must not be empty")

    env = environment(component=comp, base_env=base_env)
    kwargs = dict(subprocess_kwargs)
    kwargs.setdefault("check", False)
    return subprocess.run(
        list(command),
        cwd=None if cwd is None else Path(cwd),
        env=env,
        **kwargs,
    )
