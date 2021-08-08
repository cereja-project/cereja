from collections import OrderedDict as _OrderedDict
import random

from cereja.utils import invert_dict, obj_repr

__all__ = ['CJOrderedDict', 'CJDict', 'CJMeta', 'Multiprocess']


class CJMeta(type):
    __attr_limit = 5

    def __new__(mcs, name, bases, dct):
        x = super().__new__(mcs, name, bases, dct)
        x.__repr__ = lambda self: obj_repr(self, attr_limit=CJMeta.__attr_limit)
        return x


class CJOrderedDict(_OrderedDict):

    @property
    def first(self):
        k = next(iter(self))
        return k, self[k]


class CJDict(dict, metaclass=CJMeta):
    """
    Builtin dict class extension.

    What's new?

    methods:
    - item: get a item

    """
    __black_attr_list = dir(dict)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __invert__(self):
        """
        Invert dict values to key
        """
        return CJDict(invert_dict(self))

    def __getattr__(self, item):
        if item in self and item not in self.__black_attr_list:
            return self[item]
        return object.__getattribute__(self, item)

    def item(self, random_=True):
        if random_ is True:
            return random.choice(tuple(self.items()))
        k, v = self.popitem()
        self.update((k, v))
        return k, v


class DictOfList(CJDict):
    def add(self, key, value):
        if key not in self:
            self[key] = []
        self[key].append(value)

    def __setitem__(self, key, value):
        assert isinstance(value, list), "Send a list object"
        super(DictOfList, self).__setitem__(key, value)


import cereja as cj


class Multiprocess:
    _template = """
from multiprocessing import Pool
import cereja as cj

JOB_DIR = cj.Path('{path}')

globals().update(cj.FileIO.load(JOB_DIR.join('global_scope.pkl')).data)

{func_code}

if __name__ == '__main__':
    with Pool({n_proc}) as p:
        sequence = cj.FileIO.load(JOB_DIR.join('sequence.pkl')).data
        result = p.map({func_name}, sequence)
        cj.FileIO.create(JOB_DIR.join('result.pkl'), result).save(exist_ok=True)
    """

    def __init__(self, function, global_scope: dict = None, n_proc=8):
        self.function = function
        self.global_scope = global_scope
        self.n_proc = n_proc

    def run(self, sequence):
        import sys
        with cj.TempDir() as temp_dir:
            func_code = cj.Source(self.function)
            code = self._template.format(path=temp_dir.path, func_code=func_code.source_code, func_name=func_code.name, n_proc=self.n_proc)
            global_scope = self.global_scope if isinstance(self.global_scope, dict) else {}

            code_path = temp_dir.path.join('code.py')
            cj.FileIO.create(code_path, code).save()
            cj.FileIO.create(temp_dir.path.join('global_scope.pkl'), global_scope).save()
            cj.FileIO.create(temp_dir.path.join('sequence.pkl'), sequence).save()
            cj.run_on_terminal(f'{sys.executable} {code_path.path}')
            result = cj.FileIO.load(temp_dir.path.join('result.pkl')).data

        return result
