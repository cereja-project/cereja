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
import tempfile
import time
from datetime import datetime
from typing import List, Union


from pathlib import Path as Path_
import glob
from ..utils.decorators import on_except

logger = logging.getLogger(__name__)

__all__ = [
    "Path",
    "change_date_from_path",
    "clean_dir",
    "file_name",
    "get_base_dir",
    "group_path_from_dir",
    "mkdir",
    "normalize_path",
    "TempDir",
]


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


def group_path_from_dir(
        dir_path: str,
        num_items_on_tuple: int,
        ext_file: str,
        to_random: bool = False,
        key_sort_function=None,
):
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
    from ..utils import chunk

    if "." not in ext_file:
        ext_file = "." + ext_file

    key_sort_function = {"key": key_sort_function} if key_sort_function else {}
    paths = sorted(
            [
                os.path.join(dir_path, i)
                for i in os.listdir(dir_path)
                if ext_file == os.path.splitext(i)[1]
            ],
            **key_sort_function,
    )


    batches = chunk(paths, batch_size=num_items_on_tuple)

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
        raise TypeError("Path must be a string")

    base_name = os.path.basename(file_path)
    if with_ext:
        return base_name
    f_name, _ = os.path.splitext(base_name)
    return f_name


def change_date_from_path(path_: str, format_: str = "%d-%m-%Y %H:%M:%S"):
    m_time = os.path.getctime(path_)
    return time.strftime(format_, time.localtime(m_time))


def get_base_dir(__file__: str) -> str:
    """
    :param __file__: send your __file__ string.
    :return: absolute path.
    """
    return os.path.normpath(os.path.dirname(os.path.abspath(__file__)))


def _norm_path(path_: str):
    return os.path.normpath(path_) if os.path.isabs(path_) else os.path.abspath(path_)


class Path(os.PathLike):
    _date_format = "%Y-%m-%d %H:%M:%S"
    __sep = os.sep
    _verified = set()

    def __init__(self, initial: Union[str, os.PathLike] = ".", *pathsegments: str):
        self.__path = Path_(_norm_path(str(initial)), *pathsegments)
        self.__parent = self.__path.parent.as_posix()
        self._parent_name = self.__path.parent.name
        self._verify()

    def __fspath__(self):
        return str(self.__path)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.path})"

    def __str__(self):
        return self.path

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            other = self.__class__(other)
        return self.path == other.path

    def __len__(self):
        return len(self.parts)

    def __contains__(self, item):
        return item in self.path

    def __add__(self, other):
        return self.join(*other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __getitem__(self, item):
        if item < 0:
            raise ValueError(f"index < 0 is not possible.")
        if isinstance(item, int):
            item = slice(item + 1)
        return self.__class__("/".join(self.parts[item]))

    def __value_err(self, details=""):
        if details:
            details = f"details {details}"
        raise ValueError(f"Path <{self.path}> isn't valid. {details}")

    def _verify(self):
        part = self.__path
        for i in range(len(self.__path.parts)):
            if str(part) in self._verified:
                return
            part_split = part.name.split(".")
            if part_split[-1] == ".":
                logger.info(
                        f"It is not common to use dot <{part.name}> in the end of name."
                )
                break
            if (part.suffix or part_split[-1] == ".") and i > 0:
                logger.info(
                        f"It is not common to use dot in the middle or end of directory name <{part.name}>"
                )
                break
            if len(part_split) > 2:
                logger.info(f"<{part.name}> has more dot than usual.")
            part = part.parent
        self._verified.add(str(self.__path.parent))

    @property
    def name(self):
        return self.__path.name

    @property
    @on_except(return_value=False, warn_text="Path is not valid.")
    def exists(self):
        return self.__path.exists()

    @property
    def path(self):
        return self.__path.as_posix()

    @property
    def stem(self):
        return self.__path.stem

    @property
    def prefix(self):
        return self.stem

    @property
    def suffix(self):
        if self.exists and self.__path.is_dir():
            # is a dir
            return ""
        return self.__path.suffix

    @property
    def ext(self):
        return self.suffix

    @property
    def root(self):
        return self.__path.anchor

    @property
    def parent(self):
        """
        :return: Parent PathInfo object
        """
        return self.__class__(self.__parent)

    @property
    def parent_name(self):
        return self._parent_name

    @property
    @on_except(return_value="", warn_text="Error on parser path in uri")
    def uri(self):
        return self.__path.as_uri()

    @property
    def is_dir(self):
        if self.exists:
            return self.__path.is_dir()
        else:
            return self.ext == ""

    @property
    def is_file(self):
        if self.exists:
            return self.__path.is_file()
        return self.ext != ""

    @property
    @on_except(return_value=False)
    def is_link(self):
        return self.__path.is_symlink()

    @property
    def updated_at(self):
        return (
            datetime.fromtimestamp(os.stat(str(self.path)).st_mtime).strftime(
                    self._date_format
            )
            if self.exists
            else None
        )

    @property
    def created_at(self):
        return (
            datetime.fromtimestamp(os.stat(str(self.path)).st_ctime).strftime(
                    self._date_format
            )
            if self.exists
            else None
        )

    @property
    def last_access(self):
        return (
            datetime.fromtimestamp(os.stat(str(self.path)).st_atime).strftime(
                    self._date_format
            )
            if self.exists
            else None
        )

    @property
    @on_except(return_value=False)
    def is_hidden(self):
        """
        In Unix-like operating systems, any file or folder that starts with a dot character
        (for example, /home/user/.config), commonly called a dot file or dotfile,is to be
        treated as hidden – that is, the ls command does not display them unless the -a
        flag ( ls -a ) is used.

        Return True if the name starts with dot or path contains one of the special names reserved
        by the system, if any.

        :return: bool
        """
        return self.name.startswith(".") or self.__path.is_reserved()

    @property
    def parts(self):
        return self.__path.parts

    @property
    def sep(self):
        return self.__sep

    @classmethod
    def work_dir(cls) -> "Path":
        """
        Get current working directory
        @return:
        """
        return cls(os.getcwd())

    @classmethod
    def set_work_dir(cls, to_):
        os.chdir(to_)

    def join(self, part, *others):
        assert (
                self.suffix == ""
        ), f"join operation is only dir. full path received {self.path}"
        if isinstance(part, str):
            args = (part, *others)
        else:
            args = (*part, *others)
        return self.__class__(
                self.__path.joinpath(*map(lambda p: p.lstrip("/\\"), args)).as_posix()
        )

    def _shutil(self, command: str, **kwargs):
        if not self.exists:
            raise Exception(f"Not Found <{self.uri}>")
        if command == "rm":
            rm_tree = kwargs.get("rm_tree")
            if self.is_file:
                os.remove(self.path)
                logger.info(f"<{self}> has been removed")
            else:
                if rm_tree is True:
                    shutil.rmtree(str(self))
                    logger.info(f"<{self}> has been removed")
                else:
                    try:
                        os.rmdir(str(self))
                    except OSError as err:
                        raise Exception(
                                f"{err}.\n Use rm_tree=True to DELETE {self.uri}."
                        )
        elif command == "mv":
            to = kwargs.get("to")
            return self.__class__(shutil.move(str(self), str(to)))
        elif command == "cp":
            to = kwargs.get("to")
            if self.is_dir:
                return self.__class__(shutil.copytree(str(self), str(to)))
            elif self.is_file:
                return self.__class__(shutil.copy(str(self), str(to)))

    def rm(self, rm_tree=False):
        """
        [!] Use caution when using this command. Only use if you are sure of what you are doing.

        If it is a directory you can DELETE the entire tree, for that flag `rm_tree=True`
        """
        return self._shutil("rm", rm_tree=rm_tree)

    def mv(self, to):
        to = self.__class__(to)
        return self._shutil("mv", to=to)

    def cp(self, to):
        to = self.__class__(to)
        return self._shutil("cp", to=to)

    def rsplit(self, sep=None, max_split=-1):
        return self.path.rsplit(sep, max_split)

    def split(self, sep=None, max_split=-1):
        return self.path.rsplit(sep, max_split)

    def list_dir(
            self, search_match="*", only_name=False, recursive=False
    ) -> List["Path"]:
        """
        Extension of the listdir function of module os.

        The difference is that by default it returns the absolute path, but you can still only request the relative
        path by setting only_relative_path to True.

        """
        assert isinstance(self, Path), f"{self} is not an instance of Path"
        if not self.is_dir:
            raise NotADirectoryError(f"check that the path '{self.path}' is correct")
        try:
            return [
                self.__class__(p).stem if only_name else self.__class__(p)
                for p in glob.glob(self.join(search_match).path, recursive=recursive)
            ]
        except PermissionError as err:
            logger.error(f"{err}")
            return []

    def list_files(
            self,
            ext: str = None,
            contains_in_name: List = (),
            not_contains_in_name=(),
            recursive=False,
            only_name=False,
            ignore_dirs=(),
    ) -> List["Path"]:
        """
        List files on an dir or in dir tree for this use recursive=True


        @param ext: filter by ext
        @param contains_in_name: filter only contains
        @param not_contains_in_name: filter only not contains
        @param recursive: for tree dir
        @param only_name: get only the name without extension if it is a file
        @param ignore_dirs: name list of prohibited directories
        @return: Path object list
        """
        assert isinstance(self, Path), f"{self} is not an instance of Path"
        ignore_dirs = (
            (ignore_dirs,) if isinstance(ignore_dirs, str) else tuple(ignore_dirs)
        )

        ext = ext or ""
        files = []
        for p in self.list_dir():
            try:
                if p.is_dir and recursive and p.name not in ignore_dirs:
                    _self = Path(p)  # because exceeded recursion Error
                    files.extend(
                            _self.list_files(
                                    ext=ext,
                                    contains_in_name=contains_in_name,
                                    not_contains_in_name=not_contains_in_name,
                                    recursive=recursive,
                                    only_name=only_name,
                                    ignore_dirs=ignore_dirs,
                            )
                    )
                    continue

                if not p.is_file:
                    continue
                if ext and p.suffix != f'.{ext.strip(".")}':
                    continue
                if not_contains_in_name:
                    if any(map(p.stem.__contains__, not_contains_in_name)):
                        continue
                if contains_in_name:
                    if not any(map(p.stem.__contains__, contains_in_name)):
                        continue
            except Exception as err:
                logger.error(err)
                continue
            files.append(p.stem if only_name else p)
        return files


class TempDir:
    def __init__(self, start_name="cj_", end_name="_temp", create_on=None):
        self._tmpdir = tempfile.TemporaryDirectory(
                suffix=end_name, prefix=start_name, dir=create_on
        )
        self._path = Path(self._tmpdir.name)

    def __del__(self):
        self.__delete()

    def __repr__(self):
        return f"{self.__class__.__name__}({self.path.path})"

    def __str__(self):
        return self.path.path

    def __delete(self):
        self._tmpdir.cleanup()

    def delete(self):
        self.__delete()

    @property
    def path(self):
        if self._path.exists:
            return self._path
        raise NotADirectoryError("Not Found.")

    @property
    def files(self):
        return self.path.list_files(recursive=True)

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__delete()


def normalize_path(path_: str) -> Path:
    return Path(path_)


def clean_dir(path_: str):
    """
    Delete all files on dir
    """
    content = Path(path_).list_dir()
    for p in content:
        p.rm(rm_tree=True)
    logger.info(f"{len(content)} files were removed")
