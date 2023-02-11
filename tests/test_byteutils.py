import unittest
from acetimetools.generator.byteutils import write_i8
from acetimetools.generator.byteutils import write_i16
from acetimetools.generator.byteutils import write_i32
from acetimetools.generator.byteutils import write_u8
from acetimetools.generator.byteutils import write_u16
from acetimetools.generator.byteutils import write_u32
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

    def test_write_invalid_integer_throws_exception(self) -> None:
        data = bytearray()
        with self.assertRaises(ValueError):
            write_u8(data, -1)
        with self.assertRaises(ValueError):
            write_u8(data, 256)

        with self.assertRaises(ValueError):
            write_u16(data, -1)
        with self.assertRaises(ValueError):
            write_u16(data, 100000)

        with self.assertRaises(ValueError):
            write_u32(data, -1)
        with self.assertRaises(ValueError):
            write_u32(data, 5 * 1000 * 1000 * 1000)

        with self.assertRaises(ValueError):
            write_i8(data, -200)
        with self.assertRaises(ValueError):
            write_i8(data, 200)

        with self.assertRaises(ValueError):
            write_i16(data, -100000)
        with self.assertRaises(ValueError):
            write_i16(data, 100000)

        with self.assertRaises(ValueError):
            write_i32(data, -3 * 1000 * 1000 * 1000)
        with self.assertRaises(ValueError):
            write_i32(data, 3 * 1000 * 1000 * 1000)

    def test_write_negative_integers(self) -> None:
        data = bytearray()
        write_i8(data, -1)
        write_i16(data, -2)
        write_i32(data, -3)

        hex_string = hex_encode(data)
        expected = '\\xff\\xfe\\xff\\xfd\\xff\\xff\\xff'
        self.assertEqual(hex_string, expected)
