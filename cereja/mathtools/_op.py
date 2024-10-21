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
import math
from functools import reduce
from typing import Tuple, Union, Sequence

from ..array import flatten, get_shape
from ..utils import is_sequence, chunk
from cereja.config.cj_types import Number

__all__ = [
    "imc",
    "proportional",
    "estimate",
    "percent",
    "theta_angle",
    "distance_between_points",
    "theta_from_array",
    "greatest_common_multiple",
    "least_common_multiple",
    "degrees_to_radian",
    "radian_to_degrees",
    "nth_fibonacci_number",
]


def imc(weight: float, height: float) -> Tuple[float, str]:
    _imc = weight / (height ** 2)
    _imc = _imc if _imc > 0.1 else _imc * 10000  # convert if send in meters.
    if _imc < 18.5:
        grade = "Underweight"
    elif 18.5 <= _imc <= 24.9:
        grade = "Normal weight"
    elif 25 <= _imc <= 29.9:
        grade = "Overweight"
    elif 30 <= _imc <= 34.9:
        grade = "Obesity grade 1"
    elif 35 <= _imc <= 39.9:
        grade = "Obesity grade 2"
    else:
        grade = "Obesity grade 3"
    return _imc, grade


def greatest_common_multiple(values):
    return reduce(math.gcd, values)


def least_common_multiple(values):
    return reduce((lambda x, y: int(x * y / math.gcd(x, y))), values)


def proportional(
        value, old_max_value: Union[float, int], new_max_value: Union[float, int] = 100
):
    return (new_max_value / old_max_value) * value


def estimate(from_: Number, to: Number, based: Number, ndigits=2) -> Number:
    if from_ > 0:
        based = based or 1
        return round((based / from_) * to - based, ndigits)
    return float("NaN")


def percent(from_: Number, to: Number, ndigits=2) -> Number:
    to = to or 1
    return round((from_ / to) * 100, ndigits)


def pow_(x, y=2):
    if not is_sequence(x):
        x = (x,)
    return [math.pow(i, y) for i in x]


def theta_angle(u: Sequence[Number], v: Sequence[Number], degrees=True) -> float:
    """
    Calculates and returns theta angle between two vectors

    e.g usage:
    >>> u = (2,2)
    >>> v = (0, -2)
    >>> theta_angle(u, v)
    135.0
    """
    try:
        cos_theta = sum(an * vn for an, vn in zip(u, v)) / (math.sqrt(sum(pow_(u))) * math.sqrt(sum(pow_(v))))

        acos = math.acos(max(-1., min(1., cos_theta)))
    except ValueError:
        acos = float("NaN")
    return math.degrees(acos) if degrees else acos


def theta_from_array(a, b, degrees=True):
    s = get_shape(a)[-1]
    a = flatten(a)
    b = flatten(b)
    a = chunk(a, s)
    b = chunk(b, s)
    return [theta_angle(u, v, degrees=degrees) for u, v in zip(a, b)]


def distance_between_points(u: Tuple[float, float], v: Tuple[float, float]):
    return math.sqrt(sum(map(lambda x: (x[0] - x[-1]) ** 2, zip(u, v))))


def degrees_to_radian(val):
    return (val * math.pi) / 180.0


def radian_to_degrees(val):
    return (val * 180.0) / math.pi


def nth_fibonacci_number(val:int) -> int:
    """
    Calculates the nth fibonacci number using the golden ratio formula.

    Args:
        val(int): The index (val>0) of the Fibonacci number to calculate
    
    Returns:
        int: The nth Fibonacci number

    Example:
        >>> nth_fibonacci_number(10)
        34
    """
    if val < 1:
        raise ValueError("val should be greater than 0")
    val -= 1 # First Fibonacci number is 0
    phi = (1 + 5**0.5) / 2
    return round(phi**val / 5**0.5)
