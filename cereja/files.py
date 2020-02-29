import os

from cereja.path import get_base_dir
from cereja.display import Progress
import logging

logger = logging.Logger(__name__)

__all__ = []  # is'nt public https://www.python.org/dev/peps/pep-0008/#id50

_base_dir = get_base_dir(__file__)

CRLF = '\r\n'
LF = '\n'


def _open_file(file_path: str, mode='r'):
    with open(file_path, mode) as f:
        lines = f.readlines()
        if mode == 'r':
            return lines


_line_sep = f"{os.linesep}"


def _replace_end_line(file_path: str, old, new):
    try:
        with open(file_path, 'r') as fp:
            lines = ''.join(fp.readlines()).replace(old, new)
        with open(file_path, 'w+') as fp:
            fp.write(lines)
    except UnicodeDecodeError:
        logger.error(f'Not possibility convert {os.path.basename(file_path)}')


def _walk_dirs_and_replace(dir_path, old, new, ext_in: list = None):
    ext_in = ext_in or []
    for root_dir, _, files in os.walk(dir_path):
        if files:
            with Progress(f"Looking to {root_dir}", max_value=len(files)) as prog:
                for i, file_ in enumerate(files):
                    file_name, ext = os.path.splitext(file_)
                    if os.path.islink(file_) or (ext_in and ext not in ext_in):
                        continue
                    prog.task_name = f"Converting {root_dir} ({file_})"
                    file_path = os.path.join(root_dir, file_)
                    _replace_end_line(file_path, old, new)
                    prog.update(i)


def crlf_to_lf(path_: str, ext_in: list = None):
    """
    :param path_:
    :param ext_in:
    :return:
    """
    if os.path.isdir(path_):
        _walk_dirs_and_replace(path_, CRLF, LF, ext_in)
    else:
        with Progress(f"Converting {os.path.basename(path_)}") as prog:
            _replace_end_line(path_, CRLF, LF)


def lf_to_crlf(path_: str, ext_in: list = None):
    """
    :param path_:
    :param ext_in:
    :return:
    """
    if os.path.isdir(path_):
        _walk_dirs_and_replace(path_, LF, CRLF, ext_in)
    else:
        with Progress(f"Converting {os.path.basename(path_)}") as prog:
            _replace_end_line(path_, LF, CRLF)


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
    crlf_to_lf("/home/jlsneto/PycharmProjects/monorepo")
