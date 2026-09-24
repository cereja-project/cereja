"""Window metadata, display controls and legacy image serialization."""

import ctypes
import time
from typing import Optional

from .api import get_api
from .keyboard import Keyboard
from .mouse import Mouse
from .types import DWORD, HWND, RECT

SW_HIDE = 0
SW_SHOW = 5
SW_RESTORE = 9
SW_SHOWNA = 4


class Window:
    """
    Representa uma janela no sistema operacional Windows, fornecendo métodos para interagir com ela.

    Métodos:
        title: Obtém ou define o título da janela.
        is_visible: Retorna True se a janela estiver visível.
        show: Modifica o estado de exibição da janela.
        get_all_windows: Retorna todas as janelas visíveis.
        dimensions: Obtém ou define as dimensões da janela.
        send_command: Envia um comando para a janela.
        state: Retorna o estado atual da janela.
        capture_image_bmp: Captura a imagem da janela como BMP, mesmo se não for a janela foreground.

    Propriedades:
        hwnd: Handle da janela.
    """

    def __init__(self,
                 hwnd: HWND):
        """
        Inicializa uma instância da classe Window.

        Args:
            hwnd (HWND): Handle da janela.
        """
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
        """
        Retorna o título da janela.
        """
        length = get_api().GetWindowTextLengthW(self.hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        get_api().GetWindowTextW(self.hwnd, buff, length + 1)
        return buff.value or "UNKNOW"

    @title.setter
    def title(self,
              value: str):
        """
        Define o título da janela.
        """
        get_api().SetWindowTextW(self.hwnd, value)

    @property
    def is_visible(self) -> bool:
        """
        Verifica se a janela está visível.
        """
        return bool(get_api().IsWindowVisible(self.hwnd))

    @property
    def pid(self) -> int:
        """
        Retorna o PID do processo que criou a janela.
        """
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
        """
        Retorna uma lista de todas as janelas visíveis.
        """
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
        """
        Encontra janelas cujo título contenha 'text' (case-insensitive).
        """
        return [w for w in cls.get_all_windows() if text.lower().strip() in w.title.lower()]

    @classmethod
    def get_foreground_window(cls) -> "Window":
        """
        Retorna a janela que está atualmente em primeiro plano.
        """
        return cls(get_api().GetForegroundWindow())

    @property
    def dimensions(self) -> tuple[int, int, int, int]:
        """
        Obtém as dimensões da janela (incluindo bordas e título).

        Returns:
            (left, top, right, bottom)
        """
        rect = RECT()
        get_api().GetWindowRect(self.hwnd, ctypes.byref(rect))
        return rect.left, rect.top, rect.right, rect.bottom

    @dimensions.setter
    def dimensions(self,
                   dims: tuple[int, int, int, int]):
        """
        Define as dimensões da janela.

        Args:
            dims: (left, top, right, bottom)
        """
        left, top, right, bottom = dims
        width = right - left
        height = bottom - top
        get_api().SetWindowPos(self.hwnd, 0, left, top, width, height, 0)

    @property
    def dimensions_window_content(self) -> tuple[int, int, int, int]:
        """
        Obtém as dimensões da área cliente (coords relativas: (0,0) → (width, height)).
        """
        client_rect = RECT()
        get_api().GetClientRect(self.hwnd, ctypes.byref(client_rect))
        return (client_rect.left, client_rect.top,
                client_rect.right, client_rect.bottom)

    @property
    def size_window_content(self) -> tuple[int, int]:
        """
        Retorna (width, height) da área cliente.
        """
        left, top, right, bottom = self.dimensions_window_content
        return (right - left, bottom - top)

    @property
    def size(self) -> tuple[int, int]:
        """
        Retorna (width, height) da janela inteira.
        """
        left, top, right, bottom = self.dimensions
        return (right - left, bottom - top)

    def send_command(self,
                     command: int):
        """
        Envia um comando (WM_COMMAND) para a janela.

        Args:
            command: Código do comando a enviar.
        """
        get_api().PostMessageW(self.hwnd, 0x0111, command, 0)  # WM_COMMAND = 0x0111

    @property
    def state(self) -> str:
        """
        Retorna "Minimized", "Maximized" ou "Normal" conforme o estado da janela.
        """
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
            get_api().ShowWindow(self.hwnd, SW_RESTORE)
            time.sleep(0.05)
            get_api().ShowWindow(self.hwnd, SW_SHOWNA)
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
        """
        Captura a janela (ou área cliente) e salva como PNG.
        @param png_path:
        @param only_window_content:
        @return:
        """
        try:
            from tkinter import PhotoImage, Tk
        except ImportError:
            raise ImportError("Para salvar como PNG, é necessário ter o Tkinter instalado.")
        import cereja as cj
        root = Tk()
        root.withdraw()

        ppm_bytes = self.capture_image_ppm(ppm_path=None, only_window_content=only_window_content)
        assert cj.Path(png_path).ext.replace('.', '') == "png", f"png_path deve ter extensão .png: {png_path}"
        PhotoImage(data=ppm_bytes).write(png_path, format="png")
        # limpa memória
        del ppm_bytes

        root.destroy()

    # Métodos de exibição/ocultação
    def hide(self):
        """Oculta a janela completamente."""
        get_api().ShowWindow(self.hwnd, SW_HIDE)

    def show_normal(self):
        """Mostra a janela em estado normal."""
        get_api().ShowWindow(self.hwnd, 1)

    def show_minimized(self):
        """Minimiza a janela."""
        get_api().ShowWindow(self.hwnd, 2)

    def maximize(self):
        """Maximiza a janela."""
        get_api().ShowWindow(self.hwnd, 3)

    def show_no_activate(self):
        """Mostra a janela sem ativá-la."""
        get_api().ShowWindow(self.hwnd, SW_SHOWNA)

    def show(self):
        """Mostra/ativa a janela."""
        get_api().ShowWindow(self.hwnd, SW_SHOW)

    def minimize(self):
        """Minimiza a janela sem restaurar foco."""
        get_api().ShowWindow(self.hwnd, 6)

    def show_min_no_active(self):
        """Mostra a janela minimizada, sem ativar."""
        get_api().ShowWindow(self.hwnd, 7)

    def show_na(self):
        """Mostra a janela sem ativar."""
        get_api().ShowWindow(self.hwnd, 8)

    def restore(self):
        """Restaura a janela do estado minimizado ou maximizado."""
        get_api().ShowWindow(self.hwnd, SW_RESTORE)

    def show_default(self):
        """Define o estado de exibição com base em STARTUPINFO."""
        get_api().ShowWindow(self.hwnd, 10)

    def set_foreground(self):
        """Traz a janela ao primeiro plano."""
        get_api().SetForegroundWindow(self.hwnd)

    def bring_to_top(self):
        """Eleva a janela no Z-order sem ativá-la."""
        get_api().BringWindowToTop(self.hwnd)
