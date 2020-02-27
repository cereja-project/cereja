import sys
import logging

__all__ = []
# using by utils.module_references
_explicit_exclude = ["console_logger", "cj_modules_dotted_path"]

# Used to add the functions of each module at the root
cj_modules_dotted_path = ['cereja.arraytools', 'cereja.conf', 'cereja.decorators', 'cereja.path',
                          'cereja.utils', 'cereja.concurrently', 'cereja.display']

console_logger = logging.StreamHandler(sys.stdout)
logging.basicConfig(handlers=(console_logger,), level=logging.WARN)
