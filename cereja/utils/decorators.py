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

import functools
import threading
import time
from abc import abstractmethod
import abc
import logging
import warnings
import random

__all__ = [
    "depreciation",
    "synchronized",
    "thread_safe_generator",
    "singleton",
    "on_except",
    "use_thread",
    "retry_on_failure",
]

from typing import Callable, Any

from ..config.cj_types import PEP440

logger = logging.getLogger(__name__)

# exclude from the root import
_exclude = ["BaseDecorator", "Decorator", "logger"]


def synchronized(func):
    func.__lock__ = threading.Lock()

    def synced_func(*args, **kws):
        with func.__lock__:
            return func(*args, **kws)

    return synced_func


def use_thread(func):
    def threaded_func(*args, **kws):
        th = threading.Thread(target=func, args=args, kwargs=kws)
        th.start()
        return th

    return threaded_func


class _ThreadSafeIterator:
    def __init__(self, iterator):
        self.iterator = iterator
        self.lock = threading.Lock()

    def __iter__(self):
        return self

    def __next__(self):
        with self.lock:
            return next(self.iterator)


def thread_safe_generator(func):
    def gen(*a, **kw):
        return _ThreadSafeIterator(func(*a, **kw))

    return gen


class Decorator(abc.ABC):
    def __init__(self):
        self.func = None

    @abstractmethod
    def __call__(self, *args, **kwargs):
        """
        You can override and
        :param args:
        :param kwargs:
        :return:
        """
        return self._register

    def _register(self, func):
        self.func = func
        return self.wrapper

    @abstractmethod
    def wrapper(self, *args, **kwargs):
        return self.func(*args, **kwargs)


class __Deprecated(Decorator):
    __warn = "This function will be deprecated in future versions"
    __alternative_template = "You can use {dotted_path}."

    def __call__(
            self, alternative: str, from_version: PEP440 = None, more_info: str = None
    ):
        logger.warning("[!] It's still under development [!]")
        if more_info is not None:
            more_info = f" {more_info}."
        else:
            more_info = ""
        self.warn = f"{self.__warn}. {self.__alternative_template.format(dotted_path=alternative)}{more_info}"
        self.from_version = from_version
        return super().__call__()

    def wrapper(self, *args, **kwargs):
        warnings.warn(self.warn, DeprecationWarning)
        result = super().wrapper(*args, **kwargs)
        return result


__deprecated = __Deprecated()


# Function version
def depreciation(alternative: str = None):
    alternative = (
            f"You can use {alternative}" or "There is no alternative to this function"
    )

    def register(func):
        def wrapper(*args, **kwargs):
            warnings.warn(
                    f"This function will be deprecated in future versions. "
                    f"{alternative}",
                    DeprecationWarning,
                    2,
            )
            result = func(*args, **kwargs)
            return result

        return wrapper

    return register


def on_except(return_value=None, warn_text=None):
    def register(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if warn_text:
                    warnings.warn(f"{e}: {warn_text}")
                return return_value

        return wrapper

    return register


def retry_on_failure(retries: int = 3, initial_delay: float = 0.1, backoff_factor=2, exceptions: tuple = (Exception,),
                     verbose: bool = False):
    def register(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt < retries - 1:
                        if verbose:
                            warnings.warn(f"Retry {attempt + 1} of {retries}: {e}")
                        delay *= backoff_factor * (1 + random.random())
                        time.sleep(delay)
                    else:
                        raise e

        return wrapper

    return register


def singleton(cls):
    instances = {}

    @functools.wraps(cls)
    def instance(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return instance


def time_exec(func: Callable[[Any], Any]) -> Callable:
    """
    Decorator used to signal or perform a particular function.

    :param func: Receives the function that will be executed as well as its parameters.
    :return: Returns the function that will be executed.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        from cereja import console
        first_time = time.time()
        result = func(*args, **kwargs)
        console.log(f"[{func.__name__}] performed {time.time() - first_time}")
        return result

    return wrapper


def on_elapsed(interval: float = 1,
               loop: bool = False,
               use_threading: bool = False,
               verbose: bool = False,
               is_daemon: bool = False,
               take_last=False,
               default=None):
    """
    Run a function if the interval has elapsed

    @param interval: Interval in seconds
    @param loop: If True, the function will be executed in a loop
    @param verbose: If True, the function name will be printed
    @param use_threading: If True, the function will be executed in a thread
    @param is_daemon: If True, the thread will be a daemon
    @param take_last: If the time has not run out, it stores and returns the last result of the function execution,
                      if the function returns anything.
    @param default: return it if the time has not run out

    """

    def decorator(func: Callable):
        last_time = 0.0
        last_result = None

        def wrapper(*args, **kwargs):
            nonlocal last_time
            nonlocal last_result
            if loop:
                def run():
                    nonlocal last_time
                    while True:
                        current_time = time.time()
                        if current_time - last_time >= interval:
                            if verbose:
                                print(f"Running {func.__name__}")
                            last_time = current_time
                            func(*args, **kwargs)

                if use_threading:
                    import threading
                    th = threading.Thread(target=run, daemon=is_daemon)
                    th.start()
                    return th
                else:
                    run()
            else:
                def run():
                    nonlocal last_time
                    nonlocal last_result
                    current_time = time.time()
                    if current_time - last_time >= interval:
                        if verbose:
                            print(f"Running {func.__name__}")
                        last_time = current_time
                        if take_last:
                            last_result = func(*args, **kwargs)
                        else:
                            return func(*args, **kwargs)
                    return default or last_result

                if use_threading:
                    import threading
                    th = threading.Thread(target=run, daemon=is_daemon)
                    th.start()
                    return th
                else:
                    return run()

        return wrapper

    return decorator
