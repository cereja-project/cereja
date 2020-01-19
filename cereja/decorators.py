import functools
import time
from abc import abstractmethod
from typing import Callable, Any, Sequence, Union, List
import abc
import logging

logger = logging.getLogger(__name__)

__all__ = ['time_exec', 'valid_output_shape']


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


def valid_output_shape(func: Callable[[Sequence[Union[Any]]], Any]) -> Callable:
    # TODO: Fix import
    from .common import get_shape, is_sequence

    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> List[Union[float, Any]]:
        expected_shape = kwargs.get("shape") or args
        v = kwargs.get("v") or None
        if is_sequence(args):
            func_result = func(expected_shape, v=v)
        else:
            func_result = func(*args, **kwargs)
        shape = get_shape(func_result)
        assert shape == expected_shape, f"expected shape {shape} is different from the current {expected_shape}"
        return func_result

    return wrapper


if __name__ == '__main__':
    pass
