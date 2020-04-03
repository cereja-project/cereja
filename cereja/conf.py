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

import sys
import logging
from .utils import get_version_pep440_compliant

__all__ = []
# using by utils.module_references
_exclude = ["console_logger", "cj_modules_dotted_path"]

# Used to add the functions of each module at the root
cj_modules_dotted_path = ['cereja.arraytools', 'cereja.conf', 'cereja.decorators', 'cereja.path',
                          'cereja.utils', 'cereja.concurrently', 'cereja.display', 'cereja.filetools', 'cereja.unicode']

console_logger = logging.StreamHandler(sys.stdout)
logging.basicConfig(handlers=(console_logger,), level=logging.WARN)

NON_BMP_SUPPORTED = None
if NON_BMP_SUPPORTED is None:
    # This is important, as there may be an exception if the terminal does not support unicode bmp
    try:
        unicode_ = f"\033[31m\U0001F352\033[30m"
        sys.stdout.write(f"{unicode_} Using Cereja v.{get_version_pep440_compliant()}\n")
        NON_BMP_SUPPORTED = True
    except (UnicodeEncodeError, UnicodeDecodeError, UnicodeError, UnicodeTranslateError):
        NON_BMP_SUPPORTED = False
