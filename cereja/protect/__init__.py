"""Protected Python code runtime and build helpers."""

from ._runtime import (
    DEFAULT_KEY_ENV,
    ProtectionError,
    bootstrap_module,
    bootstrap_package,
)

__all__ = [
    "DEFAULT_KEY_ENV",
    "ProtectionError",
    "bootstrap_module",
    "bootstrap_package",
    "protect_path",
]


def protect_path(*args, **kwargs):
    """Build a protected module or package without eagerly loading the builder."""
    from ._builder import protect_path as _protect_path

    return _protect_path(*args, **kwargs)
