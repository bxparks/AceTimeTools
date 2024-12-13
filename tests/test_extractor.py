# Copyright 2018 Brian T. Park
#
# MIT License

import unittest

from acetimetools.extractor.extractor import parse_at_time_string
from acetimetools.extractor.extractor import month_to_index


class TestParseAtHourString(unittest.TestCase):
    def test_parse_at_time_string(self) -> None:
        self.assertEqual(('2:00', ''), parse_at_time_string('2:00'))
        self.assertEqual(('2:00', 'w'), parse_at_time_string('2:00w'))
        self.assertEqual(('12:00', 's'), parse_at_time_string('12:00s'))
        self.assertEqual(('12:00', 'g'), parse_at_time_string('12:00g'))
        self.assertEqual(('12:00', 'u'), parse_at_time_string('12:00u'))

    def test_pase_at_time_string_fails(self) -> None:
        self.assertRaises(Exception, parse_at_time_string, '2:00p')


class TestMonthToIndex(unittest.TestCase):
    def test_month_to_index_success(self) -> None:
        self.assertEqual(1, month_to_index('Jan'))
        self.assertEqual(1, month_to_index('jan'))
        self.assertEqual(1, month_to_index('January'))

        self.assertEqual(2, month_to_index('Feb'))
        self.assertEqual(2, month_to_index('feb'))
        self.assertEqual(2, month_to_index('February'))

        self.assertEqual(3, month_to_index('mar'))
        self.assertEqual(3, month_to_index('Mar'))
        self.assertEqual(3, month_to_index('March'))

        self.assertEqual(4, month_to_index('apr'))
        self.assertEqual(4, month_to_index('Apr'))
        self.assertEqual(4, month_to_index('April'))

        self.assertEqual(5, month_to_index('may'))
        self.assertEqual(5, month_to_index('May'))
        self.assertEqual(5, month_to_index('May'))

        self.assertEqual(6, month_to_index('jun'))
        self.assertEqual(6, month_to_index('Jun'))
        self.assertEqual(6, month_to_index('June'))

        self.assertEqual(7, month_to_index('jul'))
        self.assertEqual(7, month_to_index('Jul'))
        self.assertEqual(7, month_to_index('July'))

        self.assertEqual(8, month_to_index('aug'))
        self.assertEqual(8, month_to_index('Aug'))
        self.assertEqual(8, month_to_index('August'))

        self.assertEqual(9, month_to_index('sep'))
        self.assertEqual(9, month_to_index('Sep'))
        self.assertEqual(9, month_to_index('September'))

        self.assertEqual(10, month_to_index('oct'))
        self.assertEqual(10, month_to_index('Oct'))
        self.assertEqual(10, month_to_index('October'))

        self.assertEqual(11, month_to_index('nov'))
        self.assertEqual(11, month_to_index('Nov'))
        self.assertEqual(11, month_to_index('November'))

        self.assertEqual(12, month_to_index('dec'))
        self.assertEqual(12, month_to_index('Dec'))
        self.assertEqual(12, month_to_index('December'))

    def test_month_to_index_failure(self) -> None:
        self.assertRaises(Exception, month_to_index, '')
        self.assertRaises(Exception, month_to_index, 'none')
        self.assertRaises(Exception, month_to_index, 'ja')
        self.assertRaises(Exception, month_to_index, 'fe')


if __name__ == '__main__':
    unittest.main()
