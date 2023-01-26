import unittest
from acetimetools.generator.byteutils import hex_encode
from acetimetools.generator.byteutils import convert_to_go_string


class TestByteUtils(unittest.TestCase):

    def test_hex_encode(self) -> None:
        data = bytearray(b'01234')
        s = hex_encode(data)
        self.assertEqual(s, "\\x30\\x31\\x32\\x33\\x34")

    def test_convert_to_go_string_has_trailing(self) -> None:
        data = bytearray(b'01234')
        gs = convert_to_go_string(data, 2, '')
        self.assertEqual(gs, '''\
"\\x30\\x31" +
"\\x32\\x33" +
"\\x34"''')

    def test_convert_to_go_string_no_trailing(self) -> None:
        data = bytearray(b'01234')
        gs = convert_to_go_string(data, 5, '')
        self.assertEqual(gs, '"\\x30\\x31\\x32\\x33\\x34"')
