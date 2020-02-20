class _FileMixin(object):
    _file = None

    @classmethod
    def read_file(cls, path_: str, mode='r', encoding='utf-8', **kwargs):
        with open(path_, mode=mode, encoding=encoding, **kwargs) as fp:
            cls.lines = fp.readlines()
            cls._file = fp
        return cls()


class File(_FileMixin):
    @property
    def lines(self):
        return super().lines


if __name__ == '__main__':
    pass
