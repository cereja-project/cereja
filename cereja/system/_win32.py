import ctypes.wintypes
import sys
import threading
import time
from ctypes import wintypes
import random
from typing import Tuple

from ..utils import invert_dict, is_numeric_sequence, string_to_literal

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

BI_RGB = 0
DIB_RGB_COLORS = 0
SRCCOPY = 0xCC0020
GetDIBits = ctypes.windll.gdi32.GetDIBits


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ("bmiHeader", BITMAPINFOHEADER),
        ("bmiColors", wintypes.DWORD * 3)
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
    # Map of key names to virtual-key codes
    __KEY_NAME_TO_CODE = {'BACKSPACE':              8, 'TAB': 9, 'CLEAR': 12, 'ENTER': 13, 'SHIFT': 16, 'CTRL': 17,
                          'ALT':                    18, 'PAUSE': 19, 'CAPS_LOCK': 20, 'ESC': 27, 'SPACEBAR': 32,
                          'PAGE_UP':                33, 'PAGE_DOWN': 34, 'END': 35, 'HOME': 36, 'LEFT_ARROW': 37,
                          'UP_ARROW':               38, 'RIGHT_ARROW': 39, 'DOWN_ARROW': 40, 'SELECT': 41, 'PRINT': 42,
                          'EXECUTE':                43, 'PRINT_SCREEN': 44, 'INSERT': 45, 'DELETE': 46, 'HELP': 47,
                          '0':                      48, '1': 49, '2': 50, '3': 51, '4': 52, '5': 53, '6': 54, '7': 55,
                          '8':                      56, '9': 57, 'A': 65, 'B': 66, 'C': 67, 'D': 68, 'E': 69, 'F': 70,
                          'G':                      71, 'H': 72, 'I': 73, 'J': 74, 'K': 75, 'L': 76, 'M': 77, 'N': 78,
                          'O':                      79, 'P': 80, 'Q': 81, 'R': 82, 'S': 83, 'T': 84, 'U': 85, 'V': 86,
                          'W':                      87, 'X': 88, 'Y': 89, 'Z': 90, 'LEFT_WINDOWS': 91,
                          'RIGHT_WINDOWS':          92, 'APPLICATIONS': 93, 'SLEEP': 95, 'NUMPAD_0': 96, 'NUMPAD_1': 97,
                          'NUMPAD_2':               98, 'NUMPAD_3': 99, 'NUMPAD_4': 100, 'NUMPAD_5': 101,
                          'NUMPAD_6':               102,
                          'NUMPAD_7':               103, 'NUMPAD_8': 104, 'NUMPAD_9': 105, 'MULTIPLY_KEY': 106,
                          'ADD_KEY':                107, 'SEPARATOR_KEY': 108, 'SUBTRACT_KEY': 109, 'DECIMAL_KEY': 110,
                          'DIVIDE_KEY':             111, 'F1': 112, 'F2': 113, 'F3': 114, 'F4': 115, 'F5': 116,
                          'F6':                     117,
                          'F7':                     118, 'F8': 119, 'F9': 120, 'F10': 121, 'F11': 122, 'F12': 123,
                          'F13':                    124, 'F14': 125, 'F15': 126, 'F16': 127, 'F17': 128, 'F18': 129,
                          'F19':                    130, 'F20': 131, 'F21': 132, 'F22': 133, 'F23': 134, 'F24': 135,
                          'NUM_LOCK':               144, 'SCROLL_LOCK': 145, 'LEFT_SHIFT': 160, 'RIGHT_SHIFT': 161,
                          'LEFT_CONTROL':           162, 'RIGHT_CONTROL': 163, 'LEFT_MENU': 164, 'RIGHT_MENU': 165,
                          'BROWSER_BACK':           166, 'BROWSER_FORWARD': 167, 'BROWSER_REFRESH': 168,
                          'BROWSER_STOP':           169, 'BROWSER_SEARCH': 170, 'BROWSER_FAVORITES': 171,
                          'BROWSER_START_AND_HOME': 172, 'VOLUME_MUTE': 173, 'VOLUME_DOWN': 174, 'VOLUME_UP': 175,
                          'NEXT_TRACK':             176, 'PREVIOUS_TRACK': 177, 'STOP_MEDIA': 178,
                          'PLAY/PAUSE_MEDIA':       179, 'START_MAIL': 180, 'SELECT_MEDIA': 181,
                          'START_APPLICATION_1':    182, 'START_APPLICATION_2': 183, 'ATTN_KEY': 246, 'CRSEL_KEY': 247,
                          'EXSEL_KEY':              248, 'PLAY_KEY': 250, 'ZOOM_KEY': 251, 'CLEAR_KEY': 254, '+': 187,
                          ',':                      188, '-': 189, '.': 190, '/': 191, '`': 192, ';': 186, '[': 219,
                          '\\':                     220, ']': 221, "'": 222}
    for c in range(32, 128):
        __KEY_NAME_TO_CODE[chr(c)] = ctypes.windll.user32.VkKeyScanA(ctypes.wintypes.WCHAR(chr(c)))
    __KEY_CODE_TO_NAME = invert_dict(__KEY_NAME_TO_CODE)

    __WM_KEYDOWN = 0x0100
    __WM_KEYUP = 0x0101
    MAX_TIME_SIMULE_KEY_PRESS = 0.1

    def __init__(self, hwnd=None, is_async=False):
        self._is_async = is_async
        self.user32 = ctypes.windll.user32
        self._stop_listen = True
        self._hwnd = hwnd
        self._max_time_simule_key_press = self.MAX_TIME_SIMULE_KEY_PRESS
        self._key_press_callbacks = None

    @property
    def is_async(self):
        return self._is_async

    @is_async.setter
    def is_async(self, v):
        self._is_async = bool(v)

    def send_event(self, *args, **kwargs):
        (PostMessage if self._is_async else SendMessage)(*args, **kwargs)

    @property
    def max_time_key_press(self):
        return self._max_time_simule_key_press

    @max_time_key_press.setter
    def max_time_key_press(self, v):
        self._max_time_simule_key_press = v

    @property
    def key_map(self):
        return self.__KEY_NAME_TO_CODE

    @classmethod
    def _parse_key(cls, v):
        try:
            if not isinstance(v, (str, int)):
                raise ValueError
            if isinstance(v, str):
                if isinstance(v, str):
                    return [cls.__KEY_NAME_TO_CODE[i] for i in v.split("+")]
        except (ValueError, Exception):
            raise ValueError(f"Value {v} in't valid to keyboard.")
        return [v]

    def _is_pressed(self, key_code):
        if user32.GetAsyncKeyState(key_code) & 0x8000 != 0:
            return self._hwnd is None or self._hwnd == Window.get_foreground_window().hwnd

    def is_pressed(self, key):
        """
        Checks if a specific key is currently pressed.
        :param key: Key code to check.
        :return: True if the key is pressed, False otherwise.
        """
        return all(map(self._is_pressed, self._parse_key(key)))

    def _key_down(self, key_code):
        if self._hwnd is None:
            # Simule
            self.user32.keybd_event(key_code, 0, 0, 0)
        else:
            self.send_event(self._hwnd, self.__WM_KEYDOWN, key_code, 0)

    def _key_up(self, key_code):
        if self._hwnd is None:
            # Simule
            self.user32.keybd_event(key_code, 0, 2, 0)
        else:
            self.send_event(self._hwnd, self.__WM_KEYUP, key_code, 0)

    def _press_and_wait(self, key, secs):
        timer = Time()
        while timer.time < secs:
            self._key_down(key)
            time.sleep(0.1)
        self._key_up(key)

    def _press_n_times(self, key, n_times=1):
        for _ in range(n_times):
            self._key_down(key)
            time.sleep((random.random() * self._max_time_simule_key_press) + 0.01)
            self._key_up(key)

    def _key_press(self, key_code, n_times=1, secs=None):
        key_code = self._parse_key(key_code)
        if len(key_code) > 1:
            key = key_code.pop(-1)
            for key_comb in key_code:
                self.user32.keybd_event(key_comb, 0, 0, 0)
            if secs is not None:
                self._press_and_wait(key, secs)
            else:
                self._press_n_times(key, n_times=n_times)
            for key_comb in key_code:
                self.user32.keybd_event(key_comb, 0, 2, 0)
        else:
            if secs is not None:
                self._press_and_wait(key_code[0], secs)
            else:
                self._press_n_times(key_code[0], n_times=n_times)

    def wait_key(self, key, delay=1):
        start_time = time.time()
        while True:
            if time.time() - start_time > delay / 1000.0:
                return False
            if self.is_pressed(key):
                return True
            time.sleep(0.01)

    def key_press(self, key, n_times=1, secs=None):
        """
        Simulates a key press.
        :param key: Key code of the key to press.
        :param secs: time in seconds that the key will be pressed
        :param n_times: number of repeat key press event
        """
        self._key_press(key, n_times=n_times, secs=secs)

    def press_and_release(self, key, secs=None):
        self.key_press(key, secs=secs)

    def write(self, text):
        for char in text:
            self.key_press(char)

    def _on_key_press(self):
        while self._key_press_callbacks is not None:
            keys, callback = self._key_press_callbacks
            for key in keys:
                if self.is_pressed(key):
                    try:
                        callback(key)
                    except Exception as err:
                        raise ValueError(f"{err}. Error when calling callback for key event: {key}")
            time.sleep(0.1)

    def register_keypress_callback(self, keys, callback):
        if isinstance(keys, str):
            keys = [keys]
        assert isinstance(keys, (list, tuple)) or len(keys), "Send list or str for keys."
        try:
            for key in keys:
                self._parse_key(key)
        except Exception as err:
            raise ValueError(f"Error on keypress callback register, key value isn't valid. {err}")
        self._key_press_callbacks = (keys, callback)
        threading.Thread(target=self._on_key_press, daemon=True).start()

    def clean_keypress_callbacks(self):
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

    def __init__(self, hwnd=None, is_async=False):
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
    def position(self, value: Tuple[int, int]):
        assert is_numeric_sequence(value) and len(value) == 2, f"Value {value} isn't valid"
        self.set_position(*value)

    def set_position(self, x, y):
        self.user32.SetCursorPos(x, y)

    def _click(self, button: str, position=None, n_clicks=1, interval=0.0):
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
            l_param = (position[1] << 16) | position[0]

            self.send_event(self._hwnd, self._mouse_messages_map[f"{button}_down"], 1, l_param)
            self.send_event(self._hwnd, self._mouse_messages_map[f"{button}_up"], 0, l_param)

    def click_left(self, position: Tuple[int, int] = None, n_clicks=1):
        self._click("left", position=position, n_clicks=n_clicks)

    def click_right(self, position: Tuple[int, int] = None, n_clicks=1):
        self._click("right", position=position, n_clicks=n_clicks)

    def drag_to(self, from_, to):

        if self._hwnd is not None:
            from_l_param = (from_[1] << 16) | from_[0]
            to_l_param = (to[1] << 16) | to[0]

            self.send_event(self._hwnd, self._mouse_messages_map["left_down"], 1, from_l_param)
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
        capture_image: Captura a imagem da janela.

    Propriedades:
        hwnd: Handle da janela.
    """

    def __init__(self, hwnd: ctypes.wintypes.HWND):
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
    def keyboard(self) -> Keyboard:
        if self._keyboard is None:
            self._keyboard = Keyboard(self.hwnd)
        return self._keyboard

    @property
    def mouse(self) -> Mouse:
        if self._mouse is None:
            self._mouse = Mouse(self.hwnd)
        return self._mouse

    @property
    def title(self) -> str:
        """
        Retorna o título da janela.

        Returns:
            str: Título da janela.
        """
        length = GetWindowTextLength(self.hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(self.hwnd, buff, length + 1)
        return buff.value or "UNKNOW"

    @title.setter
    def title(self, value: str):
        """
        Define o título da janela.

        Args:
            value (str): Novo título da janela.
        """
        SetWindowText(self.hwnd, value)

    @property
    def is_visible(self) -> bool:
        """
        Verifica se a janela está visível.

        Returns:
            bool: True se a janela estiver visível, False caso contrário.
        """
        return bool(IsWindowVisible(self.hwnd))

    @property
    def pid(self):
        """
        Retorna o PID (Process Identifier) do processo que criou a janela.

        Returns:
            int: PID do processo.
        """
        pid = wintypes.DWORD()
        GetWindowThreadProcessId(self.hwnd, ctypes.byref(pid))
        return pid.value

    @staticmethod
    def _enum_windows_callback(hwnd, lParam):
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

        Returns:
            list[Window]: Lista de instâncias da classe Window representando janelas visíveis.
        """
        windows = []
        EnumWindows(EnumWindowsProc(Window._enum_windows_callback), ctypes.py_object(windows))
        return windows

    @classmethod
    def find_windows(cls, text):
        """
        Encontra janelas com o nome
        """
        return list(filter(lambda window: text.lower().strip() in window.title.lower(), cls.get_all_windows()))

    @classmethod
    def get_foreground_window(cls):
        return cls(GetForegroundWindow())

    @property
    def dimensions(self):
        """
        Obtém as dimensões da janela.

        Returns:
            tuple: Um tuple contendo as coordenadas da janela (esquerda, topo, direita, inferior).
        """
        rect = wintypes.RECT()
        GetWindowRect(self.hwnd, ctypes.byref(rect))
        return rect.left, rect.top, rect.right, rect.bottom

    @dimensions.setter
    def dimensions(self, dimensions):
        """
        Define as dimensões da janela.

        Args:
            dimensions (tuple): Um tuple contendo as novas coordenadas da janela (esquerda, topo, direita, inferior).
        """
        left, top, right, bottom = dimensions
        width = right - left
        height = bottom - top
        SetWindowPos(self.hwnd, 0, left, top, width, height, 0)

    @property
    def dimensions_window_content(self):
        client_rect = wintypes.RECT()
        ctypes.windll.user32.GetClientRect(self.hwnd, ctypes.byref(client_rect))
        return client_rect.left, client_rect.top, client_rect.right, client_rect.bottom

    @property
    def size_window_content(self):
        left, top, right, bottom = self.dimensions_window_content
        width = right - left
        height = bottom - top
        return width, height

    @property
    def size(self):
        left, top, right, bottom = self.dimensions
        width = right - left
        height = bottom - top
        return width, height

    def send_command(self, command):
        """
        Envia um comando específico para a janela. Esta funcionalidade requer conhecimento específico dos códigos de mensagem da API do Windows.

        Args:
            command: O comando a ser enviado.
        """
        # Exemplo: PostMessage(self.hwnd, WM_COMMAND, command, 0)
        pass

    @property
    def state(self):
        """
        Obtém o estado atual da janela.

        Returns:
            str: Retorna "Minimized", "Maximized" ou "Normal" com base no estado da janela.
        """
        if IsIconic(self.hwnd):
            return "Minimized"
        elif IsZoomed(self.hwnd):
            return "Maximized"
        else:
            return "Normal"

    def capture_image_bmp(self, filepath=None, only_window_content=True):
        if not user32.IsZoomed(self.hwnd):
            ctypes.windll.user32.ShowWindow(self.hwnd, 4)
        # Obtenha o DC da janela e crie um DC compatível
        window_dc = GetWindowDC(self.hwnd) if only_window_content else GetDC(self.hwnd)
        mem_dc = CreateCompatibleDC(window_dc)

        if only_window_content:
            width, height = self.size_window_content
        else:
            # Obtenha as dimensões
            left, top, right, bottom = self.dimensions
            width = right - left
            height = bottom - top

        # Crie um bitmap compatível e selecione-o no DC compatível
        screenshot = CreateCompatibleBitmap(window_dc, width, height)
        SelectObject(mem_dc, screenshot)

        # Copie o conteúdo da janela
        PrintWindow(self.hwnd, mem_dc, int(only_window_content))

        # Prepara a estrutura BITMAPINFO com os dados da imagem
        bitmap_info = BITMAPINFO()
        bitmap_info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bitmap_info.bmiHeader.biWidth = width
        bitmap_info.bmiHeader.biHeight = -height  # Negativo para origem no topo
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap_info.bmiHeader.biCompression = BI_RGB

        # Cria buffer para os dados da imagem
        bitmap_data = ctypes.create_string_buffer(
                abs(bitmap_info.bmiHeader.biWidth * bitmap_info.bmiHeader.biHeight * 4))
        # Obtém os dados da imagem
        GetDIBits(mem_dc, screenshot, 0, height, bitmap_data, ctypes.byref(bitmap_info), DIB_RGB_COLORS)

        # Se um filepath foi fornecido, salva a imagem como um arquivo BMP
        if filepath:
            with open(filepath, 'wb') as bmp_file:
                # Escreve o cabeçalho do arquivo BMP
                bmp_file.write(b'BM')
                size = 54 + len(bitmap_data.raw)  # 54 bytes para o cabeçalho BMP
                bmp_file.write(size.to_bytes(4, 'little'))
                bmp_file.write((0).to_bytes(4, 'little'))  # Reservado
                bmp_file.write((54).to_bytes(4, 'little'))  # Offset dos dados da imagem
                # Escreve o cabeçalho da imagem
                bmp_file.write(ctypes.string_at(ctypes.byref(bitmap_info.bmiHeader), ctypes.sizeof(BITMAPINFOHEADER)))
                # Escreve os dados da imagem
                bmp_file.write(bitmap_data.raw)

        # Limpeza
        DeleteObject(screenshot)
        DeleteDC(mem_dc)
        ReleaseDC(self.hwnd, window_dc)

        return bitmap_data.raw

    # SHOW implements
    def hide(self):
        """
        Oculta a janela e ativa outra janela.

        Este comando remove completamente a janela da área de trabalho e da barra de tarefas, tornando-a inacessível
        até que seja programaticamente reexibida.
        """
        ShowWindow(self.hwnd, 0)

    def show_normal(self):
        """Mostra a janela em seu estado normal."""
        ShowWindow(self.hwnd, 1)

    def show_minimized(self):
        """Mostra a janela minimizada."""
        ShowWindow(self.hwnd, 2)

    def maximize(self):
        """Maximiza a janela."""
        ShowWindow(self.hwnd, 3)

    def show_no_activate(self):
        """Mostra a janela em seu tamanho e posição atuais, sem ativá-la."""
        ShowWindow(self.hwnd, 4)

    def show(self):
        """Mostra a janela em seu estado atual."""
        ShowWindow(self.hwnd, 5)

    def minimize(self):
        """Minimiza a janela."""
        ShowWindow(self.hwnd, 6)

    def show_min_no_active(self):
        """Mostra a janela como minimizada, mas não a ativa."""
        ShowWindow(self.hwnd, 7)

    def show_na(self):
        """Mostra a janela em seu estado atual, sem ativá-la."""
        ShowWindow(self.hwnd, 8)

    def restore(self):
        """Restaura a janela para seu tamanho e posição originais."""
        ShowWindow(self.hwnd, 9)

    def show_default(self):
        """Define o estado de exibição com base no valor SW_ especificado no STARTUPINFO."""
        ShowWindow(self.hwnd, 10)

    def set_foreground(self):
        """Tenta trazer a janela para o primeiro plano."""
        ctypes.windll.user32.SetForegroundWindow(self.hwnd)

    def bring_to_top(self):
        """Move a janela para o topo do Z-Order sem necessariamente ativá-la."""
        ctypes.windll.user32.BringWindowToTop(self.hwnd)
