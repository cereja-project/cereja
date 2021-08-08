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
import math
import time
from collections import OrderedDict
from importlib import import_module
import importlib
import sys
import types
import random
from typing import Any, Union, List, Tuple, Sequence, Iterable, Dict
import logging
import itertools
from copy import copy
import inspect

# Needed init configs
from cereja.config.cj_types import ClassType, FunctionType, Number

__all__ = ['CjTest', 'camel_to_snake', 'combine_with_all', 'fill', 'get_attr_if_exists',
           'get_implements', 'get_instances_of', 'import_string',
           'install_if_not', 'invert_dict', 'logger_level', 'module_references', 'set_log_level', 'time_format',
           'string_to_literal', 'rescale_values', 'Source', 'sample', 'obj_repr', 'truncate', 'type_table_of',
           'list_methods', 'can_do', 'chunk', 'is_iterable', 'is_sequence', 'is_numeric_sequence', 'clipboard',
           'sort_dict', 'dict_append', 'to_tuple', 'dict_to_tuple', 'list_to_tuple']

logger = logging.getLogger(__name__)

_DICT_ITEMS_TYPE = type({}.items())


def chunk(data: Sequence, batch_size: int = None, fill_with: Any = None, is_random: bool = False,
          max_batches: int = None) -> List[Union[Sequence, List, Tuple, Dict]]:
    """

    e.g:
    >>> import cereja as cj

    >>> data = list(range(15))
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

    >>> cj.chunk(data, batch_size=4)
    [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11], [12, 13, 14]]

    >>> cj.chunk(data, batch_size=4, is_random=True, fill_with=0)
    [[7, 2, 11, 4], [10, 6, 1, 13], [12, 9, 5, 0], [8, 3, 14, 0]]

    >>> data = {"key1": 'value1', "key2": 'value2', "key3": 'value3', "key4": 'value4'}

    >>> cj.chunk(data, batch_size=2,is_random=True)
    [{'key3': 'value3', 'key2': 'value2'}, {'key1': 'value1', 'key4': 'value4'}]

    @param data: Iterable data
    @param batch_size: number of items per batch
    @param fill_with: Any, but isn't valid for dict
    @param is_random: shuffle data
    @param max_batches: limit number of batches
    @return: list of batches
    """

    assert is_iterable(data), f"Chunk isn't possible, because value {data} isn't iterable."
    if batch_size is None and max_batches is None:
        return [data]

    # used to return the same data type
    __parser = None

    if isinstance(data, (dict, tuple, set)):
        __parser = type(data)
        data = data.items() if isinstance(data, dict) else data

    data = list(data) if isinstance(data, (set, tuple, str, bytes, bytearray, _DICT_ITEMS_TYPE)) else copy(data)
    if not batch_size or batch_size > len(data) or batch_size < 1:
        if isinstance(max_batches, (int, float)) and max_batches > 0:
            batch_size = ((len(data) // max_batches) + len(data) % max_batches) or len(data)
        else:
            batch_size = len(data)

    if is_random:
        random.shuffle(data)

    if max_batches is None:
        max_batches = len(data) // batch_size if len(data) % batch_size == 0 else len(data) // batch_size + 1

    batches = []
    for i in range(0, len(data), batch_size):

        result = data[i:i + batch_size]
        if fill_with is not None and len(result) < batch_size:
            result += [fill_with] * (batch_size - len(result))
        batches.append(__parser(result) if __parser is not None else result)
        max_batches -= 1
        if not max_batches:
            break
    return batches


def _get_tkinter():
    try:
        from tkinter import Tk
    except ImportError:
        raise ValueError("Sorry. Isn't possible.")
    return Tk()


def clipboard() -> str:
    return _get_tkinter().clipboard_get()


def truncate(text: Union[str, bytes], k=4):
    """
    Truncate text.
    eg.:
    >>> import cereja as cj
    >>> cj.utils.truncate("Cereja is fun.", k=3)
    'Cer...'

    @param text: string or bytes
    @param k: natural numbers, default is 4
    """
    assert isinstance(text, (str, bytes)), TypeError(f"{type(text)} isn't valid. Expected str or bytes")
    if k > len(text) or k < 0:
        return text
    trunc_chars = '...' if isinstance(text, str) else b'...'
    return text[:k] + trunc_chars


def obj_repr(obj_, attr_limit=10, val_limit=3, show_methods=False, show_private=False, deep=3):
    try:
        if isinstance(obj_, (str, bytes)):
            return truncate(obj_, k=attr_limit)
        if isinstance(obj_, (bool, float, int, complex)):
            return obj_
        rep_ = []
        if deep > 0:
            for attr_ in dir(obj_):
                if attr_.startswith('_') and not show_private:
                    continue
                obj = obj_.__getattribute__(attr_)

                if isinstance(obj, (str, bool, float, int, complex, bytes, bytearray)):
                    rep_.append(f'{attr_} = {obj_repr(obj)}')
                    continue
                if callable(obj) and not show_methods:
                    continue

                if is_iterable(obj):
                    temp_v = []
                    for k in obj:
                        if isinstance(obj, dict):
                            k = f'{k}:{type(obj[k])}'
                        elif is_iterable(k):
                            k = obj_repr(k, deep=deep)
                            deep -= 1
                        else:
                            k = str(k)
                        temp_v.append(k)
                        if len(temp_v) == val_limit:
                            break
                    temp_v = ', '.join(temp_v)  # fix me, if bytes ...
                    obj = f'{obj.__class__.__name__}({temp_v} ...)'
                rep_.append(f'{attr_} = {obj}')
                if len(rep_) >= attr_limit:
                    rep_.append('...')
                    break
        else:
            return repr(obj_)

    except Exception as err:
        logger.error(err)
        rep_ = []
    rep_ = ',\n    '.join(rep_)
    __repr_template = f"""
    {rep_}
    """
    return f"{obj_.__class__.__name__} ({__repr_template})"


def can_do(obj: Any) -> List[str]:
    """
    List methods and attributes of a Python object.

    It is essentially the builtin `dir` function without the private methods and attributes

    @param obj: Any
    @return: list of attr names sorted by name
    """
    return sorted([i for i in filter(lambda attr: not attr.startswith('_'), dir(obj))])


def sample(v: Sequence, k: int = None, is_random: bool = False) -> Union[list, dict, set, Any]:
    """
    Get sample of anything

    @param v: Any
    @param k: int
    @param is_random: default False
    @return: sample iterable
    """
    result = chunk(v, batch_size=k, is_random=is_random, max_batches=1)
    if len(result) == 1:
        result = result[0]
    if isinstance(v, set):
        result = set(result)
    return result


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


def _invert_parser_key(key):
    return to_tuple(key) if isinstance(key, (list, set, dict)) else key


def _invert_append(obj, k, v):
    dict_append(obj, k, v)
    if len(obj[k]) == 1:
        obj[k] = obj[k][0]


def invert_dict(dict_: Union[dict, set]) -> dict:
    """
    Inverts the key by value
    e.g:
    >>> example = {"a": "b", "c": "d"}
    >>> invert_dict(example)
    {"b" : "a", "d": "c"}
    :return: dict
    """

    if not isinstance(dict_, dict):
        raise TypeError("Send a dict object.")
    new_dict = {}
    for key, value in dict_.items():
        key = _invert_parser_key(key)

        if isinstance(value, dict):
            if key not in new_dict:
                new_dict.update({key: invert_dict(value)})
            else:
                _invert_append(new_dict, key, invert_dict(value))
            continue
        if isinstance(value, (tuple, list, set)):
            for k in dict_[key]:
                k = _invert_parser_key(k)
                _invert_append(new_dict, k, key)
            continue

        if value not in new_dict:
            new_dict[value] = key
        else:
            value = _invert_parser_key(value)
            _invert_append(new_dict, value, key)

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
    """
    Default format is '%H:%M:%S'

    >>> time_format(3600)
    '01:00:00'

    """
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


def list_methods(klass) -> List[str]:
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
    from ..display import console
    try:
        importlib.import_module(lib_name)
        output = 'Alredy Installed'
    except ImportError:
        from ..system.commons import run_on_terminal

        command_ = f"{sys.executable} -m pip install {lib_name}"
        output = run_on_terminal(command_)
    console.log(output)


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
    __template_unittest_function = """
    def test_{func_name}(self):
        pass
        """
    __template_unittest_class = """
class {class_name}Test(unittest.TestCase):
    {func_tests}
        """

    __template_unittest = """import unittest

{tests}

if __name__ == '__main__':
    unittest.main()

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

    @classmethod
    def _get_class_test(cls, ref):
        func_tests = ''.join(cls.__template_unittest_function.format(func_name=i) for i in list_methods(ref))
        return cls.__template_unittest_class.format(class_name=ref.__name__, func_tests=func_tests)

    @classmethod
    def _get_func_test(cls, ref):
        return cls.__template_unittest_function.format(func_name=ref.__name__)

    @classmethod
    def _get_test(cls, ref):
        if isinstance(ref, (FunctionType, types.MethodType)):
            return cls._get_func_test(ref)
        if isinstance(ref, type):
            return cls._get_class_test(ref)
        raise TypeError("send a function or class reference")

    @classmethod
    def build_test(cls, reference):
        module_func_test = []
        tests = []
        if isinstance(reference, types.ModuleType):
            for _, ref in module_references(reference).items():
                if isinstance(ref, type):
                    tests.append(cls._get_test(ref))
                    continue
                module_func_test.append(cls._get_test(ref))
        else:
            if isinstance(reference, type):
                tests.append(cls._get_test(reference))
            else:
                module_func_test.append(cls._get_test(reference))
        if module_func_test:
            module_func_test = ''.join(module_func_test)
            tests = [cls.__template_unittest_class.format(class_name='Module', func_tests=module_func_test)] + tests
        return cls.__template_unittest.format(tests='\n'.join(tests))


def _add_license(base_dir, ext='.py'):
    from cereja.file import FileIO
    from cereja.config import BASE_DIR
    licence_file = FileIO.load(BASE_DIR)
    for file in FileIO.load_files(base_dir, ext=ext, recursive=True):
        if 'Copyright (c) 2019 The Cereja Project' in file.string:
            continue
        file.insert('"""\n' + licence_file.string + '\n"""')
        file.save(exist_ok=True)


def _rescale_down(input_list, size):
    assert len(input_list) >= size, f'{len(input_list), size}'

    skip = len(input_list) // size
    for n, i in enumerate(range(0, len(input_list), skip), start=1):
        if n > size:
            break
        yield input_list[i]


def _rescale_up(values, k, fill_with=None, filling='inner'):
    size = len(values)
    assert size <= k, f'Error while resizing: {size} < {k}'

    clones = (math.ceil(abs(size - k) / size))
    refill_values = abs(k - size * clones)
    if filling == 'pre':
        for i in range(abs(k - size)):
            yield fill_with if fill_with is not None else values[0]

    for value in values:
        # guarantees that the original value will be returned
        yield value

        if filling != 'inner':
            continue

        for i in range(clones - 1):  # -1 because last line.
            # value original or fill_with.
            yield fill_with if fill_with is not None else value
        if refill_values > 0:
            refill_values -= 1
            yield fill_with if fill_with is not None else value
        k -= 1
        if k < 0:
            break
    if filling == 'post':
        for i in range(abs(k - size)):
            yield fill_with if fill_with is not None else values[-1]


def _interpolate(values, k):
    size = len(values)

    first_position = 0
    last_position = size - 1
    step = (last_position - first_position) / (k - 1)

    positions = [first_position]
    previous_position = positions[-1]
    for _ in range(k - 2):
        positions.append(previous_position + step)
        previous_position = positions[-1]
    positions.append(last_position)

    for position in positions:
        previous_position = math.floor(position)
        next_position = math.ceil(position)
        if previous_position == next_position:
            yield values[previous_position]
        else:
            delta = position - previous_position
            yield values[previous_position] + (values[next_position] - values[previous_position]) / (
                    next_position - previous_position) * delta


def rescale_values(values: List[Any], granularity: int, interpolation: bool = False, fill_with=None, filling='inner') -> \
        List[Any]:
    """
    Resizes a list of values
    eg.
        >>> import cereja as cj
        >>> cj.rescale_values(values=list(range(100)),granularity=12)
        [0, 8, 16, 24, 32, 40, 48, 56, 64, 72, 80, 88]
        >>> cj.rescale_values(values=list(range(5)),granularity=10)
        [0, 0, 1, 1, 2, 2, 3, 3, 4, 4]
        >>> cj.rescale_values(values=list(range(5)),granularity=10, filling='pre')
        [0, 0, 0, 0, 0, 0, 1, 2, 3, 4]
        >>> cj.rescale_values(values=list(range(5)),granularity=10, filling='post')
        [0, 1, 2, 3, 4, 4, 4, 4, 4, 4]

        @note if you don't send any value for filling a value will be chosen arbitrarily depending on the filling type.

    If interpolation is set to True, then the resized values are calculated by interpolation, 
    otherwise they are sub- ou upsampled from the original list


    @param values: Sequence of anything
    @param granularity: is a integer
    @param interpolation: is a boolean
    @param fill_with: only scale up, send any value for filling
    @param filling: in case of scale up, you can define how the filling will be (pre, inner, post). 'inner' is default.
    @return: rescaled list of values.
    """

    if interpolation:
        result = list(_interpolate(values, granularity))
    else:
        if len(values) >= granularity:
            result = list(_rescale_down(values, granularity))
        else:
            result = list(_rescale_up(values, granularity, fill_with=fill_with, filling=filling))

    assert len(result) == granularity, f"Error while resizing the list size {len(result)} != {granularity}"
    return result


class Source:

    def __init__(self, reference: Any):
        self._name = None
        self._doc = inspect.getdoc(reference)
        self._source_code = inspect.getsource(reference)
        if hasattr(reference, '__name__'):
            self._name = reference.__name__

    @property
    def source_code(self):
        return self._source_code.lstrip()

    @property
    def name(self):
        return self._name

    @property
    def doc(self):
        return self._doc

    def save(self, path_, **kwargs):
        from cereja import FileIO, Path
        path_ = Path(path_)
        if path_.is_dir:
            path_ = path_.join(f'{self.name}.py')
        assert path_.suffix == '.py', "Only python source code."
        FileIO.create(path_, self._source_code).save(**kwargs)


def is_iterable(obj: Any) -> bool:
    """
    Return whether an object is iterable or not.

    :param obj: Any object for check
    """
    return isinstance(obj, Iterable)


def is_sequence(obj: Any) -> bool:
    """
    Return whether an object a Sequence or not, exclude strings and empty obj.

    :param obj: Any object for check
    """
    return not isinstance(obj, (str, dict, bytes)) and is_iterable(obj)


def is_numeric_sequence(obj: Sequence[Number]) -> bool:
    try:
        from cereja.array import flatten
        sum(flatten(obj))
    except (TypeError, ValueError):
        return False
    return True


def sort_dict(obj: dict, by_keys=False, by_values=False, reverse=False, by_len_values=False, func_values=None,
              func_keys=None) -> OrderedDict:
    func_values = (lambda v: len(v) if by_len_values else v) if func_values is None else func_values
    func_keys = (lambda k: k) if func_keys is None else func_keys

    key_func = None
    if (by_keys and by_values) or (not by_keys and not by_values):
        key_func = (lambda x: (func_keys(x[0]), func_values(x[1])))
    elif by_keys:
        key_func = (lambda x: func_keys(x[0]))
    elif by_values:
        key_func = (lambda x: func_values(x[1]))
    return OrderedDict(sorted(obj.items(), key=key_func, reverse=reverse))


def list_to_tuple(obj):
    assert isinstance(obj, (list, set, tuple)), f"Isn't possible convert {type(obj)} into {tuple}"
    result = []
    for i in obj:
        if isinstance(i, list):
            i = list_to_tuple(i)
        elif isinstance(i, (set, dict)):
            i = dict_to_tuple(i)
        result.append(i)
    return tuple(result)


def dict_to_tuple(obj):
    assert isinstance(obj, (dict, set)), f"Isn't possible convert {type(obj)} into {tuple}"
    result = []
    if isinstance(obj, set):
        return tuple(obj)
    for k, v in obj.items():
        if isinstance(v, (dict, set)):
            v = dict_to_tuple(v)
        elif isinstance(v, list):
            v = list_to_tuple(v)
        result.append((k, v))
    return tuple(result)


def to_tuple(obj):
    if isinstance(obj, (set, dict)):
        return dict_to_tuple(obj)
    if isinstance(obj, (list, tuple)):
        return list_to_tuple(obj)
    return tuple(obj)


def dict_append(obj: Dict[Any, Union[list, tuple]], key, *v):
    """
    Add items to a key, if the key is not in the dictionary it will be created with a list and the value sent.

    e.g:

    >>> import cereja as cj
    >>> my_dict = {}
    >>> cj.utils.dict_append(my_dict, 'key_eg', 1,2,3,4,5,6)
    {'key_eg': [1, 2, 3, 4, 5, 6]}
    >>> cj.utils.dict_append(my_dict, 'key_eg', [1,2])
    {'key_eg': [1, 2, 3, 4, 5, 6, [1, 2]]}

    @param obj: Any dict of list values
    @param key: dict key
    @param v: all values after key
    @return:
    """
    assert isinstance(obj, dict), 'Error on append values. Please send a dict object.'
    if key not in obj:
        obj[key] = []

    if not isinstance(obj[key], (list, tuple)):
        obj[key] = [obj[key]]
    if isinstance(obj[key], tuple):
        obj[key] = (*obj[key], *v,)
    else:
        for i in v:
            obj[key].append(i)
    return obj
