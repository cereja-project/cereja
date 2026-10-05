"""Typed Win32 console bindings, loaded only when the native API is constructed."""

import ctypes as C
import os


BOOL = C.c_int32
DWORD = C.c_uint32
WORD = WCHAR = C.c_uint16
SHORT = C.c_int16
HANDLE = C.c_void_p

WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 0x102
WAIT_FAILED = INFINITE = 0xFFFFFFFF


class COORD(C.Structure):
    _fields_ = [("X", SHORT), ("Y", SHORT)]


class SMALL_RECT(C.Structure):
    _fields_ = [("Left", SHORT), ("Top", SHORT), ("Right", SHORT), ("Bottom", SHORT)]


class CONSOLE_SCREEN_BUFFER_INFO(C.Structure):
    _fields_ = [("dwSize", COORD), ("dwCursorPosition", COORD),
                ("wAttributes", WORD), ("srWindow", SMALL_RECT),
                ("dwMaximumWindowSize", COORD)]


class CONSOLE_CURSOR_INFO(C.Structure):
    _fields_ = [("dwSize", DWORD), ("bVisible", BOOL)]


class CHAR_UNION(C.Union):
    _fields_ = [("UnicodeChar", WCHAR), ("AsciiChar", C.c_char)]


class KEY_EVENT_RECORD(C.Structure):
    _fields_ = [("bKeyDown", BOOL), ("wRepeatCount", WORD),
                ("wVirtualKeyCode", WORD), ("wVirtualScanCode", WORD),
                ("uChar", CHAR_UNION), ("dwControlKeyState", DWORD)]


class MOUSE_EVENT_RECORD(C.Structure):
    _fields_ = [("dwMousePosition", COORD), ("dwButtonState", DWORD),
                ("dwControlKeyState", DWORD), ("dwEventFlags", DWORD)]


class WINDOW_BUFFER_SIZE_RECORD(C.Structure):
    _fields_ = [("dwSize", COORD)]


class MENU_EVENT_RECORD(C.Structure):
    _fields_ = [("dwCommandId", DWORD)]


class FOCUS_EVENT_RECORD(C.Structure):
    _fields_ = [("bSetFocus", BOOL)]


class EVENT_UNION(C.Union):
    _fields_ = [("KeyEvent", KEY_EVENT_RECORD), ("MouseEvent", MOUSE_EVENT_RECORD),
                ("WindowBufferSizeEvent", WINDOW_BUFFER_SIZE_RECORD),
                ("MenuEvent", MENU_EVENT_RECORD), ("FocusEvent", FOCUS_EVENT_RECORD)]


class INPUT_RECORD(C.Structure):
    _fields_ = [("EventType", WORD), ("Event", EVENT_UNION)]


class Win32API:
    """Own no console handles; methods raise the original Win32 error on failure."""

    def __init__(self):
        if os.name != "nt":
            raise OSError("Win32 console APIs are available only on Windows")
        self._dll = C.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "GetConsoleMode": ([HANDLE, C.POINTER(DWORD)], BOOL),
            "SetConsoleMode": ([HANDLE, DWORD], BOOL),
            "GetConsoleCursorInfo": ([HANDLE, C.POINTER(CONSOLE_CURSOR_INFO)], BOOL),
            "SetConsoleCursorInfo": ([HANDLE, C.POINTER(CONSOLE_CURSOR_INFO)], BOOL),
            "GetConsoleScreenBufferInfo": ([HANDLE, C.POINTER(CONSOLE_SCREEN_BUFFER_INFO)], BOOL),
            "SetConsoleCursorPosition": ([HANDLE, COORD], BOOL),
            "CreateEventW": ([C.c_void_p, BOOL, BOOL, C.c_wchar_p], HANDLE),
            "SetEvent": ([HANDLE], BOOL),
            "CloseHandle": ([HANDLE], BOOL),
            "WaitForMultipleObjects": ([DWORD, C.POINTER(HANDLE), BOOL, DWORD], DWORD),
            "ReadConsoleInputW": ([HANDLE, C.POINTER(INPUT_RECORD), DWORD, C.POINTER(DWORD)], BOOL),
            "WriteConsoleW": ([HANDLE, C.c_void_p, DWORD, C.POINTER(DWORD), C.c_void_p], BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self._dll, name)
            function.argtypes, function.restype = arguments, result

    @staticmethod
    def _error():
        return C.WinError(C.get_last_error())

    @staticmethod
    def stream_handle(stream):
        import msvcrt
        try:
            handle = msvcrt.get_osfhandle(stream.fileno())
            return None if handle in (-1, 0) else handle
        except (AttributeError, OSError, ValueError, TypeError):
            return None

    def get_mode(self, handle):
        mode = DWORD()
        if handle is None or not self._dll.GetConsoleMode(handle, C.byref(mode)):
            return None
        return mode.value

    def set_mode(self, handle, mode):
        if not self._dll.SetConsoleMode(handle, mode):
            raise self._error()

    def get_cursor(self, handle):
        info = CONSOLE_CURSOR_INFO()
        if not self._dll.GetConsoleCursorInfo(handle, C.byref(info)):
            raise self._error()
        return info.dwSize, bool(info.bVisible)

    def set_cursor(self, handle, size, visible):
        info = CONSOLE_CURSOR_INFO(size, visible)
        if not self._dll.SetConsoleCursorInfo(handle, C.byref(info)):
            raise self._error()

    def get_screen(self, handle):
        info = CONSOLE_SCREEN_BUFFER_INFO()
        if not self._dll.GetConsoleScreenBufferInfo(handle, C.byref(info)):
            raise self._error()
        return (max(0, info.srWindow.Right - info.srWindow.Left + 1),
                max(0, info.srWindow.Bottom - info.srWindow.Top + 1),
                info.dwCursorPosition.X, info.dwCursorPosition.Y)

    def set_position(self, handle, x, y):
        if not self._dll.SetConsoleCursorPosition(handle, COORD(x, y)):
            raise self._error()

    def create_event(self):
        # Auto-reset coalesces wakeups for the single input consumer.
        handle = self._dll.CreateEventW(None, False, False, None)
        if not handle:
            raise self._error()
        return handle

    def set_event(self, handle):
        if not self._dll.SetEvent(handle):
            raise self._error()

    def close_handle(self, handle):
        if not self._dll.CloseHandle(handle):
            raise self._error()

    def wait(self, handles, milliseconds):
        array = (HANDLE * len(handles))(*handles)
        result = self._dll.WaitForMultipleObjects(len(handles), array, False, milliseconds)
        if result == WAIT_FAILED:
            raise self._error()
        return result

    def read_input(self, handle, limit):
        records = (INPUT_RECORD * limit)()
        read = DWORD()
        if not self._dll.ReadConsoleInputW(handle, records, limit, C.byref(read)):
            raise self._error()
        return tuple(records[index] for index in range(read.value))

    def write_console(self, handle, data):
        units = len(data) // 2
        buffer = (WCHAR * units).from_buffer_copy(data)
        written = DWORD()
        if not self._dll.WriteConsoleW(handle, buffer, units, C.byref(written), None):
            raise self._error()
        return written.value
