"""
High-level API for creating and manipulating files
"""
import os
from typing import Union, List, Iterator, Tuple

from cereja.path import get_base_dir
from cereja.display import Progress
import logging

from cereja.utils import invert_dict

logger = logging.Logger(__name__)

__all__ = []  # is'nt public https://www.python.org/dev/peps/pep-0008/#id50

_base_dir = get_base_dir(__file__)

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
DEFAULT_END_LINE = LF

_LINE_SEP_MAP = {
    CRLF: "CRLF",
    LF: "LF",
    CR: "CR",
    '': DEFAULT_END_LINE
}
_LINE_SEP_MAP.update(invert_dict(_LINE_SEP_MAP))


class FileBase(object):
    """
    High-level API for creating and manipulating files
    """

    _line_sep_map = _LINE_SEP_MAP.copy()
    _default_end_line = DEFAULT_END_LINE
    _dont_read = [".pyc",
                  ]

    def __init__(self, path_: str, content_lines: List[str]):
        self.path_ = path_
        self.__lines = content_lines
        if self.line_sep is '':
            self._apply_default_line_sep()

    def _parse_line_sep(self, _line_sep):
        _line_sep = self._line_sep_map.get(_line_sep)
        return '' if _line_sep is None else _line_sep

    def _apply_default_line_sep(self):
        self.__lines = list(map(lambda line: line + f'{self._default_end_line}', self.__lines))

    @property
    def path_(self):
        return self.__path

    @path_.setter
    def path_(self, p: str):
        self.__path = p

    @property
    def file_name(self):
        return os.path.basename(self.path_)

    @property
    def file_name_without_ext(self):
        return os.path.splitext(self.file_name)[0]

    @property
    def n_lines(self):
        return len(self.__lines)

    @property
    def is_empty(self):
        return not bool(self.n_lines)

    @property
    def dir_name(self):
        return os.path.dirname(self.path_)

    @property
    def is_link(self):
        return os.path.islink(self.path_)

    @property
    def content_str(self):
        return ''.join(self.__lines)

    @property
    def ext(self):
        return os.path.splitext(self.file_name)[-1]

    @property
    def line_sep(self):
        if self.is_empty:
            return self._parse_line_sep('')
        return self._parse_line_sep(self.__lines[0][-1])

    @property
    def content_lines(self):
        return self.__lines

    def _replace_file_sep(self, new):
        sep = self._line_sep_map[self.line_sep]
        self.__lines = self.content_str.replace(sep, new).splitlines(keepends=True)

    @classmethod
    def read(cls, path_: str, mode='r+', encoding='utf-8', **kwargs):
        file_name = os.path.basename(path_)
        ext = os.path.splitext(file_name)[-1]
        if ext in cls._dont_read:
            logger.warning(f"I can't read this file. See class attribute <{cls.__name__}._dont_read>")
            return
        try:
            with open(path_, mode=mode, encoding=encoding, newline='', **kwargs) as fp:
                lines = fp.readlines()
        except PermissionError as err:
            logger.error(err)
            return

        return cls(path_, lines)

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
                        except UnicodeDecodeError as err:
                            logger.error(f'Error reading the file {file_name}: {err}')
            yield os.path.basename(dir_name), len(files_), files_

    @classmethod
    def save(cls, path_: Union[str, None]):
        raise NotImplementedError

    def __str__(self):
        return f'{self.__class__.__name__}<{self.file_name}>'


class File(FileBase):

    def save(self, on_new_path: Union[os.PathLike, None] = None, encoding='utf-8', **kwargs):
        if on_new_path is not None:
            self.path_ = on_new_path
        with open(self.path_, 'w', newline='', encoding=encoding, **kwargs) as fp:
            fp.writelines(self.content_lines)
        return self

    def replace_file_sep(self, new, save: bool = True):
        new = self._parse_line_sep(new)
        if new is None:
            raise ValueError(f"{new} is'nt valid.")
        try:
            self._replace_file_sep(new)
            if save is True:
                self.save()
        except UnicodeDecodeError:
            logger.error(f'Not possibility convert {self.file_name}')
        return self


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


def convert_line_sep(path_: str, line_sep: str, ext_in: list = None):
    line_sep = _LINE_SEP_MAP.get(line_sep)

    if line_sep is None:
        raise ValueError(f"The value sent {line_sep} is not valid.")

    if os.path.isdir(path_):
        _walk_dirs_and_replace(path_, LF, ext_in)
    with Progress(f"Converting {os.path.basename(path_)}") as prog:
        File.read(path_).replace_file_sep(line_sep)


def crlf_to_lf(path_: str, ext_in: list = None):
    """
    :param path_:
    :param ext_in:
    :return:
    """
    convert_line_sep(path_, LF, ext_in=ext_in)


def lf_to_crlf(path_: str, ext_in: list = None):
    """
    :param path_:
    :param ext_in:
    :return:
    """
    convert_line_sep(path_, LF, ext_in=ext_in)


def to_lf(path_: str):
    convert_line_sep(path_, LF)


def to_cr(path_: str):
    convert_line_sep(path_, CR)


def to_crlf(path_: str):
    convert_line_sep(path_, CRLF)


def _auto_ident_py(path: str):
    pass


if __name__ == '__main__':
    # f = File('./test.py', ['for i in range(5):', "    print(i)"]).save()
    crlf_to_lf('../')

    pass
