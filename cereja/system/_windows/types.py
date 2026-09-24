"""Shared Win32 ABI types, structures and callback signatures.

Declaring these types does not load DLLs or change process/thread state.
"""

import ctypes
from ctypes import wintypes

BOOL = wintypes.BOOL
DWORD = wintypes.DWORD
HANDLE = wintypes.HANDLE
HBITMAP = wintypes.HBITMAP
HBRUSH = wintypes.HBRUSH
HDC = wintypes.HDC
HWND = wintypes.HWND
LONG = wintypes.LONG
LPCWSTR = wintypes.LPCWSTR
LPWSTR = wintypes.LPWSTR
POINT = wintypes.POINT
RECT = wintypes.RECT
SHORT = wintypes.SHORT
UINT = wintypes.UINT
WCHAR = wintypes.WCHAR
WORD = wintypes.WORD
# Windows uses pointer-sized values here, including on 64-bit Python.
LPARAM = ctypes.c_ssize_t
LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
ULONG_PTR = ctypes.c_size_t

# Only declarations are used outside Windows; native calls remain Windows-only.
_callback_type = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
ENUMWINDOWSPROC = _callback_type(BOOL, HWND, LPARAM)
MONITORENUMPROC = _callback_type(BOOL, HANDLE, HDC, ctypes.POINTER(RECT), LPARAM)


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BitmapInfo(ctypes.Structure):
    _fields_ = [("bmiHeader", _BitmapInfoHeader), ("bmiColors", wintypes.DWORD * 3)]


class _MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * 32),
    ]


class _CursorInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
        ("hCursor", wintypes.HANDLE), ("ptScreenPos", wintypes.POINT),
    ]


class _IconInfo(ctypes.Structure):
    _fields_ = [
        ("fIcon", wintypes.BOOL), ("xHotspot", wintypes.DWORD),
        ("yHotspot", wintypes.DWORD), ("hbmMask", wintypes.HBITMAP),
        ("hbmColor", wintypes.HBITMAP),
    ]
