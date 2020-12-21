from abc import ABCMeta, abstractmethod, ABC
from typing import Any, List, Union
import json
from cereja import Path


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

    def __init__(self, path_: Path, *args, **kwargs):
        self._path = path_
        self._data = self.load(*args, **kwargs)
        self._ext_without_point = self._path.suffix.strip(".").upper()

    def __init_subclass__(cls, **kwargs):
        for attr in cls._need_implement:
            if getattr(cls, attr) is None:
                raise NotImplementedError(cls._need_implement.get(attr).format(class_name=cls.__name__))

    def __repr__(self):
        return f'{self._ext_without_point}<{self._path.name}>'

    def __str__(self):
        return f'{self._ext_without_point}<{self._path.name}>'

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

    def _get_mode(self, mode) -> str:
        """
        if mode is 'r' return 'r+' or 'r+b' else mode is 'w' return 'w+' or 'w+b'
        """
        return f'{mode}+b' if self._is_byte else f'{mode}+'

    def load(self, *args, mode=None, **kwargs) -> List[str]:
        mode = mode or self._get_mode('r')
        assert 'r' in mode, f"{mode} for read isn't valid."
        with open(self._path, mode=mode, **kwargs) as fp:
            return self.parse(fp.read())

    def _save(self, data, mode=None, **kwargs):
        assert self._only_read is False, f"{self.name} is only read."
        mode = mode or self._get_mode('w')
        assert 'w' in mode, f"{mode} for write isn't valid."
        with open(self._path, mode=mode, **kwargs) as fp:
            fp.write(data)


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

    def parse(self, data: Union[str, bytes]) -> List[str]:
        return data.splitlines()

    def save(self, *args, **kwargs):
        super()._save('\n'.join(self.data))


class _JsonIO(_FileIO):
    _is_byte: bool = False
    _only_read = False

    def parse(self, data: Union[str, bytes]) -> dict:
        return json.loads(data)

    def save(self, *args, **kwargs):
        super()._save(json.dumps(self._data), **kwargs)


class _Mp4IO(_FileIO):
    _is_byte: bool = True
    _only_read = True

    def save(self, *args, **kwargs):
        super()._save(self._data)

    def parse(self, data: Union[str, bytes]) -> bytes:
        return data


class FileIO(_IFileIO, ABC):
    # ext: [ext_class, kwargs] *kwargs send to __builtin__ open
    __ext_supported = {'.txt':  [_TxtIO, {}],
                       '.json': [_JsonIO, {}],
                       '.mp4':  [_Mp4IO, {}],
                       }

    def __new__(cls, path_, *args, **kwargs):
        path_ = Path(path_)
        if not path_.exists:
            raise FileNotFoundError(f"{path_.path} not found.")
        try:
            klass, klass_kwargs = cls.__ext_supported.get(path_.suffix, [_GenericFile, {}])
            klass_kwargs.update(kwargs)
            return klass(path_=path_, **klass_kwargs)
        except Exception:
            raise Exception(f"Error when trying to upload file.")


if __name__ == '__main__':
    pass
