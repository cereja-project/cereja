"""Desktop and window-directed mouse input using the shared native API."""

import ctypes
import random
import time
from typing import Tuple

from ...utils import is_numeric_sequence
from .api import get_api
from .types import POINT


class Mouse:
    _button_envent_map = {
        "move": 1,
        "left_down": 2,
        "left_up": 4,
        "right_down": 8,
        "right_up": 10,
        "left_click": 6,
        "right_click": 24
    }

    _mouse_messages_map = {
        "move": 0x0200,
        "left_down": 0x0201,
        "left_up": 0x0202,
        "WM_LBUTTONDBLCLK": 0x0203,
        "right_down": 0x0204,
        "right_up": 0x0205,
        "WM_RBUTTONDBLCLK": 0x0206,
        "WM_MBUTTONDOWN": 0x0207,
        "WM_MBUTTONUP": 0x0208,
        "WM_MBUTTONDBLCLK": 0x0209,
        "WM_MOUSEWHEEL": 0x020A,
        "WM_XBUTTONDOWN": 0x020B,
        "WM_XBUTTONUP": 0x020C,
        "WM_XBUTTONDBLCLK": 0x020D,
        "WM_MOUSEHWHEEL": 0x020E
    }

    def __init__(self,
                 hwnd=None,
                 is_async=True):
        self.user32 = get_api()
        self.send_event = self.user32.PostMessageW if is_async else self.user32.SendMessageW
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
        cursor = POINT()
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

    def set_random_position(self):
        w, h = self.window_size
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        self.set_position(x, y)

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
            if n_clicks < 1:
                raise ValueError("n_clicks must be at least 1")
            if position is None:
                position = self.position
            l_param = (position[1] << 16) | position[0]  # y << 16 | x
            self.send_event(self._hwnd, self._mouse_messages_map["move"], 0, l_param)
            button_state = 0x0001 if button == "left" else 0x0002
            for index in range(n_clicks):
                if index:
                    time.sleep(interval)
                self.send_event(self._hwnd, self._mouse_messages_map[f"{button}_down"], button_state, l_param)
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
