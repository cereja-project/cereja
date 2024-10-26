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
import math
import random
import threading
import time
import time as _time
from typing import Callable, Union

__all__ = ["Timer", "set_interval", "time_format", "RandomTimer", "TimeEstimate", "IntervalScheduler"]


class Timer:
    """
    A Timer class to manage time intervals and check if a specified interval has passed.

    Attributes:
        _interval (float): The time interval in seconds.
        _start (float): The start time in seconds since the epoch.
        _auto_reset (bool): Whether the timer should automatically reset after the interval has passed.
    """

    def __init__(self, interval=-1, start=True, auto_reset=False):
        """
        Initialize the Timer.

        Args:
            interval (float): The time interval in seconds, -1 means the timer has no stopping/reset condition.
            start (bool): Whether to start the timer immediately. Default is True.
            auto_reset (bool): Whether the timer should automatically reset after the interval has passed.
                               Default is False.
        """
        self._interval = interval
        self._start = 0
        if start:
            self.start()
        self._auto_reset = auto_reset

    def __bool__(self):
        """
        Check if the specified time interval has passed.

        Returns:
            bool: True if the interval has passed, False otherwise.
        """

        if self.elapsed >= self._interval:
            if self._auto_reset:
                self.start()
            return True
        return False

    def reset(self):
        self.start()

    def start(self):
        """
        Start the timer by setting the start time to the current time.
        """
        self._start = _time.time()

    @property
    def started(self) -> bool:
        return self._start > 0

    @property
    def elapsed(self):
        """
        Get the elapsed time since the timer was started.

        Returns:
            float: The elapsed time in seconds.
        """
        return _time.time() - self._start if self.started else 0

    @property
    def remaining(self):
        """
        Get the remaining time until the interval has passed.

        Returns:
            float: The remaining time in seconds.
        """
        return max(self._interval - self.elapsed, 0) if self._interval > 0 else float("inf")

    @property
    def interval(self):
        """
        Get the time interval.

        Returns:
            float: The time interval in seconds.
        """
        return self._interval

    @property
    def auto_reset(self):
        """
        Get the auto reset setting.

        Returns:
            bool: True if the timer automatically resets after the interval has passed, False otherwise.
        """
        return self._auto_reset

    @property
    def is_timeout(self):
        return bool(self)

    @property
    def time_overflow(self):

        return max(self.elapsed - self.interval, 0) if self._interval > 0 else 0

    def wait(self):
        """
        Wait until the timer interval has passed.
        """
        _time.sleep(self.remaining)

    def __str__(self):
        return time_format(self.elapsed)

    def __repr__(self):
        eta = "" if self._interval <= 0 else f", ETA={time_format(self.remaining)}"
        return f"Timer(elapsed={self.__str__()}{eta})"

    def iter_over(self, iterable):
        """
        Iterate over an iterable and wait until the timer interval has passed.
        @param iterable: An iterable object.
        @return: An iterator object.
        """
        for item in iterable:
            self.start()
            yield item
            self.wait()


class RandomTimer(Timer):
    def __init__(self, min_interval: float, max_interval: float, start=True, auto_reset=False):
        """
        Initialize the RandomTimer.

        Args:
            min_interval (float): The minimum time interval in seconds.
            max_interval (float): The maximum time interval in seconds.
            start (bool): Whether to start the timer immediately. Default is True.
            auto_reset (bool): Whether the timer should automatically reset after the interval has passed.
                               Default is False.
        """
        assert isinstance(min_interval, (int, float)), TypeError(f"{min_interval} isn't valid. Send a number!")
        assert isinstance(max_interval, (int, float)), TypeError(f"{max_interval} isn't valid. Send a number!")
        assert min_interval >= 0, ValueError("min_interval must be greater than or equal to 0")
        assert max_interval >= 0, ValueError("max_interval must be greater than or equal to 0")
        assert min_interval < max_interval, ValueError("min_interval must be less than max_interval")
        self._min_interval = min_interval
        self._max_interval = max_interval
        self._interval = self._random_interval()
        super(RandomTimer, self).__init__(self._interval, start, auto_reset)

    def _random_interval(self):
        return random.uniform(self._min_interval, self._max_interval)

    def reset(self):
        self._interval = self._random_interval()
        self.start()

    def start(self):
        self._interval = self._random_interval()
        super(RandomTimer, self).start()

    def __repr__(self):
        eta = "" if self._interval <= 0 else f", ETA={time_format(self.remaining)}"
        return f"RandomTimer(elapsed={self.__str__()}{eta})"


class TimeEstimate:
    def __init__(self, size: int = None):
        assert size is None or isinstance(size, (int, float)), TypeError(f"{size} isn't valid. Send a number!")
        self._timer = Timer(start=True)
        self._size = size or 0
        self._total_times = 0

    @property
    def total_times(self):
        return self._total_times

    @property
    def size(self):
        return self._size

    def set_time_it(self) -> float:
        self._total_times += 1
        return self._timer.elapsed

    @property
    def duration(self) -> float:
        return self._timer.elapsed

    @property
    def duration_formated(self) -> str:
        return time_format(self.duration)

    @property
    def eta(self):
        if self._total_times == 0 or self._size == 0:
            return float("inf")
        else:
            return max(((self._timer.elapsed / self._total_times) * self._size) - self._timer.elapsed, 0)

    @property
    def eta_formated(self):
        return time_format(self.eta)

    @property
    def per_sec(self):
        return math.ceil(self._total_times / max(self._timer.elapsed, 1))

    def __str__(self):
        return f"TimeEstimate(duration={self.duration_formated}, eta={self.eta_formated}, per_sec={self.per_sec})"

    def __repr__(self):
        return self.__str__()


class IntervalScheduler:
    """
    A class to schedule the periodic execution of a function using a separate thread.

    Attributes:
        func (Callable): The function to be executed periodically.
        interval (float): The time interval in seconds between each execution of the function.
        is_daemon (bool): Whether the thread should be a daemon thread. Daemon threads are terminated when the main program exits.
        thread (threading.Thread): The thread that runs the function periodically.
        _stop_event (threading.Event): An event used to signal the thread to stop execution.
    """

    def __init__(self, func: Callable, interval: float, is_daemon: bool = False):
        """
        Initialize the IntervalScheduler.

        Args:
            func (Callable): The function to be executed periodically.
            interval (float): The time interval in seconds between each execution of the function.
            is_daemon (bool): Whether the thread should be a daemon thread. Default is False.
        """
        self.func = func
        self.interval = interval
        self.is_daemon = is_daemon
        self.thread = None
        self._stop_event = threading.Event()

    def _run(self):
        """
        The internal method that runs the function periodically.
        """
        while not self._stop_event.is_set():
            self.func()
            _time.sleep(self.interval)

    def start(self):
        """
        Start the periodic execution of the function in a new thread.
        """
        if self.thread is None or not self.thread.is_alive():
            self._stop_event.clear()
            self.thread = threading.Thread(target=self._run, daemon=self.is_daemon)
            self.thread.start()

    def stop(self):
        """
        Stop the periodic execution of the function and wait for the thread to finish.
        """
        if self.thread is not None:
            self._stop_event.set()
            self.thread.join()

    def is_running(self):
        """
        Check if the thread is currently running.

        Returns:
            bool: True if the thread is running, False otherwise.
        """
        return self.thread is not None and self.thread.is_alive()


def set_interval(func: Callable, sec: float, is_daemon=False) -> IntervalScheduler:
    """
    Call a function every sec seconds
    @param func: function
    @param is_daemon: If True, the thread will be a daemon
    @param sec: seconds
    """
    scheduler = IntervalScheduler(func, sec, is_daemon)
    scheduler.start()
    return scheduler


def time_format(seconds: float, format_="%H:%M:%S") -> Union[str, float]:
    """
    Default format is '%H:%M:%S'
    If the time exceeds 24 hours, it will return a format like 'X days HH:MM:SS'

    >>> time_format(3600)
    '01:00:00'
    >>> time_format(90000)
    '1 days 01:00:00'

    """
    # Check if seconds is a valid number
    if seconds >= 0 or seconds < 0:
        # Calculate the absolute value of days
        days = int(seconds // 86400)
        # Format the time
        time_ = time.strftime(format_, time.gmtime(abs(seconds) % 86400))
        # Return with days if more than 24 hours
        if days > 0:
            return f"{days} days {time_}"
        # Return the formatted time
        if seconds < 0:
            return f"-{time_}"
        return time_
    return seconds  # Return NaN or any invalid input as it is


def set_timeout(func: Callable, sec: float, use_thread=False, *args, **kwargs):
    """
    Call a function after sec seconds
    @param func: function
    @param sec: seconds
    @param use_thread: If True, the function will be called in a new thread
    """
    if use_thread:
        threading.Timer(sec, func, args=args, kwargs=kwargs).start()
    else:
        time.sleep(sec)
        func(*args, **kwargs)