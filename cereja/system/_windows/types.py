"""Shared Win32 ABI types, structures and callback signatures.

Names follow the Windows headers for scalars, structures and callbacks.
Structures use the aliases declared here, including pointer-sized message
parameters. Declaring these types does not load DLLs or change process state.
"""

import ctypes
from ctypes import wintypes

# Windows scalar and string types.
BOOL = wintypes.BOOL
# Python 3.11's wintypes.BYTE is signed; Windows BYTE is always unsigned.
BYTE = ctypes.c_ubyte
DWORD = wintypes.DWORD
INT = ctypes.c_int
LONG = wintypes.LONG
LPCWSTR = wintypes.LPCWSTR
LPWSTR = wintypes.LPWSTR
SHORT = wintypes.SHORT
UINT = wintypes.UINT
WCHAR = wintypes.WCHAR
WORD = wintypes.WORD

# Opaque handles and pointer-sized message parameters.
HANDLE = wintypes.HANDLE
HBITMAP = wintypes.HBITMAP
HBRUSH = wintypes.HBRUSH
HDC = wintypes.HDC
HWND = wintypes.HWND
LPVOID = ctypes.c_void_p
LPARAM = ctypes.c_ssize_t
LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
ULONG_PTR = ctypes.c_size_t

# Existing Windows structures retain their ctypes identity.
POINT = wintypes.POINT
RECT = wintypes.RECT


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", DWORD), ("biWidth", LONG),
        ("biHeight", LONG), ("biPlanes", WORD),
        ("biBitCount", WORD), ("biCompression", DWORD),
        ("biSizeImage", DWORD), ("biXPelsPerMeter", LONG),
        ("biYPelsPerMeter", LONG), ("biClrUsed", DWORD),
        ("biClrImportant", DWORD),
    ]


class RGBQUAD(ctypes.Structure):
    _fields_ = [("rgbBlue", BYTE), ("rgbGreen", BYTE),
                ("rgbRed", BYTE), ("rgbReserved", BYTE)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", RGBQUAD * 1)]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", DWORD), ("rcMonitor", RECT),
        ("rcWork", RECT), ("dwFlags", DWORD),
        ("szDevice", WCHAR * 32),
    ]


class CURSORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", DWORD), ("flags", DWORD),
        ("hCursor", HANDLE), ("ptScreenPos", POINT),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [
        ("fIcon", BOOL), ("xHotspot", DWORD),
        ("yHotspot", DWORD), ("hbmMask", HBITMAP),
        ("hbmColor", HBITMAP),
    ]


# Non-Windows imports declare types only; native invocation is Windows-only.
_callback_type = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
ENUMWINDOWSPROC = _callback_type(BOOL, HWND, LPARAM)
MONITORENUMPROC = _callback_type(BOOL, HANDLE, HDC, ctypes.POINTER(RECT), LPARAM)
