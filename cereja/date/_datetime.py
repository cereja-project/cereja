import re
from datetime import datetime
from typing import Union, List

__all__ = ['DateTime', 'AmbiguousDateFormatError']


class AmbiguousDateFormatError(ValueError):
    def __init__(self, date_string, possible_formats):
        self.date_string = date_string
        self.possible_formats = possible_formats
        message = (
            f"Ambiguous date format for '{date_string}'. "
            f"Possible formats: {possible_formats}"
        )
        super().__init__(message)


class UnrecognizedDateFormatError(ValueError):
    pass


class DateTime(datetime):
    """
    A subclass of the built-in datetime class with additional methods for parsing and comparing dates.

    This class extends the functionality of the standard datetime class by adding methods to:
    - Parse date strings in various formats into DateTime objects.
    - Compare dates for equality.
    - Add or subtract time intervals from dates.
    - Calculate the number of days between dates.
    - Validate and disambiguate date formats.

    Attributes:
        __DATE_FORMATS (dict): A dictionary mapping regex patterns to lists of date formats.
    """
    __DATE_FORMATS = {
        r'\d{1,2}/\d{1,2}/\d{2,4}':                  ['%d/%m/%Y', '%m/%d/%Y', '%d/%m/%y', '%m/%d/%y'],
        r'\d{1,2}-\d{1,2}-\d{2,4}':                  ['%d-%m-%Y', '%m-%d-%Y', '%d-%m-%y', '%m-%d-%y'],
        r'\d{2,4}/\d{1,2}/\d{1,2}':                  ['%Y/%m/%d', '%y/%m/%d', '%Y/%d/%m', '%y/%d/%m'],
        r'\d{2,4}-\d{1,2}-\d{1,2}':                  ['%Y-%m-%d', '%y-%m-%d', '%Y-%d-%m', '%y-%d-%m'],
        r'\d{8}':                                    ['%Y%m%d', '%d%m%Y', '%Y%d%m'],
        r'\d{6}':                                    ['%y%m%d', '%d%m%y', '%y%d%m'],
        r'\d{2}-\d{2}-\d{2}':                        ['%y-%m-%d', '%d-%m-%y'],
        r'\d{2}\.\d{2}\.\d{4}':                      ['%d.%m.%Y'],  # DD.MM.YYYY
        r'\d{4}\.\d{2}\.\d{2}':                      ['%Y.%m.%d'],  # YYYY.MM.DD
        r'\d{2}\s[A-Za-z]{3}\s\d{4}':                ['%d %b %Y'],  # DD Mon YYYY
        r'[A-Za-z]{3}\s\d{2},\s\d{4}':               ['%b %d, %Y'],  # Mon DD, YYYY
        r'\d{2}-[A-Za-z]{3}-\d{4}':                  ['%d-%b-%Y'],  # DD-Mon-YYYY
        r'\d{2}\s[A-Za-z]+\s\d{4}':                  ['%d %B %Y'],  # DD Month YYYY
        r'[A-Za-z]+\s\d{2},\s\d{4}':                 ['%B %d, %Y'],  # Month DD, YYYY
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}':      ['%Y-%m-%dT%H:%M:%S'],  # ISO 8601
        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}':      ['%Y-%m-%d %H:%M:%S'],  # Com tempo
        r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}':      ['%d/%m/%Y %H:%M:%S'],  # DD/MM/YYYY HH:MM:SS
        r'\d{2}-\d{2}-\d{4} \d{2}:\d{2}:\d{2}':      ['%d-%m-%Y %H:%M:%S'],  # DD-MM-YYYY HH:MM:SS
        r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}':      ['%Y/%m/%d %H:%M:%S'],  # YYYY/MM/DD HH:MM:SS
        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}':            ['%Y-%m-%d %H:%M'],  # YYYY-MM-DD HH:MM
        r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}':            ['%d/%m/%Y %H:%M'],  # DD/MM/YYYY HH:MM
        r'\d{2}-\d{2}-\d{4} \d{2}:\d{2}':            ['%d-%m-%Y %H:%M'],  # DD-MM-YYYY HH:MM
        r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}':            ['%Y/%m/%d %H:%M'],  # YYYY/MM/DD HH:MM
        r'\d{2}[A-Za-z]{3}\d{4}':                    ['%d%b%Y'],  # DDMonYYYY
        r'[A-Za-z]{3}\s\d{2}':                       ['%b %d'],  # Mon DD (ano atual)
        r'\d{2}\s[A-Za-z]{3}':                       ['%d %b'],  # DD Mon (ano atual)
        r'[A-Za-z]{3}\s\d{4}':                       ['%b %Y'],  # Mon YYYY (dia = 1)
        # Formats with timezone (manual parsing)
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z':     ['%Y-%m-%dT%H:%M:%SZ'],  # ISO 8601 UTC
        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+': ['%Y-%m-%d %H:%M:%S.%f'],  # With microseconds
        # Other formats can be added here
    }

    def __new__(cls, *args, **kwargs):
        if args and isinstance(args[0], str):
            return cls.parse_from_string(args[0])
        return super().__new__(cls, *args, **kwargs)

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
        return self.fromtimestamp(
                self.timestamp() + self.into_timestamp(days, min_, sec)
        )

    def sub(self, days=0, min_=0, sec=0):
        return self.fromtimestamp(
                abs(self.timestamp() - self.into_timestamp(days, min_, sec))
        )

    def days_between(self, other):
        return self.days_from_timestamp(
                abs(self.timestamp() - self._validate_date(other).timestamp())
        )

    def compare(self, other):
        """
        compares date time and
        returns 1 if the instantiated date is greater,
        -1 if the instantiated date is less than,
        and 0 if they are equal.
        """
        return (
            1
            if self.timestamp() > self._validate_date(other).timestamp()
            else -1
            if self.timestamp() < self._validate_date(other).timestamp()
            else 0
        )

    @classmethod
    def _parse_with_formats(cls, date_string: str, date_formats: List[str]):
        """
        Parse the given date string using a list of possible date formats.

        This method attempts to parse the date string with each format in the provided list.
        If the year or day is not specified in the format, it defaults to the current year or the first day of the month, respectively.

        Args:
            date_string (str): The date string to be parsed.
            date_formats (List[str]): A list of date formats to try for parsing the date string.

        Returns:
            List[Tuple[datetime, str]]: A list of tuples where each tuple contains a parsed datetime object and the format used.
        """
        parsed_dates = []
        for date_format in date_formats:
            try:
                parsed_date = cls.strptime(date_string, date_format)
                if '%Y' not in date_format and '%y' not in date_format:
                    parsed_date = parsed_date.replace(year=datetime.now().year)
                if '%d' not in date_format:
                    parsed_date = parsed_date.replace(day=1)
                parsed_dates.append((parsed_date, date_format))
            except ValueError:
                continue
        return parsed_dates

    @classmethod
    def _get_possible_dates(cls, date_string: str):
        possible_dates = []
        for regex, date_formats in cls.__DATE_FORMATS.items():
            if re.fullmatch(regex, date_string):
                dates = cls._parse_with_formats(date_string, date_formats)
                possible_dates.extend(dates)
        if not possible_dates:
            raise UnrecognizedDateFormatError(f"Unrecognized date format: {date_string}")
        return possible_dates

    @classmethod
    def parse_from_string(cls, date_string: str):
        """
        Parse a date string into a DateTime object.

        This method attempts to parse the given date string into a DateTime object.
        It uses a set of predefined date formats to identify the correct format of the date string.
        If multiple possible dates are found, it tries to disambiguate them to find a valid date.
        If no valid date can be determined, it raises an AmbiguousDateFormatError.

        Args:
            date_string (str): The date string to be parsed.

        Returns:
            DateTime: The parsed DateTime object.

        Raises:
            ValueError: If the date string format is unrecognized.
            AmbiguousDateFormatError: If multiple possible dates are found and cannot be disambiguated.
        """
        possible_dates = cls._get_possible_dates(date_string)

        if len(possible_dates) == 1:
            return possible_dates[0][0]
        else:
            selected_date = cls._disambiguate_date(possible_dates)
            if selected_date:
                return selected_date
            else:
                # If unable to disambiguate, throw an exception
                raise AmbiguousDateFormatError(date_string, [fmt for _, fmt in possible_dates])

    @classmethod
    def are_dates_equal(cls, date_str1: Union[str, datetime], date_str2: Union[str, datetime]) -> bool:
        """
        Check if two dates are equal.

        This method compares two dates, which can be either strings or datetime objects.
        It parses the date strings into datetime objects if necessary and then compares them.

        Args:
            date_str1 (Union[str, datetime]): The first date to compare, as a string or datetime object.
            date_str2 (Union[str, datetime]): The second date to compare, as a string or datetime object.

        Returns:
            bool: True if the dates are equal, False otherwise.
        """
        if isinstance(date_str1, datetime) and isinstance(date_str2, datetime):
            return date_str1 == date_str2
        if isinstance(date_str1, datetime):
            possible_dates1 = [(date_str1, None)]
        else:
            possible_dates1 = cls._get_possible_dates(date_str1)
        if isinstance(date_str2, datetime):
            possible_dates2 = [(date_str2, None)]
        else:
            possible_dates2 = cls._get_possible_dates(date_str2)
        for date1, _ in possible_dates1:
            for date2, _ in possible_dates2:
                if date1 == date2:
                    return True
        return False

    @classmethod
    def _disambiguate_date(cls, possible_dates):
        """
        Disambiguate a list of possible dates to find a valid date.

        This method filters the possible dates to find a date within a valid range (1900-2100).
        If there is only one valid date, it returns that date.
        If there are multiple valid dates, it further filters them to ensure the day and month are within valid ranges.
        If only one valid date remains after this filtering, it returns that date.
        If no valid date can be determined, it returns None.

        Args:
            possible_dates (List[Tuple[datetime, str]]): A list of tuples where each tuple contains a datetime object and the format used.

        Returns:
            datetime or None: The disambiguated valid date or None if no valid date can be determined.
        """
        dates_in_valid_range = [date for date, _ in possible_dates if 1900 <= date.year <= 2100]
        if len(dates_in_valid_range) == 1:
            return dates_in_valid_range[0]
        elif len(dates_in_valid_range) > 1:
            valid_dates = [
                date for date in dates_in_valid_range
                if 1 <= date.day <= 31 and 1 <= date.month <= 12
            ]
            if len(valid_dates) == 1:
                return valid_dates[0]
        else:
            return None

    def __eq__(self, other):
        if isinstance(other, str):
            return self.are_dates_equal(self, other)
        return super().__eq__(other)
