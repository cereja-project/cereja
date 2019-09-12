import os
import random


def mkdir(path_dir: str):
    """
    Creates directory regardless of whether full path exists.
    If a nonexistent path is entered the function will create the full path until it creates the requested directory.
    e.g:
    original structure
    content/

    after create_dir(/content/path/to/my/dir)
    content/
        --path/
            --to/
                --my/
                    --dir/

    It's a recursive function

    :param path_dir: directory path
    :return: None
    """

    dir_name_path = os.path.dirname(path_dir)
    if not os.path.exists(dir_name_path):
        mkdir(dir_name_path)
    if not os.path.exists(path_dir):
        os.mkdir(path_dir)


def tuples_from_dir(dir_path: str, num_items_on_tuple: int, ext_file: str, to_random=False, key_sort_function=None):
    """
    returns data tuples based on the number of items entered for each tuple, follows the default order
    if no sort function is sent

    :param dir_path:
    :param num_items_on_tuple:
    :param ext_file:
    :param to_random:
    :param key_sort_function:
    :return:
    """
    key_sort_function = {"key": key_sort_function} or {}
    paths = sorted([i for i in os.listdir(dir_path) if ext_file in i], **key_sort_function)

    tuples = []

    for i in range(0, len(paths), num_items_on_tuple):
        tuples.append((os.path.join(dir_path, p) for p in paths[i:i + num_items_on_tuple]))

    if to_random:
        random.shuffle(tuples)
    return tuples
