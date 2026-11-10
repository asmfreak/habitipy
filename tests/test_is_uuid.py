import unittest

from habitipy.cli import is_uuid


class TestIsUuid(unittest.TestCase):
    def test_valid_uuid_returns_value(self):
        value = '12345678-1234-5678-1234-567812345678'
        self.assertEqual(is_uuid(value), value)

    def test_valid_uuid_without_dashes_returns_value(self):
        value = '12345678123456781234567812345678'
        self.assertEqual(is_uuid(value), value)

    def test_garbage_string_returns_false(self):
        self.assertFalse(is_uuid('not-a-uuid'))

    def test_wrong_length_hex_returns_false(self):
        self.assertFalse(is_uuid('1234'))

    def test_non_string_returns_false(self):
        self.assertFalse(is_uuid(None))
        self.assertFalse(is_uuid(1234))


if __name__ == '__main__':
    unittest.main()
