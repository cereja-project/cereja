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
from . import geolinear
from .config import conf
from .utils import *
from . import utils
from . import display
from .display import *
from . import file
from .file import *
from . import array
from .array import *
from . import system
from .system import *
from .system.unicode import *
from .utils import decorators
from .concurrently import *
from . import mltools
from .mltools import *
from .utils.version import get_version_pep440_compliant
from .system.unicode import *
from . import date
from .date import *
from . import hashtools
from . import mathtools
from .mathtools import *
from . import experimental
from ._requests import request
from . import scraping
from . import wcag

VERSION = "2.0.5.final.0"

__version__ = get_version_pep440_compliant(VERSION)


def print_cereja_version():
    # This is important, as there may be an exception if the terminal does not support unicode bmp
    try:
        unicode_ = f"\033[31m\U0001F352\033[0;0m"
        print(f"{unicode_} Using Cereja v.{__version__}\r")
        return True
    except (UnicodeEncodeError, UnicodeDecodeError, UnicodeError, UnicodeTranslateError):
        return False


NON_BMP_SUPPORTED = print_cereja_version()
