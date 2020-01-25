import os

from cereja.path import get_base_dir

__all__ = []  # is'nt public https://www.python.org/dev/peps/pep-0008/#id50

_base_dir = get_base_dir(__file__)


def _open_file(file_path: str, mode='r'):
    with open(file_path, mode) as f:
        lines = f.readlines()
        if mode == 'r':
            return lines


_line_sep = f"{os.linesep}"


def _crlf_to_lf(path: str):
    """
    use os.walk
    :param path:
    :return:
    """
    pass


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
