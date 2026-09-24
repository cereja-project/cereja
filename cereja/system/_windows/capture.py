"""Owned Windows pixel capture, separate from native declarations and input.

Importing this module does not load native libraries, capture pixels, or change
DPI awareness. Native resources belong to one ScreenCapture instance/thread.
"""

import ctypes
from dataclasses import dataclass
import threading

from .api import _Win32, _checked
from .types import (
    DWORD, HANDLE, POINT, RECT,
    _BitmapInfo, _BitmapInfoHeader, _CursorInfo, _IconInfo, _MonitorInfo,
)


@dataclass(frozen=True, slots=True)
class ScreenMonitor:
    """An attached monitor in physical virtual-desktop pixel coordinates."""

    id: str
    name: str
    left: int
    top: int
    width: int
    height: int
    is_primary: bool


@dataclass(frozen=True, slots=True)
class ScreenFrame:
    """Owned top-down BGRA bytes, with no row padding and alpha equal to 255."""

    left: int
    top: int
    width: int
    height: int
    bgra: bytes


class _Surface:
    """A reusable top-down DIB selected into a memory DC."""

    def __init__(self, api, width, height, window=None):
        self.api = api
        self.width, self.height = width, height
        self.window = window
        self.screen_dc = self.dc = self.bitmap = self.previous = None
        self.bits = HANDLE()
        try:
            # This DC supplies a compatible pixel format, not any pixel data.
            self.screen_dc = _checked(api.GetDC(window), "GetDC")
            self.dc = _checked(api.CreateCompatibleDC(self.screen_dc), "CreateCompatibleDC")
            info = _BitmapInfo()
            info.bmiHeader.biSize = ctypes.sizeof(_BitmapInfoHeader)
            info.bmiHeader.biWidth = width
            info.bmiHeader.biHeight = -height
            info.bmiHeader.biPlanes = 1
            info.bmiHeader.biBitCount = 32
            self.bitmap = _checked(api.CreateDIBSection(
                self.screen_dc, ctypes.byref(info), 0, ctypes.byref(self.bits), None, 0,
            ), "CreateDIBSection")
            _checked(self.bits.value, "CreateDIBSection pixels")
            previous = api.SelectObject(self.dc, self.bitmap)
            if previous == HANDLE(-1).value:
                raise OSError("SelectObject failed")
            self.previous = _checked(previous, "SelectObject")
            if window is not None:
                # PrintWindow draws into our memory DC. It does not need this
                # reference DC, which would become invalid if the target closes.
                _checked(api.ReleaseDC(window, self.screen_dc), "ReleaseDC")
                self.screen_dc = None
        except BaseException as error:
            try:
                self.close()
            except Exception as cleanup_error:
                error.add_note(f"Capture resource cleanup also failed: {cleanup_error}")
            raise

    def close(self):
        # Attempt every cleanup even if one native operation fails.
        errors = []
        actions = (
            (self.previous, self.api.SelectObject, (self.dc, self.previous), "SelectObject"),
            (self.bitmap, self.api.DeleteObject, (self.bitmap,), "DeleteObject"),
            (self.dc, self.api.DeleteDC, (self.dc,), "DeleteDC"),
            (self.screen_dc, self.api.ReleaseDC, (self.window, self.screen_dc), "ReleaseDC"),
        )
        self.previous = self.bitmap = self.dc = self.screen_dc = None
        for resource, function, args, name in actions:
            if resource:
                try:
                    _checked(function(*args), name)
                except OSError as error:
                    errors.append(error)
        if errors:
            raise errors[0]

    def copy_bytes(self):
        _checked(self.api.GdiFlush(), "GdiFlush")
        pixels = bytearray(ctypes.string_at(self.bits, self.width * self.height * 4))
        # GDI's fourth byte is reserved, not reliable alpha. Publish opaque BGRA.
        pixels[3::4] = b"\xff" * (self.width * self.height)
        return bytes(pixels)

    def clear(self):
        # A window may paint only part of its DC. Never publish old pixels.
        _checked(self.api.GdiFlush(), "GdiFlush")
        ctypes.memset(self.bits, 0, self.width * self.height * 4)


class _WindowsCaptureBackend:
    def __init__(self):
        self.api = _Win32()
        self.surface = None
        self._window_identities = {}
        self._invalid_windows = set()

    def list_monitors(self):
        monitors, errors = [], []

        @self.api.monitor_callback
        def visit(handle, _dc, _rect, _data):
            try:
                info = _MonitorInfo()
                info.cbSize = ctypes.sizeof(info)
                _checked(self.api.GetMonitorInfoW(handle, ctypes.byref(info)), "GetMonitorInfoW")
                rect = info.rcMonitor
                if rect.right > rect.left and rect.bottom > rect.top:
                    name = info.szDevice
                    monitors.append(ScreenMonitor(
                        name, name.removeprefix("\\\\.\\"), rect.left, rect.top,
                        rect.right - rect.left, rect.bottom - rect.top,
                        bool(info.dwFlags & 1),
                    ))
                return True
            except Exception as error:
                # Exceptions must not escape a ctypes callback.
                errors.append(error)
                return False

        with self.api.physical_pixels():
            result = self.api.EnumDisplayMonitors(None, None, visit, 0)
            if errors:
                raise errors[0]
            _checked(result, "EnumDisplayMonitors")
        return tuple(sorted(monitors, key=lambda m: (not m.is_primary, m.left, m.top, m.id)))

    def draw_cursor(self, dc, left, top):
        cursor = _CursorInfo()
        cursor.cbSize = ctypes.sizeof(cursor)
        _checked(self.api.GetCursorInfo(ctypes.byref(cursor)), "GetCursorInfo")
        if not cursor.flags & 1 or cursor.flags & 2:
            return
        icon = _checked(self.api.CopyIcon(cursor.hCursor), "CopyIcon")
        info = _IconInfo()
        try:
            _checked(self.api.GetIconInfo(icon, ctypes.byref(info)), "GetIconInfo")
            # Native clipping handles negative positions and region boundaries.
            # DI_NORMAL preserves both alpha and monochrome AND/XOR cursors.
            _checked(self.api.DrawIconEx(
                dc, cursor.ptScreenPos.x - left - info.xHotspot,
                cursor.ptScreenPos.y - top - info.yHotspot,
                icon, 0, 0, 0, None, 3,
            ), "DrawIconEx")
        finally:
            # GetIconInfo allocates these bitmaps. The global cursor is borrowed.
            try:
                if info.hbmMask:
                    _checked(self.api.DeleteObject(info.hbmMask), "Delete cursor mask")
            finally:
                try:
                    if info.hbmColor:
                        _checked(self.api.DeleteObject(info.hbmColor), "Delete cursor color")
                finally:
                    _checked(self.api.DestroyIcon(icon), "Destroy cursor copy")

    def grab(self, left, top, width, height, include_cursor):
        with self.api.physical_pixels():
            surface = self._surface_for(width, height)
            _checked(self.api.BitBlt(
                surface.dc, 0, 0, width, height, surface.screen_dc,
                left, top, 0x00CC0020 | 0x40000000,
            ), "BitBlt")
            if include_cursor:
                self.draw_cursor(surface.dc, left, top)
            return surface.copy_bytes()

    def _surface_for(self, width, height, window=None):
        if self.surface and (
            self.surface.width, self.surface.height, self.surface.window
        ) != (width, height, window):
            self.close()
        if self.surface is None:
            self.surface = _Surface(self.api, width, height, window)
        return self.surface

    def _window_bounds(self, window, only_window_content):
        if window in self._invalid_windows or not self.api.IsWindow(window):
            self._invalid_windows.add(window)
            raise OSError("The selected window no longer exists")
        process = DWORD()
        thread = self.api.GetWindowThreadProcessId(window, ctypes.byref(process))
        if not thread or not process.value:
            self._invalid_windows.add(window)
            raise OSError("The selected window owner is no longer available")
        identity = (process.value, thread)
        previous = self._window_identities.setdefault(window, identity)
        if previous != identity:
            self._invalid_windows.add(window)
            raise OSError("The selected window identity changed")
        if self.api.IsIconic(window):
            raise OSError("The selected window is minimized")
        if self.api.IsHungAppWindow(window):
            raise OSError("The selected window is not responding")
        rect = RECT()
        if only_window_content:
            _checked(self.api.GetClientRect(window, ctypes.byref(rect)), "GetClientRect")
            origin = POINT(rect.left, rect.top)
            _checked(self.api.ClientToScreen(window, ctypes.byref(origin)), "ClientToScreen")
            left, top = origin.x, origin.y
        else:
            _checked(self.api.GetWindowRect(window, ctypes.byref(rect)), "GetWindowRect")
            left, top = rect.left, rect.top
        width, height = rect.right - rect.left, rect.bottom - rect.top
        if width <= 0 or height <= 0:
            raise OSError("The selected window has no capturable area")
        return left, top, width, height

    def grab_window(self, window, only_window_content):
        with self.api.physical_pixels():
            left, top, width, height = self._window_bounds(window, only_window_content)
            surface = self._surface_for(width, height, window)
            surface.clear()
            # PW_RENDERFULLCONTENT plus PW_CLIENTONLY only for the client area.
            # No desktop fallback is permitted, even if PrintWindow fails.
            if not self.api.PrintWindow(window, surface.dc, 2 | int(only_window_content)):
                raise OSError("PrintWindow failed; the selected window cannot be captured")
            current = self._window_bounds(window, only_window_content)
            if current[2:] != (width, height):
                raise OSError("The selected window dimensions changed during capture")
            pixels = surface.copy_bytes()
            return ScreenFrame(current[0], current[1], width, height, pixels)

    def close(self):
        surface, self.surface = self.surface, None
        if surface is not None:
            surface.close()


class ScreenCapture:
    """Capture a Windows monitor, region or window, using physical pixels.

    Construct, use and close an instance on the same thread. A returned frame
    owns its immutable bytes and remains valid after subsequent grabs or close.
    Windows 10 version 1703 or newer is required for per-monitor DPI v2.
    """

    def __init__(self, include_cursor: bool = True):
        if not isinstance(include_cursor, bool):
            raise TypeError("include_cursor must be a bool")
        self.include_cursor = include_cursor
        # Thread identifiers can be recycled after a worker exits.
        self._thread = threading.current_thread()
        self._closed = False
        self._backend = _WindowsCaptureBackend()

    def _check_thread(self):
        if threading.current_thread() is not self._thread:
            raise RuntimeError("ScreenCapture must be used and closed on its creating thread")

    def _check_open(self):
        self._check_thread()
        if self._closed:
            raise RuntimeError("ScreenCapture is closed")

    def list_monitors(self) -> tuple[ScreenMonitor, ...]:
        """Return current monitor bounds; the primary monitor is listed first."""
        self._check_open()
        return self._backend.list_monitors()

    def grab(self, *, monitor: str | ScreenMonitor | None = None,
             region: tuple[int, int, int, int] | None = None,
             window: int | None = None, only_window_content: bool = True) -> ScreenFrame:
        """Capture a monitor, (left, top, width, height), or a window HWND.

        The selectors are mutually exclusive. The default is the primary
        monitor. Regions must fit entirely within one currently attached monitor.
        Window mode uses PrintWindow without desktop fallback, omits the cursor,
        and never restores or activates the target. Minimized, closed or known
        unresponsive windows raise OSError. PrintWindow itself is synchronous.
        Invalid selectors raise TypeError/ValueError; native failures raise OSError.
        """
        self._check_open()
        if sum(value is not None for value in (monitor, region, window)) > 1:
            raise ValueError("Specify at most one of monitor, region or window")
        if not isinstance(only_window_content, bool):
            raise TypeError("only_window_content must be a bool")
        if window is not None:
            if not isinstance(window, int) or isinstance(window, bool):
                raise TypeError("window must be a positive integer HWND")
            if not 0 < window < (1 << (ctypes.sizeof(HANDLE) * 8)):
                raise ValueError("window must be a positive HWND that fits a native pointer")
            return self._backend.grab_window(window, only_window_content)
        if monitor is not None and not isinstance(monitor, (str, ScreenMonitor)):
            raise TypeError("monitor must be a monitor id or ScreenMonitor")
        if region is not None:
            if not isinstance(region, tuple) or len(region) != 4:
                raise TypeError("region must be a (left, top, width, height) tuple")
            if any(not isinstance(value, int) or isinstance(value, bool) for value in region):
                raise TypeError("region coordinates and dimensions must be integers")
            left, top, width, height = region
            if width <= 0 or height <= 0:
                raise ValueError("region width and height must be positive")
        monitors = self.list_monitors()
        if not monitors:
            raise OSError("No display monitors are available")
        if region is None:
            if monitor is None:
                selected = next((item for item in monitors if item.is_primary), None)
                if selected is None:
                    raise OSError("The primary monitor is unavailable")
            else:
                identifier = monitor.id if isinstance(monitor, ScreenMonitor) else monitor
                selected = next((item for item in monitors if item.id == identifier), None)
                if selected is None:
                    raise ValueError(f"Monitor is no longer available: {identifier!r}")
            left, top, width, height = selected.left, selected.top, selected.width, selected.height
        elif not any(
            item.left <= left and item.top <= top
            and left + width <= item.left + item.width
            and top + height <= item.top + item.height
            for item in monitors
        ):
            raise ValueError("region must fit entirely within one attached monitor")
        pixels = self._backend.grab(left, top, width, height, self.include_cursor)
        return ScreenFrame(left, top, width, height, pixels)

    def close(self):
        """Release all resources. Repeated calls on the owner thread are safe."""
        self._check_thread()
        if not self._closed:
            self._closed = True
            self._backend.close()

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.close()
        except Exception as cleanup_error:
            if exc_value is None:
                raise
            exc_value.add_note(f"ScreenCapture cleanup also failed: {cleanup_error}")
