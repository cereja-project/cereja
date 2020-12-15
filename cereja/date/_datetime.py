from datetime import datetime
from typing import Union


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
