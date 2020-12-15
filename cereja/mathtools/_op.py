import math
from typing import Tuple

from cereja.config.cj_types import Number

__all__ = ['imc', 'proportional', 'estimate', 'percent', 'theta_angle']


def imc(weight: float, height: float) -> Tuple[float, str]:
    _imc = weight / (height ** 2)
    _imc = _imc if _imc > 0.1 else _imc * 10000  # convert if send in meters.
    if _imc < 18.5:
        grade = 'Underweight'
    elif 18.5 <= _imc <= 24.9:
        grade = 'Normal weight'
    elif 25 <= _imc <= 29.9:
        grade = 'Overweight'
    elif 30 <= _imc <= 34.9:
        grade = 'Obesity grade 1'
    elif 35 <= _imc <= 39.9:
        grade = 'Obesity grade 2'
    else:
        grade = 'Obesity grade 3'
    return _imc, grade


def proportional(value, pro_of_val: int):
    return (pro_of_val / 100) * value


def estimate(from_: Number, to: Number, based: Number, ndigits=2) -> Number:
    if from_ > 0:
        based = based or 1
        return round((based / from_) * to - based, ndigits)
    return float('NaN')


def percent(from_: Number, to: Number, ndigits=2) -> Number:
    to = to or 1
    return round((from_ / to) * 100, ndigits)


def theta_angle(u: Tuple[float, float], v: Tuple[float, float]) -> float:
    """
    Calculates and returns theta angle between two vectors

    e.g usage:
    >>> u = (2,2)
    >>> v = (0, -2)
    >>> theta_angle(u, v)
    135.0
    """
    x1, y1 = u
    x2, y2 = v
    return math.degrees(math.acos((x1 * x2 + y1 * y2) / (math.sqrt(x1 ** 2 + y1 ** 2) * math.sqrt(x2 ** 2 + y2 ** 2))))
