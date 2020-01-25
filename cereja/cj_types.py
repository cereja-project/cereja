from typing import *


def _f(*args, **kwargs): pass


Function = type(_f)

T = Union[int, float, str]
Number = Union[float, int, complex]
PEP440 = Tuple[int, int, int, str, int]
