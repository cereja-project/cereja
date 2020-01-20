from . import utils
from importlib import import_module

cj_modules_dotted_path = utils.import_string('cereja.conf.cj_modules_dotted_path')

for dot_module in cj_modules_dotted_path:
    locals().update(utils.module_references(import_module(dot_module)))
