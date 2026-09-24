"""Compatibility imports for the Windows capture implementation."""

from ._windows.capture import (
    ScreenCapture, ScreenFrame, ScreenMonitor,
    _Surface, _WindowsCaptureBackend,
)
from ._windows.api import _Win32, _checked
from ._windows.types import (
    _BitmapInfo, _BitmapInfoHeader, _CursorInfo, _IconInfo, _MonitorInfo,
)
