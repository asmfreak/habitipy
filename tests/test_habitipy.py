import unittest
from unittest.mock import patch, MagicMock
import os

from habitipy import Habitipy
from habitipy.api import APIDOC_LOCAL_FILE
from plumbum import local

class TestHabitipy(unittest.TestCase):
    def test_python_keyword_escape(self):
        api = Habitipy(None)
        self.assertEqual(api.user.class_._current, ['api', 'v3', 'user', 'class'])
        self.assertEqual(api['user']['class']._current, api.user.class_._current)
        self.assertIn('tasks', dir(api))
        self.assertIn('user', dir(api.tasks))
        self.assertIn('user', dir(api))
        self.assertIn('class_', dir(api.user))
        self.assertNotIn('class', dir(api.user))

    def test_integration(self):
        api = Habitipy(None)
        with self.assertRaises(AttributeError):
            api.abracadabra
        with self.assertRaises(IndexError):
            api['abracadabra']


    def test_init_typing(self):
        with self.assertRaises(TypeError):
            api = Habitipy(None, apis='abracadabra')
        with self.assertRaises(TypeError):
            api = Habitipy(None, current='abracadabra')

    @unittest.skipIf(os.environ.get('CI', '') != 'true', 'network-heavy')
    def test_github(self):
        lp = local.path(APIDOC_LOCAL_FILE)
        Habitipy(None, from_github=True, branch='develop')
        self.assertTrue(lp.exists())
        os.remove(lp)
        Habitipy(None, from_github=True)
        self.assertTrue(lp.exists())
        import builtins
        with patch('habitipy.api.open', MagicMock(wraps=builtins.open)) as mock:
            Habitipy(None)
            mock.assert_called_with(APIDOC_LOCAL_FILE)
        os.remove(lp)
