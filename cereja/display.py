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
from cereja.cj_types import Number

__all__ = 'Progress'

if sys.platform.lower() == "win32":
    os.system('color')


class ConsoleBase(object):
    CL_DEFAULT = '\033[30m'
    CL_RED = '\033[31m'
    CL_GREEN = '\033[32m'
    CL_YELLOW = '\033[33m'
    CL_BLUE = '\033[34m'
    CL_MAGENTA = '\033[35m'
    CL_CYAN = '\033[36m'
    CL_WHITE = '\033[37m'
    CL_UNDERLINE = '\033[4m'

    __text_color = CL_DEFAULT
    __stdout_original = sys.stdout
    __stderr_original = sys.stderr
    __right_point = f"{CL_CYAN}\U000000bb{__text_color}"
    __msg_prefix = f"{CL_RED}\U0001F352{__text_color}"

    def __init__(self, text_color=CL_DEFAULT):
        self.__text_color = text_color
        self.__stdout_buffer = io.StringIO()
        self.__stderr_buffer = io.StringIO()

    def __bg(self, text_, color):
        return f"\33[48;5;{color}m{text_}{self.__text_color}"

    def text_bg(self, text_, color):
        return self.__bg(text_, color)

    def __msg_parse(self, msg: str, title=None):
        return f"{self.__msg_prefix}{self.__text_color} {title or ''} {self.__right_point} {msg}"

    def log(self, msg, title="Cereja"):
        msg = self.__msg_parse(msg, )
        self.__stdout_original.write(msg)
        self.__stdout_original.write('\u001b[0m')
        self.__stdout_original.flush()


class Progress(object):
    """
    Percentage calculation is based on max_value (default is 100) and current_value:
    percent = (current_value / max_value) * 100

    :param style: defines the type of progress that will be used. "loading" is Default

    :param task_name: Defines the name to be displayed in progress

    :param max_value: This number represents the maximum amount you want to achieve.
                      It is not a percentage, although it is purposely set to 100 by default.
    :param kwargs:
            loading_with_clock: You will see a clock if the style is loading
    """
    NON_BMP_MAP = dict.fromkeys(range(0x10000, sys.maxunicode + 1), 0xfffd)
    DONE_UNICODE = "\U00002705"
    ERROR_UNICODE = "\U0000274C"
    CLOCKS_UNICODE = ("\U0001F55C", "\U0001F55D", "\U0001F55E", "\U0001F55F", "\U0001F560", "\U0001F561", "\U0001F562",
                      "\U0001F563", "\U0001F564", "\U0001F565", "\U0001F566", "\U0001F567")
    CHERRY_UNICODE = "\U0001F352"
    RIGHT_POINTER = "\U000000bb"
    __stdout_original = sys.__stdout__
    __stderr_original = sys.__stderr__

    def __init__(self, task_name="Progress Tool", style="loading", max_value=100, **kwargs):
        self._style = style
        self.__error = False
        self.__stdout_buffer = None
        self.__stderr_buffer = None
        self.__sleep_time = 0.5
        self.max_value = max_value
        self._default_loading_symb = "."
        self._default_bar_symb = "="
        self.current_value = 0
        self._finish = False
        self._started = False
        self._last_percent = None
        self._n_times = 0
        self._max_loading_symb = 3
        self._bar_size = kwargs.get('bar_size', 30)
        self._bar = ' ' * self._bar_size
        custom_loading_seq = kwargs.get("custom_loading_seq", [])
        if not isinstance(custom_loading_seq, list):
            raise TypeError("Please send unicode list.")
        self._unicode_sequence = custom_loading_seq or self.CLOCKS_UNICODE
        self.__use_sequence = bool(kwargs.get("loading_with_clock") or custom_loading_seq)  # loading is default
        self.task_name = task_name
        self.first_time = time.time()
        self.buffer = bool(kwargs.get("buffer", True))

        # This is important, as there may be an exception if the terminal does not support unicode bmp
        try:
            sys.stdout.write(f"{self.CHERRY_UNICODE} {self.task_name}: Created!")
            self.non_bmp_supported = True
        except UnicodeEncodeError:
            self.non_bmp_supported = False

        if self.buffer:
            self._setup_buffer()

    def _setup_buffer(self):
        if self.buffer:
            self.__stdout_buffer = io.StringIO()
            self.__stderr_buffer = io.StringIO()
        sys.stdout = self.__stdout_buffer
        sys.stderr = self.__stderr_buffer

    def __parse(self, msg: str):
        """
        This is important, as there may be an exception if the terminal does not support unicode bmp
        """
        if self.non_bmp_supported:
            return msg
        return msg.translate(self.NON_BMP_MAP)

    def __send_msg(self, msg):
        writer = self.__stderr_original.write if self.__error else self.__stdout_original.write
        writer(f'\r{self.__parse(msg)}')

    def _time(self):
        self.__send_msg(time.time() - self.first_time)
        return f"Time: {round((time.time() - self.first_time) - self.__sleep_time, 2)}s"

    def _default_loading(self):
        self._n_times += 1
        if self._n_times > self._max_loading_symb:
            self._n_times = 0
        n_blanks = ' ' * (self._max_loading_symb - self._n_times)
        if self._finish:
            return self._default_loading_symb * self._max_loading_symb
        return (self._default_loading_symb * self._n_times) + n_blanks

    def _loading_progress_in_seq(self):
        self._n_times += 1
        if len(self._unicode_sequence) == self._n_times:
            self._n_times = 0
        return self._unicode_sequence[self._n_times - 1]

    def _loading_progress(self):
        return self._loading_progress_in_seq() if self.__use_sequence else self._default_loading()

    def _bar_progress(self):
        if self._current_percent != self._last_percent:
            self._last_percent = self._current_percent
        current_bar_value = int((self._bar_size / 100) * self._current_percent)
        return self._bar.replace(' ', self._default_bar_symb, current_bar_value).replace(' ', '>',
                                                                                         1)

    def _display(self):
        if self._style == 'bar':
            return self._bar_progress()
        return self._loading_progress_in_seq() if self.__use_sequence else self._loading_progress()

    def _current_value_info(self):
        if self._finish:
            error_msg = f"Error: {self.__error} {self.ERROR_UNICODE} - {self._time()}"
            done_msg = f"Done! {self.DONE_UNICODE} - {self._time()}"
            return error_msg if self.__error else done_msg
        if self._current_percent == 0:
            return ''
        return f"{self._current_percent}%"

    def _write(self):
        if self._current_percent == 0:
            self.__send_msg(
                f"{self.CHERRY_UNICODE} {self.task_name}: Awaiting {self._loading_progress()} {self._current_value_info()}")
        else:
            self.__send_msg(f"{self.CHERRY_UNICODE} {self.task_name}: [{self._display()}] {self._current_value_info()}")
        self._last_percent = self._current_percent

    def _looping(self):
        """
        Used by the thread. Checks and shows current progress
        """
        while not self._finish:
            self._write()
            time.sleep(self.__sleep_time)
        if not self.__error:
            self.current_value = self.__max_value
        self._write()

    def start(self, task_name: str = None):
        """
        Start progress task, you will need to use this method if it does not run with the "with statement"
        :param task_name: Defines the name to be displayed in progress
        """
        self.first_time = time.time()
        if task_name is not None:
            self.task_name = task_name
        if not self._started:
            self._current_percent = 0
            self.__enter__()

    def stop(self):
        """
        Stop the current task.
        This is necessary because the task is running on a separate thread.

        If you are not using with statement it is extremely important to call this method at the end,
        otherwise the thread will never die. Unless it ends the runtime.
        """
        self._finish = True
        self._started = False
        self.th.join()
        self.__send_msg('\n')

    def _reload(self):
        """
        Intermediate that calls stop and start in sequence
        """
        self.stop()
        self.start()

    @property
    def current_value(self):
        return self.__current_value

    @current_value.setter
    def current_value(self, value):
        self._current_percent = round((value / self.max_value) * 100, 2)
        self.__current_value = value

    @property
    def max_value(self):
        return self.__max_value

    @max_value.setter
    def max_value(self, value: Number):
        """
        :param value: This number represents the maximum amount you want to achieve.
                  It is not a percentage, although it is purposely set to 100 by default.
        :param value:
        :return:
        """
        if value is not None:
            if isinstance(value, (int, float, complex)) and value > 0:
                self.__max_value = value
            else:
                raise Exception("Send Number.")

    def update(self, current_value: float, max_value=None):
        """

        :param current_value: Fraction of the "max_value" you want to achieve.
                              Remember that this value is not necessarily the percentage.
                              It is totally dependent on the "max_value"
        :param max_value: This number represents the maximum amount you want to achieve.
                          It is not a percentage, although it is purposely set to 100 by default.
        """

        if max_value is not None:
            if max_value != self.max_value:
                self._reload()
        self.max_value = max_value
        self.current_value = current_value

    def display_only_once(self, current_value: float = None):
        """
        In case you need to show the bar only once. This method will cause the code to be executed on the main thread
        :param current_value:
        :return:
        """
        if current_value is not None:
            self.update(current_value)
        self._write()

    @classmethod
    def decorator(cls, func):
        def wrapper(*args, **kwargs):
            with cls(f"{func.__name__}"):
                result = func(*args, **kwargs)
            return result

        return wrapper

    @classmethod
    def bar(cls, iterator_):
        with cls("Cereja Bar", style="bar", max_value=len(iterator_)) as bar_:
            for n, value in enumerate(iterator_):
                bar_.update(n)
                yield value

    def __enter__(self):
        """
        intern method used by "with st
        :return:
        """
        self._finish = False
        self._started = True
        self.th = threading.Thread(name=self.task_name, target=self._looping)
        self.th.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if isinstance(exc_val, Exception):
            self.__error = f'{os.path.basename(exc_tb.tb_frame.f_code.co_filename)}:{exc_tb.tb_lineno}: {exc_val}'
        self._finish = True
        self._started = False
        self.th.join()
        self.__send_msg('\n')
        if self.buffer:
            output = sys.stdout.getvalue()
            error = sys.stderr.getvalue()
            self.__stdout_buffer.seek(0)
            self.__stdout_buffer.truncate()
            self.__stderr_buffer.seek(0)
            self.__stderr_buffer.truncate()
            print(output)
            print(error)
        sys.stdout = self.__stdout_original
        sys.stderr = self.__stderr_original
        if self.__error:
            sys.exit()


if __name__ == '__main__':
    # console = ConsoleBase(text_color=ConsoleBase.CL_BLUE)
    # console.log("oi", title="Test")
    for i in Progress.bar(range(90000)):
        print(i)
    # with Progress(task_name="Progress Bar Test", style="bar", max_value=100) as bar:
    #     for i in range(1, 100):
    #         time.sleep(1 / i)
    #         bar.update(i)
    #         print('oi')
    #
    #     for i in range(1, 400):
    #         time.sleep(1 / i)
    #         bar.update(i, max_value=400)
