"""Terminal capabilities and session transport (no application or legacy imports)."""

from ._capabilities import (
    Capabilities, CapabilityOptions, StreamBackend, detect_capabilities,
)
from ._session import TerminalCleanupError, TerminalSession

__all__ = ['Capabilities', 'CapabilityOptions', 'StreamBackend',
           'detect_capabilities', 'TerminalCleanupError', 'TerminalSession']
