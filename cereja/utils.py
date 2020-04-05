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

import datetime
import functools
import os
import time
from importlib import import_module
import subprocess
import importlib
import sys
import types
import random
from typing import Any, Union, Sequence, List, Tuple, Dict
import logging
import itertools
from copy import copy
# Needed init configs
from logging import config

from cereja.cj_types import PEP440, Number, ClassType, FunctionType

logger = logging.getLogger(__name__)


def invert_dict(dict_: Dict[Any, Any]) -> dict:
    """
    Inverts the key by value
    e.g:
    >>> dict_ = {"a": "b", "c": "d"}
    >>> invert_dict(dict_)
    {"b" : "a", "d": "c"}
    :return: dict
    """
    if not isinstance(dict_, dict):
        raise TypeError("Send a dict object.")
    return dict(zip(dict_.values(), dict_.keys()))


def import_string(dotted_path):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        module_path, class_name = dotted_path.rsplit('.', 1)
    except ValueError as err:
        raise ImportError(f"{dotted_path} doesn't look like a module path") from err

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError as err:
        raise ImportError(f'Module {module_path} does not define a {class_name} attribute/class') from err


def get_attr_if_exists(obj: Any, attr: str) -> Union[object, None]:
    if hasattr(obj, attr):
        return getattr(obj, attr)
    return None


def percent(from_: Number, to: Number) -> Number:
    to = to or 1
    return round((from_ / to) * 100, 2)


def estimate(from_: Number, to: Number, based: Number) -> Number:
    if from_ > 0:
        based = based or 1
        return round((based / from_) * to - based, 2)
    return float('NaN')


def time_format(seconds: float, format_='%H:%M:%S') -> Union[str, float]:
    # this because NaN
    if seconds >= 0 or seconds < 0:
        time_ = time.strftime(format_, time.gmtime(abs(seconds)))
        if seconds < 0:
            return f"-{time_}"
        return time_
    return seconds  # NaN


def fill(value: Union[list, str, tuple], max_size, with_=' ') -> Any:
    """
    Calculates and adds value
    """
    fill_values = [with_] * (max_size - len(value))
    if isinstance(value, str):
        fill_values = ' '.join(fill_values)
        value = f"{value}{fill_values}"
    elif isinstance(value, list):
        value += fill_values
    elif isinstance(value, tuple):
        value += tuple(fill_values)
    return value


def module_references(instance: types.ModuleType, **kwargs) -> dict:
    """
    dict of all functions and classes defined in the module.

    To also list the variables it is necessary to define explicitly with the special variable on your module
    _include

    **kwargs:
    _include -> to includes any definition and variables
    _exclude -> to exclude any definition

    :param instance:
    :return: List[str]
    """
    assert isinstance(instance, types.ModuleType), "You need to submit a module instance."
    logger.debug(f"Checking module {instance.__name__}")
    definitions = {}
    for i in dir(instance):
        if i.startswith('_'):
            continue
        exclude = get_attr_if_exists(instance, "_exclude") or kwargs.get("_exclude") or []
        include = get_attr_if_exists(instance, "_include") or kwargs.get("_include") or []

        obj = get_attr_if_exists(instance, i)

        if i in include:
            definitions[i] = obj

        if obj is not None and i not in exclude and callable(obj):
            if obj.__module__ == instance.__name__:
                definitions[i] = obj
    logger.debug(f"Collected: {definitions}")
    return definitions


def install_if_not(lib_name: str):
    try:
        importlib.import_module(lib_name)
    except ImportError:
        subprocess.run([f"{sys.executable}", "-m", "pip", "install", "--user", f"{lib_name}"])


def set_log_level(level: Union[int, str]):
    """
    Default log level is INFO

    CRITICAL = 50
    FATAL = CRITICAL
    ERROR = 40
    WARNING = 30
    WARN = WARNING
    INFO = 20
    DEBUG = 10
    NOTSET = 0
    """
    log = logging.getLogger()
    log.setLevel(level)
    logger.info(f"Update log level to {level}")


def logger_level():
    import logging
    return logging.getLogger().level


def get_version(version: Union[str, PEP440] = None) -> PEP440:
    """
    Dotted version of the string type is expected

    e.g:
    '1.0.3.a.3' # Pep440 see https://www.python.org/dev/peps/pep-0440/

    :param version: Dotted version of the string
    """
    if version is None:
        from cereja import VERSION as version

    if isinstance(version, str):
        version = version.split('.')
        version_note = version.pop(3)
        version = list(map(int, version))
        version.insert(3, version_note)

    assert len(version) == 5, "Version must be size 5"

    assert version[3] in ('alpha', 'beta', 'rc', 'final')
    return version


@functools.lru_cache()
def latest_git():
    """
    Return a numeric identifier of the latest git changeset.
    """
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    git_log = subprocess.run(
            ['git', 'log', '--pretty=format:%ct', '--quiet', '-1', 'HEAD'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            shell=True, cwd=repo_dir, universal_newlines=True,
    )
    timestamp = git_log.stdout
    try:
        timestamp = datetime.datetime.utcfromtimestamp(int(timestamp))
    except ValueError:
        return None
    return timestamp.strftime('%Y%m%d%H%M%S')


def get_version_pep440_compliant(version: str = None) -> str:
    """
    Dotted version of the string type is expected

    e.g:
    '1.0.3.a.3' # Pep440 see https://www.python.org/dev/peps/pep-0440/

    :param version: Dotted version of the string
    """
    version_mapping = {'alpha': 'a', 'beta': 'b', 'rc': 'rc'}
    version = get_version(version)
    root_version = '.'.join(map(str, version[:3]))

    sub = ''
    if version[3] == 'alpha' and version[4] == 0:
        git = latest_git()
        if git:
            sub = f'.dev{git}'

    elif version[3] != 'final':
        sub = version_mapping[version[3]] + str(version[4])
    elif version[3] == 'final' and version[4] != 0:
        sub = f'-{version[4]}'

    return f"{root_version}{sub}"


def proportional(value, pro_of_val: int):
    return (pro_of_val / 100) * value


def combine_with_all(a: list, b: list, n_a_combinations: int = 1, is_random: bool = False) -> List[Tuple[Any, ...]]:
    """
    >>> a = [1, 2, 3]
    >>> b = ['anything_a', 'anything_b']
    >>> combine_with_all(a, b)
    [(1, 'anything_a'), (1, 'anything_b'), (2, 'anything_a'), (2, 'anything_b'), (3, 'anything_a'), (3, 'anything_b')]

    >>> combine_with_all(a, b, n_a_combinations=2)
    [((1, 2), 'anything_a'), ((1, 2), 'anything_b'),
    ((1, 3), 'anything_a'), ((1, 3), 'anything_b'),
    ((2, 3), 'anything_a'), ((2, 3), 'anything_b')]
    """
    if not isinstance(n_a_combinations, int):
        raise TypeError(f"Please send {int}.")
    n_a_combinations = len(a) if n_a_combinations > len(a) else abs(n_a_combinations)

    combination = itertools.combinations(a, n_a_combinations) if n_a_combinations > 1 else a
    product_with_b = list(itertools.product(combination, b))
    if is_random:
        random.shuffle(product_with_b)
    return product_with_b


class CjTest(object):
    """

    """
    __prefix_attr_err = "Attr Check Error {attr_}."

    def __init__(self, instance_obj: object):
        self._prefix_attr = f"__{instance_obj.__class__.__name__}__"
        self._instance_obj = instance_obj
        self._set_attr_current_values()
        self._checks = []
        self._n_checks_passed = 0

    @property
    def checks(self):
        return self._checks

    @property
    def n_checks(self):
        return len(self._checks)

    @property
    def _instance_obj_attrs(self):
        return filter(lambda attr_: attr_.__contains__('__') is False, dir(self._instance_obj))

    def _get_attr_obj(self, attr_: str):
        if not hasattr(self._instance_obj, attr_):
            raise ValueError(f"Attr {attr_} not found.")
        value = getattr(self._instance_obj, attr_)
        return self._Attr(attr_, value)

    def _set_attr_current_values(self):
        for attr_ in self._instance_obj_attrs:
            attr_obj = self._get_attr_obj(attr_)
            attr_name = self.parse_attr(attr_)
            setattr(self, attr_name, attr_obj)

    def parse_attr(self, attr_: str):
        attr_ = self._valid_attr(attr_)
        return f'{self._prefix_attr}{attr_}'

    def __getattr__(self, item):
        return self.__getattribute__(self.parse_attr(item))

    class _Attr(object):
        def __init__(self, name: str, value: Any):
            self.name = name
            self.is_callable = callable(value)
            self.is_private = self.name.startswith('_')
            self.is_bool = value is True or value is False
            self.is_class = isinstance(value, ClassType)
            self.is_function = isinstance(value, FunctionType)
            self.class_of_attr = value.__class__
            self._operator_repr = None
            self.tests_case = []

        def __repr__(self):
            return f"{self.name}"

        def __str__(self):
            return f"{self.name}"

        def __len__(self):
            return len(self.tests_case)

        def __eq__(self, other):
            """ ==value """
            if isinstance(other, self.__class__):
                return NotImplemented
            self.tests_case = (other, self.class_of_attr.__eq__, '==')
            return self

        def __ge__(self, other):
            """>=value """
            if isinstance(other, self.__class__):
                return NotImplemented
            self.tests_case = (other, self.class_of_attr.__ge__, '>=')
            return self

        def __gt__(self, other):
            """>value """
            if isinstance(other, self.__class__):
                return NotImplemented
            self.tests_case = (other, self.class_of_attr.__gt__, '>')
            return self

        def __le__(self, other):
            """ <=value. """
            if isinstance(other, self.__class__):
                return NotImplemented
            self.tests_case = (other, self.class_of_attr.__le__, '<=')
            return self

        def __lt__(self, other):
            """ <value. """
            if isinstance(other, self.__class__):
                return NotImplemented
            self.tests_case = (other, self.class_of_attr.__lt__, '<')
            return self

        def __ne__(self, other):
            """ !=value. """
            if isinstance(other, self.__class__):
                return NotImplemented
            self.tests_case = (other, self.class_of_attr.__ne__, '!=')
            return self

        def copy(self):
            return copy(self)

        def run(self, current_value):
            expected, operator, _ = self.tests_case
            if not operator(current_value, expected):
                return [f"{repr(current_value)} not {_} {repr(expected)}"]

            return []

    def _valid_attr(self, attr_name: str):
        assert hasattr(self._instance_obj,
                       attr_name), f"{self.__prefix_attr_err.format(attr_=repr(attr_name))} isn't defined."
        return attr_name

    def add_check(self, *check_: _Attr):
        for i in check_:
            if i not in self._checks:
                self._checks.append(i)

    def remove_check(self, index: int):
        self._checks.pop(index)

    def check_attr(self, attr_name: Union[str, _Attr]):
        if isinstance(attr_name, str):
            stored_test = self.__getattribute__(self.parse_attr(attr_name))
        else:
            stored_test = attr_name
        current_value = getattr(self._instance_obj, stored_test.name)
        if not stored_test.is_callable:
            tests_ = stored_test.run(current_value)
            passed = not any(tests_)
            self._n_checks_passed += len(stored_test) - len(tests_)
            msg_err = f"{self.__prefix_attr_err.format(attr_=repr(stored_test.name))} {' '.join(tests_)}"
            assert passed, msg_err

    def check_all(self):
        for attr_ in self._checks:
            self.check_attr(attr_)


if __name__ == '__main__':
    class A:
        def __init__(self, attr_a, attr_b):
            self._attr_a = attr_a
            self._attr_b = attr_b

        def set_attr_a(self, value):
            self._attr_a = value

        def set_attr_b(self, value):
            self._attr_b = value


    my_instance = A("Cereja Tests", "Is Easy")
    my_test = CjTest(my_instance)
    my_instance.set_attr_a("Cereja")
    my_test.add_check(
            my_test._attr_a == 'Cereja',
            my_test._attr_b == "Joab"
    )
    my_test.check_all()
