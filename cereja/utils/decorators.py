import time
from typing import Callable, Any

from cereja.utils.common import logger

__all__ = ['time_exec']


def time_exec(func: Callable[[Any], Any]) -> Any:
    """
    Decorator used to signal or perform a particular function.

    :param func: Receives the function that will be executed as well as its parameters.
    :return
    """

    def wrapper(*args, **kwargs):
        first_time = time.time()
        result = func(*args, **kwargs)
        logger.info(f"[{func.__name__}] performed {time.time() - first_time}")
        return result

    return wrapper


if __name__ == '__main__':
    pass
