import sys
import logging

VERSION = "0.3.5"

# using by utils.module_references
_explicit_exclude = ["console_logger", "cj_modules"]
_explicit_include = ["VERSION"]

# Used to add the functions of each module at the root
cj_modules_dotted_path = ['cereja.common', 'cereja.conf', 'cereja.decorators', 'cereja.path',
                          'cereja.utils']

console_logger = logging.StreamHandler(sys.stdout)
logging.basicConfig(handlers=(console_logger,), level=logging.WARN)
