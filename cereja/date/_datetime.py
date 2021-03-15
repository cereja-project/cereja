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
from datetime import datetime
from typing import Union

__all__ = ['DateTime']


class DateTime(datetime):
    @classmethod
    def _validate_timestamp(cls, value) -> Union[int, float]:
        assert isinstance(value, (int, float)), f"{value} is not valid."
        return value

    @classmethod
    def _validate_date(cls, other):
        assert isinstance(other, datetime), f"Send {datetime} obj"
        return other

    @classmethod
    def days_from_timestamp(cls, timestamp):
        return timestamp / (3600 * 24)

    @classmethod
    def into_timestamp(cls, days=0, min_=0, sec=0):
        days = 3600 * 24 * days if cls._validate_timestamp(days) else days
        min_ = 3600 * 60 * min_ if cls._validate_timestamp(min_) else min_
        return days + min_ + cls._validate_timestamp(sec)

    def add(self, days=0, min_=0, sec=0):
        return self.fromtimestamp(self.timestamp() + self.into_timestamp(days, min_, sec))

    def sub(self, days=0, min_=0, sec=0):
        return self.fromtimestamp(abs(self.timestamp() - self.into_timestamp(days, min_, sec)))

    def days_between(self, other):
        return self.days_from_timestamp(abs(self.timestamp() - self._validate_date(other).timestamp()))

    def compare(self, other):
        '''
        compares date time and 
        returns 1 if the instantiated date is greater, 
        -1 if the instantiated date is less than,
        and 0 if they are equal.
        '''
        return 1 if self.timestamp() > self._validate_date(other).timestamp() else -1 if self.timestamp() < self._validate_date(other).timestamp() else 0