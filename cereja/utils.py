from importlib import import_module
import subprocess
import importlib
import sys
import types
from typing import Any, Union
import logging

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


def set_log_level(level: int):
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
    if not isinstance(level, int):
        raise TypeError(f"Value is'nt valid. {set_log_level.__doc__}")
    import logging
    log = logging.getLogger()
    log.setLevel(level)
    logger.info(f"Update log level to {level}")


def logger_level():
    import logging
    return logging.getLogger().level
