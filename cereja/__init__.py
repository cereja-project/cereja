from cereja.utils import get_version_pep440_compliant
from . import utils
from importlib import import_module

VERSION = "1.0.6.final.0"

__version__ = get_version_pep440_compliant(VERSION)

cj_modules_dotted_path = utils.import_string('cereja.conf.cj_modules_dotted_path')

for dot_module in cj_modules_dotted_path:
    globals().update(utils.module_references(import_module(dot_module)))
