import sys
import logging

# using by utils.module_references
_explicit_exclude = ["console_logger", "cj_modules_dotted_path"]

# Used to add the functions of each module at the root
cj_modules_dotted_path = ['cereja.common', 'cereja.conf', 'cereja.decorators', 'cereja.path',
                          'cereja.utils', 'cereja.concurrently']

console_logger = logging.StreamHandler(sys.stdout)
logging.basicConfig(handlers=(console_logger,), level=logging.WARN)
