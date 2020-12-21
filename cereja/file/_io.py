import logging
import os
from abc import ABCMeta, abstractmethod
from datetime import datetime
from typing import Any, List, Union, Type
import json
from cereja import Path

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

    @abstractmethod
    def load(self, *args, **kwargs) -> Any:
        pass

    @abstractmethod
    def save(self, *args, **kwargs):
        pass

    @abstractmethod
    def parse(self, data: Union[str, bytes]) -> Any:
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

    @property
    def updated_at(self):
        return datetime.fromtimestamp(os.stat(str(self.path)).st_mtime).strftime(self._date_format)

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
        return self._data

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

    def load(self, *args, mode=None, **kwargs) -> Any:
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

    def delete(self):
        self._path.rm()
        self._is_deleted = True

    def set_path(self, path_):
        self._path = Path(path_)


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
            return data.splitlines()
        if isinstance(data, (int, float, complex)):
            return [data]
        elif isinstance(data, (list, tuple)):
            return data
        else:
            raise TypeError(f"{type(data)} isn't valid")

    def save(self, *args, **kwargs):
        super()._save('\n'.join(self.data))


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


class FileIO:
    # ext: [ext_class, kwargs] *kwargs send to __builtin__ open
    __ext_supported = {'.txt':  (_TxtIO, {}),
                       '.json': (_JsonIO, {}),
                       '.mp4':  (_Mp4IO, {}),
                       }

    def __new__(cls, path_, **kwargs):
        raise Exception(f"Cannot instantiate {cls.__name__}, use the methods ['create', 'load', 'load_files']")

    @classmethod
    def create(cls, path_: Union[Type[Path], str], data: Any) -> _IFileIO:
        pass

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
    files = FileIO.load('C:/Users/leite/Downloads/tokenizador - Copia.json')
    files.save()
    input()
