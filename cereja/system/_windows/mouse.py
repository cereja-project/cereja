"""Desktop and window-directed mouse input using the shared native API."""

import ctypes
import random
import time
from typing import Tuple

from ...utils import is_numeric_sequence
from .api import get_api
from .constants import MouseEvent, MouseKeyState, SystemMetric, WindowMessage
from .types import POINT


class Mouse:
    _button_envent_map = {
        "move": MouseEvent.MOVE,
        "left_down": MouseEvent.LEFTDOWN,
        "left_up": MouseEvent.LEFTUP,
        "right_down": MouseEvent.RIGHTDOWN,
        "right_up": MouseEvent.RIGHTUP,
        "left_click": MouseEvent.LEFTDOWN | MouseEvent.LEFTUP,
        "right_click": MouseEvent.RIGHTDOWN | MouseEvent.RIGHTUP,
    }

    _mouse_messages_map = {
        "move": WindowMessage.MOUSEMOVE,
        "left_down": WindowMessage.LBUTTONDOWN,
        "left_up": WindowMessage.LBUTTONUP,
        "WM_LBUTTONDBLCLK": WindowMessage.LBUTTONDBLCLK,
        "right_down": WindowMessage.RBUTTONDOWN,
        "right_up": WindowMessage.RBUTTONUP,
        "WM_RBUTTONDBLCLK": WindowMessage.RBUTTONDBLCLK,
        "WM_MBUTTONDOWN": WindowMessage.MBUTTONDOWN,
        "WM_MBUTTONUP": WindowMessage.MBUTTONUP,
        "WM_MBUTTONDBLCLK": WindowMessage.MBUTTONDBLCLK,
        "WM_MOUSEWHEEL": WindowMessage.MOUSEWHEEL,
        "WM_XBUTTONDOWN": WindowMessage.XBUTTONDOWN,
        "WM_XBUTTONUP": WindowMessage.XBUTTONUP,
        "WM_XBUTTONDBLCLK": WindowMessage.XBUTTONDBLCLK,
        "WM_MOUSEHWHEEL": WindowMessage.MOUSEHWHEEL,
    }

    def __init__(self,
                 hwnd=None,
                 is_async=True):
        self.user32 = get_api()
        self.send_event = self.user32.PostMessageW if is_async else self.user32.SendMessageW
        self._hwnd = hwnd

    @property
    def window_size(self):
        return (self.user32.GetSystemMetrics(SystemMetric.CXSCREEN),
                self.user32.GetSystemMetrics(SystemMetric.CYSCREEN))

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
            button_state = MouseKeyState.LBUTTON if button == "left" else MouseKeyState.RBUTTON
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

            # Send the initial client-area position.
            self.send_event(self._hwnd, self._mouse_messages_map["move"], 0, from_l_param)
            # Hold the left button before moving.
            self.send_event(self._hwnd, self._mouse_messages_map["left_down"], MouseKeyState.LBUTTON, from_l_param)
            # Send the destination and release the button.
            self.send_event(self._hwnd, self._mouse_messages_map["move"], 0, to_l_param)
            self.send_event(self._hwnd, self._mouse_messages_map["left_up"], 0, to_l_param)
        else:
            self.set_position(from_[0], from_[1])
            self.user32.mouse_event(self._button_envent_map["left_down"], from_[0], from_[1], 0, 0)
            self.set_position(to[0], to[1])
            self.user32.mouse_event(self._button_envent_map["left_up"], to[0], to[1], 0, 0)

    def move_to_center(self):
        self.set_position(*self.center_position)
