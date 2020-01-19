import os

from cereja.path import get_base_dir

base_dir = get_base_dir(__file__)


def open_file(file_path: str, mode='r'):
    with open(file_path, mode) as f:
        lines = f.readlines()
        if mode == 'r':
            return lines


line_sep = f"{os.linesep}"


def crlf_to_lf(path: str):
    """
    use os.walk
    :param path:
    :return:
    """
    pass


def to_lf(path: str):
    pass


def to_cr(path: str):
    pass


def to_crlf(pat: str):
    pass


def convert_line_sep(path_dir: str, name: str):
    pass


def line_sep_from_file(path: str) -> str:
    pass


def auto_ident_py(path: str):
    pass
