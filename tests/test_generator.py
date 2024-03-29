# Copyright 2021 Brian T. Park
#
# MIT License

import unittest

from acetimetools.generator.argenerator import compressed_name_to_c_string


class TestArduinoGenerator(unittest.TestCase):
    def test_compressed_name_to_c_string(self) -> None:
        self.assertEqual('"hello"', compressed_name_to_c_string('hello'))
        self.assertEqual('"\\x01"', compressed_name_to_c_string('\u0001'))
        self.assertEqual(
            '"\\x01" "hello"',
            compressed_name_to_c_string('\u0001hello')
        )
        self.assertEqual(
            '"hello" "\\x02"',
            compressed_name_to_c_string('hello\u0002')
        )
        self.assertEqual(
            '"\\x01" "hello" "\\x02"',
            compressed_name_to_c_string('\u0001hello\u0002')
        )
        self.assertEqual(
            '"\\x01" "\\x02"',
            compressed_name_to_c_string('\u0001\u0002')
        )
