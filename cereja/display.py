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
import time
import warnings
import sys
import random
from typing import Tuple
from abc import ABCMeta as ABC
from typing import List
from abc import ABCMeta, abstractmethod
from typing import Sequence, Any, Union, AnyStr

from cereja.conf import NON_BMP_SUPPORTED
from cereja.arraytools import is_iterable
from cereja.cj_types import Number
from cereja.unicode import Unicode
from cereja.utils import percent, estimate, proportional, fill, time_format

__all__ = ['Progress', "StateBase"]
_exclude = ["_Stdout", "ConsoleBase", "BaseProgress", "ProgressLoading", "ProgressBar",
            "ProgressLoadingSequence", "State"]

_include = ["console", "Progress", "StateBase"]

try:
    _LOGIN_NAME = os.getlogin()
except OSError:
    _LOGIN_NAME = "Cereja"


class __Stdout:
    __stdout_original = sys.stdout
    __stderr_original = sys.stderr
    __user_msg = []

    def __init__(self):
        self.persisting = False
        self.th_console = None
        self.last_console_msg = ""
        self.use_th_console = False
        self.__stdout_buffer = io.StringIO()
        self.__stderr_buffer = io.StringIO()
        self.hook_err = None

    def __call__(self, console_, hook_err=None):
        self.console = console_
        if hook_err is not None:
            self.hook_err = hook_err
        return self

    def set_message(self, msg):
        self.__user_msg = msg

    def _has_user_msg(self):
        if self.__stdout_buffer.getvalue():
            return True
        else:
            return False

    def write_user_msg(self):
        while self.use_th_console:
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
                if self.hook_err is not None:
                    self.hook_err()
            time.sleep(0.1)

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
        if not self.persisting:
            self.use_th_console = True
            self.th_console = threading.Thread(name="Console", target=self.write_user_msg)
            self.th_console.start()
            sys.stdout = self.__stdout_buffer
            sys.stderr = self.__stderr_buffer
            self.persisting = True

    def disable(self):
        if self.use_th_console:
            while self._has_user_msg():
                pass
            else:
                msg = self.console.parse(f"Cereja's console {{red}}out!{{endred}}{{default}}")
                self.cj_msg(f'\n{msg}')
                self.use_th_console = False
                self.th_console.join()
        sys.stdout = self.__stdout_original
        sys.stderr = self.__stderr_original


_Stdout = __Stdout()


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
        "black":   CL_BLACK,
        "red":     CL_RED,
        "green":   CL_GREEN,
        "yellow":  CL_YELLOW,
        "blue":    CL_BLUE,
        "magenta": CL_MAGENTA,
        "cyan":    CL_CYAN,
        "white":   CL_WHITE,
        "default": __CL_DEFAULT
    }

    MAX_SPACE = 20
    MAX_BLOCKS = 5

    SPACE_BLOCKS = {""}

    def __init__(self, title: str = __login_name, color_text: str = "default", hook_error=None):
        self.__name = title
        self.__color_map = self._color_map  # get copy
        self.text_color = color_text
        self.__stdout = _Stdout(self, hook_error)

    @property
    def non_bmp_supported(self):
        return self.__non_bmp_supported

    @property
    def prefix_name(self):
        return self.__name

    def set_prefix(self, value: str):
        if not isinstance(value, str):
            raise TypeError("Please send string value.")
        self.__name = value

    @property
    def _color_map(self):
        return self.__color_map.copy()

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
            title = self.prefix_name
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
        if color == "random":
            return self.random_color(s)
        if color not in self.__color_map:
            raise ValueError(
                    f"Color {repr(color)} not found. Choose an available color"
                    f" [red, green, yellow, blue, magenta and cyan].")
        s = self.template_format(s)
        return f"{self._color_map[color]}{s}{self._color_map[color]}"

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
        self.__stdout.disable()


class State(metaclass=ABCMeta):
    size = 10

    def __repr__(self):
        return f"{self.name} {self.done(100, 100, 100, 0, 100)}"

    def blanks(self, current_size):
        blanks = '  ' * (self.size - current_size - 1)
        return blanks

    @property
    def name(self):
        return f"{self.__class__.__name__.replace('__State', '')} field"

    @abstractmethod
    def display(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
                n_times: int) -> str:
        """
        This function is always being called.
        :return: You need to return a string with the status of your progress
        """
        pass

    @abstractmethod
    def done(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
             n_times: int) -> str:
        pass


class __StateLoading(State):
    """
    lef_right_delimiter: str = String of length 2 e.g: '[]'
            Are the delimiters of the default_char
            The default value is '[]'.
            e.g: [=============] # left is '[' and right is ']'


    default_char: Single string you can send a unicode :)
            Value that will be added or replaced simulating animation.
    """
    sequence = (".", ".", ".")
    left_right_delimiter = "[]"
    default_char = "."
    size = 3

    def display(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
                n_times: int) -> str:
        idx = n_times % self.size
        value = ''.join(self.sequence[:idx + 1])
        filled = fill(value, self.size, with_=' ')
        l_delimiter, r_delimiter = self.left_right_delimiter
        return f"{l_delimiter}{filled}{r_delimiter}"

    def done(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
             n_times: int) -> str:
        l_delimiter, r_delimiter = self.left_right_delimiter
        return f"{l_delimiter}{self.default_char * self.size}{r_delimiter}"


class __StateAwaiting(__StateLoading):

    def _clean(self, result):
        return result.strip(self.left_right_delimiter)

    def display(self, *args, **kwargs) -> str:
        result = self._clean(super().display(*args, **kwargs))
        return f"Awaiting{result}"

    def done(self, *args, **kwargs) -> str:
        result = self._clean(super().done(*args, **kwargs))
        return f"Awaiting{result} Done!"


class __StateBar(State):
    left_right_delimiter = "[]"
    arrow = ">"
    default_char = "="
    size = 30

    def display(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
                n_times: int) -> AnyStr:
        l_delimiter, r_delimiter = self.left_right_delimiter
        prop_max_size = int(proportional(current_percent, self.size))
        blanks = '  ' * (self.size - prop_max_size - 1)
        return f"{l_delimiter}{'=' * prop_max_size}{self.arrow}{blanks}{r_delimiter}"

    def done(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
             n_times: int) -> str:
        l_delimiter, r_delimiter = self.left_right_delimiter
        return f"{l_delimiter}{self.default_char * self.size}{r_delimiter}"


class __StatePercent(State):
    size = 8

    def display(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
                n_times: int) -> str:
        value = f"{current_percent:.2f}"
        zeros = f"{' ' * (6 - len(value))}"
        return f"{zeros}{value}%"

    def done(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
             n_times: int) -> str:
        return f"{100:.2f}%"


class __StateTime(State):
    __clock = Unicode("\U0001F55C")
    __max_sequence = 12
    size = 11

    def display(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
                n_times: int) -> str:
        time_estimate = estimate(current_value, max_value, time_it)
        idx = int(proportional(int(current_percent), self.__max_sequence))
        t_format = f"{time_format(time_estimate)}"
        value = f"{self.__clock + idx} {t_format}"
        return f"{value}{self.blanks(len(value))} estimated"

    def done(self, current_value: Number, max_value: Number, current_percent: Number, time_it: Number,
             n_times: float) -> str:
        return f"{self.__clock} {time_format(time_it)} total"


StateBase = State
StateBar = __StateBar()
StatePercent = __StatePercent()
StateTime = __StateTime()
StateLoading = __StateLoading()
StateAwaiting = __StateAwaiting()
console = ConsoleBase()


class ProgressBase:
    default_states = (StateBar, StatePercent, StateTime,)

    __awaiting_state = StateAwaiting
    __done_unicode = Unicode("\U00002705")
    __err_unicode = Unicode("\U0000274C")
    __key_map = {
        "loading": StateLoading,
        "time":    StateTime,
        "percent": StatePercent,
        "bar":     StateBar

    }

    def __init__(self, console_: ConsoleBase, max_value: int = 100, states=None):
        self.n_times = 0
        self.__name = self.set_name("Cereja Progress Tool")
        self.__task_count = 0
        self.started = False
        self._awaiting_update = True
        self._show = False
        self.console = console_
        self.started_time = None
        self._states = self.default_states
        self.add_state(states)
        self.max_value = max_value
        self._current_value = 0
        self.th_root = self._create_progress_service()
        self._with_context = False
        self._was_done = False
        self._err = False

    @property
    def name(self):
        return self.__name

    def set_name(self, value: str):
        if not isinstance(value, str):
            raise TypeError("Please send string.")
        self.__name = value

    def _create_progress_service(self):
        return threading.Thread(name="awaiting", target=self._progress_service)

    def __repr__(self):
        state, _ = self._states_view(self.max_value)
        progress_example_view = f"{state}"
        state_conf = f"{self.__class__.__name__}{self._parse_states()}"
        return f"{state_conf}\n{self.console.parse(progress_example_view, title='Example States View')}"

    def hook_error(self, *args, **kwargs):
        self._err = True
        if not self._with_context:
            self.stop()

    def _parse_states(self):
        return tuple(map(lambda stt: stt.__class__.__name__, self._states))

    def _get_done_state(self, **kwargs):
        result = list(map(lambda state: state.done(**kwargs), self._states))
        done_msg = f"Done! {self.__done_unicode}"
        done_msg = self.console.format(done_msg, 'green')
        result.append(done_msg)
        return result

    def _get_error_state(self):
        result, _ = self._states_view(self._current_value)
        error_msg = f"Error! {self.__err_unicode}"
        error_msg = self.console.format(error_msg, 'red')
        return f'{result} {error_msg}'

    def _get_state(self, **kwargs):
        return list(map(lambda state: state.display(**kwargs), self._states))

    def _states_view(self, for_value: Number) -> Tuple[str, bool]:
        """
        Return current state and bool
        bool:
        :param for_value:
        :return: current state and bool if is done else False
        """
        self.n_times += 1
        kwargs = {
            "current_value":   for_value,
            "max_value":       self.max_value,
            "current_percent": self.percent_(for_value),
            "time_it":         time.time() - (self.started_time or time.time()),
            "n_times":         self.n_times
        }
        if for_value >= self.max_value - 1:
            return ' - '.join(self._get_done_state(**kwargs)), True

        return ' - '.join(self._get_state(**kwargs)), False

    def add_state(self, state: Union[State, Sequence[State]], idx=-1):
        self._filter_and_add_state(state, idx)

    def remove_state(self, idx):
        states = list(self._states)
        states.pop(idx)
        self._states = tuple(states)

    def _valid_states(self, states: Union[State, Sequence[State]]):
        if states is not None:
            if not is_iterable(states):
                states = (states,)
            return tuple(map(lambda st: st if isinstance(st, State) else st(), states))
        return None,

    def _filter_and_add_state(self, state: Union[State, Sequence[State]], index_=-1):
        state = self._valid_states(state)
        filtered = tuple(
                filter(
                        lambda stt: stt not in self._states,
                        tuple(state)
                ))
        if any(filtered):
            if index_ == -1:
                self._states += filtered
            else:
                states = list(self._states)
                for idx, new_state in enumerate(filtered):
                    states.insert(index_ + idx, new_state)
                self._states = tuple(states)
            self.console.log(f"Added new states! {filtered}")

    @property
    def states(self):
        return self._parse_states()

    def percent_(self, for_value: Number) -> Number:
        return percent(for_value, self.max_value)

    def update_max_value(self, max_value: int):
        """
        You can modify the progress to another value. It is not a percentage,
        although it is purposely set to 100 by default.

        :param max_value: This number represents the maximum amount you want to achieve.
        """
        if not isinstance(max_value, (int, float, complex)):
            raise Exception(f"Current value {max_value} isn't valid.")
        if max_value != self.max_value:
            self.max_value = max_value

    def _progress_service(self):
        last_value = self._current_value
        n_times = 0
        while self.started:
            if (self._awaiting_update and self._current_value != last_value) or not self._show:
                n_times += 1
                self.console.replace_last_msg(self.__awaiting_state.display(0, 0, 0, 0, n_times=n_times))
                time.sleep(0.5)
            if not self._awaiting_update or self._show:
                self._show_progress(self._current_value)
            last_value = self._current_value
            time.sleep(0.01)
        if not self._was_done:
            self._show_progress(self.max_value)

    def _show_progress(self, for_value=None):
        self._awaiting_update = False
        build_progress, is_done = self._states_view(for_value)
        end = '\n' if is_done else None

        if self._err:
            self.console.replace_last_msg((self._get_error_state()))
        if not self._was_done and not self._err:
            self.console.replace_last_msg(build_progress, end=end)
        if is_done:
            self._show = False
            self._awaiting_update = True
            self._was_done = True
        else:
            self._was_done = False

    def _update_value(self, value):
        self._awaiting_update = False
        self._show = True
        self._current_value = value

    def show_progress(self, for_value, max_value=None):
        """
        Build progress by a value.

        :param for_value: Fraction of the "max_value" you want to achieve.
                              Remember that this value is not necessarily the percentage.
                              It is totally dependent on the "max_value"
        :param max_value: This number represents the maximum amount you want to achieve.
                          It is not a percentage, although it is purposely set to 100 by default.
        """
        if max_value is not None:
            self.update_max_value(max_value)
        self._update_value(for_value)

    def _reset(self):
        self._current_value = 0
        self.n_times = 0
        self.started_time = None

    def start(self):
        if self.started:
            return
        self.started_time = time.time()
        self.started = True
        try:
            self.th_root.start()
        except:
            self.th_root.join()
            self.th_root = self._create_progress_service()
            self.th_root.start()
        self.console.persist_on_runtime()
        self.n_times = 0

    def stop(self):
        if self.started:
            self._awaiting_update = False
            self.started = False
            self.th_root.join()
            self.console.disable()

    def restart(self):
        self._reset()

    def __len__(self):
        return len(self._states)

    def __getitem__(self, slice_):
        if isinstance(slice_, tuple):
            if max(slice_) > len(self):
                raise IndexError(f"{max(slice_)} isn't in progress")
            return tuple(self._states[idx] for idx in slice_ if idx < len(self))
        if isinstance(slice_, str):
            key = self.__key_map[slice_]
            if key in self._states:
                slice_ = self._states.index(key)
            else:
                raise KeyError(f"Not exists {key}")
        return self._states[slice_]

    def __call__(self, sequence: Sequence, task_name=None) -> "ProgressBase":
        if not is_iterable(sequence):
            raise ValueError("Send a sequence.")
        self.update_max_value(len(sequence))
        self.sequence = sequence
        if task_name is not None:
            self.console.set_prefix(f"{self.name}({task_name})")
        if self._with_context and task_name is None:
            self.console.set_prefix(f"{self.name}(iter-{self.__task_count})")
        self.started_time = time.time()
        self.__task_count += 1
        return self

    def __next__(self):
        if not self._with_context:
            self.start()
        for n, obj in enumerate(self.sequence, start=1):
            self._update_value(n + 1)
            yield obj
        if not self._with_context:
            self.stop()
        self.console.set_prefix(self.name)
        self.sequence = ()

    def __iter__(self):
        return next(self)

    def __setitem__(self, key, value):
        value = self._valid_states(value)[0]
        if isinstance(value, State):
            value = value
            if isinstance(key, int):
                states_ = list(self._states)
                states_[key] = value
                self._states = tuple(states_)
        else:
            raise ValueError("Please send State object")

    def __enter__(self, *args, **kwargs):
        if hasattr(self, 'sequence'):
            raise ChildProcessError("Dont use progress instance on with statement.")
        self._with_context = True
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, Exception) and not isinstance(exc_val, DeprecationWarning):
            self.console.error(f'{os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}: {exc_val}')
        self.stop()
        self.__task_count = 0
        self._with_context = False


class Progress(ProgressBase):
    def __init__(self, name="Progress Tool", max_value=100, states=None, **kwargs):
        """
        Percentage calculation is based on max_value (default is 100) and current_value:
        percent = (current_value / max_value) * 100

        :param name: Defines the name to be displayed in progress
        :param max_value: This number represents the maximum amount you want to achieve.
                          It is not a percentage, although it is purposely set to 100 by default.
        """
        task_name = kwargs.get("task_name")
        style = kwargs.get("style")
        if task_name:
            name = task_name

        super().__init__(ConsoleBase(name, hook_error=self.hook_error), states=states)

        if max_value:
            self.max_value = max_value

        if style == "loading":
            self[0] = StateLoading

        self.set_name(name)

    @staticmethod
    def prog(sequence: Sequence[Any], style: str = "bar", task_name: str = "Cereja Progress") -> 'Progress':
        prog_ = Progress(task_name=task_name, style=style)
        return prog_(sequence)

    def update(self, current_value: Number, max_value=None):
        """
        --------------------- DEPRECATED ---------------------

        :param current_value: Fraction of the "max_value" you want to achieve.
                              Remember that this value is not necessarily the percentage.
                              It is totally dependent on the "max_value"
        :param max_value: This number represents the maximum amount you want to achieve.
                          It is not a percentage, although it is purposely set to 100 by default.
        """
        warnings.warn(f"Will be deprecated in future versions. Use 'update_max_value' or 'show_progress' methods.",
                      DeprecationWarning, 2)
        self.show_progress(current_value, max_value)

    def __del__(self):
        if (not self._with_context and self.started) or self.th_root.is_alive():
            self.stop()
        elif self.th_root.is_alive():
            self.stop()


if __name__ == "__main__":
    pass
