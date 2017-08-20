import unittest
from unittest.mock import patch, MagicMock, call
import os

import pkg_resources
import responses

from habitipy import Habitipy
from habitipy import api as hapi
from habitipy.api import APIDOC_LOCAL_FILE
from plumbum import local

class TestHabitipy(unittest.TestCase):
    def test_python_keyword_escape(self):
        api = Habitipy(None)
        self.assertEqual(api.user.class_._current, ['api', 'v3', 'user', 'class'])
        self.assertEqual(api['user']['class']._current, api.user.class_._current)
        self.assertEqual(api['user']['buy-armoire']._current, api.user.buy_armoire._current)
        self.assertEqual(api['user', 'buy-armoire']._current, api.user.buy_armoire._current)
        self.assertIn('tasks', dir(api))
        self.assertIn('user', dir(api.tasks))
        self.assertIn('user', dir(api))
        self.assertIn('class_', dir(api.user))
        self.assertNotIn('class', dir(api.user))

    def test_integration(self):
        api = Habitipy(None)
        with self.assertRaises(IndexError):
            api.abracadabra
        with self.assertRaises(IndexError):
            api['abracadabra']


    def test_init_typing(self):
        with self.assertRaises(TypeError):
            api = Habitipy(None, apis='abracadabra')
        with self.assertRaises(TypeError):
            api = Habitipy(None, current='abracadabra')

    #@unittest.skipIf(
    #    os.environ.get('CI', '') != 'true',
    #    'network-heavy (not in CI env(CI="{}"))'.format(os.environ.get('CI', '')))
    def test_download_api(self):
        with patch('habitipy.api.local') as mock:
            with responses.RequestsMock() as rsps:
                rsps.add(
                    responses.GET,
                    'https://api.github.com/repos/HabitRPG/habitica/releases/latest',
                    json=dict(tag_name='TEST_TAG'))
                m = hapi.download_api()
        self.assertEqual(
            mock.__getitem__.call_args_list,
            [call('curl'), call('tar'), call('grep'), call('sed')])
        self.assertEqual(mock.__getitem__.return_value.__getitem__.call_count, 4)
        for actual, expected in zip(mock.__getitem__.return_value.__getitem__.call_args_list, [
            call(('-sL', 'https://api.github.com/repos/HabitRPG/habitica/tarball/TEST_TAG')),
            call((
                'axzf', '-',
                '--wildcards', '*/website/server/controllers/api-v3/*', '--to-stdout')),
            call(('@api')),
            call(('-e', 's/^[ */]*//g', '-e', 's/  / /g', '-'))]):
            self.assertEqual(actual, expected)


    @patch('habitipy.api.download_api')
    def test_github(self, mock):
        with open(pkg_resources.resource_filename('habitipy','apidoc.txt')) as f:
            mock.return_value = f.read()
        import builtins
        lp = local.path(APIDOC_LOCAL_FILE)
        Habitipy(None, from_github=True, branch='develop')
        self.assertTrue(mock.called)
        self.assertTrue(lp.exists())
        with patch('builtins.open', MagicMock(wraps=builtins.open)) as mock:
            Habitipy(None)
            mock.assert_called_with(lp)
        os.remove(lp)
        Habitipy(None, from_github=True)
        self.assertTrue(mock.called)
        self.assertTrue(lp.exists())
        with patch('builtins.open', MagicMock(wraps=builtins.open)) as mock:
            Habitipy(None)
            mock.assert_called_with(lp)
        os.remove(lp)
