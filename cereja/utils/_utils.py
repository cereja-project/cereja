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
import ctypes
import gc
import math
import re
import string
import threading
from collections import OrderedDict, defaultdict
from importlib import import_module
import importlib
import sys
import types
import random
from typing import Any, Union, List, Tuple, Sequence, Iterable, Dict, MappingView, Optional, Callable, AnyStr, Iterator
import logging
import itertools
from copy import copy
import inspect
from pprint import PrettyPrinter

from .decorators import depreciation
# Needed init configs
from ..config.cj_types import ClassType, FunctionType, Number
from itertools import combinations as itertools_combinations

__all__ = [
    "CjTest",
    "camel_to_snake",
    "camel_case_to_snake",
    "snake_case_to_camel",
    "combine_with_all",
    "fill",
    "get_attr_if_exists",
    "get_implements",
    "get_instances_of",
    "import_string",
    "install_if_not",
    "invert_dict",
    "logger_level",
    "module_references",
    "set_log_level",
    "string_to_literal",
    "rescale_values",
    "Source",
    "sample",
    "visualize_sample",
    "obj_repr",
    "truncate",
    "type_table_of",
    "list_methods",
    "can_do",
    "chunk",
    "is_iterable",
    "is_indexable",
    "is_sequence",
    "is_numeric_sequence",
    "clipboard",
    "sort_dict",
    "dict_append",
    "to_tuple",
    "dict_to_tuple",
    "list_to_tuple",
    "group_by",
    "dict_values_len",
    "dict_max_value",
    "dict_min_value",
    "dict_filter_value",
    "get_zero_mask",
    "get_batch_strides",
    "prune_values",
    "split_sequence",
    "has_length",
    "combinations",
    "combinations_sizes",
    "value_from_memory",
    "str_gen",
    "SourceCodeAnalyzer",
    "map_values",
    'decode_coordinates',
    'encode_coordinates',
    'SingletonMeta',
    'PoolMeta'
]

logger = logging.getLogger(__name__)


class NoStringWrappingPrettyPrinter(PrettyPrinter):
    def __init__(self, str_width):
        super().__init__()
        self.str_width = str_width

    def _format(self, object, *args):
        if isinstance(object, str):
            width = self._width
            self._width = self.str_width
            try:
                super()._format(object, *args)
            finally:
                self._width = width
        else:
            super()._format(object, *args)


def is_indexable(v):
    return hasattr(v, "__getitem__")


def split_sequence(seq: List[Any], is_break_fn: Callable) -> List[List[Any]]:
    """
    Split a sequence into subsequences based on a break function.
    @param seq: sequence to split
    @param is_break_fn: function that returns True if the sequence should be split at the current index
    e.g:
    >>> import cereja as cj
    >>> seq = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    >>> cj.split_sequence(seq, lambda current_val: current_val % 3 == 0)
    [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    >>> cj.split_sequence(seq, lambda current_val, next_val: current_val % 2 == 0 and next_val % 3 == 0)
    [[1, 2], [3, 4, 5, 6, 7, 8], [9]]
    >>> cj.split_sequence(seq, lambda: True)
    [[1], [2], [3], [4], [5], [6], [7], [8], [9]]
    >>> cj.split_sequence(seq, lambda current_val, next_val, index: seq[index-1] % 2 == 0 and current_val % 3 == 0)
    [[1, 2, 3], [4, 5, 6, 7, 8, 9]]
    @return: list of subsequences
    """
    if not isinstance(seq, list) or not seq:
        raise ValueError("The sequence must be a non-empty list.")

    if not callable(is_break_fn):
        raise TypeError("is_break_fn must be a function.")

    sub_seqs = []
    start_idx = 0
    if len(seq) == 1:
        return [seq]
    for idx, is_break in enumerate(map_values(seq, is_break_fn)):
        if is_break:
            sub_seqs.append(seq[start_idx:idx + 1])
            start_idx = idx + 1
    if start_idx < len(seq):
        sub_seqs.append(seq[start_idx:])
    return sub_seqs


def map_values(obj: Union[dict, list, tuple, Iterator], fn: Callable) -> Union[dict, list, tuple, Iterator]:
    fn_arg_count = SourceCodeAnalyzer(fn).argument_count
    if isinstance(obj, dict):
        obj = obj.items()
    _iter = iter(obj)
    last = next(_iter, '__stop__')
    if last == '__stop__':
        return map(fn, obj)
    idx = 0
    while last != '__stop__':
        _args = None
        _next = next(_iter, '__stop__')

        if fn_arg_count == 1:
            _args = (last,)
        elif fn_arg_count == 2:
            _args = (last, None if _next == '__stop__' else _next)
        elif fn_arg_count == 3:
            _args = (last, None if _next == '__stop__' else _next, idx)
        if _next == '__stop__' and fn_arg_count >= 2:
            if idx == 0:
                yield fn(*_args)
            break
        yield fn(*_args) if _args else last
        last = _next
        idx += 1


def chunk(
        data: Sequence,
        batch_size: int = None,
        fill_with: Any = None,
        is_random: bool = False,
        max_batches: int = None,
) -> List[Union[Sequence, List, Tuple, Dict]]:
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

    assert (
            is_iterable(data) and len(data) > 0
    ), f"Chunk isn't possible, because value {data} isn't valid."
    if batch_size is None and max_batches is None:
        return [data]

    # used to return the same data type
    __parser = None

    if isinstance(data, (dict, tuple, set)):
        __parser = type(data)
        data = data.items() if isinstance(data, dict) else data

    data = (
        list(data)
        if isinstance(data, (set, tuple, str, bytes, bytearray, MappingView))
        else copy(data)
    )
    if not batch_size or batch_size > len(data) or batch_size < 1:
        if isinstance(max_batches, (int, float)) and max_batches > 0:
            batch_size = math.ceil(len(data) / max_batches)
        else:
            batch_size = len(data)

    if is_random:
        random.shuffle(data)

    if max_batches is None:
        max_batches = (
            len(data) // batch_size
            if len(data) % batch_size == 0
            else len(data) // batch_size + 1
        )

    batches = []
    for i in range(0, len(data), batch_size):

        result = data[i: i + batch_size]
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


def truncate(data: Union[Sequence], k_iter: int = 0, k_str: int = 0, k_dict_keys: int = 0):
    """
    Truncates the data to the specified number of elements in half(+1 if odd) + half, adding a filler in between.
    If the data is a dictionary, then truncates recursively until data is "truncatable".
    Allows to specify a different to k to strings and number of dictionary keys.
    Args:
        data: sequence
        k_iter: number of elements of iterable data to return
        k_str: number of elements of strings to return
        k_dict_keys: number of dictionary keys to return
    Returns:
        truncated data
    """
    assert all(isinstance(k, int) and k >= 0 for k in
               (k_iter, k_str, k_dict_keys)), 'k parameters should be an integer equal to or larger than 0'

    data = copy(data)
    if isinstance(data, dict):
        if k_dict_keys:
            data = {key: data.get(key, '<…>') for key in truncate(list(data.keys()), k_dict_keys)}
            if k_iter or k_str:
                data = {truncate(key, k_iter, k_str): value for key, value in data.items()}
        for key, value in data.items():
            data[key] = truncate(value, k_iter, k_str, k_dict_keys)
    elif isinstance(data, str):
        if k_str == 0:
            return data
        k_str = min(k_str, len(data))
        n = k_str // 2
        filler = '…' if len(data) > k_str else ''
        return data[:(k_str - n)] + filler + data[-n:] if n else data[:(k_str - n)] + filler
    elif isinstance(data, Iterable):
        if k_iter == 0:
            return data
        k_iter = min(k_iter, len(data))
        n = k_iter // 2
        if isinstance(data, bytes):
            filler = b'...' if len(data) > k_iter else b''
            return data[:(k_iter - n)] + filler + data[-n:] if n else data[:(k_iter - n)] + filler
        else:
            filler = ['<…>'] if len(data) > k_iter else []
        if isinstance(data, list):
            if n:
                return [truncate(dt, k_iter, k_str, k_dict_keys) for dt in data[:(k_iter - n)]] + filler + \
                    [truncate(dt, k_iter, k_str, k_dict_keys) for dt in data[-n:]]
            return [truncate(dt, k_iter, k_str, k_dict_keys) for dt in data[:(k_iter - n)]] + filler
        elif isinstance(data, set):
            if n:
                return set([truncate(dt, k_iter, k_str, k_dict_keys) for dt in list(data)[:(k_iter - n)]] + filler + \
                           [truncate(dt, k_iter, k_str, k_dict_keys) for dt in list(data)[-n:]])
            return set([truncate(dt, k_iter, k_str, k_dict_keys) for dt in list(data)[:(k_iter - n)]] + filler)
        return data
    return data


def obj_repr(
        obj_, attr_limit=10, val_limit=3, show_methods=False, show_private=False, deep=3
):
    try:
        if isinstance(obj_, (str, bytes)):
            return truncate(obj_, k_iter=attr_limit)
        if isinstance(obj_, (bool, float, int, complex)):
            return obj_
        rep_ = []
        if deep > 0:
            for attr_ in dir(obj_):
                if attr_.startswith("_") and not show_private:
                    continue
                obj = obj_.__getattribute__(attr_)

                if isinstance(obj, (str, bool, float, int, complex, bytes, bytearray)):
                    rep_.append(f"{attr_} = {obj_repr(obj)}")
                    continue
                if callable(obj) and not show_methods:
                    continue

                if is_iterable(obj):
                    temp_v = []
                    for k in obj:
                        if isinstance(obj, dict):
                            k = f"{k}:{type(obj[k])}"
                        elif is_iterable(k):
                            k = obj_repr(k, deep=deep)
                            deep -= 1
                        else:
                            k = str(k)
                        temp_v.append(k)
                        if len(temp_v) == val_limit:
                            break
                    temp_v = ", ".join(temp_v)  # fix me, if bytes ...
                    obj = f"{obj.__class__.__name__}({temp_v} ...)"
                rep_.append(f"{attr_} = {obj}")
                if len(rep_) >= attr_limit:
                    rep_.append("...")
                    break
        else:
            return repr(obj_)

    except Exception as err:
        logger.error(err)
        rep_ = []
    rep_ = ",\n    ".join(rep_)
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
    return sorted([i for i in filter(lambda attr: not attr.startswith("_"), dir(obj))])


def sample(
        v: Sequence, k: int = None, is_random: bool = False) -> Union[list, dict, set, Any]:
    """
    Get sample of anything

    @param v: Any
    @param k: int
    @param is_random: default False
    @return: sample iterable
    """
    result = chunk(v, batch_size=k, is_random=is_random, max_batches=1)[0]

    if k == 1 and len(result) == 1:
        if isinstance(result, dict):
            return result
        return next(iter(result))
    return result


def visualize_sample(v: Sequence, k: int = None, is_random: bool = False, tr_k_iter: int = 6, tr_k_str: int = 20,
                     tr_k_dict_keys: int = 20, p_print: bool = True, str_width: int = 200):
    """
    Samples then (p)prints a (truncated) version of the sample. Helpful for visualizing data structures.
    Args:
        v: sequence
        k: number of samples
        is_random: should shuffle
        tr_k_iter: how many items of iterables to keep in the truncated version of the sample, `0` to disable
        tr_k_str: truncated length of strings, `0` to disable
        tr_k_dict_keys: truncated number of dictionary keys, `0` to disable
        p_print: should pprint or print
        str_width: width of strings in the output, used if p_print
    """

    obj_sample = sample(v=copy(v), k=k, is_random=is_random)
    truncated_sample = truncate(data=obj_sample, k_iter=tr_k_iter, k_str=tr_k_str, k_dict_keys=tr_k_dict_keys)
    if p_print:
        pprint = NoStringWrappingPrettyPrinter(str_width=str_width).pprint
        pprint(truncated_sample)
    else:
        print(truncated_sample)


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


def camel_case_to_snake(value: str):
    snaked_ = []
    for i, char in enumerate(value):
        if not i == 0 and char.isupper():
            char = f"_{char}"
        snaked_.append(char)
    return "".join(snaked_).lower()


@depreciation(alternative="camel_case_to_snake")
def camel_to_snake(value: str):
    return camel_case_to_snake(value)


def camel_case(value: str, sep: Union[str, None] = None, upper_first=False):
    if sep is None:
        sep = [" "]
    elif isinstance(sep, (str, int, float)):
        sep = [str(sep)]
    value = value.lower().title()
    for sp in sep:
        value = value.replace(sp, '')
    if upper_first:
        return value
    return value[0].lower() + value[1:]


def snake_case_to_camel(value, upper_first=False):
    return camel_case(value, sep="_", upper_first=upper_first)


def get_implements(klass: type):
    classes = klass.__subclasses__()
    collected_classes = []
    for k in classes:
        k_classes = k.__subclasses__()
        if k_classes:
            collected_classes += get_implements(k)
        if not k.__name__.startswith("_"):
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


def group_by(values, fn, get_freq: bool = False) -> Union[dict, Tuple[dict, dict]]:
    """
    group items by result of fn (function)

    eg.
    >>> import cereja as cj
    >>> values = ['joab', 'leite', 'da', 'silva', 'Neto', 'você']
    >>> cj.group_by(values, lambda x: 'N' if x.lower().startswith('n') else 'OTHER')
    # {'OTHER': ['joab', 'leite', 'da', 'silva', 'você'], 'N': ['Neto']}
    >>> cj.group_by(values, lambda x: 'N' if x.lower().startswith('n') else 'OTHER', get_freq=True)
    # ({'OTHER': ['joab', 'leite', 'da', 'silva', 'você'], 'N': ['Neto']},
    #  {'OTHER': 5, 'N': 1})

    @param values: list of values
    @param fn: a function
    @param get_freq: if True, returns a tuple containing the main result of the function followed by the frequency
    distribution of the groups, respectively
    """
    d = defaultdict(list)
    for el in values:
        d[fn(el)].append(el)

    d = dict(d)
    result = (d, dict(map(lambda t: (t[0], len(t[1])), d.items()))) if get_freq else d
    return result


def import_string(dotted_path):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as err:
        raise ImportError(f"{dotted_path} doesn't look like a module path") from err

    module = import_module(module_path)

    try:
        return getattr(module, class_name)
    except AttributeError as err:
        raise ImportError(
                f"Module {module_path} does not define a {class_name} attribute/class"
        ) from err


def get_attr_if_exists(obj: Any, attr: str) -> Union[object, None]:
    if hasattr(obj, attr):
        return getattr(obj, attr)
    return None


def fill(value: Union[list, str, tuple], max_size, with_=" ") -> Any:
    """
    Calculates and adds value
    """
    fill_values = [with_] * (max_size - len(value))
    if isinstance(value, str):
        fill_values = " ".join(fill_values)
        value = f"{value}{fill_values}"
    elif isinstance(value, list):
        value += fill_values
    elif isinstance(value, tuple):
        value += tuple(fill_values)
    return value


def list_methods(klass) -> List[str]:
    methods = []
    for i in dir(klass):
        if i.startswith("_") or not callable(getattr(klass, i)):
            continue
        methods.append(i)
    return methods


def string_to_literal(val: Union[str, bytes]):
    if isinstance(val, (str, bytes)):
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
    assert isinstance(
            instance, types.ModuleType
    ), "You need to submit a module instance."
    logger.debug(f"Checking module {instance.__name__}")
    definitions = {}
    for i in dir(instance):
        if i.startswith("_"):
            continue
        exclude = (
                get_attr_if_exists(instance, "_exclude") or kwargs.get("_exclude") or []
        )
        include = (
                get_attr_if_exists(instance, "_include") or kwargs.get("_include") or []
        )

        obj = get_attr_if_exists(instance, i)

        if i in include:
            definitions[i] = obj

        if obj is not None and i not in exclude and callable(obj):
            if obj.__module__ == instance.__name__:
                definitions[i] = obj
    logger.debug(f"Collected: {definitions}")
    return definitions


def get_python_executable():
    import cereja as cj
    if sys.platform == 'win32':
        exec_paths = ['python.exe',
                      'Scripts/python.exe',
                      'bin/python.exe']
        exec_python = None
        for p in exec_paths:
            _exec_python = cj.Path(f'{sys.exec_prefix}/{p}')
            if _exec_python.exists:
                exec_python = _exec_python
                break
        assert exec_python is not None, 'Error to install dependences: Python executable not founded.'

    else:
        exec_python = sys.executable

    return exec_python


def install_if_not(lib_name: str):
    from cereja.display import console

    try:
        importlib.import_module(lib_name)
        output = "Alredy Installed"
    except ImportError:
        from ..system.commons import run_on_terminal

        command_ = f'"{get_python_executable()}" -m pip install {lib_name}'
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


def combine_with_all(
        a: list, b: list, n_a_combinations: int = 1, is_random: bool = False
) -> List[Tuple[Any, ...]]:
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

    combination = (
        itertools.combinations(a, n_a_combinations) if n_a_combinations > 1 else a
    )
    product_with_b = list(itertools.product(combination, b))
    if is_random:
        random.shuffle(product_with_b)
    return product_with_b


def value_from_memory(memory_id):
    """
    Retrieve the Python object stored at a specific memory address.

    Args:
    memory_id (int): The memory address of the object.

    Returns:
    object: The Python object stored at the given memory address, or None if the retrieval fails.
    """
    try:
        return ctypes.cast(memory_id, ctypes.py_object).value
    except (ValueError, ctypes.ArgumentError):
        raise ValueError(f"Memory ID {memory_id} isn't valid.")


def sort(iterable, reverse=False):
    """
    Sort a list that may contain a mix of different types including other lists or tuples.

    Args:
    iterable (list): A list which may contain mixed types.

    Returns:
    list: A sorted list.
    """

    def sort_key(elem):
        """
        A key function for sorting which handles elements of different types.
        Converts the element to a string for comparison purposes.
        """
        if isinstance(elem, (list, tuple)):
            return str([sort_key(e) for e in elem])
        return str(elem)

    return sorted(iterable, key=sort_key, reverse=reverse)


def combinations(iterable, size, is_sorted=False):
    """
    Generate all possible combinations of a certain size from an iterable.

    Args:
    iterable (iterable): An iterable of Python objects.
    size (int): The size of each combination.

    Returns:
    list of tuples: A list containing tuples of the combinations generated.
    """
    if not is_sorted:
        return list(itertools_combinations(iterable, size))
    try:
        return list(map(lambda x: tuple(sort(x)), itertools_combinations(iterable, size)))
    except Exception as err:
        raise Exception(f"Can't sort the pairs. {err}")


def combinations_sizes(iterable, min_size, max_size, is_sorted=False):
    """
    Generate all possible combinations for all sizes within the specified range from an iterable.

    Args:
    iterable (iterable): An iterable of Python objects.
    min_size (int): The minimum size of the combinations.
    max_size (int): The maximum size of the combinations.

    Returns:
    list of tuples: A list containing tuples of all combinations for sizes between min_size and max_size.
    """
    res = []
    for n in range(min_size, max_size + 1):
        res.extend(combinations(iterable, n, is_sorted=is_sorted))
    return res


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
        return filter(
                lambda attr_: attr_.__contains__("__") is False, dir(self._instance_obj)
        )

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
        return f"{self._prefix_attr}{attr_}"

    def __getattr__(self, item):
        return self.__getattribute__(self.parse_attr(item))

    class _Attr(object):
        def __init__(self, name: str, value: Any):
            self.name = name
            self.is_callable = callable(value)
            self.is_private = self.name.startswith("_")
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
            """==value"""
            if isinstance(other, self.__class__):
                return NotImplemented
            self.tests_case = (other, self.class_of_attr.__eq__, "==")
            return self

        def __ge__(self, other):
            """>=value"""
            if isinstance(other, self.__class__):
                return NotImplemented
            self.tests_case = (other, self.class_of_attr.__ge__, ">=")
            return self

        def __gt__(self, other):
            """>value"""
            if isinstance(other, self.__class__):
                return NotImplemented
            self.tests_case = (other, self.class_of_attr.__gt__, ">")
            return self

        def __le__(self, other):
            """<=value."""
            if isinstance(other, self.__class__):
                return NotImplemented
            self.tests_case = (other, self.class_of_attr.__le__, "<=")
            return self

        def __lt__(self, other):
            """<value."""
            if isinstance(other, self.__class__):
                return NotImplemented
            self.tests_case = (other, self.class_of_attr.__lt__, "<")
            return self

        def __ne__(self, other):
            """!=value."""
            if isinstance(other, self.__class__):
                return NotImplemented
            self.tests_case = (other, self.class_of_attr.__ne__, "!=")
            return self

        def copy(self):
            return copy(self)

        def run(self, current_value):
            expected, operator, _ = self.tests_case
            if not operator(current_value, expected):
                return [f"{repr(current_value)} not {_} {repr(expected)}"]

            return []

    def _valid_attr(self, attr_name: str):
        assert hasattr(
                self._instance_obj, attr_name
        ), f"{self.__prefix_attr_err.format(attr_=repr(attr_name))} isn't defined."
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
        func_tests = "".join(
                cls.__template_unittest_function.format(func_name=i)
                for i in list_methods(ref)
        )
        return cls.__template_unittest_class.format(
                class_name=ref.__name__, func_tests=func_tests
        )

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
            module_func_test = "".join(module_func_test)
            tests = [
                        cls.__template_unittest_class.format(
                                class_name="Module", func_tests=module_func_test
                        )
                    ] + tests
        return cls.__template_unittest.format(tests="\n".join(tests))


def _add_license(base_dir, ext=".py"):
    from cereja.file import FileIO
    from cereja.config import BASE_DIR

    licence_file = FileIO.load(BASE_DIR)
    for file in FileIO.load_files(base_dir, ext=ext, recursive=True):
        if "Copyright (c) 2019 The Cereja Project" in file.string:
            continue
        file.insert('"""\n' + licence_file.string + '\n"""')
        file.save(exist_ok=True)


def _rescale_down(input_list, size):
    assert len(input_list) >= size, f"{len(input_list), size}"

    skip = len(input_list) // size
    for n, i in enumerate(range(0, len(input_list), skip), start=1):
        if n > size:
            break
        yield input_list[i]


def _rescale_up(values, k, fill_with=None, filling="inner"):
    size = len(values)
    assert size <= k, f"Error while resizing: {size} < {k}"

    clones = math.ceil(abs(size - k) / size)
    refill_values = abs(k - size * clones)
    if filling == "pre":
        for i in range(abs(k - size)):
            yield fill_with if fill_with is not None else values[0]

    for value in values:
        # guarantees that the original value will be returned
        yield value

        if filling != "inner":
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
    if filling == "post":
        for i in range(abs(k - size)):
            yield fill_with if fill_with is not None else values[-1]


def _interpolate(values, k):
    if isinstance(values, list):
        from ..array import Matrix

        # because true_div ...
        values = Matrix(values)
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
            yield values[previous_position] + (
                    values[next_position] - values[previous_position]
            ) / (next_position - previous_position) * delta


def rescale_values(
        values: List[Any],
        granularity: int,
        interpolation: bool = False,
        fill_with=None,
        filling="inner",
) -> List[Any]:
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
            result = list(
                    _rescale_up(values, granularity, fill_with=fill_with, filling=filling)
            )

    assert (
            len(result) == granularity
    ), f"Error while resizing the list size {len(result)} != {granularity}"
    return result


class SourceCodeAnalyzer:
    def __init__(self, reference: Any):
        self._reference = reference
        self._name: Optional[str] = None
        self._doc: Optional[str] = None
        self._source_code: Optional[str] = None

    @property
    def source_code(self) -> str:
        if self._source_code is None:
            self._source_code = inspect.getsource(self._reference).lstrip()
        return self._source_code

    @property
    def name(self) -> str:
        if self._name is None:
            if hasattr(self._reference, "__name__"):
                self._name = self._reference.__name__
            else:
                self._name = self._reference.__class__.__name__
        return self._name

    @property
    def has_arguments(self) -> bool:
        return bool(inspect.signature(self._reference).parameters)

    @property
    def arguments(self):
        return inspect.signature(self._reference).parameters

    @property
    def argument_names(self) -> list:
        return list(self.arguments.keys())

    @property
    def argument_defaults(self) -> dict:
        return {k: v.default for k, v in self.arguments.items() if v.default != inspect.Parameter.empty}

    @property
    def argument_count(self) -> int:
        return len(self.arguments)

    @property
    def required_arguments(self) -> list:
        return [k for k, v in self.arguments.items() if v.default == inspect.Parameter.empty]

    @property
    def optional_arguments(self) -> list:
        return [k for k, v in self.arguments.items() if v.default != inspect.Parameter.empty]

    @property
    def has_kwargs(self) -> bool:
        return any(v.kind == inspect.Parameter.VAR_KEYWORD for v in self.arguments.values())

    @property
    def has_varargs(self) -> bool:
        return any(v.kind == inspect.Parameter.VAR_POSITIONAL for v in self.arguments.values())

    @property
    def docstring(self) -> Optional[str]:
        if self._doc is None:
            self._doc = inspect.getdoc(self._reference)
        return self._doc

    def save_source_code(self, path: str, **kwargs):
        from cereja import FileIO, Path

        path = Path(path)
        if path.is_dir:
            path = path.join(f"{self.name}.py")
        assert path.suffix == ".py", "Only Python source code is allowed."
        FileIO.create(path, self.source_code).save(**kwargs)


@depreciation(alternative="SourceCodeAnalyzer")
class Source(SourceCodeAnalyzer):
    def __init__(self, reference: Any):
        super().__init__(reference)


def is_iterable(obj: Any) -> bool:
    """
    Return whether an object is iterable or not.

    This function checks if the object has an __iter__ method or supports
    sequence-like indexing via __getitem__.

    Parameters:
    obj (Any): Any object to check for iterability.

    Returns:
    bool: True if the object is iterable, False otherwise.
    """
    return hasattr(obj, '__iter__') or hasattr(obj, '__getitem__')


def has_length(seq):
    try:
        _ = len(seq)
        return True
    except TypeError:
        return False


def is_sequence(obj: Any) -> bool:
    """
    Return whether an object a Sequence or not, exclude strings and empty obj.

    :param obj: Any object for check
    """
    if isinstance(obj, (str, dict, bytes, int, float)):
        return False
    return is_iterable(obj)


def is_numeric_sequence(obj: Sequence[Number]) -> bool:
    try:
        from cereja.array import flatten

        sum(flatten(obj))
    except (TypeError, ValueError):
        return False
    return True


def sort_dict(
        obj: dict,
        by_keys=False,
        by_values=False,
        reverse=False,
        by_len_values=False,
        func_values=None,
        func_keys=None,
) -> OrderedDict:
    func_values = (
        (lambda v: len(v) if by_len_values else v)
        if func_values is None
        else func_values
    )
    func_keys = (lambda k: k) if func_keys is None else func_keys

    key_func = None
    if (by_keys and by_values) or (not by_keys and not by_values):
        key_func = lambda x: (func_keys(x[0]), func_values(x[1]))
    elif by_keys:
        key_func = lambda x: func_keys(x[0])
    elif by_values:
        key_func = lambda x: func_values(x[1])
    return OrderedDict(sorted(obj.items(), key=key_func, reverse=reverse))


def list_to_tuple(obj):
    assert isinstance(
            obj, (list, set, tuple)
    ), f"Isn't possible convert {type(obj)} into {tuple}"
    result = []
    for i in obj:
        if isinstance(i, list):
            i = list_to_tuple(i)
        elif isinstance(i, (set, dict)):
            i = dict_to_tuple(i)
        result.append(i)
    return tuple(result)


def dict_values_len(obj, max_len=None, min_len=None, take_len=False):
    return {
        i: len(obj[i]) if take_len else obj[i]
        for i in obj
        if (max_len is None or len(obj[i]) <= max_len)
           and (min_len is None or len(obj[i]) >= min_len)
    }


def dict_to_tuple(obj):
    assert isinstance(
            obj, (dict, set)
    ), f"Isn't possible convert {type(obj)} into {tuple}"
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


def dict_append(obj: Dict[Any, Union[List, Tuple]],
                key: Any,
                *v,
                unique_values: bool = False,
                sort_values_by: Optional[Callable] = None,
                reverse: bool = False) -> Dict:
    """
    Add items to a key in the dictionary. If the key doesn't exist, it's created with a list and the given values.

    e.g:

    >>> my_dict = {}
    >>> dict_append(my_dict, 'key_eg', 1,2,3,4,5,6)
    {'key_eg': [1, 2, 3, 4, 5, 6]}
    >>> dict_append(my_dict, 'key_eg', [1,2])
    {'key_eg': [1, 2, 3, 4, 5, 6, [1, 2]]}

    Parameters:
    - obj: A dictionary with list or tuple values.
    - key: The key to which the values should be added.
    - v: The values to be added.
    - unique_values: Whether to ensure the values are unique.
    - sort_values_by: Optional function to sort the values.
    - reverse: Used if sort_values_by is passed.

    Returns:
    Updated dictionary.
    """
    """
        if not isinstance(obj[key], (list, tuple)):
        obj[key] = [obj[key]]
    if isinstance(obj[key], tuple):
        obj[key] = (
            *obj[key],
            *v,
        )
    else:
        for i in v:
            obj[key].append(i)
    """

    # Ensure we're working with a dictionary
    if not isinstance(obj, dict):
        raise TypeError("Error on append values. Please provide a dictionary object.")

    # Append values to existing list or tuple, or create a new list if key doesn't exist
    if key not in obj:
        obj[key] = []

    if not isinstance(obj[key], (list, tuple)):
        obj[key] = [obj[key]]

    if isinstance(obj[key], tuple):
        obj[key] = obj[key] + tuple(v)
    else:
        obj[key].extend(v)

    # Ensure unique values if requested
    if unique_values:
        if isinstance(obj[key], tuple):
            obj[key] = tuple(sorted(set(obj[key]), key=obj[key].index))
        else:
            obj[key] = sorted(set(obj[key]), key=obj[key].index)

    # Sort by given function if provided
    if sort_values_by:
        if isinstance(obj[key], tuple):
            obj[key] = tuple(sorted(obj[key], key=sort_values_by, reverse=reverse))
        else:
            obj[key].sort(key=sort_values_by, reverse=reverse)

    return obj


def dict_filter_value(obj: Dict[Any, Any], f) -> Any:
    """
    Results is a filtered dict by f func result

    @param obj: is a dict
    @param f: function filter
    @return:
    """
    inv_dict = invert_dict(obj)
    filter_val = f(inv_dict)
    res = inv_dict[filter_val]
    if isinstance(res, list):
        return dict(map(lambda x: (x, filter_val), res))
    return {res: filter_val}


def dict_max_value(obj: Dict[Any, Any]) -> Any:
    """
    Results is a filtered dict by max value

    >>> import cereja as cj
    >>> cj.dict_max_value({'oi': 10, 'aqui': 20, 'sei': 20})
    {'aqui': 20, 'sei': 20}

    @param obj: is a dict
    @return: dict filtered
    """
    return dict_filter_value(obj, max)


def dict_min_value(obj: Dict[Any, Any]) -> Any:
    """
    Results is a filtered dict by min value

    >>> import cereja as cj
    >>> cj.dict_min_value({'oi': 10, 'aqui': 20, 'sei': 20})
    {'oi': 10}

    @param obj: is a dict
    @return: dict filtered
    """
    return dict_filter_value(obj, min)


def get_zero_mask(number: int, max_len: int = 3) -> str:
    """
    Returns string of numbers formated with zero mask
    eg.
    >>> get_zero_mask(100, 4)
    '0100'
    >>> get_zero_mask(101, 4)
    '0101'
    >>> get_zero_mask(101, 4)
    '0101'
    """
    return f"%0.{max_len}d" % number


def get_batch_strides(data, kernel_size, strides=1, fill_=False, take_index=False):
    """
    Returns batches of fixed window size (kernel_size) with a given stride
    @param data: iterable
    @param kernel_size: window size
    @param strides: default is 1
    @param take_index: add number of index on items
    @param fill_: padding last batch if it needs
    """
    batches = []
    for index, item in enumerate(data):
        batches.append(item if not take_index else [index, item])
        if index % strides == 0 and len(batches) >= kernel_size:
            yield batches[:kernel_size]
            batches = batches[strides:]
    if len(batches):
        yield rescale_values(
                batches, granularity=kernel_size, filling="post"
        ) if fill_ else batches


def prune_values(values: Sequence, factor=2):
    assert is_indexable(values), TypeError("object is not subscriptable")
    if len(values) <= factor:
        return values
    w = round(len(values) / 2)
    k = int(round(w / factor))
    res = values[w - k: w + k]

    if len(res) == 0:
        return values[k]
    return res


def str_gen(pattern: AnyStr) -> Sequence[AnyStr]:
    regex = re.compile(pattern)
    return regex.findall(string.printable)


def encode_coordinates(x: int, y: int):
    """
    Encode the coordinates (x, y) into a single lParam value.

    The encoding is done by shifting the y-coordinate 16 bits to the left and
    then performing a bitwise OR with the x-coordinate.

    Args:
        x (int): The x-coordinate.
        y (int): The y-coordinate.

    Returns:
        int: The encoded lParam value.
    """
    return (y << 16) | x


def decode_coordinates(lparam: int):
    """
    Decode the lParam value back into the original coordinates (x, y).

    The decoding is done by extracting the lower 16 bits for the x-coordinate
    and the upper 16 bits for the y-coordinate.

    Args:
        lparam (int): The encoded lParam value.

    Returns:
        tuple: A tuple containing the x and y coordinates.
    """
    x = lparam & 0xFFFF
    y = (lparam >> 16) & 0xFFFF
    return x, y


class PoolMeta(type):
    """A thread-safe implementation to control the maximum number of instances."""
    _instances = []
    _lock: threading.Lock = threading.Lock()  # Class-level lock
    _max_instances = 3  # Define the maximum number of instances allowed
    _available_instances = threading.Condition(_lock)

    def __call__(cls, *args, **kwargs):
        with cls._available_instances:
            while len(cls._instances) >= cls._max_instances:
                cls._available_instances.wait()
            instance = super(PoolMeta, cls).__call__(*args, **kwargs)
            cls._instances.append(instance)
            return instance

    def release_instance(cls, instance):
        with cls._available_instances:
            if instance in cls._instances:
                cls._instances.remove(instance)
                cls._available_instances.notify()

    def set_max_instances(cls, max_instances):
        cls._max_instances = max_instances

    def get_max_instances(cls):
        return cls._max_instances

    def get_instances(cls):
        return cls._instances


class SingletonMeta(type):
    """A thread-safe implementation of Singleton."""
    _instances = {}
    _lock: threading.Lock = threading.Lock()  # Class-level lock

    def __call__(cls, *args, **kwargs):
        # First, check if an instance exists
        if cls not in cls._instances:
            with cls._lock:
                # Double-check locking
                if cls not in cls._instances:
                    cls._instances[cls] = super(SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
