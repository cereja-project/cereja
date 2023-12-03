import ctypes.wintypes
import sys
import time
from ctypes import wintypes
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
    pass


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

    def __init__(self):
        self.user32 = ctypes.windll.user32
        self._stop_listen = True

    @property
    def key_map(self):
        return self.__KEY_NAME_TO_CODE

    def _parse_key(self, v):
        try:
            if not isinstance(v, (str, int)):
                raise ValueError
            if isinstance(v, str):
                v = string_to_literal(v)
                if isinstance(v, str):
                    v = self.__KEY_NAME_TO_CODE[v]
        except (ValueError, Exception):
            raise ValueError(f"Value {v} in't valid to keyboard.")
        return v

    def _is_pressed(self, key_code):
        return self.user32.GetAsyncKeyState(key_code) & 0x8000 != 0

    def is_pressed(self, key):
        """
        Checks if a specific key is currently pressed.
        :param key: Key code to check.
        :return: True if the key is pressed, False otherwise.
        """
        return self._is_pressed(self._parse_key(key))

    def _key_press(self, key_code):
        self.user32.keybd_event(key_code, 0, 0, 0)

    def key_press(self, key):
        """
        Simulates a key press.
        :param key: Key code of the key to press.
        """
        self._key_press(self._parse_key(key))

    def _key_release(self, key_code):
        """
        Simulates a key release.
        :param key_code: Key code of the key to release.
        """
        if self._is_pressed(key_code):
            self.user32.keybd_event(key_code, 0, 2, 0)

    def key_release(self, key):
        """
        Simulates a key release.
        :param key_code: Key code of the key to release.
        """
        self._key_release(self._parse_key(key))

    def press_and_release(self, key, secs=None):
        key = self._parse_key(key)
        secs = secs or 0.0
        self._key_press(key)
        time.sleep(secs)
        self._key_release(key)

    def write(self, text, interval=0.1):
        for char in text:
            self.press_and_release(char, secs=interval)


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

    def __init__(self):
        self.user32 = ctypes.windll.user32

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
        if position is not None:
            self.set_position(position[0], position[1])
        else:
            position = self.position
        for _ in range(n_clicks):
            self.user32.mouse_event(self._button_envent_map[f"{button}_click"], position[0], position[1], 0, 0)
            time.sleep(interval)

    def click_left(self, position: Tuple[int, int] = None, n_clicks=1):
        self._click("left", position=position, n_clicks=n_clicks)

    def click_right(self, position: Tuple[int, int] = None, n_clicks=1):
        self._click("right", position=position, n_clicks=n_clicks)

    def drag_to(self, from_, to):
        self.set_position(from_[0], from_[1])
        self.user32.mouse_event(self._button_envent_map["left_down"], from_[0], from_[1], 0, 0)
        self.set_position(to[0], to[1])
        self.user32.mouse_event(self._button_envent_map["left_up"], to[0], to[1], 0, 0)

    def move_to_center(self):
        self.set_position(*self.center_position)


# Definições para a API do Windows
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
PostMessage = user32.PostMessageW
IsIconic = user32.IsIconic
IsZoomed = user32.IsZoomed
GetWindowDC = user32.GetWindowDC
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

    def __repr__(self):
        return f"{self.__class__.__name__}<{self.title}>"

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
        if IsWindowVisible(hwnd):
            windows = ctypes.cast(lParam, ctypes.py_object).value
            windows.append(Window(hwnd))
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
        # Obtenha o DC da janela e crie um DC compatível
        window_dc = GetWindowDC(self.hwnd)
        mem_dc = CreateCompatibleDC(window_dc)

        # Obtenha as dimensões
        left, top, right, bottom = self.dimensions
        if only_window_content:
            width, height = self.size_window_content
        else:
            width = right - left
            height = bottom - top

        # Crie um bitmap compatível e selecione-o no DC compatível
        screenshot = CreateCompatibleBitmap(window_dc, width, height)
        SelectObject(mem_dc, screenshot)

        # Copie o conteúdo da janela
        PrintWindow(self.hwnd, mem_dc, int(only_window_content))

        # Cria uma imagem em memória a partir do bitmap capturado
        bitmap_info = BITMAPINFO()
        bitmap_info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bitmap_info.bmiHeader.biWidth = width
        bitmap_info.bmiHeader.biHeight = -height  # Negativo indica origem no topo esquerdo
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap_info.bmiHeader.biCompression = BI_RGB

        bitmap_data = ctypes.create_string_buffer(width * height * 4)
        BitBlt(mem_dc, 0, 0, width, height, window_dc, left, top, SRCCOPY)
        GetDIBits(mem_dc, screenshot, 0, height, bitmap_data, ctypes.byref(bitmap_info), 0)  # DIB_RGB_COLORS
        if filepath:
            # Escrevendo os dados em um arquivo BMP
            with open(filepath, 'wb') as bmp_file:
                # Cabeçalho do arquivo
                bmp_file.write(b'BM')
                size = 54 + len(bitmap_data.raw)  # 54 bytes para o cabeçalho BMP
                bmp_file.write(ctypes.c_uint32(size).value.to_bytes(4, byteorder='little'))
                bmp_file.write(b'\x00\x00')  # Reservado
                bmp_file.write(b'\x00\x00')  # Reservado
                bmp_file.write((54).to_bytes(4, byteorder='little'))  # Offset para início dos dados da imagem

                # Cabeçalho da imagem
                bmp_file.write(bitmap_info.bmiHeader)

                # Dados da imagem
                bmp_file.write(bitmap_data.raw)
        raw = bitmap_data.raw
        # Limpeza
        DeleteObject(screenshot)
        DeleteDC(mem_dc)
        ReleaseDC(self.hwnd, window_dc)
        DeleteObject(bitmap_data)

        return raw

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
