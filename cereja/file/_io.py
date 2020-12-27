import ast
import copy
import csv
import logging
import os
from abc import ABCMeta, abstractmethod
from datetime import datetime
from typing import Any, List, Union, Type
import json
from cereja import Path, get_cols, flatten, get_shape, is_sequence
from cereja.utils import literal_eval

logger = logging.Logger(__name__)


class _IFileIO(metaclass=ABCMeta):

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
    def history(self):
        pass

    @property
    @abstractmethod
    def last_access(self):
        pass

    @abstractmethod
    def load(self, mode=None, **kwargs) -> Any:
        pass

    @abstractmethod
    def save(self, on_new_path: Union[str, Path] = None, exist_ok=False, overwrite=False, **kwargs):
        pass

    @abstractmethod
    def parse(self, data: Union[str, bytes]) -> Any:
        pass

    @abstractmethod
    def undo(self):
        pass

    @abstractmethod
    def redo(self):
        pass


class _FileIO(_IFileIO, metaclass=ABCMeta):
    _dont_read = [".pyc"]
    _ignore_dir = [".git"]
    _date_format = "%Y-%m-%d %H:%M:%S"
    # need implement
    _is_byte = None
    _only_read = None
    _need_implement = {'_is_byte':   """
    Define the configuration of the file in the class {class_name}:
    e.g:
    class {class_name}:
        _is_byte: bool = True # or False
    """,
                       '_only_read': """Define the configuration of the file in the class {class_name}:
    e.g:
    class {class_name}:
        _only_read: bool = True # or False
    """}

    def __init__(self, path_: Path, data=None, creation_mode=False, **kwargs):
        self._last_update = None
        self._is_deleted = False
        self._creation_mode = creation_mode
        self._path = path_
        self._ext_without_point = self._path.suffix.strip(".").upper()
        self._current_change = 0
        self._max_history_length = 50
        self._change_history = []
        if creation_mode:
            self._data = self.parse(data)
        else:
            self._data = self.load(**kwargs)

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
                '_current_change', '_max_history_length', '_change_history'):
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
    def history(self):
        return self._change_history

    @property
    def updated_at(self):
        return datetime.fromtimestamp(os.stat(str(self._path)).st_mtime).strftime(self._date_format)

    @property
    def created_at(self):
        return datetime.fromtimestamp(os.stat(str(self._path)).st_ctime).strftime(self._date_format)

    @property
    def last_access(self):
        return datetime.fromtimestamp(os.stat(str(self._path)).st_atime).strftime(self._date_format)

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

    def _get_mode(self, mode) -> str:
        """
        if mode is 'r' return 'r+' or 'r+b' else mode is 'w' return 'w+' or 'w+b'
        """
        return f'{mode}+b' if self._is_byte else f'{mode}+'

    def load(self, mode=None, **kwargs) -> Any:
        if self._path.suffix in self._dont_read:
            logger.warning(f"I can't read this file. See class attribute <{self.__name__}._dont_read>")
            return
        mode = mode or self._get_mode('r')
        assert 'r' in mode, f"{mode} for read isn't valid."
        try:
            with open(self._path.path, mode=mode, **kwargs) as fp:
                return self.parse(fp.read())
        except PermissionError as err:
            logger.error(err)
            return
        except Exception as err:
            raise IOError(f"{err}\nError when trying to read the file {self._path}")

    def _save(self, data, on_new_path: Union[str, Path] = None, mode=None, exist_ok=False, overwrite=False, **kwargs):
        if (self._last_update is not None and overwrite is False) and not self._is_deleted:
            if self._last_update != self.updated_at:
                raise AssertionError(f"File change detected (last change {self.updated_at}), if you want to overwrite "
                                     f"set overwrite=True")
        if on_new_path is not None:
            self.set_path(on_new_path)
        assert exist_ok or not self.path.exists, FileExistsError(
                "File exists. If you want override, please send 'exist_ok=True'")
        assert self._only_read is False, f"{self.name} is only read."
        mode = mode or self._get_mode('w')
        assert 'w' in mode, f"{mode} for write isn't valid."
        with open(self._path, mode=mode, **kwargs) as fp:
            fp.write(data)
        # TODO: delete file if error

    def delete(self):
        self._path.rm()
        self._is_deleted = True

    def set_path(self, path_):
        self._path = Path(path_)

    def undo(self):
        if self._current_change > 0:
            index = -2 if self._current_change == len(self._change_history) else -1
            self._select_change(index)

    def redo(self):
        if self._current_change < len(self._change_history):
            self._select_change(+1)


class _GenericFile(_FileIO):
    _is_byte: bool = True
    _only_read = False

    @property
    def lines(self):
        if isinstance(self._data, bytes):
            return self._data.splitlines()
        return [self._data]

    def save(self, *args, **kwargs):
        super()._save(self._data, **kwargs)

    def parse(self, data: Union[str, bytes]) -> bytes:
        return data


class _TxtIO(_FileIO):
    _is_byte: bool = False
    _only_read = False

    def parse(self, data: Union[str, bytes, list, tuple, int, float, complex]) -> List[Union[str, int, float, complex]]:
        if isinstance(data, (str, bytes)):
            return [literal_eval(i) for i in data.splitlines()]
        if isinstance(data, (int, float, complex)):
            return [data]
        elif isinstance(data, (list, tuple)):
            return data
        else:
            raise TypeError(f"{type(data)} isn't valid")

    def save(self, *args, **kwargs):
        super()._save(self.string, **kwargs)

    @property
    def string(self):
        return '\n'.join((str(i) for i in self.data))


class _JsonIO(_FileIO):
    _is_byte: bool = False
    _only_read = False

    def parse(self, data: Union[str, bytes, dict]) -> dict:
        if isinstance(data, (bytes, str)):
            return json.loads(data)
        elif isinstance(data, dict):
            return data
        else:
            raise TypeError(f"{type(data)} isn't valid.")

    def save(self, *args, **kwargs):
        super()._save(json.dumps(self._data, indent=True), **kwargs)


class _Mp4IO(_FileIO):
    _is_byte: bool = True
    _only_read = True

    def save(self, *args, **kwargs):
        super()._save(self._data)

    def parse(self, data: Union[str, bytes]) -> bytes:
        return data


class _CsvIO(_FileIO):
    _is_byte: bool = False
    _only_read = False
    _fieldnames = ()

    def _replace(self, value):
        return value.replace('[', '').replace(']', '').replace(' ', '').replace("'",
                                                                                '').replace(
                '"', '')

    def save(self, **kwargs):
        fields = self._replace(str(list(self._fieldnames))) + '\n'
        super()._save(
                fields + '\n'.join((self._replace(str(i)) for i in self.data)),
                **kwargs)

    @property
    def cols(self):
        return self._fieldnames

    @property
    def n_cols(self):
        return len(self._fieldnames)

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

    def parse(self, data: Union[str, bytes]) -> Any:
        data = data.splitlines()
        self._fieldnames = data.pop(0).split(',')
        return list(map(lambda r: self._ast(r.split(',')), data))

    def to_dict(self):
        return dict(zip(self.cols, get_cols(self.data)))

    def flatten(self):
        return flatten(self._data)

    def shape(self):
        return get_shape(self._data)

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


class FileIO:
    # ext: [ext_class, kwargs] *kwargs send to __builtin__ open
    __ext_supported = {'.txt':  (_TxtIO, {}),
                       '.json': (_JsonIO, {}),
                       '.mp4':  (_Mp4IO, {}),
                       '.csv':  (_CsvIO, {})
                       }

    def __new__(cls, path_, **kwargs):
        raise Exception(f"Cannot instantiate {cls.__name__}, use the methods ['create', 'load', 'load_files']")

    @classmethod
    def create(cls, path_: Union[Type[Path], str], data: Any) -> _IFileIO:
        path_ = Path(path_)
        klass, klass_kwargs = cls.__ext_supported.get(path_.suffix, [_GenericFile, {}])
        return klass(path_=path_, data=data, creation_mode=True)

    @classmethod
    def load(cls, path_: Union[str, Path], **kwargs) -> _IFileIO:
        path_ = Path(path_)
        if not path_.exists:
            raise FileNotFoundError(f"{path_.path} not found.")
        klass, klass_kwargs = cls.__ext_supported.get(path_.suffix, [_GenericFile, {}])
        klass_kwargs.update(kwargs)
        return klass(path_=path_, **klass_kwargs)

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


if __name__ == '__main__':
    files = FileIO.load('C:/Users/leite/Downloads/LZvTCUd3YgDhQprErnQV_0.61.csv')
    files.save(exist_ok=True)
