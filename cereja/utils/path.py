import os
import random
from typing import List

from cereja.utils.common import group_items_in_batches

__all__ = ['mkdir', 'group_path_from_dir', 'file_name', 'listdir']


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


def listdir(path: str, full_path: bool = True, ext: str = None) -> List[str]:
    return [os.path.join(path, p) if full_path else p for p in os.listdir(path) if os.path.splitext(p)[1] == ext]


if __name__ == '__main__':
    pass
