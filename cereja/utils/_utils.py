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
import ast
import gc
import time
from importlib import import_module
import subprocess
import importlib
import sys
import types
import random
from typing import Any, Union, List, Tuple
import logging
import itertools
from copy import copy
import inspect
# Needed init configs
from cereja.array import is_iterable

from cereja.config.cj_types import ClassType, FunctionType

__all__ = ['CjTest', 'camel_to_snake', 'combine_with_all', 'fill', 'get_attr_if_exists',
           'get_implements', 'get_instances_of', 'import_string',
           'install_if_not', 'invert_dict', 'logger_level', 'module_references', 'set_log_level', 'time_format',
           'string_to_literal', 'rescale_values', 'Source', 'sample']
logger = logging.getLogger(__name__)


def sample(v, k=None, is_random=False):
    """
    Get sample of anything

    @param v: Any
    @param k: int
    @param is_random: default False
    @return: sample list
    """
    if not is_iterable(v):
        return [v]

    k = k or len(v)
    res = random.sample(list(v), k) if is_random else list(v)[:k]

    if isinstance(v, (dict, set)):
        return {key: v[key] for key in res}
    return res


def type_table_of(o: Union[list, tuple, dict]):
    if isinstance(o, (list, tuple)):
        type_table = {i: type(i) for i in o}
    elif isinstance(o, dict):
        type_table = {}
        for k, v in o.items():
            if isinstance(o, dict):
                v = type_table_of(v)
            type_table[k] = (v, type(v))
    else:
        type_table = {o: type(o)}

    return type_table


def camel_to_snake(value: str):
    snaked_ = []
    for i, char in enumerate(value):
        if not i == 0 and char.isupper():
            char = f'_{char}'
        snaked_.append(char)
    return ''.join(snaked_).lower()


def get_implements(klass: type):
    classes = klass.__subclasses__()
    collected_classes = []
    for k in classes:
        k_classes = k.__subclasses__()
        if k_classes:
            collected_classes += get_implements(k)
        if not k.__name__.startswith('_'):
            collected_classes.append(k)
    return collected_classes


def get_instances_of(klass: type):
    return filter(lambda x: isinstance(x, klass), gc.get_objects())


def invert_dict(dict_: Union[dict, set]) -> dict:
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
    new_dict = {}
    for key, value in dict_.items():
        if isinstance(value, dict):
            new_dict.update({key: invert_dict(value)})
            continue
        if isinstance(value, (tuple, list, set)):
            new_dict.update({k: key for k in dict_[key]})
            continue
        new_dict[value] = key
    return new_dict


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


def class_methods(klass) -> List[str]:
    methods = []
    for i in dir(klass):
        if i.startswith('_') or not callable(getattr(klass, i)):
            continue
        methods.append(i)
    return methods


def string_to_literal(val: str):
    if isinstance(val, str):
        try:
            return ast.literal_eval(val)
        except:
            pass
    return val


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


def _add_license(base_dir, ext='.py'):
    from cereja.file import File
    from cereja.config import BASE_DIR
    licence_file = File.load(BASE_DIR)
    for file in File.load_files(base_dir, ext=ext, recursive=True):
        if 'Copyright (c) 2019 The Cereja Project' in file.string:
            continue
        file.insert('"""\n' + licence_file.string + '\n"""')
        file.save(exist_ok=True)


def _compress_list(input_list, size):
    assert len(input_list) >= size, f'{len(input_list), size}'

    skip = len(input_list) // size

    output = [input_list[i] for i in range(0, len(input_list), skip)]

    return output[:size]


def rescale_values(values: List[Any], granularity: int) -> List[Any]:
    """
    Resizes a list of values
    eg.
        >>> import cereja as cj
        >>> cj.rescale_values(values=list(range(100)), granularity=10)
        [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
        >>> cj.rescale_values(values=list(range(5)), granularity=10)
        [0, 0, 0, 1, 1, 1, 2, 2, 2, 3]

    @param values: Sequence of anything
    @param granularity: is a integer
    @return: rescaled list of values.
    """
    if len(values) >= granularity:
        return _compress_list(values, granularity)
    if len(values) == 0:
        return []
    cluster = int(len(values) / granularity)
    if cluster == 0:
        multiplier = int(granularity / len(values) + 1)
        oversampling = []

        for array in values:
            for i in range(multiplier):
                oversampling.append(array)

        values = oversampling
        cluster = 1

    flatten_result = []
    start_interval = 0

    for i in range(granularity):
        frames = values[start_interval:start_interval + cluster]
        flatten_result.append(frames[-1])
        start_interval += cluster

    assert len(
            flatten_result) == granularity, f"Error while resizing the list size {len(flatten_result)} != {granularity}"
    return flatten_result


class Source:
    def __init__(self, reference: Any):
        self._source_code = inspect.getsource(reference)

    @property
    def source_code(self):
        return self._source_code

    def save(self, path_, **kwargs):
        from cereja import FileIO, Path
        assert Path(path_).suffix == '.py', "Only python source code."
        FileIO.create(path_, self._source_code).save(**kwargs)
