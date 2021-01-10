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
import ast
import json
import os
import warnings
from abc import ABCMeta
from typing import Union, List, Iterator, Tuple, Sequence, Any

from cereja.array import is_sequence, is_iterable, get_cols, flatten, get_shape
from cereja.display import Progress
import logging

from cereja.system.path import normalize_path, Path
from cereja.utils import invert_dict
import copy
import csv
from datetime import datetime
from base64 import b64encode

__all__ = ['TxtFile', "CsvFile", "JsonFile", "File"]
logger = logging.Logger(__name__)

_exclude = ["_auto_ident_py", "FileBase", "_walk_dirs_and_replace"]

"""
CRLF platforms:
Atari TOS, Microsoft Windows, DOS (MS-DOS, PC DOS, etc.), DEC TOPS-10, RT-11, CP/M, MP/M, OS/2,
Symbian OS, Palm OS, Amstrad CPC, and most other early non-Unix and non-IBM operating systems
"""
CRLF = '\r\n'
"""
LF platforms:
Multics, Unix and Unix-like systems (Linux, macOS, FreeBSD, AIX, Xenix, etc.), BeOS, Amiga, RISC OS, and others
"""
LF = '\n'
"""
CR platforms:
Commodore 8-bit machines (C64, C128), Acorn BBC, ZX Spectrum, TRS-80, Apple II series, Oberon,
the classic Mac OS, MIT Lisp Machine and OS-9
"""
CR = "\r"

# UNIX is DEFAULT
DEFAULT_NEW_LINE_SEP = LF

_NEW_LINE_SEP_MAP = {
    CRLF: "CRLF",
    LF:   "LF",
    CR:   "CR"
}
_STR_NEW_LINE_SEP_MAP = invert_dict(_NEW_LINE_SEP_MAP)


class FileBase(metaclass=ABCMeta):
    """
    High-level API for creating and manipulating files
    """
    __size_map = {"B":  1.e0,
                  "KB": 1.e3,
                  "MB": 1.e6,
                  "GB": 1.e9,
                  "TB": 1.e12
                  }

    _new_line_sep_map = _NEW_LINE_SEP_MAP.copy()
    _str_new_line_sep_map = _STR_NEW_LINE_SEP_MAP.copy()
    _default_new_line_sep = DEFAULT_NEW_LINE_SEP
    _dont_read = [".pyc"]
    _ignore_dir = [".git"]
    _allowed_ext = ()
    _date_format = "%Y-%m-%d %H:%M:%S"
    _is_deleted = False

    def __init__(self, path_: Union[str, Path], content_file: Union[Sequence, str, Any] = None, **kwargs):
        warnings.warn(f"cereja.file.v1.File will be deprecated in future versions. "
                      "you can use `cereja.file.FileIO`", DeprecationWarning, 2)
        self._last_update = None
        self._is_byte = kwargs.get('is_byte', False) or isinstance(content_file, bytes)
        self._can_edit = not self._is_byte
        if isinstance(path_, Path):
            self.__path = path_
        else:
            self.__path = Path(normalize_path(path_))
        if self.__path.exists:
            assert not self.__path.is_dir, f'Path is a directory. Change your path. {self.__path}'
            self._last_update = self.updated_at
        if self._allowed_ext:
            assert self.ext in self._allowed_ext, ValueError(
                    f'type of file {self.ext} not allowed. Only allowed {self._allowed_ext}')
        if not content_file:
            content_file = []
        self._lines = self.normalize_data(content_file)
        if not self.is_empty:
            line_sep_ = self._default_new_line_sep
            self.set_new_line_sep(line_sep_)
        else:
            self._new_line_sep = self._default_new_line_sep
        self._current_change = 0
        self._max_history_length = 50
        self._change_history = []
        self._set_change('_lines', self._lines.copy())

    def __setattr__(self, key, value):
        object.__setattr__(self, key, copy.copy(value))
        if hasattr(self, '_change_history') and key not in (
                '_current_change', '_max_history_length', '_change_history'):
            self._set_change(key, copy.copy(object.__getattribute__(self, key)))  # append last_value of attr

    def __sizeof__(self):
        return self.string.__sizeof__() - ''.__sizeof__()  # subtracts the size of the python string object

    def __str__(self):
        return f'{self.__class__.__name__}<{self.file_name}>'

    def __repr__(self):
        return f'{self.__str__()}'

    def __getitem__(self, item) -> str:
        return self._lines[item]

    def __setitem__(self, key, value):
        if isinstance(key, Tuple):
            raise ValueError("invalid assignment.")
        self._insert(key, value)

    def __iter__(self):
        for i in self._lines:
            yield i

    def __len__(self):
        return self.__sizeof__()

    def _set_change(self, key, value):
        self._change_history = self._change_history[:self._current_change + 1]
        if len(self._change_history) >= self._max_history_length:
            self._change_history.pop(0)
        self._change_history.append((key, value))
        self._current_change = len(self._change_history)

    def _select_change(self, index):
        try:

            key, value = self._change_history[self._current_change + index]
            object.__setattr__(self, key, copy.copy(value))
            self._current_change += index
            logger.warning(f'You selected amendment {self._current_change + 1}')
        except IndexError:
            logger.info("It's not possible")

    def _save(self, encoding='utf-8', **kwargs):
        encoding = None if self._is_byte else encoding
        newline = None if self._is_byte else ''
        mode = 'w+b' if self._is_byte else 'w'
        content = self._lines[0] if self._is_byte else self.string
        with open(self.path, mode=mode, newline=newline, encoding=encoding, **kwargs) as fp:
            fp.write(content)
        self._last_update = self.updated_at

    @property
    def history(self):
        return self._change_history

    @property
    def data(self) -> Union[List[str], dict]:
        return self.lines

    @property
    def lines(self) -> List[str]:
        return self._lines.copy()

    @property
    def string(self) -> str:
        if self._is_byte:
            return f'{self._new_line_sep}'.join(map(lambda x: x.decode(), self._lines))
        return f'{self._new_line_sep}'.join(self._lines)

    @property
    def content_str(self):
        warnings.warn(f"This property will be deprecated in future versions. "
                      "you can use property `File.string`", DeprecationWarning, 2)
        return f'{self._new_line_sep}'.join(self._lines)

    @property
    def content_file(self) -> List[str]:
        warnings.warn(f"This property will be deprecated in future versions. "
                      "you can use property `File.lines`", DeprecationWarning, 2)
        return self._lines

    @property
    def base64(self):
        return b64encode(self.string.encode())

    @property
    def path(self):
        return self.__path

    @property
    def file_name(self):
        return self.__path.name

    @property
    def file_name_without_ext(self):
        return self.__path.stem

    @property
    def n_lines(self):
        return len(self._lines)

    @property
    def is_empty(self):
        return not bool(self.n_lines)

    @property
    def dir_name(self):
        return self.__path.parent.name

    @property
    def dir_path(self):
        return self.__path.parent.path

    @property
    def is_link(self):
        return self.__path.is_link

    @property
    def ext(self):
        return self.__path.suffix

    @property
    def updated_at(self):
        return datetime.fromtimestamp(os.stat(str(self.path)).st_mtime).strftime(self._date_format)

    @property
    def created_at(self):
        return datetime.fromtimestamp(os.stat(str(self.path)).st_ctime).strftime(self._date_format)

    @property
    def last_access(self):
        return datetime.fromtimestamp(os.stat(str(self.path)).st_atime).strftime(self._date_format)

    @property
    def new_line_sep(self) -> str:
        return self._new_line_sep

    @property
    def new_line_sep_repr(self):
        return self._new_line_sep_map[self._new_line_sep]

    @classmethod
    def normalize_unix_line_sep(cls, content: str) -> str:
        return content.replace(cls._str_new_line_sep_map['CRLF'],
                               cls._default_new_line_sep).replace(cls._str_new_line_sep_map['CR'],
                                                                  cls._default_new_line_sep)

    @classmethod
    def normalize_data(cls, data: Any, *args, **kwargs) -> Union[List[str], Any]:
        if not data:
            return data
        if isinstance(data, bytes):
            return [data]
        if isinstance(data, str):
            data = data.splitlines()
        elif isinstance(data, int):
            data = [data]
        if is_iterable(data):
            return [str(line).replace(CRLF, '').replace(CR, '').replace(LF, '') for line in data]
        raise ValueError(f"{data} Invalid value. Send other ")

    @classmethod
    def parse_new_line_sep(cls, line: str) -> Union[str, None]:
        if is_iterable(line):
            for ln in cls._new_line_sep_map:
                if ln in line:
                    return ln
        try:
            if line in cls._str_new_line_sep_map:
                return cls._str_new_line_sep_map[line]
        except TypeError:
            return None
        return None

    @classmethod
    def load(cls, path_: Union[str, Path], **kwargs):
        """
        Read and create new file object.

        :param path_: File Path
        :param kwargs:
                encoding: utf-8 is default
                mode: r+ is default
                newline: '' is default
        :return: File object
        """
        path_ = Path(path_)
        assert path_.exists, FileNotFoundError('No such file', path_)
        encoding = kwargs.pop('encoding') if 'encoding' in kwargs else 'utf-8'
        mode = kwargs.pop('mode') if 'mode' in kwargs else 'r+'
        newline = kwargs.pop('newline') if 'newline' in kwargs else ''
        if path_.suffix in cls._dont_read:
            logger.warning(f"I can't read this file. See class attribute <{cls.__name__}._dont_read>")
            return
        try:
            encoding = None if 'b' in mode else encoding
            newline = None if 'b' in mode else newline
            with open(path_, mode=mode, encoding=encoding, newline=newline, **kwargs) as fp:
                content = fp.read()
        except PermissionError as err:
            logger.error(err)
            return
        except UnicodeDecodeError:
            encoding = None
            newline = None
            mode = 'r+b'
            with open(path_, mode=mode, encoding=encoding, newline=newline, **kwargs) as fp:
                content = fp.read()
        return cls(path_, content, is_byte=True if 'b' in mode else False)

    @classmethod
    def load_files(cls, path_, ext=None, contains_in_name: List = (), not_contains_in_name=(), take_empty=True,
                   recursive=False, mode='r+'):

        ext = ext or ''
        path_ = Path.list_files(path_, ext=ext, contains_in_name=contains_in_name,
                                not_contains_in_name=not_contains_in_name, recursive=recursive)
        loaded = []
        for p in path_:
            if recursive and p.is_dir:
                loaded.extend(cls.load_files(path_=path_, ext=ext, contains_in_name=contains_in_name,
                                             not_contains_in_name=not_contains_in_name, take_empty=take_empty,
                                             mode=mode, recursive=recursive))
                continue
            if not p.exists or p.is_dir:
                continue
            file_ = cls.load(p, mode=mode)
            if file_ is None:
                continue
            if take_empty is True and file_.is_empty:
                continue
            if not (file_.ext == f'.{ext.strip(".")}' or ext == ''):
                continue
            if contains_in_name:
                if not any(map(file_.file_name_without_ext.__contains__, contains_in_name)):
                    continue
            if not_contains_in_name:
                if any(map(file_.file_name_without_ext.__contains__, not_contains_in_name)):
                    continue
            loaded.append(file_)
        return loaded

    @classmethod
    def walk(cls, root_dir: str) -> Iterator[Tuple[str, int, list]]:
        """
        It works in a similar way to os.walk. With the difference that the File instance returns.
        :param root_dir: Root directory you want to start browsing
        :return:
        """
        for dir_name, _, files in os.walk(root_dir):
            files_ = []
            if files:
                for file_name in files:
                    file_path = os.path.join(dir_name, file_name)
                    if not os.path.islink(file_path):
                        try:
                            file_obj = cls.load(file_path)
                            if file_obj is not None:
                                files_.append(file_obj)
                        except Exception as err:
                            logger.error(f'Error reading the file {file_name}: {err}')
            yield os.path.basename(dir_name), len(files_), files_

    def set_new_line_sep(self, new_line_: str):
        self._new_line_sep = self.parse_new_line_sep(new_line_) or self._default_new_line_sep

    def undo(self):
        if self._current_change > 0:
            index = -2 if self._current_change == len(self._change_history) else -1
            self._select_change(index)

    def redo(self):
        if self._current_change < len(self._change_history):
            self._select_change(+1)

    def set_path(self, path_):
        self.__path = Path(path_)

    def size(self, unit: str = "KB"):
        """
        returns the size that the file occupies on the disk.

        :param unit: choose anyone in ('B', 'KB', 'MB', 'GB', 'TB')

        """
        assert isinstance(unit, str), f"expected {str.__name__} not {type(unit).__name__}."

        unit = unit.upper()

        assert unit in self.__size_map, f"{repr(unit)} is'nt valid. Choose anyone in {tuple(self.__size_map)}"

        return self.__sizeof__() / self.__size_map[unit]

    def _insert(self, line: int, data: Union[Sequence, str, int], **kwargs):
        assert self._can_edit, "can't edit file type."
        data = self.normalize_data(data, **kwargs)
        if is_sequence(data):
            if line == -1:
                self._lines += list(data)
                return
            for pos, i in enumerate(data, line):
                self._lines.insert(pos, i)
        if isinstance(data, str):
            if line == -1:
                self._lines.append(data)
            else:
                self._lines.insert(line, data)
        self._set_change('_lines', self._lines.copy())

    def remove(self, line: Union[int, str]):
        self._lines.pop(line)
        self._set_change('_lines', self._lines.copy())

    def delete(self):
        self.__path.rm()
        self._is_deleted = True

    def save(self, on_new_path: Union[os.PathLike, None] = None, encoding='utf-8', exist_ok=False, overwrite=False,
             **kwargs):
        if (self._last_update is not None and overwrite is False) and not self._is_deleted:
            if self._last_update != self.updated_at:
                raise AssertionError(f"File change detected (last change {self.updated_at}), if you want to overwrite "
                                     f"set overwrite=True")
        if on_new_path is not None:
            self.set_path(on_new_path)
        assert exist_ok or not self.path.exists, FileExistsError(
                "File exists. If you want override, please send 'exist_ok=True'")

        self._save(encoding=encoding, **kwargs)
        return self

    def replace_file_sep(self, new, save: bool = True):
        new = self.parse_new_line_sep(new)
        if new is None:
            raise ValueError(f"{new} is'nt valid.")
        try:
            self.set_new_line_sep(new)
            if save is True:
                self._save(exist_ok=True)
        except UnicodeDecodeError:
            logger.error(f'Not possibility convert {self.file_name}')
        return self


class TxtFile(FileBase):
    _allowed_ext = ('.txt',)

    def append(self, data: Union[Sequence, str, int], **kwargs):
        self._insert(-1, data, **kwargs)

    def insert(self, data: Union[Sequence, str, int], line: int = 0, **kwargs):
        super()._insert(line=line, data=data, **kwargs)


class CsvFile(FileBase):
    _allowed_ext = ('.csv',)

    def __init__(self, path_: Union[str, Path], fieldnames: Union[Tuple, tuple, list] = (), data=None):
        self._fieldnames = fieldnames if fieldnames is not None else ()
        assert isinstance(self._fieldnames, (tuple, list)), ValueError(
                f"for fieldnames is expected {tuple} or {list}")
        super().__init__(path_, data)

    @property
    def n_cols(self):
        return len(self._fieldnames)

    @property
    def cols(self):
        return self._fieldnames

    @property
    def string(self) -> str:
        return f"{self.new_line_sep}".join([','.join([str(i) for i in row]) for row in [self._fieldnames] + self.lines])

    @property
    def rows(self):
        """
        generator for each row
        :return: only row without cols
        """
        for row in self.lines:
            yield row

    def add_row(self, data: List[Any], fill_with=None):
        """
        Add row is similar to list.append

        :param data: expected row with n elements equal to k cols, if not it will be fill with `fill_with` value.
        :param fill_with: Any value.
        """
        self._insert(-1, data, fill_with=fill_with)

    @classmethod
    def _ast(cls, row):
        vals = []
        for val in row:
            if isinstance(val, str):
                try:
                    val_parsed = ast.literal_eval(val)
                    val = val_parsed if isinstance(val_parsed, (int, float, complex)) else val
                except:
                    pass
            vals.append(val)
        return vals

    def normalize_data(self, data: Any, fill_with=None, literal_eval=True, **kwargs) -> Union[List[str], Any]:
        normalized_data = []
        if is_sequence(data):
            for row in data:
                if not is_sequence(row):
                    if not self._fieldnames:
                        self._fieldnames = (None,)
                    assert len(data) <= len(
                            self._fieldnames), f'number of lines ({len(data)}) > number of cols {len(self._fieldnames)}'
                    data += [fill_with] * abs((len(self._fieldnames) - len(data)))
                    normalized_data.append(self._ast(data) if literal_eval else data)
                    break
                if not self._fieldnames:
                    self._fieldnames = (None,) * len(row)
                assert len(row) <= len(
                        self._fieldnames), f'number of lines ({len(row)}) > number of cols {len(self._fieldnames)}'
                row = list(row)
                row += [fill_with] * abs((len(self._fieldnames) - len(row)))
                normalized_data.append(self._ast(row) if literal_eval else row)
        else:
            assert not isinstance(data, dict), TypeError("dict data isn't valid.")
            data = [data]
            if not self._fieldnames:
                self._fieldnames = (None,)
            data += [fill_with] * (len(self._fieldnames) - len(data))
            normalized_data.append(self._ast(data) if literal_eval else data)
        self._fieldnames = tuple(value if value is not None else f'unamed_col_{i}' for i, value in
                                 enumerate(self._fieldnames))
        return normalized_data

    @property
    def data(self):
        """
        generator for each row

        format -> {col_name: value, col_name2: value, ...}

        :return: rows with column. Is a dict type
        """
        for row in self.lines:
            yield dict(zip(self._fieldnames, row))

    def _save(self, encoding='utf-8', **kwargs):
        with open(self.path, 'w', newline='', encoding=encoding, **kwargs) as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self._fieldnames)
            writer.writeheader()
            writer.writerows(self.data)

    @classmethod
    def read(cls, path_: str, has_col=True, encoding='utf-8', **kwargs):
        warnings.warn(f"This function will be deprecated in future versions. "
                      "you can use `CsvFile.load`", DeprecationWarning, 2)
        return cls.load(path_, has_col, encoding, **kwargs)

    @classmethod
    def load(cls, path_: str, has_col=True, encoding='utf-8', **kwargs):
        path_ = Path(path_)
        assert path_.exists, FileNotFoundError('No such file', path_)
        if path_.suffix != '.csv':
            raise ValueError("isn't .csv file.")
        with open(path_.path, encoding=encoding, newline='') as fp:
            reader = csv.reader(fp)
            fields = None
            if has_col:
                fields = next(reader)
            data = list(reader)
        return cls(path_, fieldnames=fields, data=data)

    def to_dict(self):
        return dict(zip(self.cols, get_cols(self.lines)))

    def flatten(self):
        return flatten(self.lines)

    def shape(self):
        return get_shape(self.lines)

    def __getitem__(self, item):
        if isinstance(item, str):
            if item not in self.cols:
                raise ValueError(f'Column name <{item}> not in {self.cols}')
            return get_cols(self.lines)[self.cols.index(item)]
        if isinstance(item, tuple):
            lines, col = item
            if isinstance(col, tuple):
                raise ValueError("Isn't Possible.")
            assert col <= self.n_cols - 1, ValueError(
                    f"Invalid Column. Choice available index {list(range(self.n_cols))}")
            return get_cols(self.lines)[col][lines]
        return super().__getitem__(item)


class JsonFile(FileBase):
    _allowed_ext = ('.json',)

    def __init__(self, path_: Union[str, Path], data: dict = None):
        setattr(self, 'items', lambda: self.data.items())
        setattr(self, 'keys', lambda: self.data.keys())
        setattr(self, 'values', lambda: self.data.values())
        super().__init__(path_=path_, content_file=data)

    def __getitem__(self, item):
        try:
            return self.data[item]
        except KeyError:
            raise KeyError(f"{item} not found.")

    @classmethod
    def parse(cls, data) -> dict:
        if isinstance(data, str):
            return json.loads(data)
        elif isinstance(data, dict):
            return json.loads(json.dumps(data))
        return super().normalize_data(data)

    def __setitem__(self, key, value):
        data = self.data
        data[key] = value
        self._lines = self.normalize_data(data)

    def __iter__(self):
        for i in self.data:
            yield i

    @property
    def string(self) -> str:
        return json.dumps(self.data, indent=4)

    @staticmethod
    def _parse_key_value(data: Tuple[Any, Any], take_tuple=False) -> Union[dict, Any]:
        if isinstance(data, dict):
            return data
        try:
            key, value = data
            return (key, value) if take_tuple is True else {key: value}
        except Exception as err:
            if is_sequence(data):
                if len(data) > 2:
                    raise ValueError(f"Invalid data {data}.")
                if len(data) == 1:
                    return (data[0], None) if take_tuple is True else {data[0]: None}
            if isinstance(data, (str, int, float, complex)):
                return (data, None) if take_tuple is True else {data: None}
            logger.error(
                    f"Internal Error: Intern function '_parse_key_value' error {err}. Please report this issue on "
                    f"github https://github.com/jlsneto/cereja")
            return data

    @staticmethod
    def is_valid(data: dict):
        try:
            json.dumps(data)
            return True
        except:
            return False

    @classmethod
    def normalize_data(cls, data: Any, *args, **kwargs) -> dict:
        if data is None:
            return {}
        if isinstance(data, (dict, set)):
            return cls.parse(data)
        if is_sequence(data):
            if len(data) == 2:
                if len(flatten(data)) == 2:
                    return cls.parse(cls._parse_key_value(data))
            normalized_data = {}
            for item in data:
                k, v = cls._parse_key_value(item, take_tuple=True)
                assert k not in normalized_data, ValueError(f'Data contains duplicate keys <{k}>')
                normalized_data[k] = v
            return cls.parse(normalized_data)
        return cls.parse({data: None})

    def remove(self, key):
        if key in self.data:
            data = self.data
            data.pop(key)
            self._lines = data
        else:
            raise ValueError(f'{key} not found.')

    def _insert(self, key, value, **kwargs):
        key, value = self._parse_key_value((key, value), take_tuple=True)
        assert key not in self.data and str(key) not in self.data, ValueError(f'Data contains duplicate keys <{key}>')
        data = self.data
        data[key] = value
        if not self.is_valid(data):
            raise ValueError('Invalid JSON data.')
        self._lines = data

    def get(self, _key):
        return self.data.get(_key)

    @classmethod
    def load(cls, path_: Union[str, Path], **kwargs):
        encoding = kwargs.pop('encoding') if 'encoding' in kwargs else 'utf-8'
        path_ = Path(path_)
        assert path_.exists, FileNotFoundError('No such file', path_)
        assert path_.suffix == '.json', "isn't .json file."
        with open(path_, encoding=encoding, **kwargs) as fp:
            data = json.load(fp)
        return cls(path_, data=data)


class PyFile(TxtFile):
    _allowed_ext = ('.py',)
    pass


class File(FileBase):
    """
    High-level API for creating and manipulating files

    Identify and create the object based on the extension
    """

    __classes_by_ext = {
        '.json': JsonFile,
        '.csv':  CsvFile,
        '.txt':  TxtFile,
        '.py':   PyFile
    }

    def __init__(self, path_, *args, **kwargs):
        super().__init__(path_, *args, **kwargs)

    def __new__(cls, path_: str, *args, **kwargs) -> Union[FileBase, JsonFile, CsvFile, TxtFile, 'PyFile']:
        """
        Create instance based

        :param path_: File path
        :param kwargs:
            content_file: file content depends on the type of file
            data: file content depends on the type of file
            fieldnames: only .csv data.
        """
        path_ = Path(path_)
        if not args:
            if 'content_file' in kwargs and 'data' in kwargs:
                raise ValueError("Cannot send content_file and data")
            content_file = kwargs.get('content_file') or kwargs.get('data')
        else:
            content_file = args[0]

        if path_.exists:
            logger.warning(
                    f'You are creating a new file, but file path {str(path_)} already exists. \nIf you want to read or '
                    f'write the content of file use <File.read>')

        if path_.suffix == '.csv':
            fieldnames = kwargs.get('fieldnames')
            return CsvFile(path_, fieldnames=fieldnames, data=content_file)
        elif path_.suffix == '.json':
            return JsonFile(path_, data=content_file)
        elif path_.suffix == '.txt':
            return TxtFile(path_, content_file=content_file)
        return FileBase(path_=path_, content_file=content_file)

    @classmethod
    def read(cls, path_: str, **kwargs):
        warnings.warn(f"This function will be deprecated in future versions. "
                      "you can use property `File.load`", DeprecationWarning, 2)
        return cls.load(path_, **kwargs)

    @classmethod
    def load(cls, path_: str, **kwargs) -> Union['TxtFile', 'CsvFile', 'JsonFile', 'FileBase', 'PyFile']:
        """
        Read and create instance based on extension.

        :param path_: File path
        :param kwargs:
        :return:
        """
        encoding = kwargs.pop('encoding') if 'encoding' in kwargs else 'utf-8'
        mode = kwargs.pop('mode') if 'mode' in kwargs else 'r+'
        newline = kwargs.pop('newline') if 'newline' in kwargs else ''
        path_ = Path(path_)
        assert path_.exists, FileNotFoundError('No such file', path_)
        return cls.__classes_by_ext.get(path_.suffix, FileBase).load(path_=path_, mode=mode, encoding=encoding,
                                                                     newline=newline,
                                                                     **kwargs)


def _walk_dirs_and_replace(dir_path, new, ext_in: list = None):
    ext_in = ext_in or []
    with Progress(f"Looking to {dir_path}") as prog:
        for dir_name, n_files, files_obj in File.walk(dir_path):
            if files_obj:
                prog.show_progress(1, n_files)
                for i, file_obj in enumerate(files_obj):
                    if file_obj.is_link or (ext_in and file_obj.ext not in ext_in):
                        continue
                    prog.task_name = f"Converting {dir_name} ({file_obj})"
                    file_obj.replace_file_sep(new)
                    prog.update_max_value(i)


def convert_new_line_sep(path_: str, line_sep: str, ext_in: list = None):
    line_sep = File.parse_new_line_sep(line_sep)

    if line_sep is None:
        raise ValueError(f"The value sent {line_sep} is not valid.")

    if os.path.isdir(path_):
        _walk_dirs_and_replace(path_, LF, ext_in)
    else:
        with Progress(f"Converting {os.path.basename(path_)}"):
            File.load(path_).replace_file_sep(line_sep)


def crlf_to_lf(path_: str, ext_in: list = None):
    """
    :param path_:
    :param ext_in:
    :return:
    """
    convert_new_line_sep(path_, LF, ext_in=ext_in)


def lf_to_crlf(path_: str, ext_in: list = None):
    """
    :param path_:
    :param ext_in:
    :return:
    """
    convert_new_line_sep(path_, CRLF, ext_in=ext_in)


def to_lf(path_: str):
    convert_new_line_sep(path_, LF)


def to_cr(path_: str):
    convert_new_line_sep(path_, CR)


def to_crlf(path_: str):
    convert_new_line_sep(path_, CRLF)
