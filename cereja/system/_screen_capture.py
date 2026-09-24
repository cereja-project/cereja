"""Compatibility imports for the Windows capture implementation."""

from ._windows.capture import (
    ScreenCapture, ScreenFrame, ScreenMonitor,
    _Surface, _WindowsCaptureBackend,
)
from ._windows.api import _Win32, _checked
from ._windows.types import (
    BITMAPINFO as _BitmapInfo, BITMAPINFOHEADER as _BitmapInfoHeader,
    CURSORINFO as _CursorInfo, ICONINFO as _IconInfo, MONITORINFOEXW as _MonitorInfo,
)
