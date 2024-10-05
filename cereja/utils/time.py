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
import threading
import time as _time
from typing import Callable

__all__ = ["Timer", "set_interval"]


class Timer:
    """
    A Timer class to manage time intervals and check if a specified interval has passed.

    Attributes:
        _interval (float): The time interval in seconds.
        _start (float): The start time in seconds since the epoch.
        _auto_reset (bool): Whether the timer should automatically reset after the interval has passed.
    """

    def __init__(self, interval, start=True, auto_reset=False):
        """
        Initialize the Timer.

        Args:
            interval (float): The time interval in seconds.
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

    def start(self):
        """
        Start the timer by setting the start time to the current time.
        """
        self._start = _time.time()

    @property
    def elapsed(self):
        """
        Get the elapsed time since the timer was started.

        Returns:
            float: The elapsed time in seconds.
        """
        return _time.time() - self._start

    @property
    def remaining(self):
        """
        Get the remaining time until the interval has passed.

        Returns:
            float: The remaining time in seconds.
        """
        return self._interval - self.elapsed

    @property
    def interval(self):
        """
        Get the time interval.

        Returns:
            float: The time interval in seconds.
        """
        return self._interval

    @interval.setter
    def interval(self, value):
        """
        Set the time interval.

        Args:
            value (float): The time interval in seconds.
        """
        self._interval = value

    @property
    def auto_reset(self):
        """
        Get the auto reset setting.

        Returns:
            bool: True if the timer automatically resets after the interval has passed, False otherwise.
        """
        return self._auto_reset

    @auto_reset.setter
    def auto_reset(self, value):
        """
        Set the auto reset setting.

        Args:
            value (bool): True to automatically reset the timer after the interval has passed, False otherwise.
        """
        self._auto_reset = value


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
