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
from typing import Callable, Any
import abc
import logging
import warnings

__all__ = ['depreciation', 'synchronized', 'time_exec', 'sync_to_async', 'async_to_sync', 'thread_safe_generator',
           'singleton']

from cereja.concurrently import SyncToAsync, AsyncToSync
from cereja.config.cj_types import PEP440

logger = logging.getLogger(__name__)

# exclude from the root import
_exclude = ['BaseDecorator', 'Decorator', 'logger']


def synchronized(func):
    func.__lock__ = threading.Lock()

    def synced_func(*args, **kws):
        with func.__lock__:
            return func(*args, **kws)

    return synced_func


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


def time_exec(func: Callable[[Any], Any]) -> Callable:
    """
    Decorator used to signal or perform a particular function.

    :param func: Receives the function that will be executed as well as its parameters.
    :return
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        first_time = time.time()
        result = func(*args, **kwargs)
        logger.info(f"[{func.__name__}] performed {time.time() - first_time}")
        return result

    return wrapper


# Lowercase is more sensible for most things, and import_string is because Cyclic imports
sync_to_async = SyncToAsync
async_to_sync = AsyncToSync


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

    def __call__(self, alternative: str, from_version: PEP440 = None, more_info: str = None):
        logger.warning("[!] It's still under development [!]")
        if more_info is not None:
            more_info = f" {more_info}."
        else:
            more_info = ''
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
    alternative = f"You can use {alternative}" or "There is no alternative to this function"

    def register(func):
        def wrapper(*args, **kwargs):
            warnings.warn(f"This function will be deprecated in future versions. "
                          f"{alternative}", DeprecationWarning, 2)
            result = func(*args, **kwargs)
            return result

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
