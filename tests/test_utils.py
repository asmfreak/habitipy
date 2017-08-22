import unittest
from unittest.mock import patch, MagicMock
from contextlib import ExitStack
import os
import uuid

from habitipy.cli import load_conf
from habitipy.util import secure_filestore, SecurityError, assert_secure_file, is_secure_file
from habitipy.util import progressed

def touch(fname, times=None):
    with open(fname, 'a'):
        os.utime(fname, times)

class TestFileUtils(unittest.TestCase):
    def setUp(self):
        self.filename = 'test.yay'
        touch(self.filename)

    def tearDown(self):
        if os.path.exists(self.filename):
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
        with patch('plumbum.cli.terminal.ask', MagicMock(return_value=False)) as m:
            conf = load_conf(self.filename)
            self.assertTrue(m.called)
        self.assertEqual(conf['url'], 'https://habitica.com')
        self.assertTrue(is_secure_file(self.filename))
        os.remove(self.filename)
        with ExitStack() as s:
            ask = s.enter_context(
                patch('plumbum.cli.terminal.ask', MagicMock(return_value=True)))
            prompt = s.enter_context(
                patch('plumbum.cli.terminal.prompt', MagicMock(return_value='TEST_DATA')))
            conf = load_conf(self.filename)
            self.assertEqual(ask.call_count, 1)
            self.assertEqual(prompt.call_count, 2)
        self.assertEqual(conf['url'], 'https://habitica.com')
        self.assertEqual(conf['login'], 'TEST_DATA')
        self.assertEqual(conf['password'], 'TEST_DATA')
        self.assertTrue(is_secure_file(self.filename))
        os.chmod(self.filename, 0o666)
        with self.assertRaises(SecurityError):
            conf = load_conf(self.filename)
