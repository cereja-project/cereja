"""
Copyright (c) 2019 The Cereja Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
import io
import os
import threading
import sys
import time
from abc import ABCMeta as ABC, abstractmethod
from typing import Union, List
import random
from cereja.cj_types import Number

__all__ = 'Progress'

from cereja.utils import proportional

if sys.platform.lower() == "win32":
    os.system('color')


class _Stdout:
    __stdout_original = sys.stdout
    __stderr_original = sys.stderr
    __user_msg = []

    def __init__(self, console):
        self.last_console_msg = ""
        self.console = console
        self.use_th_console = True
        self.__stdout_buffer = io.StringIO()
        self.__stderr_buffer = io.StringIO()
        self.th_console = threading.Thread(name="Console", target=self.write_user_msg)
        self.th_console.setDaemon(True)
        self.th_console.start()

    def set_message(self, msg):
        self.__user_msg = msg

    def write_user_msg(self):
        while True:
            stdout = self.__stdout_buffer.getvalue()[:-1]
            stderr = self.__stderr_buffer.getvalue()[:-1]
            if stdout and not (stdout in ["\n", "\r\n", "\n"]):
                values = []
                for value in stdout.splitlines():
                    value = f"{self.console.parse(value, title='Sys[out]')}"
                    values.append(value)
                value = '\n'.join(values)
                value = f'\r{value}\n{self.last_console_msg}'
                self._write(value)
                self.__stdout_buffer.seek(0)
                self.__stdout_buffer.truncate()
            if stderr and not (stderr in ["\n", "\r\n", "\n"]):
                unicode_err = '\U0000274C'
                prefix = self.console.template_format(f"{{red}}{unicode_err} Error:{{endred}}")
                msg_err_prefix = f"{self.console.parse(prefix, title='Sys[err]')}"
                msg_err = self.console.format(stderr, color="red")
                msg_err = f'\r{msg_err_prefix}\n{msg_err}\n{self.last_console_msg}'
                self._write(msg_err)
                self.__stderr_buffer.seek(0)
                self.__stderr_buffer.truncate()
            time.sleep(1)

    def _write(self, msg: str):
        self.__stdout_original.write(msg)
        self.__stdout_original.flush()

    def cj_msg(self, msg: str, line_sep=None, replace_last=False):
        self.last_console_msg = msg
        if replace_last:
            msg = f"\r{msg}"
        self._write(msg)
        if line_sep is not None:
            self._write(line_sep)

    def __del__(self):
        sys.stdout = self.__stdout_original
        sys.stderr = self.__stderr_original

    def write_error(self, msg, **ars):
        msg = self.console.format(msg, color="red")
        self.__stdout_buffer.write(msg)

    def flush(self):
        self.__stdout_original.flush()

    def persist(self):
        sys.stdout = self.__stdout_buffer
        sys.stderr = self.__stderr_buffer

    def disable(self):
        sys.stdout = self.__stdout_original
        sys.stderr = self.__stderr_original


class ConsoleBase(metaclass=ABC):
    __CL_DEFAULT = '\033[30m'
    CL_RED = '\033[31m'
    CL_GREEN = '\033[32m'
    CL_YELLOW = '\033[33m'
    CL_BLUE = '\033[34m'
    CL_MAGENTA = '\033[35m'
    CL_CYAN = '\033[36m'
    CL_WHITE = '\033[37m'
    CL_UNDERLINE = '\033[4m'

    __line_sep_list = ['\r\n', '\n', '\r']
    __os_line_sep = os.linesep

    __login_name = os.getlogin()
    __right_point = f"{CL_CYAN}\U000000bb{__CL_DEFAULT}"
    __msg_prefix = f"{CL_RED}\U0001F352{CL_BLUE}"
    __color_map = {
        "black": __CL_DEFAULT,
        "red": CL_RED,
        "green": CL_GREEN,
        "yellow": CL_YELLOW,
        "blue": CL_BLUE,
        "magenta": CL_MAGENTA,
        "cyan": CL_CYAN,
        "white": CL_WHITE,
        "default": __CL_DEFAULT
    }
    MAX_SPACE = 20
    MAX_BLOCKS = 5

    SPACE_BLOCKS = {""}

    def __init__(self, title: str = __login_name, color_text: str = "default"):
        self.title = title
        self.__color_map = self._color_map  # get copy
        self.text_color = color_text
        self.__stdout = _Stdout(self)

    @property
    def title(self):
        return self.__name

    @property
    def _color_map(self):
        return self.__color_map.copy()

    @title.setter
    def title(self, value):
        self.__name = value

    @property
    def text_color(self):
        return self.__text_color

    @text_color.setter
    def text_color(self, color: str):
        color = color.strip('CL_').lower() if color.upper().startswith('CL_') else color.lower()
        if color not in self.__color_map:
            raise ValueError(f"Color not found.")
        self.__color_map['default'] = self.__color_map[color]
        self.__text_color = self.__color_map[color]

    def __bg(self, text_, color):
        return f"\33[48;5;{color}m{text_}{self.__text_color}"

    def _msg_prefix(self, title=None):
        if title is None:
            title = self.title
        return f"{self.__msg_prefix} {title} {self.__right_point}{self.__text_color}"

    def _parse(self, msg: str, title=None, color: str = None, remove_line_sep=True):
        if color is None:
            color = "default"
        msg = self.format(msg, color)
        if remove_line_sep:
            msg = ' '.join(msg.splitlines())
        prefix = self._msg_prefix(title)
        return f"{prefix} {msg}{self.__CL_DEFAULT}"

    def _write(self, msg, line_sep=None):
        self.__stdout.cj_msg(msg, line_sep)

    def _normalize_format(self, s):
        for color_name in self.__color_map:
            s = s.replace(f'end{color_name}', 'default')
        s = s.replace('  ', ' ')
        return s

    def parse(self, msg, title=None):
        return self._parse(msg, title)

    def template_format(self, s):
        """
        You can make format with variables
        :param s:
        :return:
        """
        s = self._normalize_format(s)
        try:
            s = f'{s}'.format_map(self.__color_map)
            return s
        except KeyError as err:
            self.error(f"Color {err} not found.")
        return s

    def format(self, s: str, color: str):
        if color not in self.__color_map:
            raise ValueError(
                f"Color {repr(color)} not found. Choose an available color"
                f" [red, green, yellow, blue, magenta and cyan].")
        s = f"{{{color}}}{s}{{{'end' + color}}}"
        return self.template_format(s)

    def random_color(self, text: str):
        color = random.choice(list(self.__color_map))
        template_format = f'{{{color}}}{text}{{{"end" + color}}}'
        return self.template_format(template_format)

    def colorful_words(self, text: Union[List[str], str]) -> str:
        msg_error = "You need send string or list of string."
        if isinstance(text, str):
            text = text.split()
        elif isinstance(text, list):
            if not isinstance(next(iter(text)), str):
                self.error(msg_error)
        else:
            self.error(msg_error)
        result = []
        for word in text:
            result.append(self.random_color(word))
        return ' '.join(result)

    def text_bg(self, text_, color):
        return self.__bg(text_, color)

    def error(self, msg: str):
        msg = f"Error: {msg}"
        msg = self.format(msg, color="red")
        self.__print(msg)

    def replace_last_msg(self, msg: str, end=None):
        msg = self._parse(msg, remove_line_sep=True)
        self.__stdout.cj_msg(msg, replace_last=True, line_sep=end)

    def log(self, msg, title=None, color: str = "default", end: str = __os_line_sep):
        """
        Send message with default configuration and colors
        title is login name.

        :param msg: value you want to display
        :param title: You can custom title of message
        :param color: You can custom color of message
                colors available: black, red, green, yellow, blue, magenta, cyan and white.
        :param end: if you send None or '' remove line_sep
        """
        self.__print(msg=msg, title=title, color=color, end=end)

    def persist_on_runtime(self):
        self.__stdout.persist()

    def __print(self, msg, title=None, color: str = None, end=__os_line_sep):
        remove_line_sep = True if end is None else False
        msg = self._parse(msg=msg, title=title, color=color, remove_line_sep=remove_line_sep)
        self.__stdout.cj_msg(msg, end)

    def disable(self):
        self.title = "Cereja"
        self.__print(f"Cereja's console {{red}}out!{{endred}}{{default}}")
        self.__stdout.disable()


class BaseProgress:
    NON_BMP_MAP = dict.fromkeys(range(0x10000, sys.maxunicode + 1), 0xfffd)
    DONE_UNICODE = "\U00002705"
    ERROR_UNICODE = "\U0000274C"
    CHERRY_UNICODE = "\U0001F352"
    RIGHT_POINTER = "\U000000bb"

    def __init__(self, name: str, progress_size: int, max_value=100, **kwargs):
        self.__use_loading = True
        self.__running: bool = False
        self.__done = False
        self.__error = False
        self.__time_sleep = 0.5
        self.name = name
        self.loading_state: str = ''
        self.state: str = ''
        self.max_value: float = max_value
        self.distance_inner_states = 10
        self.current_value = 0.0
        self.current_percent = 0.0
        self.progress_size = progress_size
        self.root = threading.Thread(name=self.name, target=self.__update)
        self.th_loading = threading.Thread(name="loading", target=self.__update_loading)
        self.th_loading.setDaemon(True)
        self.console = ConsoleBase(name)

    def complete_with_blank(self, value: str) -> str:
        """
        Calculates and adds blanks, allowing a more static display
        :param value: is the current sizeof default char value or the proportion of this value in the case of a bar
        :return: string with sizeof max_size
        """
        blanks = '  ' * (self.distance_inner_states - len(value))
        return f"{value}{blanks}"

    def size_prop(self, value: Number):
        """
        Returns the proportion of any number in relation to max_size
        :param value: any number
        """
        return proportional(value, self.progress_size)

    def update(self, current_value: Number, max_value=None):
        """
        :param current_value: Fraction of the "max_value" you want to achieve.
                              Remember that this value is not necessarily the percentage.
                              It is totally dependent on the "max_value"
        :param max_value: This number represents the maximum amount you want to achieve.
                          It is not a percentage, although it is purposely set to 100 by default.
        """
        if max_value is not None:
            if max_value != self.max_value:
                self.reset(new_max_value=max_value)
        if current_value is not None:
            if isinstance(current_value, (int, float, complex)) and current_value > 0:
                self.current_percent = round((current_value / self.max_value) * 100, 2)
                self.current_value = current_value
            else:
                raise Exception("Send Number.")

    def __parse(self) -> str:
        loading_state = self.loading_state
        percent = f"{self.current_percent}%"
        state_ = f"{percent} {self.state}"
        if self.__use_loading:
            state_ = f"{loading_state} - {state_}"
        return state_

    def is_done(self):
        return self.__done

    def is_running(self):
        return self.__running

    @classmethod
    def done(cls, *args, **kwargs):
        pass

    @classmethod
    def progress(cls) -> str:
        """
        Is a callback to threading named loading. This function is always being called.
        The request time is defined by the `time_sleep` property
        :return: You need to return a string with the status of your progress
        """
        pass

    def __update_loading(self):
        while self.is_running and not self.__done:
            self.loading_state = self.progress()
            self.sleep()

    def __update(self):
        while self.__running:
            self.console.replace_last_msg(self.__parse())
            self.sleep()
        self._done()

    def sleep(self):
        time.sleep(self.__time_sleep)

    def set_up(self):
        if self.__running:
            self.console.log(f"{self.name} already started!")
        else:
            self.__running = True
            self.state = "Running"
            if self.__use_loading:
                self.th_loading.start()
            self.console.persist_on_runtime()
            self.root.start()

    def reset(self, new_max_value, _state_msg="Reseted!"):
        self.max_value = new_max_value
        self.stop()
        self.set_up()
        self.loading_state = ''

    def _done(self, _state_msg="Done!", user_msg=None, color: str = 'green'):
        if self.__error:
            return
        self.done()
        self.__done = True
        self.current_percent = 100
        self.state = self.console.template_format(f"{{{color}}}{self.DONE_UNICODE} {_state_msg}{{{'end' + color}}}")
        if user_msg is not None:
            self.__user_output_state = user_msg

    def stop(self):
        self.__running = False
        self.console.replace_last_msg(self.__parse(), "\n")  # las update
        self.root.join()
        self.console.disable()

    def _error(self, msg):
        self.__error = True
        self.state = self.console.template_format(f"{{red}}{self.ERROR_UNICODE} Error: {msg}{{endred}}")

    def __enter__(self):
        self.set_up()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, Exception):
            self._error(f'{os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}: {exc_val}')

        self.stop()


class ProgressLoading(BaseProgress):
    CLOCKS_UNICODE = ("\U0001F55C", "\U0001F55D", "\U0001F55E", "\U0001F55F", "\U0001F560", "\U0001F561", "\U0001F562",
                      "\U0001F563", "\U0001F564", "\U0001F565", "\U0001F566", "\U0001F567")

    """
    :param lef_right_delimiter: str = String of length 2 e.g: '[]'
            Are the delimiters of the default_char
            The default value is '[]'.
            e.g: [=============] # left is '[' and right is ']'
            
            
    :param default_char: Single string you can send a unicode :)
            Value that will be added or replaced simulating animation.
    """

    def __init__(self, name, progress_size=3, default_char='.', lef_right_delimiter="[]", **kwargs):
        super().__init__(name=name, progress_size=progress_size, **kwargs)
        self.default_char = default_char

        if not isinstance(lef_right_delimiter, str):
            raise TypeError("Delimiters validation. Please send string.")
        elif len(lef_right_delimiter) != 2:
            raise ValueError("Delimiters validation. Please send a string of length 2")

        self.left_right_delimiter = lef_right_delimiter

    def progress(self):
        current = self.loading_state or ''
        current = current.strip()  # clean blanks
        if current is not None and len(current) < self.progress_size:
            current = f"{current}{self.default_char}"
        else:
            current = ''
        current = self.complete_with_blank(current)
        return f"{current}"


class ProgressBar(ProgressLoading):

    def __init__(self, name, max_value=100, progress_size=30, default_char='=', lef_right_delimiter="[]", **kwargs):
        super().__init__(name, max_value=max_value, progress_size=progress_size, default_char=default_char,
                         lef_right_delimiter=lef_right_delimiter, **kwargs)
        self.arrow: str = '>'
        self.use_arrow: bool = True

    def use_arrow(self):
        return self.use_arrow

    def set_arrow(self, value: bool):
        self.use_arrow = value

    def progress(self):
        last_char = self.arrow if self.use_arrow and not self.is_done() else self.default_char
        l_delimiter, r_delimiter = self.left_right_delimiter
        prop_max_size = int(self.size_prop(self.current_percent))
        blanks = '  ' * (self.progress_size - prop_max_size)
        return f"{l_delimiter}{self.default_char * prop_max_size}{last_char}{blanks}{r_delimiter}"

    def done(self, *args, **kwargs):
        l_delimiter, r_delimiter = self.left_right_delimiter
        self.loading_state = f"{l_delimiter}{self.default_char * self.progress_size}{r_delimiter}"


if __name__ == '__main__':

    with ProgressBar("Cerejinha", max_value=300) as p:
        for i in range(1, 300):
            time.sleep(1 / i)
            p.update(i)
        for i in range(1, 300):
            time.sleep(1 / i)
            print(i)
            p.update(i, max_value=300)
