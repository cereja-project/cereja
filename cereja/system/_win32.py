import ctypes.wintypes
import os
import sys
import tempfile
import threading
import time
from ctypes import wintypes
import random
from typing import Tuple, Optional
from ..utils import invert_dict, is_numeric_sequence

import ctypes
from ctypes.wintypes import HWND, LPARAM, BOOL

if sys.platform != 'win32':
    raise ImportError('The module should only be loaded on a Windows system.')

# Corrige problema de escala
try:
    ctypes.windll.user32.SetProcessDPIAware()
except AttributeError:
    print("ERRO")
    pass

# Definir MessageBeep
MessageBeep = ctypes.windll.user32.MessageBeep
MessageBeep.argtypes = [wintypes.UINT]
MessageBeep.restype = wintypes.BOOL

# Constantes para os tipos de sons de alerta
MB_ICONASTERISK = 0x00000040
MB_ICONEXCLAMATION = 0x00000030
MB_ICONHAND = 0x00000010
MB_ICONQUESTION = 0x00000020
MB_OK = 0x00000000

# Definições para a API do Windows
SendMessage = ctypes.windll.user32.SendMessageW
SendMessage.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
SendMessage.restype = ctypes.c_long  # Usando ctypes.c_long para LRESULT

PostMessage = ctypes.windll.user32.PostMessageW
PostMessage.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
PostMessage.restype = wintypes.BOOL

GetWindowText = ctypes.windll.user32.GetWindowTextW
GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
SetWindowText = ctypes.windll.user32.SetWindowTextW
IsWindowVisible = ctypes.windll.user32.IsWindowVisible
ShowWindow = ctypes.windll.user32.ShowWindow
EnumWindows = ctypes.windll.user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(BOOL, HWND, LPARAM)
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
GetClientRect = user32.GetClientRect
ClientToScreen = user32.ClientToScreen
GetSystemMetrics = user32.GetSystemMetrics
GetDIBits = gdi32.GetDIBits
SetForegroundWindow = user32.SetForegroundWindow
BringWindowToTop = user32.BringWindowToTop
PostMessage = user32.PostMessageW
GetAsyncKeyState = user32.GetAsyncKeyState
VkKeyScanA = user32.VkKeyScanA
MapVirtualKey = user32.MapVirtualKeyW
GetWindowRect = user32.GetWindowRect
SetWindowPos = user32.SetWindowPos
IsIconic = user32.IsIconic
IsZoomed = user32.IsZoomed
GetWindowDC = user32.GetWindowDC
GetDC = user32.GetDC
GetForegroundWindow = user32.GetForegroundWindow
ReleaseDC = user32.ReleaseDC
PrintWindow = user32.PrintWindow
CreateCompatibleDC = ctypes.windll.gdi32.CreateCompatibleDC
CreateCompatibleBitmap = ctypes.windll.gdi32.CreateCompatibleBitmap
SelectObject = ctypes.windll.gdi32.SelectObject
BitBlt = ctypes.windll.gdi32.BitBlt
DeleteObject = ctypes.windll.gdi32.DeleteObject
DeleteDC = ctypes.windll.gdi32.DeleteDC
GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId

# Constantes para mensagens de teclado
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
# Constantes ShowWindow
SW_HIDE = 0
SW_SHOW = 5
SW_RESTORE = 9
SW_SHOWNA = 4

# Constantes GDI e DIB
SRCCOPY = 0x00CC0020
BI_RGB = 0
DIB_RGB_COLORS = 0
PW_RENDERFULLCONTENT = 0x00000002  # força DWM a renderizar o conteúdo completo, mesmo se não for foreground


# Estruturas para GetDIBits
class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", ctypes.c_long),
        ("biHeight", ctypes.c_long),
        ("biPlanes", ctypes.c_ushort),
        ("biBitCount", ctypes.c_ushort),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", ctypes.c_long),
        ("biYPelsPerMeter", ctypes.c_long),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3),
    ]


class Time:
    def __init__(self):
        self._t0 = None
        self._started = False
        self._stopped_on = None
        self._endtime = None
        self._last_time_check = None

    @property
    def t0(self):
        return self._t0

    @property
    def time(self):
        if self._t0 is None:
            self.start()
        self._last_time_check = time.time()
        if self._stopped_on:
            return self._stopped_on - self._t0
        return time.time() - self._t0

    @property
    def last_check_time(self):
        return time.time() - self._last_time_check

    def start(self):
        self._stopped_on = None
        self._t0 = time.time()
        self._last_time_check = self._t0

    def stop(self):
        if self._started:
            self._stopped_on = time.time()
            return
        raise Exception("Time counting has not started. Use Time.start method.")


def play_alert_sound(sound_type=MB_ICONHAND):
    MessageBeep(sound_type)


class Keyboard:
    """
    Simula e detecta pressionamentos de teclas EM UMA JANELA ESPECÍFICA, mesmo se não estiver em primeiro plano.

    Ao instanciar, passe o handle (HWND) da janela alvo:
        kb = Keyboard(hwnd=meu_hwnd)

    Todos os métodos de key_press enviarão WM_KEYDOWN/WM_KEYUP diretamente para self._hwnd,
    construindo lParam com código de varredura apropriado para que a aplicação receba a mensagem
    como se fosse teclado real—even que esteja em segundo plano.
    """

    __KEY_NAME_TO_CODE = {
        'BACKSPACE': 8, 'TAB': 9, 'CLEAR': 12, 'ENTER': 13, 'SHIFT': 16, 'CTRL': 17,
        'ALT':       18, 'PAUSE': 19, 'CAPS_LOCK': 20, 'ESC': 27, 'SPACEBAR': 32,
        'PAGE_UP':   33, 'PAGE_DOWN': 34, 'END': 35, 'HOME': 36, 'LEFT_ARROW': 37,
        'UP_ARROW':  38, 'RIGHT_ARROW': 39, 'DOWN_ARROW': 40, 'INSERT': 45,
        'DELETE':    46, '0': 48, '1': 49, '2': 50, '3': 51, '4': 52, '5': 53,
        '6':         54, '7': 55, '8': 56, '9': 57,
        'A':         65, 'B': 66, 'C': 67, 'D': 68, 'E': 69, 'F': 70, 'G': 71, 'H': 72,
        'I':         73, 'J': 74, 'K': 75, 'L': 76, 'M': 77, 'N': 78, 'O': 79, 'P': 80,
        'Q':         81, 'R': 82, 'S': 83, 'T': 84, 'U': 85, 'V': 86, 'W': 87, 'X': 88,
        'Y':         89, 'Z': 90,
        'F1':        112, 'F2': 113, 'F3': 114, 'F4': 115, 'F5': 116, 'F6': 117,
        'F7':        118, 'F8': 119, 'F9': 120, 'F10': 121, 'F11': 122, 'F12': 123,
        '+':         187, ',': 188, '-': 189, '.': 190, '/': 191, '`': 192, ';': 186,
        '[':         219, '\\': 220, ']': 221, "'": 222
    }
    # Adiciona códigos ASCII imprimíveis (32–127)
    for c in range(32, 128):
        ch = chr(c)
        sc = VkKeyScanA(ctypes.c_wchar(ch))
        vk = sc & 0xFF
        __KEY_NAME_TO_CODE[ch] = vk

    __KEY_CODE_TO_NAME = invert_dict(__KEY_NAME_TO_CODE)
    MAX_TIME_SIMULATE_KEY_PRESS = 0.1

    def __init__(self,
                 hwnd: int = None,
                 is_async: bool = True):
        """
        Args:
            hwnd: handle da janela alvo. Se None, métodos apenas detectam estado de teclas, sem enviar.
            is_async: se True, usa PostMessage; se False, usa SendMessage.
        """
        self._hwnd = hwnd
        self._is_async = bool(is_async)
        self._max_time_simulate = self.MAX_TIME_SIMULATE_KEY_PRESS
        self._key_press_callbacks = None

    @property
    def hwnd(self) -> int:
        return self._hwnd

    @hwnd.setter
    def hwnd(self,
             value: int):
        self._hwnd = value

    @property
    def is_async(self) -> bool:
        return self._is_async

    @is_async.setter
    def is_async(self,
                 v: bool):
        self._is_async = bool(v)

    @property
    def max_time_key_press(self) -> float:
        return self._max_time_simulate

    @max_time_key_press.setter
    def max_time_key_press(self,
                           v: float):
        self._max_time_simulate = v

    @property
    def key_map(self) -> dict:
        return self.__KEY_NAME_TO_CODE.copy()

    @classmethod
    def _parse_key(cls,
                   v) -> list[int]:
        """
        Recebe nome de tecla (ex: "A", "CTRL+A") ou código int.
        Retorna lista de códigos virtuais.
        """
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            parts = v.split("+")
            codes = []
            for p in parts:
                p = p.strip().upper()
                if p not in cls.__KEY_NAME_TO_CODE:
                    raise ValueError(f"Tecla inválida: {p}")
                codes.append(cls.__KEY_NAME_TO_CODE[p])
            return codes
        raise ValueError(f"Valor de tecla não reconhecido: {v}")

    def _is_pressed(self,
                    key_code: int) -> bool:
        """
        Verifica estado físico da tecla via GetAsyncKeyState.
        """
        return bool(GetAsyncKeyState(key_code) & 0x8000)

    def is_pressed(self,
                   key) -> bool:
        """
        Checa se TODAS as teclas do combo estão pressionadas fisicamente.
        """
        codes = self._parse_key(key)
        return all(self._is_pressed(code) for code in codes)

    def _make_lparam(self,
                     vk_code: int,
                     is_keyup: bool = False) -> int:
        """
        Monta o lParam para PostMessage/SendMessage de WM_KEYDOWN ou WM_KEYUP:
            bits 0–15: contagem de repetição (usamos 1)
            bits 16–23: código de varredura
            bit 24: estado EXTENDED? (0 para teclas padrão)
            bit 30: contexto (0 para tecla não precedida por ALT)
            bit 31: transição (0 para KEYDOWN, 1 para KEYUP)
        """
        scan_code = MapVirtualKey(vk_code, 0) & 0xFF
        repeat_count = 1
        extended = 0
        context = 0
        transition = 1 if is_keyup else 0
        lparam = (
                repeat_count
                | (scan_code << 16)
                | (extended << 24)
                | (context << 29)
                | (transition << 31)
        )
        return lparam

    def _send_key_down(self,
                       vk_code: int):
        """
        Envia WM_KEYDOWN para a janela selecionada (self._hwnd), mesmo em background.
        """
        if not self._hwnd:
            return
        lparam = self._make_lparam(vk_code, is_keyup=False)
        if self._is_async:
            PostMessage(self._hwnd, WM_KEYDOWN, vk_code, lparam)
        else:
            SendMessage(self._hwnd, WM_KEYDOWN, vk_code, lparam)

    def _send_key_up(self,
                     vk_code: int):
        """
        Envia WM_KEYUP para a janela selecionada (self._hwnd).
        """
        if not self._hwnd:
            return
        lparam = self._make_lparam(vk_code, is_keyup=True)
        if self._is_async:
            PostMessage(self._hwnd, WM_KEYUP, vk_code, lparam)
        else:
            SendMessage(self._hwnd, WM_KEYUP, vk_code, lparam)

    def _press_and_wait(self,
                        vk_code: int,
                        duration: float):
        """
        Mantém a tecla pressionada por 'duration' segundos, enviando repetidos KEYDOWN.
        """
        timer = Time()
        while timer.time < duration:
            self._send_key_down(vk_code)
            time.sleep(0.01)
        self._send_key_up(vk_code)

    def _press_n_times(self,
                       vk_code: int,
                       n_times: int = 1):
        """
        Pressiona e solta a tecla n vezes, com pequena aleatoriedade entre eventos.
        """
        for _ in range(n_times):
            self._send_key_down(vk_code)
            time.sleep((random.random() * self._max_time_simulate) + 0.01)
            self._send_key_up(vk_code)

    def _press_key_sequence(self,
                            vk_codes: list[int],
                            n_times: int = 1,
                            secs: float = None):
        """
        Envia combinação de teclas (ex: [CTRL, 'A']): KEYDOWN dos modificadores, depois 'last',
        depois KEYUP dos modificadores.
        """
        if len(vk_codes) > 1:
            *mods, last = vk_codes
            # Down de todos os modificadores
            for m in mods:
                self._send_key_down(m)
            # Pressiona 'last' conforme tempo ou n_times
            if secs is not None:
                self._press_and_wait(last, secs)
            else:
                self._press_n_times(last, n_times)
            # Up dos modificadores
            for m in mods:
                self._send_key_up(m)
        else:
            code = vk_codes[0]
            if secs is not None:
                self._press_and_wait(code, secs)
            else:
                self._press_n_times(code, n_times)

    def key_press(self,
                  key,
                  n_times: int = 1,
                  secs: float = None):
        """
        Simula pressionamento de tecla NA JANELA selecionada, mesmo em background.

        :param key: string ou int (ex: "A", "CTRL+A", 65).
        :param n_times: quantas vezes repetir (se secs for None).
        :param secs: se fornecido, mantém a tecla pressionada por secs segundos.
        """
        vk_codes = self._parse_key(key)
        self._press_key_sequence(vk_codes, n_times=n_times, secs=secs)

    def press_and_release(self,
                          key,
                          secs: float = None):
        """
        Atalho para key_press(key, secs=secs).
        """
        self.key_press(key, secs=secs)

    def write(self,
              text: str):
        """
        Escreve sequência de caracteres, enviando cada caractere para a janela.
        """
        for ch in text:
            self.key_press(ch)

    def _on_key_press_loop(self):
        """
        Laço interno para monitorar teclas. Chama callback se detecta alguma.
        """
        while self._key_press_callbacks is not None:
            keys, callback = self._key_press_callbacks
            for key in keys:
                if self.is_pressed(key):
                    try:
                        callback(key)
                    except Exception as e:
                        raise RuntimeError(f"Erro no callback de tecla '{key}': {e}")
            time.sleep(0.05)

    def register_keypress_callback(self,
                                   keys,
                                   callback):
        """
        Registra callback para quando uma das teclas for detectada fisicamente.
        'keys' pode ser string ou lista de strings.
        """
        if isinstance(keys, str):
            keys = [keys]
        for k in keys:
            self._parse_key(k)  # valida
        self._key_press_callbacks = (keys, callback)
        threading.Thread(target=self._on_key_press_loop, daemon=True).start()

    def clean_keypress_callbacks(self):
        """
        Cancela o monitoramento de teclas.
        """
        self._key_press_callbacks = None


class Mouse:
    _button_envent_map = {
        "move":        1,
        "left_down":   2,
        "left_up":     4,
        "right_down":  8,
        "right_up":    10,
        "left_click":  6,
        "right_click": 24
    }

    _mouse_messages_map = {
        "move":             0x0200,
        "left_down":        0x0201,
        "left_up":          0x0202,
        "WM_LBUTTONDBLCLK": 0x0203,
        "right_down":       0x0204,
        "right_up":         0x0205,
        "WM_RBUTTONDBLCLK": 0x0206,
        "WM_MBUTTONDOWN":   0x0207,
        "WM_MBUTTONUP":     0x0208,
        "WM_MBUTTONDBLCLK": 0x0209,
        "WM_MOUSEWHEEL":    0x020A,
        "WM_XBUTTONDOWN":   0x020B,
        "WM_XBUTTONUP":     0x020C,
        "WM_XBUTTONDBLCLK": 0x020D,
        "WM_MOUSEHWHEEL":   0x020E
    }

    def __init__(self,
                 hwnd=None,
                 is_async=True):
        self.send_event = PostMessage if is_async else SendMessage
        self.user32 = ctypes.windll.user32
        self._hwnd = hwnd

    @property
    def window_size(self):
        return self.user32.GetSystemMetrics(0), self.user32.GetSystemMetrics(1)

    @property
    def center_position(self):
        w, h = self.window_size
        return w // 2, h // 2

    @property
    def position(self):
        cursor = ctypes.wintypes.POINT()
        self.user32.GetCursorPos(ctypes.byref(cursor))
        return cursor.x, cursor.y

    @position.setter
    def position(self,
                 value: Tuple[int, int]):
        assert is_numeric_sequence(value) and len(value) == 2, f"Value {value} isn't valid"
        self.set_position(*value)

    def set_position(self,
                     x,
                     y):
        self.user32.SetCursorPos(x, y)

    def _click(self,
               button: str,
               position=None,
               n_clicks=1,
               interval=0.1):
        if button not in ("left", "right"):
            raise ValueError(f"button {button} isn't valid")

        if self._hwnd is None:
            if position is not None:
                self.set_position(position[0], position[1])
            else:
                position = self.position
            for _ in range(n_clicks):
                self.user32.mouse_event(self._button_envent_map[f"{button}_click"], position[0], position[1], 0, 0)
                time.sleep(interval)
        else:
            if position is None:
                position = self.position
            l_param = (position[1] << 16) | position[0]  # y << 16 | x
            if n_clicks < 1:
                raise ValueError("n_clicks must be at least 1")
            # envia evento de localização do mouse
            self.send_event(self._hwnd, self._mouse_messages_map["move"], 0, l_param)
            # envia evento de clique
            self.send_event(self._hwnd, self._mouse_messages_map[f"{button}_down"], 1, l_param)
            for _ in range(n_clicks - 1):
                time.sleep(interval)
                self.send_event(self._hwnd, self._mouse_messages_map[f"{button}_click"], 0, l_param)
            self.send_event(self._hwnd, self._mouse_messages_map[f"{button}_up"], 0, l_param)

    def click_left(self,
                   position: Tuple[int, int] = None,
                   n_clicks=1):
        self._click("left", position=position, n_clicks=n_clicks)

    def click_right(self,
                    position: Tuple[int, int] = None,
                    n_clicks=1):
        self._click("right", position=position, n_clicks=n_clicks)

    def drag_to(self,
                from_,
                to):

        if self._hwnd is not None:
            from_l_param = (from_[1] << 16) | from_[0]
            to_l_param = (to[1] << 16) | to[0]

            # Envia evento de localização do mouse
            self.send_event(self._hwnd, self._mouse_messages_map["move"], 0, from_l_param)
            # Envia eventos de clique e arrasto
            self.send_event(self._hwnd, self._mouse_messages_map["left_down"], 1, from_l_param)
            # Envia evento de movimento para a posição final
            self.send_event(self._hwnd, self._mouse_messages_map["move"], 0, to_l_param)
            self.send_event(self._hwnd, self._mouse_messages_map["left_up"], 0, to_l_param)
        else:
            self.set_position(from_[0], from_[1])
            self.user32.mouse_event(self._button_envent_map["left_down"], from_[0], from_[1], 0, 0)
            self.set_position(to[0], to[1])
            self.user32.mouse_event(self._button_envent_map["left_up"], to[0], to[1], 0, 0)

    def move_to_center(self):
        self.set_position(*self.center_position)


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
                 hwnd: wintypes.HWND):
        """
        Inicializa uma instância da classe Window.

        Args:
            hwnd (ctypes.wintypes.HWND): Handle da janela.
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
        length = GetWindowTextLength(self.hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(self.hwnd, buff, length + 1)
        return buff.value or "UNKNOW"

    @title.setter
    def title(self,
              value: str):
        """
        Define o título da janela.
        """
        SetWindowText(self.hwnd, value)

    @property
    def is_visible(self) -> bool:
        """
        Verifica se a janela está visível.
        """
        return bool(IsWindowVisible(self.hwnd))

    @property
    def pid(self) -> int:
        """
        Retorna o PID do processo que criou a janela.
        """
        pid = wintypes.DWORD()
        GetWindowThreadProcessId(self.hwnd, ctypes.byref(pid))
        return pid.value

    @staticmethod
    def _enum_windows_callback(hwnd,
                               lParam):
        try:
            if IsWindowVisible(hwnd):
                windows = ctypes.cast(lParam, ctypes.py_object).value
                windows.append(Window(hwnd))
        except:
            return False
        return True

    @staticmethod
    def get_all_windows():
        """
        Retorna uma lista de todas as janelas visíveis.
        """
        windows = []
        EnumWindows(EnumWindowsProc(Window._enum_windows_callback), ctypes.py_object(windows))
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
        return cls(GetForegroundWindow())

    @property
    def dimensions(self) -> tuple[int, int, int, int]:
        """
        Obtém as dimensões da janela (incluindo bordas e título).

        Returns:
            (left, top, right, bottom)
        """
        rect = wintypes.RECT()
        GetWindowRect(self.hwnd, ctypes.byref(rect))
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
        SetWindowPos(self.hwnd, 0, left, top, width, height, 0)

    @property
    def dimensions_window_content(self) -> tuple[int, int, int, int]:
        """
        Obtém as dimensões da área cliente (coords relativas: (0,0) → (width, height)).
        """
        client_rect = wintypes.RECT()
        GetClientRect(self.hwnd, ctypes.byref(client_rect))
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
        PostMessage(self.hwnd, 0x0111, command, 0)  # WM_COMMAND = 0x0111

    @property
    def state(self) -> str:
        """
        Retorna "Minimized", "Maximized" ou "Normal" conforme o estado da janela.
        """
        if IsIconic(self.hwnd):
            return "Minimized"
        elif IsZoomed(self.hwnd):
            return "Maximized"
        else:
            return "Normal"

    def capture_image_bmp(self,
                          filepath: str = None,
                          only_window_content: bool = True) -> bytes:
        """
        Captura a janela (ou apenas a área cliente) e retorna os bytes do BMP (header + pixels BGRA 32-bit).
        Mesmo que a janela não seja a atual, usa PrintWindow com PW_RENDERFULLCONTENT para forçar a renderização
        pelo DWM. Se estiver minimizada, restaura e mostra sem ativar antes da captura.

        Args:
            filepath: caminho para salvar o BMP (opcional).
            only_window_content: se True, captura só a área cliente; caso contrário, captura a janela inteira.

        Returns:
            bytes: conteúdo raw do BMP (header + pixels).
        """
        # 1) Obtém coords da janela inteira e da área cliente
        left, top, right, bottom = self.dimensions
        cl_left, cl_top, cl_right, cl_bottom = self.dimensions_window_content
        cl_width = cl_right - cl_left
        cl_height = cl_bottom - cl_top

        # Converte (0,0) do cliente para coords de tela
        pt = wintypes.POINT(cl_left, cl_top)
        ClientToScreen(self.hwnd, ctypes.byref(pt))
        client_origin_x = pt.x
        client_origin_y = pt.y

        # 2) Define origem e tamanho conforme only_window_content
        if only_window_content:
            origin_x = client_origin_x
            origin_y = client_origin_y
            width = cl_width
            height = cl_height
        else:
            origin_x = left
            origin_y = top
            width = right - left
            height = bottom - top

        if width <= 0 or height <= 0:
            raise RuntimeError(f"Dimensões inválidas: width={width}, height={height}")

        # 3) Se estiver minimizada, restaura sem ativar
        if IsIconic(self.hwnd):
            ShowWindow(self.hwnd, SW_RESTORE)
            time.sleep(0.05)  # aguarda redraw
            ShowWindow(self.hwnd, SW_SHOWNA)

        # 4) Tenta PrintWindow com PW_RENDERFULLCONTENT (não muda o foco)
        window_dc = GetWindowDC(self.hwnd) if not only_window_content else GetDC(self.hwnd)
        mem_dc = CreateCompatibleDC(window_dc)
        bmp_handle = CreateCompatibleBitmap(window_dc, width, height)
        SelectObject(mem_dc, bmp_handle)

        # Usa PW_RENDERFULLCONTENT para capturar mesmo que não esteja em foreground
        pw_result = PrintWindow(self.hwnd, mem_dc, 0x00000001 | PW_RENDERFULLCONTENT)
        if not pw_result:
            # Fallback: PrintWindow sem flags
            pw_result = PrintWindow(self.hwnd, mem_dc, 0)
        ReleaseDC(self.hwnd, window_dc)

        # 5) Extrai pixels do bitmap
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = width
        bmi.bmiHeader.biHeight = -height  # negativo = top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        buffer_size = abs(width * height * 4)
        bitmap_data = ctypes.create_string_buffer(buffer_size)
        scan = GetDIBits(mem_dc, bmp_handle, 0, height, bitmap_data, ctypes.byref(bmi), DIB_RGB_COLORS)

        # 6) Se GetDIBits falhar (scan == 0), retorna um BMP preto do tamanho correto
        if scan == 0:
            # Preenche buffer com zeros (preto)
            bitmap_data = ctypes.create_string_buffer(buffer_size)

        # 7) Se foi solicitado, salva em arquivo BMP
        if filepath:
            with open(filepath, "wb") as f:
                f.write(b"BM")
                size_file = 54 + buffer_size
                f.write(size_file.to_bytes(4, "little"))
                f.write((0).to_bytes(4, "little"))  # reservado
                f.write((54).to_bytes(4, "little"))  # offset do pixel data
                f.write(ctypes.string_at(
                        ctypes.byref(bmi.bmiHeader),
                        ctypes.sizeof(BITMAPINFOHEADER)
                ))
                f.write(bitmap_data.raw)

        # 8) Limpeza dos handles GDI usados
        DeleteObject(bmp_handle)
        DeleteDC(mem_dc)

        return bitmap_data.raw

    def capture_image_ppm(self,
                          ppm_path: Optional[str] = None,
                          only_window_content: bool = True) -> bytes:
        """
        Captura a janela (ou área cliente) e gera um arquivo PPM (P6) contendo apenas
        os canais RGB, sem usar dependências externas. Se ppm_path for fornecido,
        salva o PPM nesse caminho e retorna os bytes do PPM (cabeçalho + dados RGB).

        Args:
            ppm_path: caminho para salvar o arquivo .ppm (opcional). Se None, retorna apenas os bytes.
            only_window_content: se True, captura só a área cliente; caso contrário, captura a janela inteira.

        Returns:
            bytes: conteúdo raw do arquivo PPM (cabeçalho + pixels RGB).
        """
        # 1) Captura o BMP bruto (BGRA) em memória
        raw_bgra = self.capture_image_bmp(filepath=None, only_window_content=only_window_content)

        # 2) Determina largura e altura da região capturada
        if only_window_content:
            w, h = self.size_window_content
        else:
            w, h = self.size

        # 3) Monta o cabeçalho PPM (P6)
        header = f"P6\n{w} {h}\n255\n".encode("ascii")

        # 4) Converte cada pixel BGRA → RGB e acumula em bytearray
        rgb_data = bytearray()
        # O BMP retornado é top-down, cada linha tem w pixels, cada pixel 4 bytes (B, G, R, A)
        for y in range(h):
            row_start = y * w * 4
            for x in range(w):
                idx = row_start + x * 4
                b = raw_bgra[idx]
                g = raw_bgra[idx + 1]
                r = raw_bgra[idx + 2]
                # ignorar alpha (idx+3)
                rgb_data.extend((r, g, b))

        ppm_bytes = header + rgb_data

        # 5) Se foi fornecido caminho, salva o PPM em disco
        if ppm_path:
            try:
                with open(ppm_path, "wb") as f:
                    f.write(ppm_bytes)
            except Exception as e:
                raise RuntimeError(f"Não foi possível salvar PPM em '{ppm_path}': {e}")

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
        ShowWindow(self.hwnd, SW_HIDE)

    def show_normal(self):
        """Mostra a janela em estado normal."""
        ShowWindow(self.hwnd, 1)

    def show_minimized(self):
        """Minimiza a janela."""
        ShowWindow(self.hwnd, 2)

    def maximize(self):
        """Maximiza a janela."""
        ShowWindow(self.hwnd, 3)

    def show_no_activate(self):
        """Mostra a janela sem ativá-la."""
        ShowWindow(self.hwnd, SW_SHOWNA)

    def show(self):
        """Mostra/ativa a janela."""
        ShowWindow(self.hwnd, SW_SHOW)

    def minimize(self):
        """Minimiza a janela sem restaurar foco."""
        ShowWindow(self.hwnd, 6)

    def show_min_no_active(self):
        """Mostra a janela minimizada, sem ativar."""
        ShowWindow(self.hwnd, 7)

    def show_na(self):
        """Mostra a janela sem ativar."""
        ShowWindow(self.hwnd, 8)

    def restore(self):
        """Restaura a janela do estado minimizado ou maximizado."""
        ShowWindow(self.hwnd, SW_RESTORE)

    def show_default(self):
        """Define o estado de exibição com base em STARTUPINFO."""
        ShowWindow(self.hwnd, 10)

    def set_foreground(self):
        """Traz a janela ao primeiro plano."""
        SetForegroundWindow(self.hwnd)

    def bring_to_top(self):
        """Eleva a janela no Z-order sem ativá-la."""
        BringWindowToTop(self.hwnd)
