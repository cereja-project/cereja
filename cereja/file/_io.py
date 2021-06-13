import copy
import csv
import logging
import os
import re
import pickle
import tempfile
from abc import ABCMeta, abstractmethod, ABC
from collections import ValuesView
from io import BytesIO
from typing import Any, List, Union, Type, TextIO, Iterable, Tuple, KeysView, ItemsView
import json
from .._requests import request
from zipfile import ZipFile, ZIP_DEFLATED

from cereja.system import Path, mkdir
from cereja.array import get_cols, flatten, get_shape
from cereja.utils import is_sequence, clipboard
from cereja.system import memory_of_this
from cereja.utils import string_to_literal, sample, fill

logger = logging.Logger(__name__)

__all__ = ['FileIO']


class _IFileIO(metaclass=ABCMeta):
    _size_map = {"B":  1.e0,
                 "KB": 1.e3,
                 "MB": 1.e6,
                 "GB": 1.e9,
                 "TB": 1.e12
                 }
    _dont_read = [".pyc"]
    _ignore_dir = [".git"]
    _date_format = "%Y-%m-%d %H:%M:%S"
    # need implement
    _is_byte = None
    _only_read = None
    _newline = True
    _ext_allowed = None
    _need_implement = {'_is_byte':     """
    Define the configuration of the file in the class {class_name}:
    e.g:
    class {class_name}:
        _is_byte: bool = True # or False
    """,
                       '_only_read':   """Define the configuration of the file in the class {class_name}:
    e.g:
    class {class_name}:
        _only_read: bool = True # or False

    """,
                       '_ext_allowed': """Define the configuration of the file in the class {class_name}:
                       e.g:
                       class {class_name}:
                           _ext_allowed: bool = '.txt' # or ''

                       """
                       }

    def __init__(self):
        self._built = False
        self._length = None
        self._last_update = None
        self._is_deleted = False
        self._current_change = 0
        self._max_history_length = 50
        self._change_history = []
        self._data = None

    @property
    @abstractmethod
    def data(self) -> Any:
        pass

    @property
    @abstractmethod
    def path(self) -> Path:
        pass

    @property
    @abstractmethod
    def name(self):
        pass

    @property
    @abstractmethod
    def ext(self):
        pass

    @property
    @abstractmethod
    def name_without_ext(self):
        pass

    @property
    @abstractmethod
    def dir_name(self):
        pass

    @property
    @abstractmethod
    def dir_path(self):
        pass

    @property
    @abstractmethod
    def is_empty(self):
        pass

    @property
    @abstractmethod
    def updated_at(self):
        pass

    @property
    @abstractmethod
    def created_at(self):
        pass

    @property
    @abstractmethod
    def was_changed(self) -> bool:
        pass

    @property
    @abstractmethod
    def length(self):
        pass

    @property
    @abstractmethod
    def history(self):
        pass

    @property
    @abstractmethod
    def exists(self):
        pass

    @property
    @abstractmethod
    def last_access(self):
        pass

    @abstractmethod
    def _load(self, mode=None, **kwargs) -> Any:
        pass

    @abstractmethod
    def save(self, on_new_path: Union[str, Path] = None, exist_ok=False, overwrite=False, **kwargs):
        pass

    @abstractmethod
    def _parse_fp(self, fp: Union[TextIO, BytesIO]) -> Any:
        pass

    @abstractmethod
    def _save_fp(self, fp: Union[TextIO, BytesIO]) -> None:
        pass

    @abstractmethod
    def undo(self):
        pass

    @abstractmethod
    def redo(self):
        pass

    @abstractmethod
    def parse(self, data):
        pass

    @abstractmethod
    def add(self, data, **kwargs):
        pass

    @abstractmethod
    def size(self, unit: str = "KB"):
        pass

    @abstractmethod
    def delete(self):
        pass

    @abstractmethod
    def __iter__(self):
        pass

    @abstractmethod
    def set_path(self, p: str):
        pass


class _FileIO(_IFileIO, ABC):

    def __init__(self, path_: Path, data=None, creation_mode=False, is_byte=None, **kwargs):
        super().__init__()
        if is_byte is not None:
            self._is_byte = bool(is_byte)
        if not isinstance(path_, Path):
            path_ = Path(path_)
        self._creation_mode = creation_mode
        self._path = path_
        if self._ext_allowed:
            msg_assert_err = f'{path_.suffix} != {self._ext_allowed}. Force with support_ext = ".xyz" '
            assert self._path.suffix in self._ext_allowed, msg_assert_err
        self._ext_without_point = self._path.suffix.strip(".").upper()
        self._built = True  # next setattr will be saved in history to be future recovery
        if creation_mode:
            self._data = self.parse(data)
        else:
            self._data = self._load(**kwargs)

    def __init_subclass__(cls, **kwargs):
        for attr in cls._need_implement:
            if getattr(cls, attr) is None:
                raise NotImplementedError(cls._need_implement.get(attr).format(class_name=cls.__name__))

    def __repr__(self):
        return f'{self._ext_without_point}<{self._path.name}>'

    def __str__(self):
        return f'{self._ext_without_point}<{self._path.name}>'

    def __setattr__(self, key, value):
        object.__setattr__(self, key, copy.copy(value))
        if hasattr(self, '_change_history') and key not in (
                '_current_change', '_max_history_length', '_change_history', '_built',
                '_last_update') and self._built is True:
            self._set_change(key, copy.copy(object.__getattribute__(self, key)))  # append last_value of attr

    def __getitem__(self, item):
        try:
            return self.data[item]
        except TypeError:
            raise TypeError(f"'{self.__class__.__name__}' object is not subscriptable")

    def __setitem__(self, key, value):
        # TODO: save only the index that has been changed
        try:
            self._data[key] = value
            self._set_change('_data', copy.copy(self._data))
        except TypeError:
            raise TypeError(f"'{self.__class__.__name__}' object is not subscriptable")

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

    @property
    def line_sep(self):
        return os.linesep

    @property
    def was_changed(self) -> bool:
        """
        Detect if file is changed by another application
        if file not exists return False

        @return: bool
        """
        if not self.exists:
            return False
        return self._last_update is not None and self.updated_at != self._last_update

    @property
    def length(self):
        return len(self._data)

    @property
    def history(self):
        return self._change_history

    @property
    def updated_at(self):
        return self._path.updated_at

    @property
    def created_at(self):
        return self._path.created_at

    @property
    def last_access(self):
        return self._path.last_access

    @property
    def name(self):
        return self._path.name

    @property
    def ext(self):
        return self._path.suffix

    @property
    def name_without_ext(self):
        return self._path.stem

    @property
    def data(self):
        return copy.copy(self._data)

    @property
    def path(self):
        return self._path

    @property
    def dir_name(self):
        return self._path.parent_name

    @property
    def dir_path(self):
        return self._path.parent

    @property
    def is_empty(self):
        return not bool(self._data)

    @property
    def exists(self):
        return self.path.exists

    @property
    def only_read(self) -> bool:
        return self._only_read

    @classmethod
    def add(cls, *args, **kwargs):
        raise NotImplementedError("it's not implemented")

    @classmethod
    def parse_ext(cls, ext: str) -> str:
        if not isinstance(ext, str):
            raise TypeError('Error during parsing ext. Send a string.')
        return '.' + ext.replace('.', '')

    def _get_mode(self, mode) -> str:
        """
        if mode is 'r' return 'r+' or 'r+b' else mode is 'w' return 'w+' or 'w+b'
        """
        return f'{mode}+b' if self._is_byte else f'{mode}+'

    def size(self, unit: str = "KB"):
        """
        returns the size that the file occupies on the disk.

        :param unit: choose anyone in ('B', 'KB', 'MB', 'GB', 'TB')

        """
        assert isinstance(unit, str), f"expected {str.__name__} not {type(unit).__name__}."

        unit = unit.upper()

        assert unit in self._size_map, f"{repr(unit)} is'nt valid. Choose anyone in {tuple(self._size_map)}"
        # subtracts the size of the python object
        return (memory_of_this(self._data) - self._data.__class__().__sizeof__()) / self._size_map[unit]

    def _load(self, mode=None, **kwargs) -> Any:
        if self._path.suffix in self._dont_read:
            logger.warning(f"I can't read this file. See class attribute <{self.__name__}._dont_read>")
            return
        mode = mode or self._get_mode('r')
        encoding = None if self._is_byte else 'utf-8'
        assert 'r' in mode, f"{mode} for read isn't valid."
        try:
            with open(self._path.path, mode=mode, encoding=encoding, **kwargs) as fp:
                parsed = self._parse_fp(fp)
                self._last_update = self.updated_at
                return parsed
        except PermissionError as err:
            logger.error(err)
            return
        except Exception as err:
            raise IOError(f"Error when trying to read the file {self._path}\n{err}")

    def save(self, on_new_path: Union[str, Path] = None, mode=None, exist_ok=False, overwrite=False, force=False,
             encoding=None,
             **kwargs):

        if not force:
            assert self._only_read is False, f"{self.name} is only read."

            if on_new_path is not None:
                self.set_path(on_new_path)

            if self.was_changed:
                assert overwrite is True, AssertionError(
                        f"File change detected (last change {self.updated_at}), if you want to "
                        + f"overwrite set overwrite=True")

            assert (exist_ok or not self.path.exists) or overwrite is True or force is True, FileExistsError(
                    "File exists. If you want override, please send 'exist_ok=True'")

        mode = mode or self._get_mode('w')
        assert 'w' in mode, f"{mode} for write isn't valid."
        encoding = None if self._is_byte else 'utf-8'
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmp_file = Path(tmpdirname).join(self.name)
            if not self._newline and not self._is_byte:
                kwargs.update({'newline': ''})
            try:
                with open(tmp_file, mode=mode, encoding=encoding, **kwargs) as fp:
                    self._save_fp(fp)
            except Exception as err:
                raise IOError(f'Error writing to the file system file: {err}')
            tmp_file.cp(self.path)
            self._last_update = self.updated_at

    def delete(self):
        self._path.rm()
        self._is_deleted = True

    def set_path(self, path_):
        p = Path(path_)
        assert not p.is_dir, f"{p.path} is a directory."
        self._path = p

    def undo(self):
        if self._current_change > 0:
            index = -2 if self._current_change == len(self._change_history) else -1
            self._select_change(index)

    def redo(self):
        if self._current_change < len(self._change_history):
            self._select_change(+1)

    def sample_items(self, k: int = 1, is_random=False):
        """
        Get sample of this.

        @param k: length of sample
        @param is_random: bool
        """
        assert isinstance(k, int) and k > 0, f"k = {k} isn't valid."
        return sample(self.data, k=k, is_random=is_random)

    def __len__(self):
        if self._length is None:
            return len(self._data)
        return self._length

    def __next__(self):
        for i in self._data:
            yield i

    def __iter__(self):
        return self.__next__()

    @classmethod
    def load(cls, path_, **kwargs):
        return cls(path_, creation_mode=False, **kwargs)

    @classmethod
    def create(cls, path_, data=None, **kwargs):
        return cls(path_=path_, data=data, creation_mode=True, **kwargs)


class _Generic(_FileIO):
    _is_byte: bool = True
    _only_read = False
    _ext_allowed = ()
    _split_lines = False

    def _parse_fp(self, fp: BytesIO) -> List[bytes]:
        if self._split_lines or not bool(self.ext):
            data = fp.read().splitlines()
        else:
            data = fp.read()
        return self.parse(data)

    def _save_fp(self, fp: Union[TextIO, BytesIO]) -> None:
        fp.write(self._convert('\n').join(self._data))

    def _convert(self, val):
        if self._is_byte and not isinstance(val, bytes):
            return str(val).encode()
        return val

    def parse(self, data) -> List[bytes]:
        if isinstance(data, (bytes, str, int, float, complex)):
            return [self._convert(data)]
        if not data:
            return [self._convert('')]
        if isinstance(data, (list, tuple)):
            return [self._convert(i) for i in data]
        raise ValueError(f"{type(data)} isn't valid.")

    def add(self, data, line=-1):
        data = self.parse(data)
        if line != -1:
            for pos, i in enumerate(data, line):
                self._data.insert(pos, i)
        else:
            self._data += data
            return
        self._set_change('_data', self._data.copy())

    def remove(self, line: Union[int, str]):
        self._data.pop(line)
        self._set_change('_data', self._data.copy())


class _TxtIO(_Generic):
    _is_byte: bool = False
    _only_read = False
    _ext_allowed = ()
    _split_lines = True


class _JsonIO(_FileIO):
    _is_byte: bool = False
    _only_read = False
    _ext_allowed = ('.json',)
    indent = 4
    ensure_ascii = False

    def __init__(self, path_: Path, **kwargs):
        if 'indent' in kwargs:
            self.indent = kwargs.pop('indent')
        if 'ensure_ascii' in kwargs:
            self.ensure_ascii = kwargs.pop('ensure_ascii')
        super().__init__(path_, **kwargs)

    def _parse_fp(self, fp: TextIO) -> dict:
        return json.load(fp)

    def _save_fp(self, fp):
        json.dump(self._data, fp, indent=self.indent, ensure_ascii=self.ensure_ascii)

    def items(self) -> ItemsView:
        return self._data.items()

    def keys(self) -> KeysView:
        return self._data.keys()

    def values(self) -> ValuesView:
        return self._data.values()

    def parse(self, data) -> dict:
        if isinstance(data, dict):
            return data
        else:
            raise TypeError(f"{type(data)} isn't valid.")

    def _add(self, k, v):
        self._data[k] = v

    def add(self, key, value):
        self._add(key, value)

    def remove(self, key):
        self._data.pop(key)

    def get(self, _key):
        return self._data.get(_key)

    def __getitem__(self, item):
        try:
            return self.data[item]
        except KeyError:
            raise KeyError(f"{item} not found.")

    def __setitem__(self, key, value):
        self.add(key, value)

    def __iter__(self):
        for i in self.data:
            yield i


class _Mp4IO(_FileIO, ABC):
    _is_byte: bool = True
    _only_read = True
    _ext_allowed = ('.mp4',)

    def _save_fp(self, fp):
        fp.write(self._data)

    def _parse_fp(self, fp: BytesIO) -> bytes:
        return fp.read()

    def parse(self, data):
        return self._data


class _CsvIO(_FileIO):
    _is_byte: bool = False
    _only_read = False
    _newline = False
    _ext_allowed = ('.csv',)

    def __init__(self, *args, cols: Union[Tuple[str], List[str]] = (), fill_with=None,
                 str_to_literal=True, has_col=False, **kwargs):
        """
        :param data: expected row or list of rows with `n` elements equal to `k` cols, if not it will be fill with
        `fill_with` value.
        :param fill_with: fill empty
        :param has_col: bool
        :param literal_values: Convert `str` on literal types e.g `"'1'"` (str) -> `1` (int)
        """
        self._cols = cols
        self._str_to_literal = str_to_literal
        self._fill_with = fill_with
        self._n_values = 0
        self._has_col = has_col
        super().__init__(*args, **kwargs)

    @property
    def cols(self):
        return tuple(value if value is not None else f'unamed_col_{i}' for i, value in
                     enumerate(self._cols))

    @property
    def n_cols(self):
        return len(self.cols)

    @property
    def n_values(self):
        return self._n_values

    @property
    def rows(self):
        """
        generator for each row

        format -> {col_name: value, col_name2: value, ...}

        :return: rows with column. Is a dict type
        """
        for row in self.data:
            yield dict(zip(self.cols, row))

    def _parse_fp(self, fp: TextIO, **kwargs) -> List[List[Any]]:
        reader = csv.reader(fp)
        return self.parse(reader)

    def _save_fp(self, fp: TextIO):
        writer = csv.DictWriter(fp, fieldnames=self.cols)
        writer.writeheader()
        writer.writerows(self.rows)

    def _normalize_row(self, row, fill_with=None, literal_values=True):
        if not is_sequence(row):
            row = [row]
        if self._cols:
            row = fill(value=list(row), max_size=len(self.cols), with_=fill_with) if len(row) < len(self.cols) else row
        return [string_to_literal(item) if isinstance(item, str) else item for item in row if literal_values]

    def parse(self, data: Union[Iterable[Iterable[Any]], str, int, float, complex], fill_with=None) -> List[List[Any]]:
        if fill_with is None:
            fill_with = self._fill_with
        normalized_data = []
        if isinstance(data, dict):
            self._cols = tuple(data)
            data = data.values()
        if not is_sequence(data):
            data = [data]
        for row in data:
            if not self._cols:
                # set cols on first iter
                self._cols = fill(value=list(row), max_size=len(row), with_=fill_with)
                continue
            row_normalized = self._normalize_row(row, fill_with=fill_with, literal_values=self._str_to_literal)
            self._n_values += len(row_normalized)
            normalized_data.append(row_normalized)
        return normalized_data

    def to_dict(self):
        return dict(zip(self.cols, get_cols(self.data)))

    def flatten(self):
        return flatten(self._data)

    def shape(self):
        return get_shape(self._data)

    def _add(self, row: List[Any], index, fill_with=None):
        row = self.parse([row], fill_with=fill_with)
        if index != -1:
            for pos, i in enumerate(row, index):
                self._data.insert(pos, i)
        else:
            self._data += row

    def add(self, row: List[Any], index=-1, fill_with=None):
        """
        Add row is similar to list.append

        :param row: expected row with n elements equal to k cols, if not it will be fill with `fill_with` value.
        :param index: position that will be added
        :param fill_with: None
        """
        self._add(row=row, index=index, fill_with=fill_with)

    def __getitem__(self, item):
        if isinstance(item, str):
            if item not in self.cols:
                raise ValueError(f'Column name <{item}> not in {self.cols}')
            return get_cols(self.data)[self.cols.index(item)]
        if isinstance(item, tuple):
            lines, col = item
            if isinstance(col, tuple):
                raise ValueError("Isn't Possible.")
            assert col <= self.n_cols - 1, ValueError(
                    f"Invalid Column. Choice available index {list(range(self.n_cols))}")
            return get_cols(self.data)[col][lines]
        return super().__getitem__(item)


class _PyObj(_FileIO):
    _is_byte: bool = True
    _only_read = False
    _newline = False
    _ext_allowed = ('.pkl',)

    def _parse_fp(self, fp: TextIO, **kwargs) -> List[List[Any]]:
        loaded_obj = pickle.load(fp, **kwargs)
        return self.parse(loaded_obj)

    def _save_fp(self, fp: TextIO):
        pickle.dump(self.data, fp)

    def parse(self, data):
        return data


class _ZipFileIO(_FileIO):
    _is_byte: bool = False
    _only_read = False
    _newline = False
    _ext_allowed = ('.zip',)

    def __init__(self, path_: Path, load_on_memory=False, **kwargs):

        self._load_on_memory = load_on_memory
        super().__init__(path_, **kwargs)

    def add(self, data: Union[str, list, tuple]):
        parsed = self.parse(data)
        self._data += parsed

    def _parse_fp(self, fp: Union[TextIO, BytesIO]) -> Any:
        return self.unzip(fp.name, load_on_memory=self._load_on_memory)

    @classmethod
    def unzip(cls, file_path, save_on: str = None, load_on_memory=False):
        with ZipFile(file_path, mode='r') as myzip:
            if save_on or load_on_memory:
                with tempfile.TemporaryDirectory() as tmpdirname:
                    unzip_dir = save_on or tmpdirname
                    unzip_dir = Path(unzip_dir).join(Path(myzip.filename).stem)
                    mkdir(unzip_dir)
                    myzip.extractall(unzip_dir)
                    if load_on_memory:
                        return FileIO.load_files(unzip_dir)
            return myzip.namelist()

    def _save_fp(self, fp: Union[TextIO, BytesIO]) -> None:
        raise NotImplementedError

    def save(self, on_new_path: Union[str, Path] = None, exist_ok=False, overwrite=False, force=False,
             **kwargs):
        with tempfile.TemporaryDirectory() as tmpdirname:
            tmp_file = Path(tmpdirname).join(self.name)
            try:
                with ZipFile(tmp_file.path, mode='w', compression=ZIP_DEFLATED) as myzip:
                    for i in self.data:
                        myzip.write(i)
            except Exception as err:
                raise IOError(f'Error writing to the file system file: {err}')
            tmp_file.cp(self.path)
            self._last_update = self.updated_at

    def parse(self, data):
        if not data:
            return []
        if isinstance(data, (str, Path)):
            data = [data]

        if not is_sequence(data):
            raise ValueError("Send list of paths invalid.")
        res = []

        for p in data:
            p = Path(p)
            if not p.exists:
                raise ValueError(f'{p.path} not Found.')
            res.append(p)
        return res


class _SrtFile(_TxtIO):
    _only_read = False
    _ext_allowed = ('.srt', '.vtt')

    @classmethod
    def is_block_start(cls, line) -> bool:
        return bool(re.match(r'\d{2}:\d{2}:\d{2}[.,]\d+\s-->\s\d{2}:\d{2}:\d{2}[.,]\d+', line))

    def parse(self, data):
        data = super().parse(data)
        blocks = []
        current_block = 0
        block = []
        block_started = False
        for i in data:
            if self.is_block_start(i):
                if block_started:
                    blocks.append(self.Block(current_block, *block))
                block_started = True
                current_block += 1
                block = []
            if block_started and not i.isdigit():
                block.append(i)
        if block:
            blocks.append(self.Block(current_block, *block))

        return blocks

    @property
    def string(self):
        return '\n'.join([str(block_item) for block in self.data for block_item in block])

    def add(self, data, line=-1):
        raise NotImplementedError

    @classmethod
    def from_url(cls, url: str, *args, **kwargs):
        # TODO: need improves
        resp = request.get(url, *args, **kwargs)
        if resp.code == 200:
            return cls(Path('./subtitle.srt'), resp.data, creation_mode=True)

    @property
    def text(self):
        return [content.strip() for block in self.data for content in block.content if content]

    class Block:
        def __init__(self, number, *content):
            self.number = number
            time_, *content = content

            self.time = time_
            start, time_separator, end = time_.split()
            self._start = start
            self._end = end
            self.content = content
            self._time_separator = time_separator

        @property
        def start(self):
            return self._start

        @property
        def end(self):
            return self._end

        @property
        def _values(self):
            return (self.number, self.time, *self.content)

        def __getitem__(self, item):
            return self._values[item]

        def __repr__(self):
            return f'{self._values}'


class FileIO:
    txt = _TxtIO
    json = _JsonIO
    mp4 = _Mp4IO
    csv = _CsvIO
    pkl = _PyObj
    zip = _ZipFileIO
    srt = _SrtFile
    _generic = _Generic

    def __new__(cls, path_, data=None, **kwargs):
        raise Exception(f"Cannot instantiate {cls.__name__}, use the methods ['create', 'load', 'load_files']")

    @classmethod
    def create(cls, path_: Union[Type[Path], str], data: Any, **kwargs) -> _FileIO:
        path_ = Path(path_)
        return cls.lookup(path_.suffix).create(path_=path_, data=data, **kwargs)

    @classmethod
    def lookup(cls, ext: str) -> Type[_FileIO]:
        ext = ext.replace('.', '')
        if hasattr(cls, ext):
            return getattr(cls, ext)
        return cls._generic

    @classmethod
    def load(cls, path_: Union[str, Path], **kwargs) -> _FileIO:
        path_ = Path(path_)
        if not path_.exists:
            raise FileNotFoundError(f"{path_.path} not found.")
        return cls.lookup(path_.suffix).load(path_=path_, **kwargs)

    @classmethod
    def load_from_clipboard(cls):
        return cls.load(Path(clipboard()))

    @classmethod
    def load_files(cls, path_, ext=None, contains_in_name: List = (), not_contains_in_name=(), take_empty=True,
                   recursive=False):

        ext = ext or ''
        f_paths = Path.list_files(path_, ext=ext, contains_in_name=contains_in_name,
                                  not_contains_in_name=not_contains_in_name, recursive=recursive)
        loaded = []
        for p in f_paths:
            if recursive and p.is_dir:
                loaded.extend(cls.load_files(path_=p, ext=ext, contains_in_name=contains_in_name,
                                             not_contains_in_name=not_contains_in_name, take_empty=take_empty,
                                             recursive=recursive))
                continue
            if not p.exists or p.is_dir:
                continue
            file_ = cls.load(path_=p)
            if file_ is None:
                continue
            if take_empty is True and file_.is_empty:
                continue
            if not (file_.ext == f'.{ext.strip(".")}' or ext == ''):
                continue
            if contains_in_name:
                if not any(map(file_.name_without_ext.__contains__, contains_in_name)):
                    continue
            if not_contains_in_name:
                if any(map(file_.name_without_ext.__contains__, not_contains_in_name)):
                    continue
            loaded.append(file_)
        return loaded


FileType = Type[_Generic]
FileTxtType = Type[_TxtIO]
FileJsonType = Type[_JsonIO]
FileCsvType = Type[_CsvIO]
FilePythonObj = Type[_PyObj]
