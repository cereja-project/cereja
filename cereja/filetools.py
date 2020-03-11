import os
from typing import Union, List

from cereja.path import get_base_dir
from cereja.display import Progress
import logging

from cereja.utils import invert_dict

logger = logging.Logger(__name__)

__all__ = []  # is'nt public https://www.python.org/dev/peps/pep-0008/#id50

_base_dir = get_base_dir(__file__)


class FileBase(object):
    CRLF = '\r\n'
    LF = '\n'
    CR = "\r"
    END_LINE = LF

    _line_sep_to_str = {
        CRLF: "CRLF",
        LF: "LF",
        CR: "CR"
    }

    _dont_read = [".pyc",
                  ]

    def __init__(self, path_: str, file_name, content_lines: List[str]):
        self._str_to_line_sep = invert_dict(self._line_sep_to_str)
        self.file_name = file_name
        self.path_ = path_
        self.__lines = content_lines

    def _parse_line_sep(self, _line_sep):
        _line_sep = self._line_sep_to_str.get(_line_sep) or self._str_to_line_sep.get(_line_sep)
        return '' if _line_sep is None else _line_sep

    @property
    def n_lines(self):
        return len(self.__lines)

    @property
    def is_empty(self):
        return bool(self.n_lines)

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
            return ''
        return self._parse_line_sep(self.__lines[0][-1])

    @property
    def content_lines(self):
        return self.__lines

    def _replace_file_sep(self, new):
        self.__lines = [line.replace(self.line_sep, new) for line in self.__lines]

    @classmethod
    def read(cls, path_: str, mode='r', encoding='utf-8', **kwargs):
        file_name = os.path.basename(path_)
        ext = os.path.splitext(file_name)[-1]
        if ext in cls._dont_read:
            logger.warning(f"I can't read this file. See class attribute <{cls.__name__}._dont_read>")
            return None
        with open(path_, mode=mode, encoding=encoding, **kwargs) as fp:
            lines = fp.readlines()

        return cls(path_, file_name, lines)

    @classmethod
    def walk(cls, root_dir):
        for dir_name, _, files in os.walk(root_dir):
            if files:
                for file_name in files:
                    file_path = os.path.join(dir_name, file_name)
                    if not os.path.islink(file_path):
                        try:
                            yield dir_name, cls.read(file_path)
                        except UnicodeDecodeError as err:
                            logger.error(err)

    @classmethod
    def save(cls, path_: Union[str, None]):
        raise NotImplementedError

    def __str__(self):
        return f'{self.__class__.__name__}<{self.file_name}>'


class File(FileBase):

    def save(self, path_: Union[str, None] = None, **kwargs):
        if self.line_sep is None: pass
        if path_ is not None:
            self.path_ = path_
        with open(self.path_, 'w+', **kwargs) as fp:
            fp.write(self.content_str)

    def replace_file_sep(self, new):
        new = self._parse_line_sep(new)
        if new is None:
            raise ValueError(f"{new} is'nt valid.")
        try:
            self._replace_file_sep(new)
            self.save()
        except UnicodeDecodeError:
            logger.error(f'Not possibility convert {self.file_name}')


def _walk_dirs_and_replace(dir_path, new, ext_in: list = None):
    ext_in = ext_in or []
    with Progress(f"Looking to {dir_path}") as prog:
        for i, (dir_name, file_obj) in enumerate(File.walk(dir_path)):
            if file_obj.is_link or (ext_in and file_obj.ext not in ext_in):
                continue
            prog.task_name = f"Converting {dir_name} ({file_obj})"
            file_obj.replace_file_sep(new)
            prog.update(i)


def crlf_to_lf(path_: str, ext_in: list = None):
    """
    :param path_:
    :param ext_in:
    :return:
    """
    if os.path.isdir(path_):
        _walk_dirs_and_replace(path_, File.LF, ext_in)
    else:
        with Progress(f"Converting {os.path.basename(path_)}") as prog:
            File.read(path_).replace_file_sep(File.LF)


def lf_to_crlf(path_: str, ext_in: list = None):
    """
    :param path_:
    :param ext_in:
    :return:
    """
    if os.path.isdir(path_):
        _walk_dirs_and_replace(path_, File.CRLF, ext_in)
    else:
        with Progress(f"Converting {os.path.basename(path_)}") as prog:
            File.read(path_).replace_file_sep(File.CRLF)


def _to_lf(path: str):
    pass


def _to_cr(path: str):
    pass


def _to_crlf(pat: str):
    pass


def _convert_line_sep(path_dir: str, name: str):
    pass


def _line_sep_from_file(path: str) -> str:
    pass


def _auto_ident_py(path: str):
    pass


if __name__ == '__main__':
    lf_to_crlf("/home/jlsneto/PycharmProjects/monorepo")
