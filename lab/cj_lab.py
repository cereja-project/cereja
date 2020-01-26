import operator
from typing import TypeVar, Sequence

from cereja.common import flatten, get_shape

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


class Matrix:
    def __init__(self, values):
        self.values = values
        self.shape = cj.get_shape(self.values)

    def __iter__(self):
        return iter(self.values)

    def __repr__(self):
        return f'Matrix({self.values})'

    def _get_col(self, idx, values=None):
        input(idx)
        values = self.values if values is None else values
        return [i[idx] for i in values]

    def __getitem__(self, slice_):
        if isinstance(slice_, int):
            result = self.values[slice_]
            if isinstance(result, int):
                return result
            return Matrix(result)
        if isinstance(slice_, tuple):
            a1, a2 = slice_
            values = self[a1]
            if isinstance(a2, int) or not any((a2.start, a2.step, a2.stop)) or len(values.shape) > 1:
                return values[a2]
            return Matrix(self._get_col(a2, values))
        return Matrix(self.values[slice_])


def get_cols(sequence: Sequence):
    """
    >>>get_cols([[1,2,3],[1,2,3]])
    [[1, 1], [2, 2], [3, 3]]
    :param sequence:
    :return:
    """
    lines, cols = get_shape(sequence)
    return [[sequence[i][j] for i in range(lines)] for j in range(cols)]


def dotproduct(vec1, vec2):
    return sum(map(operator.mul, vec1, vec2))


def dot(a, b):
    shape_a = get_shape(a)
    shape_b = get_shape(b)
    assert shape_a[-2] == shape_b[-1]
    return [[dotproduct(line, col) for col in get_cols(b)] for line in a]


def test_get_cols():
    assert get_cols([[1, 2, 3], [1, 2, 3]]) == [[1, 1], [2, 2], [3, 3]]


def test_dot():
    a = [[1, 2], [3, 4]]
    b = a
    assert dot(a, b) == [[7, 10], [15, 22]]


if __name__ == '__main__':
    a = Matrix([1, 2, 3])
    print(a)
