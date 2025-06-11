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
from typing import Iterable, Tuple, Union, NamedTuple, TypeVar, List, Generic, Any

"""
This module defines the types of variables, used for hint

see more PEP484 (Python Enhancement Proposals) :
https://www.python.org/dev/peps/pep-0484/
"""


def _f(*args,
       **kwargs):
    pass


class _C:
    pass


T_NUMBER = Union[int, float, complex]
VECT = Iterable[Tuple[T_NUMBER, T_NUMBER]]

T_FUNC = type(_f)
T_CLASS = type(_C)

T_PEP440 = Tuple[int, int, int, str, int]
T_SHAPE = Tuple[int, ...]

T_POINT = Tuple[T_NUMBER, T_NUMBER]


# T_RECT = Tuple[T_NUMBER, T_NUMBER, T_NUMBER, T_NUMBER]


class BaseField(NamedTuple):
    name: str
    value: Any
    hidden: bool = False


T_RECT = Tuple[T_NUMBER, T_NUMBER, T_NUMBER, T_NUMBER]


class RectField(BaseField):
    value: T_RECT = None


class Hotkey(NamedTuple):
    name: str
    key: str


T = TypeVar('T', bound=Hotkey)


class Hotkeys(Generic[T]):
    def __init__(self,
                 hotkeys: Union[Iterable[T], T]):
        if isinstance(hotkeys, Iterable):
            self._hotkeys = list(hotkeys)
        else:
            self._hotkeys = [hotkeys]

    def __iter__(self):
        return iter(self._hotkeys)

    def __getitem__(self,
                    index: int) -> T:
        return self._hotkeys[index]

    def __len__(self) -> int:
        return len(self._hotkeys)
