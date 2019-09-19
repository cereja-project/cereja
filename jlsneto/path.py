import os
import random

from jlsneto.utils import group_items_in_batches


def mkdir(path_dir: str):
    """
    Creates directory regardless of whether full jlsneto exists.
    If a nonexistent jlsneto is entered the function will create the full jlsneto until it creates the requested directory.
    e.g:
    original structure
    content/

    after create_dir(/content/jlsneto/to/my/dir)
    content/
        --jlsneto/
            --to/
                --my/
                    --dir/

    It's a recursive function

    :param path_dir: directory jlsneto
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
    key_sort_function = {"key": key_sort_function} if key_sort_function else {}
    paths = sorted([os.path.join(dir_path, i) for i in os.listdir(dir_path) if ext_file in i], **key_sort_function)

    batches = group_items_in_batches(items=paths, items_per_batch=num_items_on_tuple)

    if to_random:
        random.shuffle(batches)
    return batches


if __name__ == '__main__':
    pass
