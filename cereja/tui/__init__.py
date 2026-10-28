"""Opt-in Cereja TUI application; resolving TUI never constructs a session."""
from cereja._lazy import attach as _attach

_attach(globals())
