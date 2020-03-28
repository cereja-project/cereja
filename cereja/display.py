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
from typing import Union, List, Sequence, Any
import random
from cereja.cj_types import Number
from cereja.conf import NON_BMP_SUPPORTED
from cereja.utils import proportional

__all__ = ['Progress']
_exclude = ["_Stdout", "ConsoleBase", "BaseProgress", "ProgressLoading", "ProgressBar",
            "ProgressLoadingSequence"]

_include = ["console", "Progress"]

try:
    _LOGIN_NAME = os.getlogin()
except OSError:
    _LOGIN_NAME = "Cereja"

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
        try:
            self.__stdout_original.write(msg)
            self.__stdout_original.flush()
        except UnicodeError:
            msg = self.console.translate_non_bmp(msg)
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
    NON_BMP_MAP = dict.fromkeys(range(0x10000, sys.maxunicode + 1), 0xfffd)
    DONE_UNICODE = "\U00002705"
    ERROR_UNICODE = "\U0000274C"
    CHERRY_UNICODE = "\U0001F352"
    RIGHT_POINTER = "\U000000bb"
    __CL_DEFAULT = '\033[37m'
    CL_BLACK = '\033[30m'
    CL_RED = '\033[31m'
    CL_GREEN = '\033[32m'
    CL_YELLOW = '\033[33m'
    CL_BLUE = '\033[34m'
    CL_MAGENTA = '\033[35m'
    CL_CYAN = '\033[36m'
    CL_WHITE = '\033[37m'
    CL_UNDERLINE = '\033[4m'
    __line_sep_list = ['\r\n', '\n', '\r']
    __non_bmp_supported = NON_BMP_SUPPORTED
    __os_line_sep = os.linesep

    __login_name = _LOGIN_NAME
    __right_point = f"{CL_CYAN}{RIGHT_POINTER}{__CL_DEFAULT}"
    __msg_prefix = f"{CL_RED}{CHERRY_UNICODE}{CL_BLUE}"
    __color_map = {
        "black": CL_BLACK,
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
    def non_bmp_supported(self):
        return self.__non_bmp_supported

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
        return f"{self.__msg_prefix} {title} {self.__right_point}"

    def translate_non_bmp(self, msg: str):
        """
        This is important, as there may be an exception if the terminal does not support unicode bmp
        """
        if self.non_bmp_supported:
            return msg
        return msg.translate(self.NON_BMP_MAP)

    def _parse(self, msg: str, title=None, color: str = None, remove_line_sep=True):

        if color is None:
            color = "default"
        msg = self.format(msg, color)
        if remove_line_sep:
            msg = ' '.join(msg.splitlines())
        prefix = self._msg_prefix(title)
        return f"{prefix} {msg} {self.__CL_DEFAULT}"

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
        self.__stdout._write("\n")
        self.__print(f"Cereja's console {{red}}out!{{endred}}{{default}}")
        self.__stdout.disable()


class BaseProgress(metaclass=ABC):

    def __init__(self, task_name: str, progress_size: int, max_value=100, **kwargs):
        self.__use_loading = True
        self.__running: bool = False
        self.__done = False
        self.__error = False
        self.__time_sleep = 0.5
        self.task_name = task_name
        self.loading_state: str = ''
        self.state: str = ''
        self.max_value: float = max_value
        self.distance_inner_states = 5
        self.current_value = 0.0
        self.current_percent = 0.0
        self.progress_size = progress_size
        self.first_time = 0.0

    def complete_with_blank(self, value: str) -> str:
        """
        Calculates and adds blanks, allowing a more static display
        :param value: is the current sizeof default char value or the proportion of this value in the case of a bar
        :return: string with sizeof max_size
        """
        blanks = '  ' * (self.progress_size - len(value))
        return f"{value}{blanks}"

    def size_prop(self, value: Number):
        """
        Returns the proportion of any number in relation to max_size
        :param value: any number
        """
        return proportional(value, self.progress_size)

    def update(self, current_value: Number, max_value=100):
        """
        :param current_value: Fraction of the "max_value" you want to achieve.
                              Remember that this value is not necessarily the percentage.
                              It is totally dependent on the "max_value"
        :param max_value: This number represents the maximum amount you want to achieve.
                          It is not a percentage, although it is purposely set to 100 by default.
        """
        self.max_value = max(self.max_value, max_value)
        if current_value > self.max_value:
            raise ValueError(f"Current value {current_value} is greater than max_value")

        if current_value is not None:
            if isinstance(current_value, (int, float, complex)) and current_value > 0:
                percent = round((current_value / self.max_value) * 100, 2)
                if self.current_percent > percent:
                    self.reset()
                self.current_percent = percent
                self.state = f"Loading"
                self.current_value = current_value
            else:
                raise Exception(f"Current value {current_value} isn't valid.")

    def __parse(self) -> str:
        loading_state = self.loading_state
        percent = f"{self.current_percent}%"
        state_ = f"{percent} - {self.state}"
        if self.__done:
            time_ = f"\U0001F55C Total: {self._time_it()}s"
        else:
            time_ = f"\U0001F55C Estimated: {self.estimated_time()}s"
        if self.__use_loading:
            state_ = f"{loading_state} {state_} - {time_}"
        return state_

    def is_done(self):
        return self.__done

    def is_running(self):
        return self.__running

    @classmethod
    def done(cls, *args, **kwargs):
        pass

    @abstractmethod
    def progress(self) -> str:
        """
        Is a callback to threading named loading. This function is always being called.
        The request time is defined by the `time_sleep` property
        :return: You need to return a string with the status of your progress
        """
        pass

    def _time_it(self) -> float:
        return round((time.time() - self.first_time), 2)

    def estimated_time(self):
        time_it = max(self._time_it(), 1)
        current_value = self.current_value or 1
        return round((time_it / current_value) * self.max_value - time_it, 2)

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

    def _done(self, _state_msg="Done!", color: str = 'green'):
        if self.__error:
            return
        self.done()
        self.__done = True
        self.current_percent = 100
        self.state = self.console.template_format(
            f"{{{color}}}{self.console.DONE_UNICODE} {_state_msg}{{{'end' + color}}}")

    def _error(self, msg):
        self.__error = True
        self.state = self.console.template_format(f"{{red}}{self.console.ERROR_UNICODE} Error: {msg}{{endred}}")

    def _reset(self):
        self._done()
        self.__done = False
        self.console.replace_last_msg(self.__parse(), "\n")  # las update
        self.current_percent = 0
        self.current_value = 1
        self.first_time = time.time()

    def start(self):
        if not self.__running:
            self.__enter__()

    def stop(self, restart_only: bool = False):
        if restart_only:
            self._reset()
        else:
            self.__exit__(None, None, None)

    def reset(self, _state_msg="Reseted!"):
        self.stop(restart_only=True)
        self.start()

    def __enter__(self):
        self.th_loading = threading.Thread(name="loading", target=self.__update_loading)
        self.root = threading.Thread(name=self.task_name, target=self.__update)
        self.console = ConsoleBase(self.task_name)
        self.first_time = time.time()
        self.__running = True
        self.__done = False
        self.state = "Loading"
        if self.__use_loading:
            self.th_loading.setDaemon(True)
            self.th_loading.start()
        self.console.persist_on_runtime()
        self.root.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, Exception):
            self._error(f'{os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}: {exc_val}')
        else:
            self._done()
        self.__running = False
        self.console.replace_last_msg(self.__parse(), "\n")  # las update
        self.root.join()
        self.console.disable()


class ProgressLoading(BaseProgress):
    """
    :param lef_right_delimiter: str = String of length 2 e.g: '[]'
            Are the delimiters of the default_char
            The default value is '[]'.
            e.g: [=============] # left is '[' and right is ']'
            
            
    :param default_char: Single string you can send a unicode :)
            Value that will be added or replaced simulating animation.
    """

    def __init__(self, task_name, progress_size=3, default_char='.', lef_right_delimiter="[]", **kwargs):
        super().__init__(task_name=task_name, progress_size=progress_size, **kwargs)
        self.default_char = default_char

        if not isinstance(lef_right_delimiter, str):
            raise TypeError("Delimiters validation. Please send string.")
        elif len(lef_right_delimiter) != 2:
            raise ValueError("Delimiters validation. Please send a string of length 2")

        self.left_right_delimiter = lef_right_delimiter

    def progress(self):
        l_delimiter, r_delimiter = self.left_right_delimiter
        current = self.loading_state or ''
        current = current.strip(l_delimiter).strip(r_delimiter).strip()  # clean blanks
        if current is not None and len(current) < self.progress_size:
            current = f"{current}{self.default_char}"
        else:
            current = ''
        current = self.complete_with_blank(current)
        return f"{l_delimiter}{current}{r_delimiter}"

    def done(self):
        l_delimiter, r_delimiter = self.left_right_delimiter
        self.loading_state = f"{l_delimiter}{self.default_char * self.progress_size}{r_delimiter}"


class ProgressBar(ProgressLoading):

    def __init__(self, task_name, max_value=100, progress_size=30, default_char='=', lef_right_delimiter="[]",
                 **kwargs):
        super().__init__(task_name, max_value=max_value, progress_size=progress_size, default_char=default_char,
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


class ProgressLoadingSequence(ProgressLoading):
    __sequence = ("\U0001F55C", "\U0001F55D", "\U0001F55E", "\U0001F55F", "\U0001F560", "\U0001F561", "\U0001F562",
                  "\U0001F563", "\U0001F564", "\U0001F565", "\U0001F566", "\U0001F567")

    def __init__(self, task_name, sequence: Union[list, tuple] = None, *args, **kwargs):
        super().__init__(task_name, *args, **kwargs)
        if sequence is not None:
            self.__sequence = sequence
        self._n_times = 0

    def progress(self):
        self._n_times += 1
        if len(self.__sequence) == self._n_times:
            self._n_times = 0
        return self.__sequence[self._n_times - 1]


class Progress:
    __style_map = {
        "loading": ProgressLoading,
        "bar": ProgressBar,
        "sequence": ProgressLoadingSequence
    }

    def __init__(self):
        self.__items = None

    @property
    def styles(self):
        return list(self.__style_map)

    def __call__(self, task_name="Progress Tool", style="loading", max_value=100, **kwargs) -> BaseProgress:
        """
        Percentage calculation is based on max_value (default is 100) and current_value:
        percent = (current_value / max_value) * 100

        :param style: defines the type of progress that will be used. "loading" is Default
                    You can choose those available ['loading', 'bar', 'sequence']
        :param task_name: Defines the name to be displayed in progress
        :param max_value: This number represents the maximum amount you want to achieve.
                          It is not a percentage, although it is purposely set to 100 by default.
        :param kwargs:
                loading_with_clock: You will see a clock if the style is loading
        :return: Progress
        """
        if "loading_with_clock" in kwargs and style == "loading":
            use_sequence = bool(kwargs.pop("loading_with_clock"))
            style = "sequence" if use_sequence else "loading"
        return self._get_progress(style=style, task_name=task_name, max_value=max_value, **kwargs)

    def _get_progress(self, style, **kwargs):
        if style not in self.__style_map:
            raise ValueError(f"Unknown {repr(style)} progress style. You can choose those available {self.styles}")
        return self.__style_map[style](**kwargs)

    def __iter__(self):
        return next(self.__items)

    def prog(self, iterator_: Sequence[Any], style: str = "bar", task_name: str = "Cereja Progress") -> Sequence[Any]:
        """
        Percentage calculation is based on iterator_ length and current_value:
        percent = (current_value / len(iterator_)) * 100

        :param iterator_: Sequence of anything
        :param style: choose those available 'loading', 'bar' and 'sequence'
        :param task_name: Prefix on console.
        :return: Same sequence.
        """
        bar_ = self._get_progress(task_name=task_name, style=style, max_value=len(iterator_))
        bar_.start()
        for n, value in enumerate(iterator_, start=1):
            self.__items = yield value
            bar_.update(n)
        bar_.stop()
        return bar_


class __Console(ConsoleBase):
    pass


console = __Console()

Progress = Progress()
if __name__ == '__main__':
    for n, i in enumerate(Progress.prog(range(100))):
        if n > 0:
            time.sleep(1 / n)
        if n % 20 == 0:
            print(i)

    for n, i in enumerate(Progress.prog(['cj_progress'] * 300)):
        if n > 0:
            time.sleep(1 / n)
        if n % 10 == 0:
            print(i)

    console.log(console.random_color("hi"))
