"""Window-directed keyboard input and physical key-state polling."""

import random
import threading
import time

from ...utils import invert_dict
from ...utils.time import Timer
from .api import get_api
from .constants import (
    KeyboardMask, KeyMessageFlag, MapVirtualKeyType, VirtualKey, WindowMessage,
)


class Keyboard:
    """Send keyboard messages to a target window and inspect physical keys.

    Messages are addressed directly to the selected HWND, including when
    it is in the background. Applications may ignore synthetic messages.
    This class does not inject system-wide keyboard events."""

    __KEY_NAME_TO_CODE = {
        key.name: key for key in VirtualKey
        if not key.name.startswith(("DIGIT_", "OEM_"))
    }
    __KEY_NAME_TO_CODE.update({str(digit): VirtualKey[f"DIGIT_{digit}"] for digit in range(10)})
    __KEY_NAME_TO_CODE.update({
        '+': VirtualKey.OEM_PLUS, ',': VirtualKey.OEM_COMMA, '-': VirtualKey.OEM_MINUS,
        '.': VirtualKey.OEM_PERIOD, '/': VirtualKey.OEM_SLASH, '`': VirtualKey.OEM_BACKTICK,
        ';': VirtualKey.OEM_SEMICOLON, '[': VirtualKey.OEM_LBRACKET, '\\': VirtualKey.OEM_BACKSLASH,
        ']': VirtualKey.OEM_RBRACKET, "'": VirtualKey.OEM_QUOTE,
    })
    # Keep the public key_map values as plain integers.
    __KEY_NAME_TO_CODE = {name: int(code) for name, code in __KEY_NAME_TO_CODE.items()}
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
                    mapping[character] = api.VkKeyScanW(character) & KeyboardMask.VIRTUAL_KEY
                cls.__KEY_NAME_TO_CODE = mapping
                cls.__KEY_CODE_TO_NAME = invert_dict(mapping)
                cls.__KEY_MAP_READY = True

    MAX_TIME_SIMULATE_KEY_PRESS = 0.1

    def __init__(self,
                 hwnd: int = None,
                 is_async: bool = True):
        """Select an optional HWND and asynchronous or synchronous message delivery.

        With hwnd=None, physical key polling remains available and sending
        messages is a no-op. is_async selects PostMessageW instead of SendMessageW."""
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
        """Parse a virtual-key integer or names such as "A" and "CTRL+A"."""
        cls._ensure_key_map()
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            parts = v.split("+")
            codes = []
            for p in parts:
                p = p.strip().upper()
                if p not in cls.__KEY_NAME_TO_CODE:
                    raise ValueError(f"Invalid key: {p}")
                codes.append(cls.__KEY_NAME_TO_CODE[p])
            return codes
        raise ValueError(f"Unsupported key value: {v}")

    def _is_pressed(self,
                    key_code: int) -> bool:
        """Read whether a virtual key is physically pressed."""
        return bool(get_api().GetAsyncKeyState(key_code) & KeyboardMask.PRESSED)

    def is_pressed(self,
                   key) -> bool:
        """Return whether every key in a combination is physically pressed."""
        codes = self._parse_key(key)
        return all(self._is_pressed(code) for code in codes)

    def _make_lparam(self,
                     vk_code: int,
                     is_keyup: bool = False) -> int:
        """Build the legacy key-message payload with a scan code and repeat count.

        Key release sets the transition flag. Extended-key, context and
        previous-key-state flags retain their legacy zero values."""
        scan_code = get_api().MapVirtualKeyW(vk_code, MapVirtualKeyType.VK_TO_VSC) & KeyboardMask.VIRTUAL_KEY
        repeat_count = 1
        transition = KeyMessageFlag.KEY_UP if is_keyup else 0
        lparam = repeat_count | (scan_code << 16) | transition
        return lparam

    def _send_key_down(self,
                       vk_code: int):
        """Send WM_KEYDOWN to the selected HWND without changing foreground."""
        if not self._hwnd:
            return
        lparam = self._make_lparam(vk_code, is_keyup=False)
        if self._is_async:
            get_api().PostMessageW(self._hwnd, WindowMessage.KEYDOWN, vk_code, lparam)
        else:
            get_api().SendMessageW(self._hwnd, WindowMessage.KEYDOWN, vk_code, lparam)

    def _send_key_up(self,
                     vk_code: int):
        """Send WM_KEYUP to the selected HWND without changing foreground."""
        if not self._hwnd:
            return
        lparam = self._make_lparam(vk_code, is_keyup=True)
        if self._is_async:
            get_api().PostMessageW(self._hwnd, WindowMessage.KEYUP, vk_code, lparam)
        else:
            get_api().SendMessageW(self._hwnd, WindowMessage.KEYUP, vk_code, lparam)

    def _press_and_wait(self,
                        vk_code: int,
                        duration: float):
        """Repeat key-down messages for the duration, then send key-up."""
        timer = Timer()
        while timer.elapsed < duration:
            self._send_key_down(vk_code)
            time.sleep(0.01)
        self._send_key_up(vk_code)

    def _press_n_times(self,
                       vk_code: int,
                       n_times: int = 1):
        """Send n key-down/key-up pairs with a short randomized hold time."""
        for _ in range(n_times):
            self._send_key_down(vk_code)
            time.sleep((random.random() * self._max_time_simulate) + 0.01)
            self._send_key_up(vk_code)

    def _press_key_sequence(self,
                            vk_codes: list[int],
                            n_times: int = 1,
                            secs: float = None):
        """Hold modifiers while sending the final key, then release them."""
        if len(vk_codes) > 1:
            *mods, last = vk_codes
            # Press all modifiers.
            for m in mods:
                self._send_key_down(m)
            # Send the final key for the requested duration or repetition count.
            if secs is not None:
                self._press_and_wait(last, secs)
            else:
                self._press_n_times(last, n_times)
            # Release the modifiers.
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
        """Send a key or combination to the selected window.

        key accepts a name, combination or virtual-key integer. n_times
        controls repetitions unless secs specifies a hold duration."""
        vk_codes = self._parse_key(key)
        self._press_key_sequence(vk_codes, n_times=n_times, secs=secs)

    def press_and_release(self,
                          key,
                          secs: float = None):
        """Call key_press with an optional hold duration."""
        self.key_press(key, secs=secs)

    def write(self,
              text: str):
        """Send each character in text through key_press."""
        for ch in text:
            self.key_press(ch)

    def _on_key_press_loop(self):
        """Poll registered keys and invoke the callback while each is held."""
        while self._key_press_callbacks is not None:
            keys, callback = self._key_press_callbacks
            for key in keys:
                if self.is_pressed(key):
                    try:
                        callback(key)
                    except Exception as e:
                        raise RuntimeError(f"Keyboard callback for '{key}' failed: {e}")
            time.sleep(0.05)

    def register_keypress_callback(self,
                                   keys,
                                   callback):
        """Poll keys on a daemon thread and call callback(key) while held.

        keys accepts one key name or a sequence of names."""
        if isinstance(keys, str):
            keys = [keys]
        for k in keys:
            self._parse_key(k)  # Validate before starting the polling thread.
        self._key_press_callbacks = (keys, callback)
        threading.Thread(target=self._on_key_press_loop, daemon=True).start()

    def clean_keypress_callbacks(self):
        """Stop polling registered key callbacks."""
        self._key_press_callbacks = None
