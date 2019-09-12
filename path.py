import os


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
