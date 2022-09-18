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
from typing import Union, AnyStr
import unicodedata

__all__ = ["Unicode"]


class Unicode(object):
    """
    Copyright (c) 2019 The Cereja Project
    source: https://github.com/jlsneto/cereja

    Returns the unicode that the `value` represents.
    Supports unicodes in the `range(1114111)`

    usage e.g:

    Acceptable string and integer values
    (binary, octal, decimal or hex)
    >>> Unicode("0x1F352") # Unicode("1F352") is acceptable
    Unicode('\U0001f352', 'CHERRIES')
    >>> Unicode(127826) # Unicode(0x1F352) is acceptable
    Unicode('\U0001f352', 'CHERRIES')

    Acceptable operators '+' and '-'
    >>> unicode_a = Unicode(127826)
    Unicode('\U0001f352', 'CHERRIES')
    >>> unicode_b = unicode_a + 10
    Unicode('\U0001f35c', 'STEAMING BOWL')
    >>> unicode_c = unicode_a - 50
    Unicode('\U0001f320', 'SHOOTING STAR')
    :param value: you can sent strings and integers
    :return: Type Unicode
    """

    __max_unicode = sys.maxunicode

    def __init__(self, value: Union[str, int]):
        self._value = self.__parse(value)
        self.value = self.__value
        self.name = self.__name
        self.decimal = self.__decimal
        self.hex = self.__hex
        self.bin = self.__bin
        self.oct = self.__oct

    def __repr__(self):
        return f"{self.__class__.__name__}{self._value, self.name}"

    def __str__(self):
        return self.value

    def __add__(self, other):
        if isinstance(other, int):
            other = self.parse(other)
            return self.parse(self.decimal + other.decimal)
        raise TypeError("Isn't possible. You can add with integer type")

    def __sub__(self, other):
        if isinstance(other, int):
            other = self.parse(other)
            return self.parse(self.decimal - other.decimal)
        raise TypeError("Isn't possible. You can sub with integer type")

    @classmethod
    def __parse_ord(cls, value: str) -> int:
        value = value.encode("ascii", "backslashreplace").lower()

        if value.startswith(b"\u") or value.startswith(b"\\u"):
            value = value.replace(b"\u", b"")

        value = value.decode("unicode_escape").lower()
        if value.startswith("u"):
            value = value.replace("u+", "").replace("u", "")

        if value.startswith("0x"):
            value = int(value, 16)
        elif value.startswith("0b"):
            value = int(value, 2)
        elif value.startswith("0o"):
            value = int(value, 8)
        else:
            value = int(value, 16)
        return value

    @classmethod
    def __parse(cls, code_) -> AnyStr:
        try:
            if isinstance(code_, str):
                code_ = cls.__parse_ord(code_)
            return chr(code_)
        except Exception as err:
            msg_error = "Conversion error."
            if isinstance(code_, int):
                if code_ > cls.__max_unicode:
                    msg_error = f"{msg_error} Max unicode is {hex(cls.__max_unicode)} ({cls.__max_unicode} on base 10)"
            raise ValueError(msg_error) from err

    @classmethod
    def parse(cls, value: Union[str, int]) -> "Unicode":
        """
        Copyright (c) 2019 The Cereja Project
        source: https://github.com/jlsneto/cereja

        Returns the unicode that the `value` represents.
        Supports unicodes in the `range(1114111)`

        usage e.g:

        Acceptable string values
        >>> Unicode.parse("1F352") # is the unicode value
        '\U0001f352'
        >>> Unicode.parse("0x1F352") # full hexadecimal
        '\U0001f352'

        Acceptable int values in system of numerical notation:
        (binary, octal, decimal or hex)
        >>> Unicode.parse(127826) # is a decimal
        '\U0001f352'
        >>> Unicode.parse(0x1F352) # is a same value in hexadecimal
        '\U0001f352'

        :param value: you can sent strings and integers
        :return: Type Unicode
        """
        return cls(value)

    @property
    def __decimal(self):
        return ord(self._value)

    @property
    def __hex(self):
        return hex(self.__decimal)

    @property
    def __oct(self):
        return oct(self.__decimal)

    @property
    def __bin(self):
        return bin(self.__decimal)

    @property
    def __name(self):
        try:
            return unicodedata.name(self._value)
        except ValueError:
            return "UNKNOWN"

    @property
    def __value(self) -> str:
        return self._value
