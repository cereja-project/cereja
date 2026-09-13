"""Cross-platform system inventory facade."""

from __future__ import annotations

import sys

from .models import HardwareInfo

SECTIONS = frozenset({"system", "os", "cpu", "memory", "gpu", "motherboard", "bios"})
DETAILS = frozenset({"basic", "full"})


def info(*, detail: str = "basic", include_sensitive: bool = False, sections=None) -> HardwareInfo:
    detail = str(detail).lower()
    if detail not in DETAILS:
        raise ValueError(f"detail must be one of {sorted(DETAILS)!r}")
    selected = _normalize_sections(sections)
    backend = _backend()
    return backend.collect(
        detail=detail,
        include_sensitive=bool(include_sensitive),
        sections=selected,
    )


def _normalize_sections(sections):
    if sections is None:
        return SECTIONS
    if isinstance(sections, str):
        sections = (sections,)
    selected = frozenset(str(section).lower() for section in sections)
    invalid = selected - SECTIONS
    if invalid:
        raise ValueError(f"unsupported hardware sections: {', '.join(sorted(invalid))}")
    return selected


def _backend():
    if sys.platform == "win32":
        from . import _windows
        return _windows
    if sys.platform.startswith("linux"):
        from . import _linux
        return _linux
    if sys.platform == "darwin":
        from . import _macos
        return _macos
    raise RuntimeError(f"Unsupported platform for system inventory: {sys.platform}")
