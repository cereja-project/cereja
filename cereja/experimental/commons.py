from collections import OrderedDict as _OrderedDict
import random

from cereja.utils import invert_dict, obj_repr

__all__ = ['CJOrderedDict', 'CJDict', 'CJMeta']


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
