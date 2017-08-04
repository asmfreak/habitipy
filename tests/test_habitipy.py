import unittest

from habitipy import Habitipy

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

    @unittest.skip
    def test_github(self):
        Habitipy(None, from_github=True, branch='develop')
        Habitipy(None, from_github=True)
