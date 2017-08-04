import unittest
import os

from habitipy.cli import load_conf
from habitipy.util import secure_filestore, SecurityError, assert_secure_file, is_secure_file

def touch(fname, times=None):
    with open(fname, 'a'):
        os.utime(fname, times)

class TestUtils(unittest.TestCase):
    def setUp(self):
        self.filename = 'test.yay'
        touch(self.filename)

    def tearDown(self):
        os.remove(self.filename)

    def test_secure_filestore(self):
        with open(self.filename, 'w') as f:
            f.write('this is a test')
        self.assertFalse(is_secure_file(self.filename))
        os.remove(self.filename)
        with secure_filestore(), open(self.filename, 'w') as f:
            f.write('this is a test')
        self.assertTrue(is_secure_file(self.filename))

    def test_load_conf(self):
        os.remove(self.filename)
        with self.assertWarns(UserWarning):
            conf = load_conf(self.filename)
        self.assertEqual(conf['url'], 'https://habitica.com')
        self.assertTrue(is_secure_file(self.filename))
        os.chmod(self.filename, 0o666)
        with self.assertRaises(SecurityError):
            conf = load_conf(self.filename)
