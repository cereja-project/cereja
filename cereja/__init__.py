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
from .config import conf
from cereja.utils import *
from . import utils
from . import display
from cereja.display import *
from . import file
from cereja.file import *
from . import array
from cereja.array import *
from . import system
from cereja.system import *
from cereja.system.unicode import *
from . import utils
from .utils import decorators
from cereja.concurrently import *
from . import mltools
from cereja.mltools import *
from cereja.utils.version import get_version_pep440_compliant
from cereja.system.unicode import *
from . import date
from cereja.date import *
from . import hashtools
from . import mathtools
from cereja.mathtools import *
from . import experimental
from ._requests import request

VERSION = "1.4.4.final.1"

__version__ = get_version_pep440_compliant(VERSION)

NON_BMP_SUPPORTED = None
if NON_BMP_SUPPORTED is None:
    # This is important, as there may be an exception if the terminal does not support unicode bmp
    try:
        unicode_ = f"\033[31m\U0001F352\033[30m"
        print(f"{unicode_} Using Cereja v.{get_version_pep440_compliant()}\r")
        NON_BMP_SUPPORTED = True
    except (UnicodeEncodeError, UnicodeDecodeError, UnicodeError, UnicodeTranslateError):
        NON_BMP_SUPPORTED = False
# cj_modules_dotted_path = utils.import_string('cereja.conf.cj_modules_dotted_path')
#
# for dot_module in cj_modules_dotted_path:
#     globals().update(utils.module_references(import_module(dot_module)))
