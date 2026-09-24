"""One typed native boundary for capture, window management and input.

Importing this module does not load a DLL or configure DPI awareness.
"""

import ctypes
from contextlib import contextmanager
import sys
import threading

from . import types
from .types import (
    ENUMWINDOWSPROC, MONITORENUMPROC,
    _BitmapInfo, _CursorInfo, _IconInfo, _MonitorInfo,
)


def _checked(result, operation):
    if not result:
        error = ctypes.get_last_error()
        if error:
            raise ctypes.WinError(error)
        raise OSError(f"{operation} failed")
    return result


class _Win32:
    """Typed user32/gdi32 bindings, loaded only when explicitly instantiated."""

    def __init__(self):
        if sys.platform != "win32":
            raise OSError("Win32 APIs require Windows")
        user = ctypes.WinDLL("user32", use_last_error=True)
        gdi = ctypes.WinDLL("gdi32", use_last_error=True)
        self.monitor_callback = MONITORENUMPROC
        self.enum_windows_callback = ENUMWINDOWSPROC

        def bind(library, name, result, *args):
            function = getattr(library, name)
            function.restype = result
            function.argtypes = list(args)
            setattr(self, name, function)

        bind(user, "SetProcessDPIAware", types.BOOL)
        # Keep legacy window/input APIs usable when per-monitor v2 is absent.
        if hasattr(user, "SetThreadDpiAwarenessContext"):
            bind(user, "SetThreadDpiAwarenessContext", types.HANDLE, types.HANDLE)
        else:
            self.SetThreadDpiAwarenessContext = None
        bind(user, "MessageBeep", types.BOOL, types.UINT)
        bind(user, "SendMessageW", types.LRESULT, types.HWND, types.UINT,
             types.WPARAM, types.LPARAM)
        bind(user, "PostMessageW", types.BOOL, types.HWND, types.UINT,
             types.WPARAM, types.LPARAM)
        bind(user, "GetWindowTextW", ctypes.c_int, types.HWND, types.LPWSTR, ctypes.c_int)
        bind(user, "GetWindowTextLengthW", ctypes.c_int, types.HWND)
        bind(user, "SetWindowTextW", types.BOOL, types.HWND, types.LPCWSTR)
        bind(user, "IsWindowVisible", types.BOOL, types.HWND)
        bind(user, "ShowWindow", types.BOOL, types.HWND, ctypes.c_int)
        bind(user, "EnumWindows", types.BOOL, self.enum_windows_callback, types.LPARAM)
        bind(user, "GetSystemMetrics", ctypes.c_int, ctypes.c_int)
        bind(user, "SetForegroundWindow", types.BOOL, types.HWND)
        bind(user, "BringWindowToTop", types.BOOL, types.HWND)
        bind(user, "GetAsyncKeyState", types.SHORT, ctypes.c_int)
        bind(user, "VkKeyScanW", types.SHORT, types.WCHAR)
        bind(user, "MapVirtualKeyW", types.UINT, types.UINT, types.UINT)
        bind(user, "SetWindowPos", types.BOOL, types.HWND, types.HWND,
             ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, types.UINT)
        bind(user, "IsZoomed", types.BOOL, types.HWND)
        bind(user, "GetForegroundWindow", types.HWND)
        bind(user, "GetCursorPos", types.BOOL, ctypes.POINTER(types.POINT))
        bind(user, "SetCursorPos", types.BOOL, ctypes.c_int, ctypes.c_int)
        bind(user, "mouse_event", None, types.DWORD, types.DWORD, types.DWORD,
             types.DWORD, types.ULONG_PTR)
        bind(user, "EnumDisplayMonitors", types.BOOL, types.HDC,
             ctypes.POINTER(types.RECT), self.monitor_callback, types.LPARAM)
        bind(user, "GetMonitorInfoW", types.BOOL, types.HANDLE,
             ctypes.POINTER(_MonitorInfo))
        bind(user, "GetDC", types.HDC, types.HWND)
        bind(user, "ReleaseDC", ctypes.c_int, types.HWND, types.HDC)
        bind(user, "IsWindow", types.BOOL, types.HWND)
        bind(user, "IsIconic", types.BOOL, types.HWND)
        bind(user, "IsHungAppWindow", types.BOOL, types.HWND)
        bind(user, "GetWindowThreadProcessId", types.DWORD, types.HWND,
             ctypes.POINTER(types.DWORD))
        bind(user, "GetWindowRect", types.BOOL, types.HWND, ctypes.POINTER(types.RECT))
        bind(user, "GetClientRect", types.BOOL, types.HWND, ctypes.POINTER(types.RECT))
        bind(user, "ClientToScreen", types.BOOL, types.HWND, ctypes.POINTER(types.POINT))
        bind(user, "PrintWindow", types.BOOL, types.HWND, types.HDC, types.UINT)
        bind(user, "GetCursorInfo", types.BOOL, ctypes.POINTER(_CursorInfo))
        bind(user, "CopyIcon", types.HANDLE, types.HANDLE)
        bind(user, "GetIconInfo", types.BOOL, types.HANDLE,
             ctypes.POINTER(_IconInfo))
        bind(user, "DestroyIcon", types.BOOL, types.HANDLE)
        bind(user, "DrawIconEx", types.BOOL, types.HDC, ctypes.c_int,
             ctypes.c_int, types.HANDLE, ctypes.c_int, ctypes.c_int,
             types.UINT, types.HBRUSH, types.UINT)
        bind(gdi, "CreateCompatibleDC", types.HDC, types.HDC)
        bind(gdi, "CreateDIBSection", types.HBITMAP, types.HDC,
             ctypes.POINTER(_BitmapInfo), types.UINT,
             ctypes.POINTER(ctypes.c_void_p), types.HANDLE, types.DWORD)
        bind(gdi, "SelectObject", types.HANDLE, types.HDC, types.HANDLE)
        bind(gdi, "DeleteObject", types.BOOL, types.HANDLE)
        bind(gdi, "DeleteDC", types.BOOL, types.HDC)
        bind(gdi, "BitBlt", types.BOOL, types.HDC, ctypes.c_int,
             ctypes.c_int, ctypes.c_int, ctypes.c_int, types.HDC,
             ctypes.c_int, ctypes.c_int, types.DWORD)
        bind(gdi, "GdiFlush", types.BOOL)

    @contextmanager
    def physical_pixels(self):
        # Per-monitor v2 applies only to this thread and is restored on exit.
        if self.SetThreadDpiAwarenessContext is None:
            raise OSError("ScreenCapture requires Windows 10 version 1703 or newer")
        previous = _checked(self.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4)),
                            "SetThreadDpiAwarenessContext")
        try:
            yield
        finally:
            _checked(self.SetThreadDpiAwarenessContext(previous),
                     "Restore thread DPI awareness")


_shared_api = None
_shared_api_lock = threading.Lock()


def get_api():
    """Lazily share typed bindings across window and input helpers, without DPI changes."""
    global _shared_api
    if _shared_api is None:
        with _shared_api_lock:
            if _shared_api is None:
                _shared_api = _Win32()
    return _shared_api
