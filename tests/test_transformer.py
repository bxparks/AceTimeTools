# Copyright 2018 Brian T. Park
#
# MIT License

import unittest
from collections import OrderedDict

from acetimetools.datatypes.attyping import INVALID_YEAR
from acetimetools.datatypes.attyping import INVALID_YEAR_TINY
from acetimetools.datatypes.attyping import MIN_YEAR
from acetimetools.datatypes.attyping import MIN_YEAR_TINY
from acetimetools.datatypes.attyping import MAX_TO_YEAR
from acetimetools.datatypes.attyping import MAX_TO_YEAR_TINY
from acetimetools.datatypes.attyping import MAX_UNTIL_YEAR
from acetimetools.datatypes.attyping import MAX_UNTIL_YEAR_TINY
from acetimetools.transformer.transformer import _parse_on_day_string
from acetimetools.transformer.transformer import _days_in_month
from acetimetools.transformer.transformer import calc_day_of_month
from acetimetools.transformer.transformer import time_string_to_seconds
from acetimetools.transformer.transformer import seconds_to_hms
from acetimetools.transformer.transformer import hms_to_seconds
from acetimetools.transformer.transformer import div_to_zero
from acetimetools.transformer.transformer import truncate_to_granularity
from acetimetools.transformer.transformer import INVALID_SECONDS
from acetimetools.transformer.transformer import hash_name
from acetimetools.transformer.transformer import add_string
from acetimetools.transformer.transformer import to_tiny_from_to_year
from acetimetools.transformer.transformer import to_tiny_until_year


class TestParseOnDayString(unittest.TestCase):
    def test_parse_transition_day(self) -> None:
        self.assertEqual((0, 20), _parse_on_day_string('20'))
        self.assertEqual((7, 10), _parse_on_day_string('Sun>=10'))
        self.assertEqual((7, -10), _parse_on_day_string('Sun<=10'))
        self.assertEqual((5, 0), _parse_on_day_string('lastFri'))

    def test_parse_transition_day_fails(self) -> None:
        self.assertEqual((0, 0), _parse_on_day_string('20ab'))
        self.assertEqual((0, 0), _parse_on_day_string('lastFriday'))


class TestCalcDayOfMonth(unittest.TestCase):
    def test_calc_day_of_month(self) -> None:
        # 2013 Mar Fri>=23
        self.assertEqual((3, 29), calc_day_of_month(2013, 3, 5, 23))
        # 2013 Mar Fri>=30, shifts into April
        self.assertEqual((4, 5), calc_day_of_month(2013, 3, 5, 30))
        # 2002 Sep lastFri
        self.assertEqual((9, 27), calc_day_of_month(2002, 9, 5, 0))
        # 2005 Apr Fri<=7
        self.assertEqual((4, 1), calc_day_of_month(2005, 4, 5, -7))
        # 2005 Apr Fri<=1
        self.assertEqual((4, 1), calc_day_of_month(2005, 4, 5, -1))
        # 2006 Apr Fri<=1, shifts into March
        self.assertEqual((3, 31), calc_day_of_month(2006, 4, 5, -1))


class TestDaysInMonth(unittest.TestCase):
    def test_days_in_month(self) -> None:
        self.assertEqual(30, _days_in_month(2002, 9))  # Sep
        self.assertEqual(31, _days_in_month(2002, 0))  # Dec of prev year
        self.assertEqual(31, _days_in_month(2002, 13))  # Jan of following year


class TestTimeStringToSeconds(unittest.TestCase):
    def test_time_string_to_seconds(self) -> None:
        self.assertEqual(0, time_string_to_seconds('0'))
        self.assertEqual(0, time_string_to_seconds('0:00'))
        self.assertEqual(0, time_string_to_seconds('00:00'))
        self.assertEqual(0, time_string_to_seconds('00:00:00'))

        self.assertEqual(3600, time_string_to_seconds('1'))
        self.assertEqual(3720, time_string_to_seconds('1:02'))
        self.assertEqual(3723, time_string_to_seconds('1:02:03'))

        self.assertEqual(-3600, time_string_to_seconds('-1'))
        self.assertEqual(-3720, time_string_to_seconds('-1:02'))
        self.assertEqual(-3723, time_string_to_seconds('-1:02:03'))

    def test_hour_string_to_offset_code_fails(self) -> None:
        self.assertEqual(INVALID_SECONDS, time_string_to_seconds('26:00'))
        self.assertEqual(INVALID_SECONDS, time_string_to_seconds('+26:00'))
        self.assertEqual(INVALID_SECONDS, time_string_to_seconds('1:60'))
        self.assertEqual(INVALID_SECONDS, time_string_to_seconds('1:02:60'))
        self.assertEqual(INVALID_SECONDS, time_string_to_seconds('1:02:03:04'))
        self.assertEqual(INVALID_SECONDS, time_string_to_seconds('abc'))


class TestSecondsToHms(unittest.TestCase):
    def test_seconds_to_hms(self) -> None:
        self.assertEqual((0, 0, 0), seconds_to_hms(0))
        self.assertEqual((0, 0, 1), seconds_to_hms(1))
        self.assertEqual((0, 1, 1), seconds_to_hms(61))
        self.assertEqual((1, 1, 1), seconds_to_hms(3661))

    def test_hms_to_seconds(self) -> None:
        self.assertEqual(0, hms_to_seconds(0, 0, 0))
        self.assertEqual(1, hms_to_seconds(0, 0, 1))
        self.assertEqual(61, hms_to_seconds(0, 1, 1))
        self.assertEqual(3661, hms_to_seconds(1, 1, 1))


class TestIntegerDivision(unittest.TestCase):
    def test_div_to_zero(self) -> None:
        self.assertEqual(1, div_to_zero(3, 3))
        self.assertEqual(0, div_to_zero(2, 3))
        self.assertEqual(0, div_to_zero(1, 3))
        self.assertEqual(0, div_to_zero(0, 3))
        self.assertEqual(0, div_to_zero(-1, 3))
        self.assertEqual(0, div_to_zero(-2, 3))
        self.assertEqual(-1, div_to_zero(-3, 3))
        self.assertEqual(-1, div_to_zero(-4, 3))
        self.assertEqual(-1, div_to_zero(-5, 3))
        self.assertEqual(-2, div_to_zero(-6, 3))

    def test_truncate_to_granularity(self) -> None:
        self.assertEqual(0, truncate_to_granularity(0, 15))
        self.assertEqual(0, truncate_to_granularity(14, 15))
        self.assertEqual(15, truncate_to_granularity(15, 15))
        self.assertEqual(15, truncate_to_granularity(16, 15))
        self.assertEqual(0, truncate_to_granularity(-1, 15))
        self.assertEqual(-15, truncate_to_granularity(-15, 15))
        self.assertEqual(-15, truncate_to_granularity(-29, 15))
        self.assertEqual(-30, truncate_to_granularity(-31, 15))


class TestAddString(unittest.TestCase):
    def test_add_string(self) -> None:
        strings: OrderedDict[str, int] = OrderedDict()
        self.assertEqual(0, add_string(strings, 'a'))
        self.assertEqual(0, add_string(strings, 'a'))
        self.assertEqual(1, add_string(strings, 'b'))
        self.assertEqual(2, add_string(strings, 'd'))
        self.assertEqual(3, add_string(strings, 'c'))
        self.assertEqual(2, add_string(strings, 'd'))


class TestHash(unittest.TestCase):
    def test_hash(self) -> None:
        self.assertEqual(5381, hash_name(''))
        self.assertEqual(177670, hash_name('a'))
        self.assertEqual(177671, hash_name('b'))
        self.assertEqual(5863208, hash_name('ab'))
        self.assertEqual(193485963, hash_name('abc'))
        self.assertEqual(2090069583, hash_name('abcd'))
        self.assertEqual(252819604, hash_name('abcde'))


class TestTinyYear(unittest.TestCase):
    def test_to_tiny_from_to_year(self) -> None:
        self.assertEqual(
            INVALID_YEAR_TINY,
            to_tiny_from_to_year(INVALID_YEAR, 2000))
        self.assertEqual(MIN_YEAR_TINY, to_tiny_from_to_year(MIN_YEAR, 2000))
        self.assertEqual(MIN_YEAR_TINY, to_tiny_from_to_year(1800, 2000))
        self.assertEqual(MIN_YEAR_TINY, to_tiny_from_to_year(1873, 2000))
        self.assertEqual(-126, to_tiny_from_to_year(1874, 2000))
        self.assertEqual(-1, to_tiny_from_to_year(1999, 2000))
        self.assertEqual(0, to_tiny_from_to_year(2000, 2000))
        self.assertEqual(23, to_tiny_from_to_year(2023, 2000))
        self.assertEqual(125, to_tiny_from_to_year(2125, 2000))
        self.assertEqual(MAX_TO_YEAR_TINY, to_tiny_from_to_year(2126, 2000))
        self.assertEqual(MAX_TO_YEAR_TINY, to_tiny_from_to_year(2127, 2000))
        self.assertEqual(MAX_TO_YEAR_TINY, to_tiny_from_to_year(2200, 2000))
        self.assertEqual(
            MAX_TO_YEAR_TINY,
            to_tiny_from_to_year(MAX_TO_YEAR, 2000))

    def test_to_tiny_until_year(self) -> None:
        self.assertEqual(
            INVALID_YEAR_TINY,
            to_tiny_until_year(INVALID_YEAR, 2000))
        self.assertEqual(MIN_YEAR_TINY, to_tiny_until_year(MIN_YEAR, 2000))
        self.assertEqual(MIN_YEAR_TINY, to_tiny_until_year(1800, 2000))
        self.assertEqual(MIN_YEAR_TINY, to_tiny_until_year(1873, 2000))
        self.assertEqual(-126, to_tiny_until_year(1874, 2000))
        self.assertEqual(-1, to_tiny_until_year(1999, 2000))
        self.assertEqual(0, to_tiny_until_year(2000, 2000))
        self.assertEqual(23, to_tiny_until_year(2023, 2000))
        self.assertEqual(125, to_tiny_until_year(2125, 2000))
        self.assertEqual(126, to_tiny_until_year(2126, 2000))
        self.assertEqual(MAX_UNTIL_YEAR_TINY, to_tiny_until_year(2127, 2000))
        self.assertEqual(MAX_UNTIL_YEAR_TINY, to_tiny_until_year(2200, 2000))
        self.assertEqual(
            MAX_UNTIL_YEAR_TINY,
            to_tiny_until_year(MAX_UNTIL_YEAR, 2000))
