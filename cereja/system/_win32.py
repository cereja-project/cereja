"""Compatibility import for the legacy Windows automation helpers.

Native implementations live in ``cereja.system._windows``. Importing this
legacy path retains its historical process DPI configuration; the capture
package itself does not perform that process-wide initialization.
"""

import sys

if sys.platform != "win32":
    raise ImportError("The module should only be loaded on a Windows system.")

from ._windows.api import get_api

# Preserve the legacy opt-in import behavior. Windows may reject a second DPI
# setting when an embedding application has already chosen its own context.
get_api().SetProcessDPIAware()

from ._windows.common import Time, play_alert_sound
from ._windows.keyboard import Keyboard
from ._windows.mouse import Mouse
from ._windows.window import Window

__all__ = ["Keyboard", "Mouse", "Window", "Time", "play_alert_sound"]
