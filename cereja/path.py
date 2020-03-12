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

import logging
import os
import random
import shutil
import time
from typing import List
from cereja.arraytools import group_items_in_batches

logger = logging.getLogger(__name__)

__all__ = ['mkdir', 'group_path_from_dir', 'file_name', 'listdir', 'normalize_path']


def mkdir(path_dir: str):
    """
    Creates directory regardless of whether full cereja exists.
    If a nonexistent cereja is entered the function will create the full cereja until it creates the requested directory.
    e.g:
    original structure
    content/

    after create_dir(/content/cereja/to/my/dir)
    content/
        --cereja/
            --to/
                --my/
                    --dir/

    It's a recursive function

    :param path_dir: directory cereja
    :return: None
    """

    dir_name_path = os.path.dirname(path_dir)
    if not os.path.exists(dir_name_path):
        mkdir(dir_name_path)
    if not os.path.exists(path_dir):
        os.mkdir(path_dir)


def group_path_from_dir(dir_path: str, num_items_on_tuple: int, ext_file: str, to_random: bool = False,
                        key_sort_function=None):
    """
    returns data tuples based on the number of items entered for each tuple, follows the default order
    if no sort function is sent

    :param dir_path: full path to dir
    :param num_items_on_tuple: how much items have your tuple?
    :param ext_file: is file extension to scan
    :param to_random: randomize result
    :param key_sort_function: function order items
    :return:
    """

    if '.' not in ext_file:
        ext_file = '.' + ext_file

    key_sort_function = {"key": key_sort_function} if key_sort_function else {}
    paths = sorted([os.path.join(dir_path, i) for i in os.listdir(dir_path) if ext_file == os.path.splitext(i)[1]],
                   **key_sort_function)

    batches = group_items_in_batches(items=paths, items_per_batch=num_items_on_tuple)

    if to_random:
        random.shuffle(batches)
    return batches


def file_name(file_path: str, with_ext: bool = False) -> str:
    """
    Pass a path from a file and the file name will be returned

    >>> file_name('/content/myfile.ext')
    'myfile'
    >>> file_name(file_path='/content/myfile.ext', with_ext=True)
    'myfile.ext'

    :param file_path: string with file path
    :param with_ext: define if you want the file name with the extension
    :return: the file name
    """

    if not isinstance(file_path, str):
        raise TypeError('Path must be a string')

    base_name = os.path.basename(file_path)
    if with_ext:
        return base_name
    f_name, _ = os.path.splitext(base_name)
    return f_name


def change_date_from_path(path_: str, format_: str = '%d-%m-%Y %H:%M:%S'):
    m_time = os.path.getctime(path_)
    return time.strftime(format_, time.localtime(m_time))


def get_base_dir(__file__: str) -> str:
    """
    :param __file__: send your __file__ string.
    :return: absolute path.
    """
    return os.path.normpath(os.path.dirname(os.path.abspath(__file__)))


def listdir(path: str, only_relative_path: bool = False) -> List[str]:
    """
    Extension of the listdir function of module os.

    The difference is that by default it returns the absolute path, but you can still only request the relative path by
    setting only_relative_path to True.

    """
    return [os.path.join(path, p) if not only_relative_path else p for p in os.listdir(path)]


def _norm_path(path_: str):
    return os.path.normpath(path_) if os.path.isabs(path_) else os.path.abspath(path_)


def normalize_file_path(path_: str) -> str:
    path_ = _norm_path(path_)
    if not os.path.isfile(path_):
        raise ValueError(f"{path_} Is'nt File")
    return path_


def normalize_dir_path(path_: str) -> str:
    path_ = _norm_path(path_)
    if not os.path.isdir(path_):
        raise ValueError(f"{path_} Is'nt Dir")
    return path_


def normalize_path(path_: str, is_file: bool = None, is_dir: bool = None) -> str:
    if is_file is True:
        return normalize_file_path(path_)
    elif is_dir is True:
        return normalize_dir_path(path_)
    return _norm_path(path_)


def clean_dir(path_: str):
    """
    Delete all files on dir
    """
    content = listdir(path_)
    for p in content:
        shutil.rmtree(p)
    logger.info(f"{len(content)} files were removed")


if __name__ == '__main__':
    pass
