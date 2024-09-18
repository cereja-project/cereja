import unittest
from datetime import datetime

from cereja import DateTime, AmbiguousDateFormatError  # Replace 'date_time_module' with the actual module name


class TestDateTime(unittest.TestCase):
    def test_validate_timestamp(self):
        self.assertEqual(DateTime._validate_timestamp(1609459200), 1609459200)
        self.assertEqual(DateTime._validate_timestamp(1609459200.0), 1609459200.0)
        with self.assertRaises(AssertionError):
            DateTime._validate_timestamp("1609459200")

    def test_validate_date(self):
        now = datetime.now()
        self.assertEqual(DateTime._validate_date(now), now)
        with self.assertRaises(AssertionError):
            DateTime._validate_date("2021-01-01")

    def test_days_from_timestamp(self):
        self.assertEqual(DateTime.days_from_timestamp(86400), 1)
        self.assertEqual(DateTime.days_from_timestamp(172800), 2)

    def test_into_timestamp(self):
        self.assertEqual(DateTime.into_timestamp(days=1), 86400)
        self.assertEqual(DateTime.into_timestamp(min_=1), 3600 * 60)
        self.assertEqual(DateTime.into_timestamp(sec=60), 60)
        self.assertEqual(DateTime.into_timestamp(days=1, min_=1, sec=60), 86400 + 3600 * 60 + 60)

    def test_add(self):
        dt = DateTime(2021, 1, 1)
        new_dt = dt.add(days=1)
        self.assertEqual(new_dt, datetime(2021, 1, 2))

    def test_sub(self):
        dt = DateTime(2021, 1, 2)
        new_dt = dt.sub(days=1)
        self.assertEqual(new_dt, datetime(2021, 1, 1))

    def test_days_between(self):
        dt1 = DateTime(2021, 1, 1)
        dt2 = DateTime(2021, 1, 3)
        self.assertEqual(dt1.days_between(dt2), 2)

    def test_compare(self):
        dt1 = DateTime(2021, 1, 1)
        dt2 = DateTime(2021, 1, 2)
        self.assertEqual(dt1.compare(dt2), -1)
        self.assertEqual(dt2.compare(dt1), 1)
        self.assertEqual(dt1.compare(dt1), 0)

    def test_parse_from_string(self):
        # Test with unambiguous formats
        self.assertEqual(
                DateTime.parse_from_string("2021/01/01 12:00:00"),
                datetime(2021, 1, 1, 12, 0, 0)
        )

        # Test with ambiguous formats
        with self.assertRaises(AmbiguousDateFormatError):
            DateTime.parse_from_string("01/02/03")
            DateTime.parse_from_string("2021-01-01")
            DateTime.parse_from_string("01/01/2021")
            DateTime.parse_from_string("20210101")

        # Test with formats that require disambiguation
        self.assertEqual(
                DateTime.parse_from_string("20210113"),
                datetime(2021, 1, 13)
        )

    def test_disambiguate_date(self):
        # Internal method, but we can test via parse_from_string
        self.assertEqual(
                DateTime.parse_from_string("12-31-2021"),
                datetime(2021, 12, 31)
        )

    def test_ambiguous_date_format_error(self):
        try:
            DateTime.parse_from_string("01/02/03")
        except AmbiguousDateFormatError as e:
            self.assertIn("Possible formats", str(e))
            self.assertEqual(e.date_string, "01/02/03")
            self.assertIsInstance(e.possible_formats, list)

    def test_unrecognized_format(self):
        with self.assertRaises(ValueError):
            DateTime.parse_from_string("Not a date")

    def test_parse_with_formats(self):
        # Testing the internal method indirectly via parse_from_string
        self.assertEqual(
                DateTime.parse_from_string("31 Dec 2021"),
                datetime(2021, 12, 31)
        )

    def test_timezone_formats(self):
        # Test parsing ISO 8601 UTC format
        self.assertEqual(
                DateTime.parse_from_string("2021-12-31T23:59:59Z"),
                datetime(2021, 12, 31, 23, 59, 59)
        )

        # Test parsing with microseconds
        self.assertEqual(
                DateTime.parse_from_string("2021-12-31 23:59:59.123456"),
                datetime(2021, 12, 31, 23, 59, 59, 123456)
        )

    def test_partial_dates(self):
        # Test parsing dates without year (assumes current year)
        date = DateTime.parse_from_string("Dec 31")
        self.assertEqual(date.month, 12)
        self.assertEqual(date.day, 31)
        self.assertEqual(date.year, datetime.now().year)

        # Test parsing dates without day (assumes day=1)
        date = DateTime.parse_from_string("Dec 2021")
        self.assertEqual(date.month, 12)
        self.assertEqual(date.day, 1)
        self.assertEqual(date.year, 2021)

    def test_formats_with_textual_month(self):
        self.assertEqual(
                DateTime.parse_from_string("31 December 2021"),
                datetime(2021, 12, 31)
        )
        self.assertEqual(
                DateTime.parse_from_string("December 31, 2021"),
                datetime(2021, 12, 31)
        )

    def test_formats_with_different_separators(self):
        self.assertEqual(
                DateTime.parse_from_string("31-12-2021"),
                datetime(2021, 12, 31)
        )
        self.assertEqual(
                DateTime.parse_from_string("31.12.2021"),
                datetime(2021, 12, 31)
        )

    def test_instance_with_string(self):
        dt = DateTime("2021-01-31")
        self.assertEqual(dt, datetime(2021, 1, 31))

    def test_dates_are_equal_when_both_are_datetime_objects(self):
        date1 = DateTime(2023, 10, 5)
        date2 = DateTime(2023, 10, 5)
        self.assertTrue(DateTime.are_dates_equal(date1, date2))

    def test_dates_are_not_equal_when_both_are_datetime_objects(self):
        date1 = DateTime(2023, 10, 5)
        date2 = DateTime(2023, 10, 6)
        self.assertFalse(DateTime.are_dates_equal(date1, date2))

    def test_dates_are_equal_when_one_is_string(self):
        date1 = DateTime(2023, 10, 5)
        date_str2 = "2023-10-05"
        self.assertTrue(DateTime.are_dates_equal(date1, date_str2))

    def test_dates_are_not_equal_when_one_is_string(self):
        date1 = DateTime(2023, 10, 5)
        date_str2 = "2023-10-06"
        self.assertFalse(DateTime.are_dates_equal(date1, date_str2))

    def test_dates_are_equal_when_both_are_strings(self):
        date_str1 = "2023-10-05"
        date_str2 = "2023-10-05"
        self.assertTrue(DateTime.are_dates_equal(date_str1, date_str2))

    def test_dates_are_not_equal_when_both_are_strings(self):
        date_str1 = "2023-10-05"
        date_str2 = "2023-10-06"
        self.assertFalse(DateTime.are_dates_equal(date_str1, date_str2))

    def test_dates_are_equal_with_different_formats(self):
        date_str1 = "05/10/2023"
        date_str2 = "2023-10-05"
        self.assertTrue(DateTime.are_dates_equal(date_str1, date_str2))


if __name__ == '__main__':
    unittest.main()
