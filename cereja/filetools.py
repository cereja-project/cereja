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

import os
import warnings
from abc import ABCMeta, abstractmethod
from typing import Union, List, Iterator, Tuple, Sequence, Any

from cereja.arraytools import is_sequence, is_iterable
from cereja.display import Progress
import logging

from cereja.path import normalize_path
from cereja.utils import invert_dict
import copy

logger = logging.Logger(__name__)

_exclude = ["_auto_ident_py", "FileBase", "_walk_dirs_and_replace"]

"""
CRLF platforms:
Atari TOS, Microsoft Windows, DOS (MS-DOS, PC DOS, etc.), DEC TOPS-10, RT-11, CP/M, MP/M, OS/2,
Symbian OS, Palm OS, Amstrad CPC, and most other early non-Unix and non-IBM operating systems
"""
CRLF = '\r\n'
"""
LF platforms:
Multics, Unix and Unix-like systems (Linux, macOS, FreeBSD, AIX, Xenix, etc.), BeOS, Amiga, RISC OS, and others
"""
LF = '\n'
"""
CR platforms:
Commodore 8-bit machines (C64, C128), Acorn BBC, ZX Spectrum, TRS-80, Apple II series, Oberon,
the classic Mac OS, MIT Lisp Machine and OS-9
"""
CR = "\r"

# UNIX is DEFAULT
DEFAULT_NEW_LINE_SEP = LF

_NEW_LINE_SEP_MAP = {
    CRLF: "CRLF",
    LF:   "LF",
    CR:   "CR"
}
_STR_NEW_LINE_SEP_MAP = invert_dict(_NEW_LINE_SEP_MAP)


class FileBase(metaclass=ABCMeta):
    """
    High-level API for creating and manipulating files
    """
    __size_map = {"B":  1.e0,
                  "KB": 1.e3,
                  "MB": 1.e6,
                  "GB": 1.e9,
                  "TB": 1.e12
                  }

    _new_line_sep_map = _NEW_LINE_SEP_MAP.copy()
    _str_new_line_sep_map = _STR_NEW_LINE_SEP_MAP.copy()
    _default_new_line_sep = DEFAULT_NEW_LINE_SEP
    _dont_read = [".pyc"]
    _ignore_dir = [".git"]

    def __init__(self, path_: str, content_file: Union[Sequence, str, Any] = None):
        if content_file is None:
            content_file = []
        self.__path = normalize_path(path_)
        self._lines = self.normalize_data(content_file)
        if not self.is_empty:
            line_sep_ = self.parse_new_line_sep(content_file[0]) or self._default_new_line_sep
            self.set_new_line_sep(line_sep_)
        else:
            self._new_line_sep = self._default_new_line_sep
        self._current_change = 0
        self._max_history_length = 50
        self._change_history = []
        self._set_change('_lines', self.lines.copy())

    @classmethod
    def normalize_unix_line_sep(cls, content: str) -> str:
        return content.replace(cls._str_new_line_sep_map['CRLF'],
                               cls._default_new_line_sep).replace(cls._str_new_line_sep_map['CR'],
                                                                  cls._default_new_line_sep)

    def __setattr__(self, key, value):
        object.__setattr__(self, key, value)
        if hasattr(self, '_change_history') and key not in (
                '_current_change', '_max_history_length', '_change_history'):
            self._set_change(key, object.__getattribute__(self, key))  # append last_value of attr

    @property
    def history(self):
        return self._change_history

    def _set_change(self, key, value):
        self._change_history = self._change_history[:self._current_change + 1]
        if len(self._change_history) >= self._max_history_length:
            self._change_history.pop(0)
        self._change_history.append((key, value))
        self._current_change = len(self._change_history)

    def _select_change(self, index):
        try:

            key, value = self._change_history[self._current_change + index]
            object.__setattr__(self, key, copy.copy(value))
            self._current_change += index
            logger.warning(f'You selected amendment {self._current_change + 1}')
        except IndexError:
            logger.info("It's not possible")

    def undo(self):
        if self._current_change > 0:
            index = -2 if self._current_change == len(self._change_history) else -1
            self._select_change(index)

    def redo(self):
        if self._current_change < len(self._change_history):
            self._select_change(+1)

    @classmethod
    def normalize_data(cls, data: Any) -> Union[List[str], Any]:
        if not data:
            return data
        if is_iterable(data) or isinstance(data, int):
            if is_sequence(data) and not isinstance(data, int):
                data = [str(line).replace(CRLF, '').replace(CR, '').replace(LF, '') for line in data]
            elif isinstance(data, str):
                data = data.splitlines()
            elif isinstance(data, int):
                data = str(data)
            return data
        else:
            raise ValueError(f"{data} Invalid value. Send other ")

    @property
    def lines(self) -> List[str]:
        return self._lines

    @property
    def string(self) -> str:
        return f'{self._new_line_sep}'.join(self._lines)

    @property
    def content_str(self):
        warnings.warn(f"This property will be deprecated in future versions. "
                      "you can use property `File.string`", DeprecationWarning, 2)
        return f'{self._new_line_sep}'.join(self._lines)

    @property
    def content_file(self) -> List[str]:
        warnings.warn(f"This property will be deprecated in future versions. "
                      "you can use property `File.lines`", DeprecationWarning, 2)
        return self._lines

    @classmethod
    def parse_new_line_sep(cls, line: str) -> Union[str, None]:
        if is_iterable(line):
            for ln in cls._new_line_sep_map:
                if ln in line:
                    return ln

        if line in cls._str_new_line_sep_map:
            return cls._str_new_line_sep_map[line]
        return None

    @property
    def new_line_sep(self) -> str:
        return self._new_line_sep

    def set_new_line_sep(self, new_line_: str):
        self._new_line_sep = self.parse_new_line_sep(new_line_) or self._default_new_line_sep

    @property
    def new_line_sep_repr(self):
        return self._new_line_sep_map[self._new_line_sep]

    def set_path(self, path_):
        self.__path = normalize_path(path_)

    @property
    def path(self):
        return self.__path

    @property
    def file_name(self):
        return os.path.basename(self.__path)

    @property
    def file_name_without_ext(self):
        return os.path.splitext(self.file_name)[0]

    @property
    def n_lines(self):
        return len(self._lines)

    @property
    def is_empty(self):
        return not bool(self.n_lines)

    @property
    def dir_name(self):
        return os.path.basename(self.dir_path)

    @property
    def dir_path(self):
        return os.path.dirname(self.__path)

    @property
    def is_link(self):
        return os.path.islink(self.__path)

    @property
    def ext(self):
        return os.path.splitext(self.file_name)[-1]

    def size(self, unit: str = "KB"):
        """
        returns the size that the file occupies on the disk.

        :param unit: choose anyone in ('B', 'KB', 'MB', 'GB', 'TB')

        """
        assert isinstance(unit, str), f"expected {str.__name__} not {type(unit).__name__}."

        unit = unit.upper()

        assert unit in self.__size_map, f"{repr(unit)} is'nt valid. Choose anyone in {tuple(self.__size_map)}"

        return self.__sizeof__() / self.__size_map[unit]

    def __sizeof__(self):
        return self.string.__sizeof__() - ''.__sizeof__()  # subtracts the size of the python string object

    @classmethod
    def read(cls, path_: str, encoding='utf-8', **kwargs):
        path_ = normalize_path(path_)
        file_name = os.path.basename(path_)
        ext = os.path.splitext(file_name)[-1]
        if ext in cls._dont_read:
            logger.warning(f"I can't read this file. See class attribute <{cls.__name__}._dont_read>")
            return
        try:
            with open(path_, mode='r+', encoding=encoding, newline='', **kwargs) as fp:
                content = fp.read()
        except PermissionError as err:
            logger.error(err)
            return

        return cls(path_, content)

    @classmethod
    def replace_file_sep(cls, new, save: bool = True):
        raise NotImplementedError

    @classmethod
    def walk(cls, root_dir: str) -> Iterator[Tuple[str, int, list]]:
        """
        It works in a similar way to os.walk. With the difference that the File instance returns.
        :param root_dir: Root directory you want to start browsing
        :return:
        """
        for dir_name, _, files in os.walk(root_dir):
            files_ = []
            if files:
                for file_name in files:
                    file_path = os.path.join(dir_name, file_name)
                    if not os.path.islink(file_path):
                        try:
                            file_obj = cls.read(file_path)
                            if file_obj is not None:
                                files_.append(file_obj)
                        except Exception as err:
                            logger.error(f'Error reading the file {file_name}: {err}')
            yield os.path.basename(dir_name), len(files_), files_

    def insert(self, line: int, data: Union[Sequence, str, int]):
        data = self.normalize_data(data)
        if is_sequence(data):
            for pos, i in enumerate(data, line):
                self._lines.insert(pos, i)
        if isinstance(data, str):
            self._lines.insert(line, data)
        self._set_change('_lines', self._lines.copy())

    def remove(self, line: int):
        self._lines.pop(line)
        self._set_change('_lines', self._lines.copy())

    def _save(self, encoding='utf-8', **kwargs):
        with open(self.path, 'w', newline='', encoding=encoding, **kwargs) as fp:
            fp.write(self.string)

    @abstractmethod
    def save(self, path_: Union[str, None]):
        raise NotImplementedError

    def __str__(self):
        return f'{self.__class__.__name__}<{self.file_name}>'

    def __repr__(self):
        return f'{self.__str__()} {self.size(unit="KB")} KB'

    def __getitem__(self, item) -> str:
        return self._lines[item]

    def __setitem__(self, key, value):
        if isinstance(key, Tuple):
            raise ValueError("invalid assignment.")
        self.insert(key, value)

    def __iter__(self):
        for i in self._lines:
            yield i

    def __len__(self):
        return len(self._lines)


class File(FileBase):
    """
    High-level API for creating and manipulating files
    """

    def save(self, on_new_path: Union[os.PathLike, None] = None, encoding='utf-8', exist_ok=False, **kwargs):
        if on_new_path is not None:
            self.set_path(on_new_path)
        assert exist_ok or not os.path.exists(self.path), FileExistsError(
                "File exists. If you want override, please send 'exist_ok=True'")
        self._save(encoding, **kwargs)
        return self

    def replace_file_sep(self, new, save: bool = True):
        new = self.parse_new_line_sep(new)
        if new is None:
            raise ValueError(f"{new} is'nt valid.")
        try:
            self.set_new_line_sep(new)
            if save is True:
                self._save()
        except UnicodeDecodeError:
            logger.error(f'Not possibility convert {self.file_name}')
        return self


class _FilePython(File):
    def insert_license(self):
        pass


def _walk_dirs_and_replace(dir_path, new, ext_in: list = None):
    ext_in = ext_in or []
    with Progress(f"Looking to {dir_path}") as prog:
        for dir_name, n_files, files_obj in File.walk(dir_path):
            if files_obj:
                prog.update(1, n_files)
                for i, file_obj in enumerate(files_obj):
                    if file_obj.is_link or (ext_in and file_obj.ext not in ext_in):
                        continue
                    prog.task_name = f"Converting {dir_name} ({file_obj})"
                    file_obj.replace_file_sep(new)
                    prog.update(i)


def convert_new_line_sep(path_: str, line_sep: str, ext_in: list = None):
    line_sep = File.parse_new_line_sep(line_sep)

    if line_sep is None:
        raise ValueError(f"The value sent {line_sep} is not valid.")

    if os.path.isdir(path_):
        _walk_dirs_and_replace(path_, LF, ext_in)
    else:
        with Progress(f"Converting {os.path.basename(path_)}") as prog:
            File.read(path_).replace_file_sep(line_sep)


def crlf_to_lf(path_: str, ext_in: list = None):
    """
    :param path_:
    :param ext_in:
    :return:
    """
    convert_new_line_sep(path_, LF, ext_in=ext_in)


def lf_to_crlf(path_: str, ext_in: list = None):
    """
    :param path_:
    :param ext_in:
    :return:
    """
    convert_new_line_sep(path_, CRLF, ext_in=ext_in)


def to_lf(path_: str):
    convert_new_line_sep(path_, LF)


def to_cr(path_: str):
    convert_new_line_sep(path_, CR)


def to_crlf(path_: str):
    convert_new_line_sep(path_, CRLF)


def _auto_ident_py(path: str):
    pass


if __name__ == '__main__':
    pass
