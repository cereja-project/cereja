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

import sys
import logging
from abc import abstractmethod, ABCMeta
import os

__all__ = ['BasicConfig', 'BASE_DIR']

# using by utils.module_references
_exclude = ["console_logger", "cj_modules_dotted_path"]

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BasicConfig(metaclass=ABCMeta):
    def __init__(self, hook=None, **kwargs):
        self._fields = ()
        self._listen = hook
        self.set_config(**kwargs)

    def __repr__(self):
        return f'{self.__class__.__name__}({self.get()})'

    def __setattr__(self, key, value):
        if hasattr(self, '_locked'):
            if self._locked is True:
                er = 'This is a critical config. You can use <set_config> method.'
                raise ValueError(er)
        super().__setattr__(key, value)

    def __unlock(self):
        super().__setattr__('_locked', False)

    def __lock(self):
        self._fields = tuple(self.get().keys())
        super().__setattr__('_locked', True)

    def set_config(self, **kwargs) -> None:
        self._before(kwargs)
        self.__unlock()
        for k, i in kwargs.items():
            self.__setattr__(k, i)
        self.__lock()
        if self._listen is not None:
            self._listen()

    @abstractmethod
    def _before(self, new_config: dict):
        for k in new_config:
            if k not in self._fields and self._fields:
                raise ValueError(f"<{k}> not in config attrs {self._fields}")

    def get(self, item=None):
        config = {}
        if item is None:
            for attr_ in dir(self):
                if attr_.startswith('_'):
                    continue
                obj = self.__getattribute__(attr_)
                if callable(obj):
                    continue
                config[attr_] = obj
            return config
        if hasattr(self, item):
            obj = self.__getattribute__(item)
            if not callable(obj):
                return obj
        return {}


# Used to add the functions of each module at the root
cj_modules_dotted_path = ['cereja.array', 'cereja.conf', 'cereja.decorators', 'cereja.path',
                          'cereja.utils', 'cereja.concurrently', 'cereja.display', 'cereja.filetools', 'cereja.unicode',
                          'cereja.datatools.split_data', 'cereja.datatools.pln', 'cereja.datatools.data']

console_logger = logging.StreamHandler(sys.stdout)
logging.basicConfig(handlers=(console_logger,), level=logging.WARNING)
