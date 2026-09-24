"""Window-directed keyboard input and physical key-state polling."""

import random
import threading
import time

from ...utils import invert_dict
from .api import get_api
from .common import Time

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101


class Keyboard:
    """
    Simula e detecta pressionamentos de teclas EM UMA JANELA ESPECÍFICA, mesmo se não estiver em primeiro plano.

    Ao instanciar, passe o handle (HWND) da janela alvo:
        kb = Keyboard(hwnd=meu_hwnd)

    Todos os métodos de key_press enviarão WM_KEYDOWN/WM_KEYUP diretamente para self._hwnd,
    construindo lParam com código de varredura apropriado para que a aplicação receba a mensagem
    como se fosse teclado real, mesmo que esteja em segundo plano.
    """

    __KEY_NAME_TO_CODE = {
        'BACKSPACE': 8, 'TAB': 9, 'CLEAR': 12, 'ENTER': 13, 'SHIFT': 16, 'CTRL': 17,
        'ALT': 18, 'PAUSE': 19, 'CAPS_LOCK': 20, 'ESC': 27, 'SPACEBAR': 32,
        'PAGE_UP': 33, 'PAGE_DOWN': 34, 'END': 35, 'HOME': 36, 'LEFT_ARROW': 37,
        'UP_ARROW': 38, 'RIGHT_ARROW': 39, 'DOWN_ARROW': 40, 'INSERT': 45,
        'DELETE': 46, '0': 48, '1': 49, '2': 50, '3': 51, '4': 52, '5': 53,
        '6': 54, '7': 55, '8': 56, '9': 57,
        'A': 65, 'B': 66, 'C': 67, 'D': 68, 'E': 69, 'F': 70, 'G': 71, 'H': 72,
        'I': 73, 'J': 74, 'K': 75, 'L': 76, 'M': 77, 'N': 78, 'O': 79, 'P': 80,
        'Q': 81, 'R': 82, 'S': 83, 'T': 84, 'U': 85, 'V': 86, 'W': 87, 'X': 88,
        'Y': 89, 'Z': 90,
        'F1': 112, 'F2': 113, 'F3': 114, 'F4': 115, 'F5': 116, 'F6': 117,
        'F7': 118, 'F8': 119, 'F9': 120, 'F10': 121, 'F11': 122, 'F12': 123,
        '+': 187, ',': 188, '-': 189, '.': 190, '/': 191, '`': 192, ';': 186,
        '[': 219, '\\': 220, ']': 221, "'": 222
    }
    __KEY_CODE_TO_NAME = invert_dict(__KEY_NAME_TO_CODE)
    __KEY_MAP_READY = False
    __KEY_MAP_LOCK = threading.Lock()

    @classmethod
    def _ensure_key_map(cls):
        """Resolve the active Windows keyboard layout only when needed."""
        if cls.__KEY_MAP_READY:
            return
        with cls.__KEY_MAP_LOCK:
            if not cls.__KEY_MAP_READY:
                mapping = cls.__KEY_NAME_TO_CODE.copy()
                api = get_api()
                for value in range(32, 128):
                    character = chr(value)
                    mapping[character] = api.VkKeyScanW(character) & 0xFF
                cls.__KEY_NAME_TO_CODE = mapping
                cls.__KEY_CODE_TO_NAME = invert_dict(mapping)
                cls.__KEY_MAP_READY = True

    MAX_TIME_SIMULATE_KEY_PRESS = 0.1

    def __init__(self,
                 hwnd: int = None,
                 is_async: bool = True):
        """
        Args:
            hwnd: handle da janela alvo. Se None, métodos apenas detectam estado de teclas, sem enviar.
            is_async: se True, usa PostMessage; se False, usa SendMessage.
        """
        self._ensure_key_map()
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
        self._ensure_key_map()
        return self.__KEY_NAME_TO_CODE.copy()

    @classmethod
    def _parse_key(cls,
                   v) -> list[int]:
        """
        Recebe nome de tecla (ex: "A", "CTRL+A") ou código int.
        Retorna lista de códigos virtuais.
        """
        cls._ensure_key_map()
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
        return bool(get_api().GetAsyncKeyState(key_code) & 0x8000)

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
        scan_code = get_api().MapVirtualKeyW(vk_code, 0) & 0xFF
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
            get_api().PostMessageW(self._hwnd, WM_KEYDOWN, vk_code, lparam)
        else:
            get_api().SendMessageW(self._hwnd, WM_KEYDOWN, vk_code, lparam)

    def _send_key_up(self,
                     vk_code: int):
        """
        Envia WM_KEYUP para a janela selecionada (self._hwnd).
        """
        if not self._hwnd:
            return
        lparam = self._make_lparam(vk_code, is_keyup=True)
        if self._is_async:
            get_api().PostMessageW(self._hwnd, WM_KEYUP, vk_code, lparam)
        else:
            get_api().SendMessageW(self._hwnd, WM_KEYUP, vk_code, lparam)

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
