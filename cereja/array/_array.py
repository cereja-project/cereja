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
from cereja.config.cj_types import T_NUMBER, T_SHAPE
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

from .. import check_type_on_sequence
from ..utils import is_iterable, is_sequence, is_numeric_sequence, chunk, dict_to_tuple

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


def reshape(sequence: Sequence,
            shape):
    sequence = flatten(sequence)

    expected_size = prod(shape)
    current_size = len(sequence)

    if current_size != expected_size:
        raise ValueError(f"cannot reshape array of size {current_size} into shape {shape}")
    for batch in shape[::-1]:
        sequence = chunk(sequence, batch_size=batch)
    return sequence[0]


def array_gen(
        shape: Tuple[int, ...],
        v: Union[Sequence[Any], Any] = None
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


def flatten(
        sequence: Union[Sequence[Any], "Matrix"],
        depth: Optional[int] = -1,
        return_shapes=False,
        **kwargs,
) -> Union[List[Any], Any]:
    """
    Flattens arrays of values regardless of their shape and depth.

    This function recursively flattens nested sequences to a specified depth level,
    with support for various sequence types including lists, tuples, sets, and custom
    objects with 'tolist' or 'to_list' methods (like numpy arrays or Matrix objects).

    Args:
        sequence: The sequence of values to be flattened. Can be a nested list, tuple,
            set, Matrix object, or any object with 'tolist'/'to_list' methods.
        depth: Maximum flattening depth. -1 means completely flatten (default).
            A value of 0 returns the original sequence, 1 flattens one level, etc.
        return_shapes: If True, returns a tuple containing both the flattened array
            and a dictionary mapping depth levels to the shapes at each level.
        **kwargs: Additional keyword arguments. Supports 'max_recursion' as an
            alias for the depth parameter.

    Returns:
        Union[List[Any], Tuple[List[Any], Dict[int, List[int]]]]: If return_shapes
            is False, returns the flattened list. If True, returns a tuple containing
            the flattened list and a dictionary of shapes at each depth level.

    Raises:
        AssertionError: If the sequence is not a valid sequence type.
        TypeError: If depth is not an integer value.
        Exception: If the sequence cannot be copied.

    Examples:
        >>> sequence = [[1, 2, 3], [], [[2, [3], 4], 6]]
        >>> flatten(sequence)
        [1, 2, 3, 2, 3, 4, 6]
        >>> flatten(sequence, depth=2)
        [1, 2, 3, 2, [3], 4, 6]
        >>> flatten([[1, 2], [3, 4]], return_shapes=True)
        ([1, 2, 3, 4], {0: [2], 1: [2, 2]})
    """

    # Types that should be treated as sequences
    SEQUENCE_TYPES = (list, tuple, set)
    # Types that should NOT be flattened
    NON_FLATTENABLE = (str, bytes, bytearray, dict)

    # Initial type conversion
    if hasattr(sequence, 'tolist'):
        sequence = sequence.tolist()
    elif hasattr(sequence, 'to_list'):
        sequence = sequence.to_list()
    elif isinstance(sequence, dict):
        sequence = list(dict_to_tuple(sequence))
    elif isinstance(sequence, (tuple, set)):
        sequence = list(sequence)
    elif not isinstance(sequence, SEQUENCE_TYPES):
        raise TypeError(f"Invalid value to sequence: {type(sequence)}")

    try:
        sequence = sequence.copy()
    except:
        raise Exception("Invalid value to sequence")

    depth = kwargs.get("max_recursion") or depth

    if not isinstance(depth, int):
        raise TypeError(
                f"Type {type(depth)} is not valid for max depth. Please send integer."
        )

    deep = 0
    shapes = {deep: [len(sequence)]} if return_shapes else None
    depth_ = len(get_shape(sequence)) - 1 if depth == -1 else depth # max depth to flatten

    while deep < depth or depth == -1:
        result = []
        len_seqs = [] if return_shapes else None
        has_nested = False
        for item in sequence:
            # Direct type checking - much faster than is_sequence
            # Checks if it's a valid sequence (not string, bytes, etc)
            if type(item) in SEQUENCE_TYPES or (
                    hasattr(item, '__iter__') and
                    not isinstance(item, NON_FLATTENABLE)
            ):
                has_nested = True
                if return_shapes:
                    len_seqs.append(len(item))
                result.extend(item)
            else:
                result.append(item)

        sequence = result
        deep += 1

        if return_shapes:
            shapes[deep] = len_seqs

        if deep == depth_:
            # Final check to avoid unnecessary iterations
            if check_type_on_sequence(sequence, (int, float, str, bool, type(None), complex, bytes)):
                break

        # Stop immediately if there are no nested sequences
        if not has_nested:
            break

    return (sequence, shapes) if return_shapes else sequence


def rand_uniform(_from: T_NUMBER,
                 to: T_NUMBER):
    return _from + (to - _from) * random.random()


def rand_n(
        _from: T_NUMBER = 0.0,
        to: T_NUMBER = 1.0,
        n: int = 1
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
    if not isinstance(n, int):
        raise TypeError("n must be an integer value.")
    if _from >= to:
        raise ValueError("please send a valid range. The first value must not be greater than the second")

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


def array_randn(shape: Tuple[int, ...],
                *args,
                **kwargs) -> List[Union[float, Any]]:
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


def prod(sequence: Sequence[T_NUMBER],
         start=1) -> T_NUMBER:
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

    return reduce((lambda x,
                          y: x * y), [start, *sequence])


def sub(sequence: Sequence[T_NUMBER]) -> T_NUMBER:
    if not is_sequence(sequence):
        raise TypeError(
                f"Value of {sequence} is not valid. Please send a numeric list."
        )

    return reduce((lambda x,
                          y: x - y), sequence)


def _div(a,
         b):
    if not isinstance(a, (int, float)) and not isinstance(b, (int, float)):
        temp_res = []
        for _a, _b in zip(a, b):
            temp_res.append(_div(_a, _b))
        return temp_res
    return a / b


def div(sequence: Sequence[T_NUMBER]) -> T_NUMBER:
    if not is_sequence(sequence):
        raise TypeError(
                f"Value of {sequence} is not valid. Please send a numeric list."
        )

    return reduce(_div, sequence)


def dotproduct(vec1,
               vec2):
    return sum(map(operator.mul, vec1, vec2))


def dot(a,
        b):
    shape_a = get_shape(a)
    shape_b = get_shape(b)
    if shape_a[-2] != shape_b[-1]:
        raise ValueError(f"shapes {shape_a} and {shape_b} are not aligned for dot product")
    return [[dotproduct(line, col) for col in get_cols(b)] for line in a]


def determinant(sequence: Sequence[Union[Sequence[T_NUMBER], "Matrix"]]) -> T_NUMBER:
    """
    Calculate the determinant of a square matrix.

    This function is inteded specifically for use with an (nxn) martix
    and may reject non-square matricies

    :param matrix: Is an (nxn) matrix of numbers
    :return:
    """
    shape = get_shape(sequence)
    if not (len(shape) == 2 and shape[0] == shape[1]):
        raise ValueError(f"Matrix: {sequence} is not (nxn), please provide a square matrix.")
    if len(sequence) == 2:
        return sequence[0][0] * sequence[1][1] - sequence[0][1] * sequence[1][0]
    det = 0
    for c in range(len(sequence)):
        sub_matrix = [row[:c] + row[c + 1:] for row in sequence[1:]]
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


class Matrix:
    """
    Matrix manipulation tool similar to numpy array.

    This class provides basic linear algebra and matrix operations,
    including arithmetic operations, dot product, reshape and
    determinant calculation.

    Args:
        values: Sequence of values to initialize the matrix. Can be a
                nested list, tuple, or any iterable sequence.

    Attributes:
        shape: Tuple representing the matrix dimensions.

    Examples:
        >>> m = Matrix([[1, 2], [3, 4]])
        >>> m.shape
        (2, 2)
        >>> m.mean()
        2.5
    """

    # Maximum lines for visual representation
    _MAX_REPR_LINES = 50

    def __init__(self,
                 values):
        """
        Initialize a new Matrix instance.

        Args:
            values: Values to initialize the matrix.

        Raises:
            ValueError: If the provided values do not form a valid matrix.
        """
        self._values = self._validate_values(values)
        self._shape = get_shape(self._values)
        self._cols = None  # Column cache

    @staticmethod
    def _validate_values(values):
        """
        Validate and normalize input values.

        Args:
            values: Values to be validated.

        Returns:
            Normalized list of values.

        Raises:
            ValueError: If the values are not valid.
        """
        if not is_sequence(values):
            raise ValueError("Matrix values must be a valid sequence")
        return list(values) if not isinstance(values, list) else values

    @property
    def values(self):
        """Return the internal matrix values."""
        return self._values

    @property
    def shape(self):
        """Return the shape (dimensions) of the matrix."""
        return self._shape

    @property
    def cols(self):
        """
        Return the matrix columns.

        For one-dimensional matrices, returns the values list itself.
        For multi-dimensional matrices, computes and caches the columns.
        """
        if self._cols is None:
            if len(self._shape) > 1:
                self._cols = get_cols(self._values)
            else:
                self._cols = self._values
        return self._cols

    def __iter__(self):
        """Allow iteration over the matrix elements."""
        return iter(self._values)

    def __eq__(self,
               other):
        """
        Check equality between two matrices.

        Args:
            other: Matrix or sequence to be compared.

        Returns:
            True if the matrices are equal, False otherwise.
        """
        return flatten(self) == flatten(other)

    def __len__(self):
        """Return the number of elements in the first dimension."""
        return len(self._values)

    def __matmul__(self,
                   other):
        """
        Implement the @ operator for matrix multiplication.

        Args:
            other: Matrix to be multiplied.

        Returns:
            New Matrix resulting from the multiplication.
        """
        return self.dot(other)

    def __add__(self,
                other):
        """
        Implement matrix or scalar addition.

        Args:
            other: Matrix, sequence, or scalar value to be added.

        Returns:
            New Matrix with the addition result.

        Raises:
            ValueError: If the matrix shapes are not compatible.
        """
        other_shape = get_shape(other)
        if self._shape != other_shape:
            raise ValueError(
                    f"Cannot add matrices with shapes {self._shape} and {other_shape}"
            )

        if len(self._shape) == 1:
            return Matrix([sum(pair) for pair in zip(self, other)])

        return Matrix([
            [sum(pair) for pair in zip(*rows)]
            for rows in zip(self, other)
        ])

    def __sub__(self,
                other):
        """
        Implement matrix or scalar subtraction.

        Args:
            other: Matrix, sequence, or scalar value to be subtracted.

        Returns:
            New Matrix with the subtraction result.

        Raises:
            ValueError: If the matrix shapes are not compatible.
        """
        if is_numeric_sequence(other):
            other_shape = get_shape(other)
            if self._shape != other_shape:
                raise ValueError(
                        f"Cannot subtract matrices with shapes {self._shape} and {other_shape}"
                )

            if len(self._shape) == 1:
                return Matrix([sub(pair) for pair in zip(self, other)])

            return Matrix([
                [sub(pair) for pair in zip(*rows)]
                for rows in zip(self, other)
            ])

        # Scalar subtraction
        flat_values = [x - other for x in self.flatten()]
        return Matrix(array_gen(self._shape, flat_values))

    def __mul__(self,
                other):
        """
        Element-wise scalar multiplication.

        Args:
            other: Scalar value for multiplication.

        Returns:
            New Matrix with multiplied values.
        """
        flat_values = [x * other for x in self.flatten()]
        return Matrix(array_gen(self._shape, flat_values))

    def __rmul__(self,
                 other):
        """Reverse multiplication (allows scalar * Matrix)."""
        return self.__mul__(other)

    def __truediv__(self,
                    other):
        """
        Element-wise division.

        Args:
            other: Scalar value, Matrix, or sequence.

        Returns:
            New Matrix with the division result.

        Raises:
            ValueError: If the shapes are not compatible.
            ZeroDivisionError: If division by zero occurs.
        """
        if isinstance(other, (float, int)):
            if other == 0:
                raise ZeroDivisionError("Cannot divide by zero")
            other = Matrix(array_gen(self._shape, other))

        other_shape = get_shape(other)
        if self._shape != other_shape:
            raise ValueError(
                    f"Cannot divide matrices with shapes {self._shape} and {other_shape}"
            )

        if len(self._shape) == 1:
            result = Matrix([div(pair) for pair in zip(self, other)])
        else:
            result = Matrix([
                [div(pair) for pair in zip(*rows)]
                for rows in zip(self, other)
            ])

        return result

    def __iadd__(self,
                 other):
        """
        In-place scalar addition.

        Args:
            other: Scalar value to be added.

        Returns:
            New Matrix with summed values.
        """
        flat_values = [x + other for x in self.flatten()]
        return Matrix(array_gen(self._shape, flat_values))

    def __getitem__(self,
                    key):
        """
        Access elements via indexing.

        Args:
            key: Integer index, slice, or tuple of indices/slices.

        Returns:
            Scalar element, Matrix, or sub-matrix.
        """
        if isinstance(key, int):
            result = self._values[key]
            # Return scalar if it's a number
            if isinstance(result, (float, int)):
                return result
            return Matrix(result)

        if isinstance(key, tuple):
            row_index, col_index = key
            row_values = Matrix(self._values[row_index])

            if isinstance(col_index, int):
                if len(row_values.shape) <= 1:
                    return row_values[col_index]
                return row_values.cols[col_index]

            # Column slice
            if not any((col_index.start, col_index.step, col_index.stop)) or \
                    len(row_values.shape) <= 1:
                return row_values[col_index]

            if row_values.cols:
                return Matrix(row_values.cols[col_index]).cols

            return row_values._values[col_index]

        return Matrix(self._values[key])

    def __repr__(self):
        """String representation of the matrix."""
        if len(self._values) >= self._MAX_REPR_LINES:
            preview = self._format_values()
            dots = "\n            .\n            .\n            ."
            footer = f"\n\n[displaying {self._MAX_REPR_LINES} of {len(self._values)} rows]"
            return f"{self.__class__.__name__}({preview}{dots}){footer}"

        preview = self._format_values()
        return f"{self.__class__.__name__}({preview})"

    def _format_values(self):
        """
        Format values for display.

        Returns:
            Formatted string with the matrix values.
        """
        values = self._values[:self._MAX_REPR_LINES]
        if len(self._shape) <= 1:
            return str(values)

        return "\n      ".join(str(val) for val in values)

    def to_list(self):
        """
        Convert the matrix to a native Python list.

        Returns:
            List with the matrix values.
        """
        return self._values

    def flatten(self):
        """
        Return a flattened (1D) version of the matrix.

        Returns:
            New one-dimensional Matrix.
        """
        return Matrix(flatten(self._values))

    def reshape(self,
                shape: T_SHAPE):
        """
        Reshape the matrix to a new form.

        Args:
            shape: Tuple with the new dimensions.

        Returns:
            New Matrix with the specified shape.

        Raises:
            ValueError: If the total number of elements is not compatible.
        """
        return Matrix(reshape(self._values, shape))

    def dot(self,
            other):
        """
        Compute the dot product with another matrix.

        Args:
            other: Matrix or sequence for multiplication.

        Returns:
            New Matrix resulting from the dot product.

        Raises:
            ValueError: If the dimensions are not compatible.
        """
        other = Matrix(other) if not isinstance(other, Matrix) else other
        n_cols = -1 if len(other.shape) == 1 else -2

        if self._shape[-1] != other.shape[n_cols]:
            raise ValueError(
                    f"Cannot multiply: columns {self._shape[-1]} != rows {other.shape[n_cols]}"
            )

        if len(other.shape) == 1:
            return Matrix([
                dotproduct(line, col)
                for col in other.cols
                for line in self
            ])

        return Matrix([
            [dotproduct(line, col) for col in other.cols]
            for line in self
        ])

    def determinant(self):
        """
        Compute the matrix determinant.

        Returns:
            Numeric value of the determinant.

        Raises:
            ValueError: If the matrix is not square.
        """
        return determinant(self._values)

    def mean(self):
        """
        Compute the mean of all elements.

        Returns:
            Mean value of the elements.
        """
        flattened = self.flatten()
        return sum(flattened) / len(flattened)

    def std(self):
        """
        Compute the population standard deviation.

        Returns:
            Standard deviation of the elements.
        """
        return statistics.pstdev(self.flatten())

    def sqrt(self):
        """
        Compute the square root of each element.

        Returns:
            New Matrix with square roots.

        Raises:
            ValueError: If there are negative values.
        """
        sqrt_values = [math.sqrt(x) for x in self.flatten()]
        return Matrix(array_gen(self._shape, sqrt_values))

    def argmax(self):
        """
        Return the index of the maximum value in the flattened matrix.

        Returns:
            Index of the maximum element.
        """
        flattened = self.flatten()
        return flattened.to_list().index(max(flattened))

    def copy(self):
        """
        Create a shallow copy of the matrix.

        Returns:
            New Matrix instance with the same values.
        """
        return copy.copy(self)

    @staticmethod
    def arange(*args):
        """
        Create a matrix from a numeric range.

        Args:
            *args: Arguments passed to range() (start, stop, step).

        Returns:
            New Matrix with sequential values.

        Examples:
            >>> Matrix.arange(5)
            Matrix([0, 1, 2, 3, 4])
            >>> Matrix.arange(1, 10, 2)
            Matrix([1, 3, 5, 7, 9])
        """
        return Matrix(list(range(*args)))
