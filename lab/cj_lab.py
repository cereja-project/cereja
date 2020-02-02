import itertools
import operator
from typing import TypeVar, Sequence, List, Any, Generator

from cereja.common import flatten, get_shape
from cereja.decorators import time_exec
from cereja.utils import set_log_level

T = TypeVar('T')


class Vector(list):
    """
    -- Development proposal --
    Vector is a dynamic array, whose size can be increased and can store any type of objects

    """

    def __init__(self, values):
        super().__init__(values)
        self._size = len(self.flatten())
        self._shape = get_shape(self)

    @property
    def size(self):
        # Need to create smart way to check changes
        return self._size

    @property
    def shape(self):
        # need to create smart way to check changes
        return self._shape

    def first(self) -> T:
        return self[0]

    def flatten(self):
        return flatten(self)


class Matrix(object):
    def __init__(self, values):
        self.values = values
        self.shape = get_shape(values)
        self.cols = self._get_cols()
        self._n_max_repr = min(50, len(values))

    def __iter__(self):
        return iter(self.to_list())

    def __len__(self):
        return len(self.to_list())

    def __repr(self):
        values = self.to_list()[:self._n_max_repr]
        if len(self.shape) <= 1:
            return values
        return '\n      '.join(
            f'{val}' for i, val in enumerate(values) if i <= self._n_max_repr)

    def __repr__(self):
        if len(self.values) >= 50:
            dott = f"""
            .
            .
            .
            """
            msg_max_display = f"\n\ndisplaying {self._n_max_repr} of {len(self.values)} lines"
        else:
            msg_max_display = ''
            dott = ''
        return f"{self.__class__.__name__}({self.__repr()}{dott}){msg_max_display}"

    def __getattribute__(self, item):
        obj = object.__getattribute__(self, item)
        if isinstance(obj, list):
            return Matrix(obj)
        return obj

    def to_list(self):
        return object.__getattribute__(self, 'values')

    def __getitem__(self, slice_):
        if isinstance(slice_, int):
            result = self.to_list()[slice_]
            if isinstance(result, int):
                return result
            return Matrix(result)
        if isinstance(slice_, tuple):
            slice_1, slice_2 = slice_
            values = Matrix(self.to_list()[slice_1])
            if isinstance(slice_2, int):
                if len(values.shape) <= 1:
                    return values[slice_2]
                return values.cols[slice_2]
            if not any((slice_2.start, slice_2.step, slice_2.stop)) or len(values.shape) <= 1:
                return values[slice_2]
            if values.cols:
                return values.cols[slice_2].cols
            return values.values[slice_2]
        return Matrix(self.to_list()[slice_])

    def _get_cols(self):
        obj = self.to_list()
        shape = self.shape
        if len(shape) <= 1:
            return [obj]
        return list(map(list, itertools.zip_longest(*obj)))

    def dot(self, b):
        b = Matrix(b)
        if not len(b.shape) == 1:
            assert self.shape[-1] == b.shape[-2], f'Number of columns {self.shape[-1]} != number of rows {b.shape[-2]}'
            return Matrix([[dotproduct(line, col) for col in b.cols] for line in self])
        return Matrix([dotproduct(line, col) for col in b.cols for line in self])


def get_cols(sequence: Sequence):
    lines, cols = get_shape(sequence)
    return [[sequence[i][j] for i in range(lines)] for j in range(cols)]


def dotproduct(vec1, vec2):
    return sum(map(operator.mul, vec1, vec2))


def dot(a, b):
    shape_a = get_shape(a)
    shape_b = get_shape(b)
    assert shape_a[-2] == shape_b[-1]
    return [[dotproduct(line, col) for col in get_cols(b)] for line in a]


if __name__ == '__main__':
    pass
