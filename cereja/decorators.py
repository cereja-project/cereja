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
import sys
import time
from abc import abstractmethod
from typing import Callable, Any
import abc
import logging

from cereja import utils
__all__ = ['time_exec']
logger = logging.getLogger(__name__)

# exclude from the root import
_exclude = ['BaseDecorator', 'Decorator', 'logger']


class BaseDecorator(abc.ABC):
    def __init__(self):
        self.func = None

    def register(self, name, wrapper):
        setattr(self, name, wrapper)
        return self.__getattribute__(name)

    @abstractmethod
    def wrapper(self, *args, **kwargs):
        return self.func(*args, **kwargs)


class Decorator(BaseDecorator):
    def wrapper(self, *args, **kwargs):
        result = super().wrapper(*args, **kwargs)
        return result


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
sync_to_async = utils.import_string('cereja.concurrently.SyncToAsync')
async_to_sync = utils.import_string('cereja.concurrently.AsyncToSync')
