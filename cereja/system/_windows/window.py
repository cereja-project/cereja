"""Window metadata, display controls and legacy image serialization."""

import ctypes
import time
from typing import Optional

from .api import get_api
from .constants import ShowWindowCommand, WindowMessage
from .keyboard import Keyboard
from .mouse import Mouse
from .types import DWORD, HWND, RECT


class Window:
    """Query, control and capture a Windows window by its native handle.

    Keyboard and mouse helpers target this HWND. Display methods may
    activate the window according to the requested Windows command."""

    def __init__(self,
                 hwnd: HWND):
        """Associate this instance with a native window handle."""
        self.hwnd = hwnd
        self._keyboard = None
        self._mouse = None

    def __repr__(self):
        return f"{self.__class__.__name__}<{self.title}>"

    @property
    def keyboard(self) -> "Keyboard":
        if self._keyboard is None:
            self._keyboard = Keyboard(self.hwnd)
        return self._keyboard

    @property
    def mouse(self) -> "Mouse":
        if self._mouse is None:
            self._mouse = Mouse(self.hwnd)
        return self._mouse

    @property
    def title(self) -> str:
        """Get or set the window title."""
        length = get_api().GetWindowTextLengthW(self.hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        get_api().GetWindowTextW(self.hwnd, buff, length + 1)
        return buff.value or "UNKNOW"

    @title.setter
    def title(self,
              value: str):
        """Get or set the window title."""
        get_api().SetWindowTextW(self.hwnd, value)

    @property
    def is_visible(self) -> bool:
        """Return whether the window has the Windows visible style."""
        return bool(get_api().IsWindowVisible(self.hwnd))

    @property
    def pid(self) -> int:
        """Return the process ID that owns this window."""
        pid = DWORD()
        get_api().GetWindowThreadProcessId(self.hwnd, ctypes.byref(pid))
        return pid.value

    @staticmethod
    def _enum_windows_callback(hwnd,
                               lParam):
        try:
            if get_api().IsWindowVisible(hwnd):
                windows = ctypes.cast(lParam, ctypes.POINTER(ctypes.py_object)).contents.value
                windows.append(Window(hwnd))
        except Exception:
            return False
        return True

    @staticmethod
    def get_all_windows():
        """Return Window instances for visible top-level windows."""
        windows = []
        api = get_api()
        payload = ctypes.py_object(windows)
        address = ctypes.cast(ctypes.pointer(payload), ctypes.c_void_p).value
        callback = api.enum_windows_callback(Window._enum_windows_callback)
        api.EnumWindows(callback, address)
        return windows

    @classmethod
    def find_windows(cls,
                     text: str):
        """Return visible windows whose titles contain text, ignoring case."""
        return [w for w in cls.get_all_windows() if text.lower().strip() in w.title.lower()]

    @classmethod
    def get_foreground_window(cls) -> "Window":
        """Return the current foreground window."""
        return cls(get_api().GetForegroundWindow())

    @property
    def dimensions(self) -> tuple[int, int, int, int]:
        """Get or set (left, top, right, bottom), including title bar and borders."""
        rect = RECT()
        get_api().GetWindowRect(self.hwnd, ctypes.byref(rect))
        return rect.left, rect.top, rect.right, rect.bottom

    @dimensions.setter
    def dimensions(self,
                   dims: tuple[int, int, int, int]):
        """Get or set (left, top, right, bottom), including title bar and borders."""
        left, top, right, bottom = dims
        width = right - left
        height = bottom - top
        get_api().SetWindowPos(self.hwnd, 0, left, top, width, height, 0)

    @property
    def dimensions_window_content(self) -> tuple[int, int, int, int]:
        """Return the client-area rectangle in client coordinates."""
        client_rect = RECT()
        get_api().GetClientRect(self.hwnd, ctypes.byref(client_rect))
        return (client_rect.left, client_rect.top,
                client_rect.right, client_rect.bottom)

    @property
    def size_window_content(self) -> tuple[int, int]:
        """Return the client-area (width, height)."""
        left, top, right, bottom = self.dimensions_window_content
        return (right - left, bottom - top)

    @property
    def size(self) -> tuple[int, int]:
        """Return the full window (width, height)."""
        left, top, right, bottom = self.dimensions
        return (right - left, bottom - top)

    def send_command(self,
                     command: int):
        """Post a WM_COMMAND message with the supplied command identifier."""
        get_api().PostMessageW(self.hwnd, WindowMessage.COMMAND, command, 0)

    @property
    def state(self) -> str:
        """Return "Minimized", "Maximized" or "Normal"."""
        if get_api().IsIconic(self.hwnd):
            return "Minimized"
        elif get_api().IsZoomed(self.hwnd):
            return "Maximized"
        else:
            return "Normal"

    def _capture_frame(self, only_window_content=True):
        """Use the shared capture core, retaining legacy minimized restoration."""
        from .capture import ScreenCapture

        if get_api().IsIconic(self.hwnd):
            get_api().ShowWindow(self.hwnd, ShowWindowCommand.RESTORE)
            time.sleep(0.05)
            get_api().ShowWindow(self.hwnd, ShowWindowCommand.SHOWNOACTIVATE)
        hwnd = self.hwnd.value if isinstance(self.hwnd, ctypes.c_void_p) else self.hwnd
        with ScreenCapture(include_cursor=False) as capture:
            return capture.grab(window=hwnd, only_window_content=only_window_content)

    def capture_image_bmp(self,
                          filepath: str = None,
                          only_window_content: bool = True) -> bytes:
        """Return raw top-down BGRA pixels; optionally write a BMP file.

        The return value has no BMP header, preserving the existing contract.
        A file written through ``filepath`` includes a 54-byte BMP header.
        Capturing uses the same PrintWindow core as ScreenCapture, without a
        desktop fallback. Unlike ScreenCapture, this legacy API restores a
        minimized window before capture. Native capture failures raise OSError.
        """
        import struct

        frame = self._capture_frame(only_window_content)
        if filepath:
            header = struct.pack("<2sIHHI", b"BM", 54 + len(frame.bgra), 0, 0, 54)
            header += struct.pack("<IiiHHIIiiII", 40, frame.width, -frame.height,
                                  1, 32, 0, 0, 0, 0, 0, 0)
            with open(filepath, "wb") as output:
                output.write(header)
                output.write(frame.bgra)
        return frame.bgra

    def capture_image_ppm(self,
                          ppm_path: Optional[str] = None,
                          only_window_content: bool = True) -> bytes:
        """Return a P6 PPM image and optionally write it to ``ppm_path``.

        Dimensions and pixels come from one shared capture frame, including
        when DPI or window dimensions differ from a later desktop query.
        """
        frame = self._capture_frame(only_window_content)
        rgb = bytearray(frame.width * frame.height * 3)
        rgb[0::3] = frame.bgra[2::4]
        rgb[1::3] = frame.bgra[1::4]
        rgb[2::3] = frame.bgra[0::4]
        ppm_bytes = f"P6\n{frame.width} {frame.height}\n255\n".encode("ascii") + bytes(rgb)
        if ppm_path:
            try:
                with open(ppm_path, "wb") as output:
                    output.write(ppm_bytes)
            except Exception as error:
                raise RuntimeError(f"Could not save PPM to '{ppm_path}': {error}") from error
        return ppm_bytes

    def to_png_file(self,
                    png_path: str,
                    only_window_content: bool = True):
        """Capture the window or client area and save a PNG using Tkinter."""
        try:
            from tkinter import PhotoImage, Tk
        except ImportError:
            raise ImportError("Saving PNG files requires Tkinter.")
        import cereja as cj
        root = Tk()
        root.withdraw()

        ppm_bytes = self.capture_image_ppm(ppm_path=None, only_window_content=only_window_content)
        assert cj.Path(png_path).ext.replace('.', '') == "png", f"png_path must have a .png extension: {png_path}"
        PhotoImage(data=ppm_bytes).write(png_path, format="png")
        # Release the serialized image buffer.
        del ppm_bytes

        root.destroy()

    # Window display commands.
    def hide(self):
        """Hide the window."""
        get_api().ShowWindow(self.hwnd, ShowWindowCommand.HIDE)

    def show_normal(self):
        """Activate the window and restore its original size and position."""
        get_api().ShowWindow(self.hwnd, ShowWindowCommand.SHOWNORMAL)

    def show_minimized(self):
        """Activate the window and display it minimized."""
        get_api().ShowWindow(self.hwnd, ShowWindowCommand.SHOWMINIMIZED)

    def maximize(self):
        """Activate and maximize the window."""
        get_api().ShowWindow(self.hwnd, ShowWindowCommand.SHOWMAXIMIZED)

    def show_no_activate(self):
        """Restore the window size and position without activating it."""
        get_api().ShowWindow(self.hwnd, ShowWindowCommand.SHOWNOACTIVATE)

    def show(self):
        """Activate the window and display its current size and position."""
        get_api().ShowWindow(self.hwnd, ShowWindowCommand.SHOW)

    def minimize(self):
        """Minimize the window and activate the next top-level window."""
        get_api().ShowWindow(self.hwnd, ShowWindowCommand.MINIMIZE)

    def show_min_no_active(self):
        """Display the window minimized without activating it."""
        get_api().ShowWindow(self.hwnd, ShowWindowCommand.SHOWMINNOACTIVE)

    def show_na(self):
        """Display the current window size and position without activating it."""
        get_api().ShowWindow(self.hwnd, ShowWindowCommand.SHOWNA)

    def restore(self):
        """Activate the window and restore it from a minimized or maximized state."""
        get_api().ShowWindow(self.hwnd, ShowWindowCommand.RESTORE)

    def show_default(self):
        """Use the display state specified in the process startup information."""
        get_api().ShowWindow(self.hwnd, ShowWindowCommand.SHOWDEFAULT)

    def set_foreground(self):
        """Ask Windows to activate this window and bring it to the foreground."""
        get_api().SetForegroundWindow(self.hwnd)

    def bring_to_top(self):
        """Raise the window in Z-order; a top-level window is also activated."""
        get_api().BringWindowToTop(self.hwnd)
