import os

from cereja.path import get_base_dir
from cereja.display import Progress

__all__ = []  # is'nt public https://www.python.org/dev/peps/pep-0008/#id50

_base_dir = get_base_dir(__file__)


def _open_file(file_path: str, mode='r'):
    with open(file_path, mode) as f:
        lines = f.readlines()
        if mode == 'r':
            return lines


_line_sep = f"{os.linesep}"


def _replace_end_line(file_path: str, old, new):
    with open(file_path, 'r', encoding='utf-8') as fp:
        lines = ''.join(fp.readlines()).replace(old, new)
    with open(file_path, 'w+') as fp:
        fp.write(lines)

def _walk_dirs_and_replace(dir_path, old, new):
    for root_dir, _, files in os.walk(dir_path):
        with cj.Progress(root_dir) as prog:
            for file_ in files:
                file_path = os.path.join(root_dir, file_)
                _replace_end_line(file_path, old, new)

def crlf_to_lf(path_: str):
    """
    :param path_:
    :return:
    """
    _walk_dirs_and_replace(path_, '\r\n', '\n')

def lf_to_crlf(path_: str):
    """
    :param path_:
    :return:
    """
    _walk_dirs_and_replace(path_, '\n', '\r\n')


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
