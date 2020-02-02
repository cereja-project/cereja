"""
This module defines the types of variables, used for hint

see more PEP484 (Python Enhancement Proposals) :
https://www.python.org/dev/peps/pep-0484/
"""
from typing import TypeVar, Iterable, Tuple


def _f(*args, **kwargs): pass


T_number = TypeVar('T_number', int, float, complex)  # Number type
Vector = Iterable[Tuple[T_number, T_number]]

Function = type(_f)

Number = T_number
PEP440 = Tuple[int, int, int, str, int]
Shape = Tuple[int, ...]
