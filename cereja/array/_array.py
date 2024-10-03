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
import operator
import random
import statistics
import math
from functools import reduce
from itertools import chain
from typing import Any, Sequence, Tuple, Union, List, Optional
import copy
from cereja.config.cj_types import Number, Shape
import logging

__all__ = [
    "Matrix",
    "array_gen",
    "array_randn",
    "flatten",
    "get_cols",
    "get_shape",
    "is_empty",
    "rand_n",
    "rand_uniform",
    "remove_duplicate_items",
    "reshape",
    "shape_is_ok",
    "dot",
    "dotproduct",
    "determinant",
    "div",
    "sub",
    "prod",
    "reshape",
    "get_min_max",
    "apply_proportional_mask",
]

from ..utils import is_iterable, is_sequence, is_numeric_sequence, chunk, dict_to_tuple
from ..utils.decorators import time_exec

logger = logging.getLogger(__name__)


def shape_is_ok(
        sequence: Union[Sequence[Any], Any]
) -> bool:
    """
    Check the number of items the array has and compare it with the shape product
    """
    try:
        expected_shape = get_shape(sequence)
        sequence_len = len(flatten(sequence))
    except Exception as err:
        logger.debug(f"Error when trying to compare shapes. {err}")
        return False
    return prod(expected_shape) == sequence_len


def is_empty(sequence: Sequence) -> bool:
    if is_sequence(sequence):
        try:
            sequence[0]
        except:
            return True
    return False


def get_shape(sequence: Sequence) -> Tuple[Union[int, None], ...]:
    """
    Get the shape (dimensions and sizes) of a nested sequence (like a list or tuple).

    If the sequence is empty or not uniform (e.g., sub-sequences have different lengths),
    returns None for the dimension(s) where uniformity breaks.

    Parameters:
    sequence (Sequence): A sequence of values, possibly nested.

    Returns:
    Tuple[Union[int, None], ...]: A tuple representing the size of each dimension of the sequence.
    """
    if not sequence if not type(sequence).__name__ == "ndarray" else len(sequence) == 0:
        return (None,)

    shape = []
    while is_sequence(sequence) and not is_empty(sequence):
        shape.append(len(sequence))
        sequence = sequence[0] if len(sequence) else None

    return tuple(shape)


def reshape(sequence: Sequence, shape):
    sequence = flatten(sequence)

    expected_size = prod(shape)
    current_size = len(sequence)

    assert (
            current_size == expected_size
    ), f"cannot reshape array of size {current_size} into shape {shape}"
    for batch in shape[::-1]:
        sequence = chunk(sequence, batch_size=batch)
    return sequence[0]


def array_gen(
        shape: Tuple[int, ...], v: Union[Sequence[Any], Any] = None
) -> List[Union[float, Any]]:
    """
    Generates array based on passed shape

    e.g:
    >>> array_gen(shape=(2, 2, 3))
    [[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]], [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]]

    >>>array_gen(shape=(1, 3, 2, 1, 1))
    [[[[[0.0]], [[0.0]]], [[[0.0]], [[0.0]]], [[[0.0]], [[0.0]]]]]

    >>> array_gen(shape=(2, 1, 1),v=['hail','pythonics!'])
    [[['hail']], [['pythonics!']]]

    >>> shape = (2, 1, 1)
    >>> array_gen(shape, v = flatten(array_randn(shape)))
    [[[0.43022826643029777]], [[0.5697717335697022]]]

    :param shape: it's the shape of array
    :param v: sequence or Any obj that allows insertion of values
    :return: Sequence -> List[Union[float, Any]]
    """

    is_seq = is_sequence(v)

    allow_reshape = shape_is_ok(v) and is_seq

    if not is_seq:
        v = [v if v else 0.0]

    for k in shape[::-1]:
        if allow_reshape:
            v = chunk(v, batch_size=k)
            continue
        v = [v * k]
    return v[0]


def flatten2(
        sequence: Union[Sequence[Any], "Matrix"],
        depth: Optional[int] = -1,
        return_shapes=False,
        **kwargs,
) -> Union[List[Any], Any]:
    """
    Receives values, whether arrays of values, regardless of their shape and flatness

    :param return_shapes: should return the shapes of the original values?
    :param sequence: Is sequence of values.
    :param depth: allows you to control a max depth, for example if you send a
    sequence=[1,2, [[3]]] and depth=1 your return will be [1, 2, [3]].
    :return: flattened array

    # thanks https://github.com/rickards

    e.g usage:

    >>> sequence = [[1, 2, 3], [], [[2, [3], 4], 6]]
    >>> flatten(sequence)
    [1, 2, 3, 2, 3, 4, 6]
    >>> flatten(sequence, depth=2)
    [1, 2, 3, 2, [3], 4, 6]
    """
    if isinstance(sequence, dict):
        sequence = dict_to_tuple(sequence)
    else:
        assert is_sequence(sequence), f"Invalid value {sequence}"

    depth = kwargs.get("max_recursion") or depth

    if not isinstance(depth, int):
        raise TypeError(
                f"Type {type(depth)} is not valid for max depth. Please send integer."
        )

    flattened = []
    i = 0
    jump = len(sequence)
    deep = 0
    deep_counter = {deep: jump}
    shapes = {deep: [jump]}
    while i < len(sequence):
        element = sequence[i]
        if is_sequence(element) and (depth == -1 or depth > deep):
            jump = len(element)
            deep += 1
            deep_counter[deep] = deep_counter.get(deep, 0) + jump
            shapes[deep] = shapes.get(deep, []) + [jump]
            sequence = list(element) + list(sequence[i + 1:])
            if jump == 0:
                deep -= 1
            i = 0
        else:
            flattened.append(element)
            deep_counter[deep] -= 1
            i += 1
            if i >= jump:
                for d in range(deep, 0, -1):
                    if deep_counter[d] == 0:
                        deep_counter[d - 1] -= 1
                        deep -= 1
                    else:
                        break

    if return_shapes:
        return flattened, shapes
    return flattened


def flatten(
        sequence: Union[Sequence[Any], "Matrix"],
        depth: Optional[int] = -1,
        return_shapes=False,
        **kwargs,
) -> Union[List[Any], Any]:
    """
    Receives values, whether arrays of values, regardless of their shape and flatness

    :param return_shapes: should return the shapes of the original values?
    :param sequence: Is sequence of values.
    :param depth: allows you to control a max depth, for example if you send a
    sequence=[1,2, [[3]]] and depth=1 your return will be [1, 2, [3]].
    :return: flattened array

    # thanks https://github.com/rickards

    e.g usage:

    >>> sequence = [[1, 2, 3], [], [[2, [3], 4], 6]]
    >>> flatten(sequence)
    [1, 2, 3, 2, 3, 4, 6]
    >>> flatten(sequence, depth=2)
    [1, 2, 3, 2, [3], 4, 6]
    """
    if isinstance(sequence, dict):
        sequence = list(dict_to_tuple(sequence))
    elif isinstance(sequence, (tuple, set)):
        sequence = list(sequence)
    else:
        assert is_sequence(sequence), f"Invalid value to sequence"

    try:
        sequence = sequence.copy()
    except:
        raise Exception(f"Invalid value to sequence")
    depth = kwargs.get("max_recursion") or depth

    if not isinstance(depth, int):
        raise TypeError(
                f"Type {type(depth)} is not valid for max depth. Please send integer."
        )

    def _iter(seq_, take_shapes=False):
        _has_sequence = False
        len_seqs = []
        for n, i in enumerate(seq_):
            if is_sequence(i):
                _has_sequence = True
                if take_shapes:
                    len_seqs.append(len(i))
                continue
            else:
                seq_[n] = [i]
        return list(chain.from_iterable(seq_)), _has_sequence, len_seqs

    deep = 0
    shapes = {deep: [len(sequence)]}
    while deep < depth or depth == -1:
        try:
            sequence, has_sequence, shape = _iter(sequence, take_shapes=return_shapes)
        except TypeError:
            sequence, has_sequence, shape = _iter(sequence, take_shapes=return_shapes)
        deep += 1
        if return_shapes:
            shapes[deep] = shape
        if not any(map(is_sequence, sequence)):
            break
    return (sequence, shapes) if return_shapes else sequence


def rand_uniform(_from: Number, to: Number):
    return _from + (to - _from) * random.random()


def rand_n(
        _from: Number = 0.0, to: Number = 1.0, n: int = 1
) -> Union[float, List[float]]:
    """
    All values ​​are random and their sum is equal to 1 (default) or the value sent in parameter (to)

    :param _from: start in number
    :param to: stop in number
    :param n: n is length of array
    :return: Sequence of floats

    >>> array = rand_n(_from = 10, to=15, n = 3)
    [13.638625715965802, 1.3384682252134166, 0.022906058820781894]

    >>>sum(flatten(array))
    15
    """
    assert isinstance(n, int) is True, "ValueError: n: int is a integer value."
    assert (
            _from < to
    ), "please send a valid range. The first value must not be greater than the second"

    _to = to
    values = [rand_uniform(_from, to) / n]
    n = n - 1

    if not n:
        return values[0]  # if n was not sent

    while n:
        to = to - values[-1]
        values.append(rand_uniform(_from, to) / n)
        n -= 1

    # recover to value
    to = _to
    # ensures that the sum of all values ​​is equal to b
    values[-1] = to - sum(values[:-1])
    return values


def array_randn(shape: Tuple[int, ...], *args, **kwargs) -> List[Union[float, Any]]:
    """
    Responsible for creating matrix in the requested form. All values ​​are random and their sum is equal to 1 (
    default) or the value sent in parameter (to)

    :param shape: it's the shape of array
    :param args: Arguments that will be passed on to the auxiliary function rand_n:
                _from: Number = 0.,
                to: Number = 1.,
                n: int = 1
    :return: array with shape that you _requests

    e.g:

    >>> array = array_randn((1,2,3,4))
    [[[[0.2592981659911938, -0.12315716616964649, 0.82133729291841,
    -0.25879078816834644], [1.3629594254754838, -3.774314741021747, 5.274492839788345, -11.601343746754297],
    [3.604096666087614, -27.650903465459855, 19.296830893462964, -58.83686412036615]], [[69.41859240028415,
    -179.33687885859996, 361.42747499197384, -610.1513132786013], [1072.0398936663296, -894.6318240273097,
    1448.8891836211283, -4183.174313279926], [8139.152167926057, -12466.659181206918, 24595.19100297986,
    -17279.53844619006]]]]

    >>>sum(flatten(array))
    1.0

    >>> cj_randn = array_randn((4,4), _from = 0, to = 20)
    [[10.290409563999265, -10.551079712904698, 2.901380773471479, -27.545318358270105], [11.611327651418236,
    -29.461575728235626, 108.82486378444688, -72.92672196142121], [166.27689950355855, -400.36353360213354,
    575.2273799798464, -1362.4824677079241], [2689.652915457324, -4310.834087972777, 4834.662753875761,
    -2165.28314554616]]

    >>> sum(flatten(cj_randn))
    20.0

    """
    rand_n_values = rand_n(*args, n=prod(shape), **kwargs)
    return array_gen(shape=shape, v=rand_n_values)


def remove_duplicate_items(items: Optional[list]) -> Any:
    """
    remove duplicate items in an item list or duplicate items list of list

    e.g usage:
    >>> remove_duplicate_items([1,2,1,2,1])
    [1, 2]
    >>> remove_duplicate_items(['hi', 'hi', 'ih'])
    ['hi', 'ih']

    >>> remove_duplicate_items([['hi'], ['hi'], ['ih']])
    [['hi'], ['ih']]
    >>> remove_duplicate_items([[1,2,1,2,1], [1,2,1,2,1], [1,2,1,2,3]])
    [[1, 2, 1, 2, 1], [1, 2, 1, 2, 3]]
    """
    # TODO: improve function
    if not is_iterable(items) or isinstance(items, str):
        raise TypeError("Send iterable except string.")

    try:
        return list(dict.fromkeys(items))
    except TypeError:
        return sorted(
                [list(item) for item in set(tuple(x) for x in items)], key=items.index
        )


def get_cols(sequence: Union[Sequence, "Matrix"]):
    return list(zip(*sequence))


def prod(sequence: Sequence[Number], start=1) -> Number:
    """
    Calculate the product of all the elements in the input iterable.

    The default start value for the product is 1.

    This function is intended specifically for use with numeric values and may
    reject non-numeric types.

    :param sequence: Is a sequence of numbers.
    :param start: is a number
    :return:
    """
    if hasattr(math, "prod"):
        # New in Python 3.8
        return math.prod(sequence, start=start)
    # alternative for Python < 3.8
    if not is_sequence(sequence):
        raise TypeError(
                f"Value of {sequence} is not valid. Please send a numeric list."
        )

    return reduce((lambda x, y: x * y), [start, *sequence])


def sub(sequence: Sequence[Number]) -> Number:
    if not is_sequence(sequence):
        raise TypeError(
                f"Value of {sequence} is not valid. Please send a numeric list."
        )

    return reduce((lambda x, y: x - y), sequence)


def _div(a, b):
    if not isinstance(a, (int, float)) and not isinstance(b, (int, float)):
        temp_res = []
        for _a, _b in zip(a, b):
            temp_res.append(_div(_a, _b))
        return temp_res
    return a / b


def div(sequence: Sequence[Number]) -> Number:
    if not is_sequence(sequence):
        raise TypeError(
                f"Value of {sequence} is not valid. Please send a numeric list."
        )

    return reduce(_div, sequence)


def dotproduct(vec1, vec2):
    return sum(map(operator.mul, vec1, vec2))


def dot(a, b):
    shape_a = get_shape(a)
    shape_b = get_shape(b)
    assert shape_a[-2] == shape_b[-1]
    return [[dotproduct(line, col) for col in get_cols(b)] for line in a]

def determinant(sequence: Sequence[Union[Sequence[Number], "Matrix"]]) -> Number:
    """
    Calculate the determinant of a square matrix.

    This function is inteded specifically for use with an (nxn) martix
    and may reject non-square matricies

    :param matrix: Is an (nxn) matrix of numbers
    :return:
    """
    assert(
        len(get_shape(sequence)) == 2 and get_shape(sequence)[0] == get_shape(sequence)[1]
    ), f"Matrix: {sequence} is not (nxn), please provide a square matrix."
    if len(sequence) == 2:
        return sequence[0][0] * sequence[1][1] - sequence[0][1] * sequence[1][0]
    det = 0
    for c in range(len(sequence)):
        sub_matrix = [row[:c] + row[c+1:] for row in sequence[1:]]
        det += ((-1) ** c) * sequence[0][c] * determinant(sub_matrix)
    return det

def get_min_max(values: List[Any]) -> Tuple[Any, ...]:
    if not values or len(values) == 0:
        raise ValueError("values must have at least one element")

    result = []
    try:
        shape = get_shape(values)
        if len(shape) > 1:
            values_ = flatten(values, depth=len(shape) - 2)
            for i in range(shape[-1]):
                result.append((min(values_, key=lambda val: val[i])[i], max(values_, key=lambda val: val[i])[i]))
            return tuple(result)
        return min(values), max(values)
    except Exception as err:
        raise ValueError(f"Error when trying to get min and max values. {err}")


def apply_proportional_mask(
        positions: List[Tuple[int, int]],
        mask_size: Tuple[int, int],
        original_size: Optional[Tuple[int, int]] = None
) -> List[List[int]]:
    """
    Applies a proportional mask to a list of positions and returns an array (list of lists) representing the mask,
    where each index of the main list corresponds to a row.

    Args:
        positions (List[Tuple[int, int]]): List of tuples representing positions (x, y) on the original scale.
        mask_size (Tuple[int, int]): Mask size (columns, rows), where columns is the number of columns and rows is
                                     the number of rows.
        original_size (Optional[Tuple[int, int]]): Original image size (width, height). If not provided, it will be
                                                   calculated based on positions.

    Returns:
        List[List[int]]: Matrix resulting from the proportional application of the mask, where each index represents a row.
    """

    # If original_size is not given, calculate based on positions
    min_x, max_x, min_y, max_y = 0, 0, 0, 0
    if original_size is None:
        (min_x, max_x), (min_y, max_y) = get_min_max(positions)
        original_width = max_x - min_x
        original_height = max_y - min_y
    else:
        original_width, original_height = original_size

    mask_cols, mask_rows = mask_size

    # Initialize the array with zeros
    matrix = [[0 for _ in range(mask_cols)] for _ in range(mask_rows)]

    # Calculate scale factors for columns and rows
    scale_x = mask_cols / original_width
    scale_y = mask_rows / original_height

    # Fill the matrix based on the scaled positions
    for x, y in positions:
        # Adjust position to new coordinate system if necessary
        if original_size is None:
            x -= min_x
            y -= min_y

        scaled_x = int(x * scale_x)
        scaled_y = int(y * scale_y)

        if 0 <= scaled_x < mask_cols and 0 <= scaled_y < mask_rows:
            matrix[scaled_y][scaled_x] = 1

    return matrix


class Matrix(object):
    """
    Matrix is ​​a tool similar to the numpy array
    TODO: add documentation for all class
    """

    def __init__(self, values):
        self.values = values
        self.shape = get_shape(values)
        self.cols = self._get_cols()
        self._n_max_repr = min(50, len(values))

    def __iter__(self):
        return iter(self.to_list())

    def __eq__(self, other):
        return flatten(self) == flatten(other)

    def __len__(self):
        return len(self.to_list())

    def __matmul__(self, other):
        return self.dot(other)

    def __add__(self, other):
        assert self.shape == get_shape(other), "the shape must be the same"
        if len(self.shape) == 1:
            return Matrix([sum(t) for t in zip(self, other)])
        else:
            return Matrix([list(map(sum, zip(*t))) for t in zip(self, other)])

    def __sub__(self, other):
        if is_numeric_sequence(other):
            assert self.shape == get_shape(other), "the shape must be the same"
            if len(self.shape) == 1:
                return Matrix([sub(t) for t in zip(self, other)])
            else:
                return Matrix([list(map(sub, zip(*t))) for t in zip(self, other)])
        return Matrix(
                array_gen(self.shape, list(map(lambda x: x - other, self.flatten())))
        )

    def __mul__(self, other):
        return Matrix(
                array_gen(self.shape, list(map(lambda x: x * other, self.flatten())))
        )

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if isinstance(other, (float, int)):
            other = Matrix(array_gen(self.shape, other))
        assert self.shape == get_shape(other), "the shape must be the same"
        if len(self.shape) == 1:
            result = Matrix([div(t) for t in zip(self, other)])
        else:
            result = Matrix([list(map(div, zip(*t))) for t in zip(self, other)])
        assert self.shape == result.shape, "the shape must be the same"
        return result

    def __iadd__(self, other):
        return Matrix(list(map(lambda x: x + other, self.flatten())))

    def __getitem__(self, slice_):
        if isinstance(slice_, int):
            result = self.to_list()[slice_]
            if isinstance(result, (float, int)):
                return result
            return Matrix(result)
        if isinstance(slice_, tuple):
            slice_1, slice_2 = slice_
            values = Matrix(self.to_list()[slice_1])
            if isinstance(slice_2, int):
                if len(values.shape) <= 1:
                    return values[slice_2]
                return values.cols[slice_2]
            if (
                    not any((slice_2.start, slice_2.step, slice_2.stop))
                    or len(values.shape) <= 1
            ):
                return values[slice_2]
            if values.cols:
                return values.cols[slice_2].cols
            return values.values[slice_2]
        return Matrix(self.to_list()[slice_])

    def __repr__(self):
        if len(self.values) >= 50:
            dott = f"""
            .
            .
            .
            """
            msg_max_display = (
                f"\n\ndisplaying {self._n_max_repr} of {len(self.values)} lines"
            )
        else:
            msg_max_display = ""
            dott = ""
        return f"{self.__class__.__name__}({self.__repr()}{dott}){msg_max_display}"

    def __getattribute__(self, item):
        obj = object.__getattribute__(self, item)
        if isinstance(obj, list):
            return Matrix(obj)
        return obj

    def std(self):
        return statistics.pstdev(self.flatten())

    def sqrt(self):
        return Matrix(list(map(math.sqrt, self.flatten()))).reshape(self.shape)

    def copy(self):
        return copy.copy(self)

    def __repr(self):
        values = self.to_list()[: self._n_max_repr]
        if len(self.shape) <= 1:
            return values
        return "\n      ".join(
                f"{val}" for i, val in enumerate(values) if i <= self._n_max_repr
        )

    def to_list(self):
        return object.__getattribute__(self, "values")

    def _get_cols(self):
        if len(self.shape) > 1:
            return get_cols(self)
        return self.to_list()

    def dot(self, b):
        b = Matrix(b)
        n_cols = -1 if len(b.shape) == 1 else -2
        assert (
                self.shape[-1] == b.shape[n_cols]
        ), f"Number of columns {self.shape[-1]} != number of rows {b.shape[n_cols]}"
        if not len(b.shape) == 1:
            return Matrix([[dotproduct(line, col) for col in b.cols] for line in self])
        return Matrix([dotproduct(line, col) for col in b.cols for line in self])

    def flatten(self):
        return Matrix(flatten(self))

    def mean(self):
        flattened = self.flatten()
        return sum(flattened) / len(flattened)

    def reshape(self, shape: Shape):
        return Matrix(reshape(self, shape))
    
    def determinant(self):
        return Matrix(determinant(self))

    @staticmethod
    def arange(*args):
        return Matrix(list(range(*args)))

    def argmax(self):
        flattened = self.flatten()
        return flattened.to_list().index(max(flattened))
