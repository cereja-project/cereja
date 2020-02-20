import datetime
import functools
import os
from importlib import import_module
import subprocess
import importlib
import sys
import types
import random
from typing import Any, Union, Sequence, List, Tuple
import logging
import itertools

# Needed init configs
from logging import config

from cereja.cj_types import PEP440

logger = logging.getLogger(__name__)


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


def is_function(obj: Any) -> bool:
    return isinstance(obj, types.FunctionType)


def module_references(instance: types.ModuleType, **kwargs) -> dict:
    """
    dict of all functions and classes defined in the module.

    To also list the variables it is necessary to define explicitly with the special variable on your module
    _implicit_include

    **kwargs:
    _implicit_include -> to include any definition and variables
    _explicit_exclude -> to exclude any definition

    :param instance:
    :return: List[str]
    """
    assert isinstance(instance, types.ModuleType), "You need to submit a module instance."
    logger.debug(f"Checking module {instance.__name__}")
    definitions = {}
    for i in dir(instance):
        if i.startswith('_'):
            continue
        excludes = get_attr_if_exists(instance, "_explicit_exclude") or kwargs.get("_explicit_exclude") or []
        implicit = get_attr_if_exists(instance, "_explicit_include") or kwargs.get("_explicit_include") or []

        obj = get_attr_if_exists(instance, i)

        if i in implicit:
            definitions[i] = obj

        if obj is not None and i not in excludes and callable(obj):
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

    return f"{root_version}{sub}"


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


if __name__ == '__main__':
    print(combine_with_all([1, 2, 3], ['anything_a', 'anything_b'], 2))
