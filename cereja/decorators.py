import functools
import sys
import time
from abc import abstractmethod
from typing import Callable, Any
import abc
import logging

from cereja import utils
from cereja.arraytools import rand_n

__all__ = ['time_exec']
logger = logging.getLogger(__name__)

# exclude from the root import
_explicit_exclude = ['BaseDecorator', 'Decorator', 'logger']


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
