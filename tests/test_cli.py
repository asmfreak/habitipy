import unittest
from unittest import mock
from unittest.mock import patch, call
import os
from contextlib import contextmanager, ExitStack
import tempfile
from textwrap import dedent
import responses
from hypothesis import given, assume, settings, HealthCheck
from hypothesis.strategies import uuids, integers, text, lists, booleans
from hypothesis.strategies import one_of, sampled_from, composite

from habitipy import cli


def crange(m,mx):
    return ''.join(map(chr, range(ord(m), ord(mx)+1)))

numbers_alphabet = crange('0', '9')
alphas_alphabet = crange('a','z')+crange('A', 'Z')

@composite
def aliases(draw):
    f = draw(text(alphabet=alphas_alphabet+'_', min_size=1))
    f1 = draw(text(alphabet=alphas_alphabet+numbers_alphabet+'_-'))
    return f + f1


@composite
def tasks(draw):
    r = dict()
    r['id'] = r['_id'] = str(draw(uuids()))
    r['alias'] = draw(aliases())
    return r


task_lists = lists(tasks(), unique_by=lambda x: x['alias'], min_size=1)


@composite
def integer_range(draw, min_value=None, max_value=None):
    i = integers(min_value=min_value, max_value=max_value)
    a = draw(i)
    b = draw(i)
    assume(a != b)
    return (min(a,b), max(a,b))


@composite
def index_id_alias(draw, length):
    r = dict()
    r['i'] = draw(integers(min_value=0,max_value=length-1))
    r['type'] = draw(sampled_from(('index','id','alias')))
    return r

@composite
def test_data(draw):
    can_overlap = draw(booleans())
    user_tasks = draw(task_lists)
    more_tasks = draw(task_lists)
    all_tasks = []
    all_tasks.extend(user_tasks)
    all_tasks.extend(more_tasks)
    index_lists = lists(
        one_of(
            index_id_alias(len(user_tasks)),
            integer_range(0, len(user_tasks) - 1)),
        min_size=1, average_size=5)
    arguments = draw(lists(index_lists, min_size=1, average_size=5))
    arguments_strings = []
    task_ids = []
    for indexes in arguments:
        arg = ''
        for index in indexes:
            comma = ',' if arg else ''
            if isinstance(index, tuple):
                task_ids.extend(map(lambda x: user_tasks[x]['_id'], range(index[0],index[1]+1)))
                arg += '{comma}{0}-{1}'.format(index[0] + 1, index[1] + 1, comma=comma)
            elif isinstance(index, dict):
                task_ids.append(user_tasks[index['i']]['_id'])
                if index['type'] == 'index':
                    arg += '{comma}{i}'.format(i=index['i'] + 1, comma=comma)
                elif index['type'] == 'id':
                    arg += '{comma}{i}'.format(i=user_tasks[index['i']]['_id'], comma=comma)
                elif index['type'] == 'alias':
                    arg += '{comma}{i}'.format(i=user_tasks[index['i']]['alias'], comma=comma)
        arguments_strings.append(arg)
    if not can_overlap:
        task_ids = list(set(task_ids))
    return (can_overlap, user_tasks, more_tasks, all_tasks, arguments_strings, task_ids, arguments)


class DevNull(object):
    def write(self, what):
        pass
    def flush(self):
        pass

def nop(s, *args):
    pass

class DevNullLog(object):
    def __getattr__(self, a):
        if a in dir(super()):
            return super().__getattr__(a)
        else:
            return nop


@contextmanager
def to_devnull():
    import sys
    stdout = sys.stdout
    sys.stdout = DevNull()
    try:
        yield
    finally:
        sys.stdout = stdout

def cfg_main(self):
    self.config = cli.load_conf(self.config_filename)
    self.log = DevNullLog()

class TestCli(unittest.TestCase):
    def setUp(self):
        self.file = tempfile.NamedTemporaryFile(delete=False)
        with self.file:
            self.file.write(dedent("""
            [habitipy]
            url = https://habitica.com
            login = this-is-a-sample-login
            password = this-is-a-sample-password
            """).encode('utf-8'))

    def tearDown(self):
        os.remove(self.file.name)

    def test_task_print(self):
        data = [{'first':1}, {'second':2}]
        more = [{'third':3}]
        context = [
            patch.object(cli.TasksPrint, 'domain', 'testdomain'),
            patch.object(
                cli.TasksPrint, 'domain_format',
                mock.Mock(wraps=cli.TasksPrint.domain_format, return_value='')),
            patch('habitipy.cli.prettify', mock.Mock(wraps=cli.prettify)),
            patch.object(cli.TasksPrint, 'more_tasks', more)]
        rsps = responses.RequestsMock()
        context.extend([rsps, to_devnull()])
        with ExitStack() as stack:
            for cm in context:
                stack.enter_context(cm)
            rsps.add(
                responses.GET,
                url='https://habitica.com/api/v3/tasks/user?type=testdomain',
                content_type='application/json',
                match_querystring=True,
                json=dict(data=data))
            instance, retcode = cli.TasksPrint.invoke(config_filename=self.file.name)
            self.assertIsNotNone(instance)
            self.assertIsNone(retcode)
            self.assertTrue(cli.TasksPrint.domain_format.called)
            all_data = []
            all_data.extend(data)
            all_data.extend(more)
            data_calls = [call(x) for x in all_data]
            cli.TasksPrint.domain_format.assert_has_calls(data_calls)
            self.assertTrue(cli.prettify.called)

    @settings(suppress_health_check=[HealthCheck.too_slow])
    @given(test_data())
    def test_tasks_change(self, arg):
        can_overlap, user_tasks, more_tasks, all_tasks, arguments_strings, task_ids, args = arg
        context = [
            patch.object(cli.ConfiguredApplication, 'main', cfg_main),
            patch.object(cli.TasksChange, 'domain', 'testdomain'),
            patch.object(cli.TasksChange, 'ids_can_overlap', can_overlap),
            patch.object(cli.TasksChange, 'op'),
            patch.object(cli.TasksChange, 'log_op'),
            patch.object(
                cli.TasksChange, 'domain_print',
                mock.Mock(wraps=cli.TasksChange.domain_print, return_value='')),
            patch('habitipy.cli.prettify', mock.Mock(wraps=cli.prettify, return_value='')),
            patch.object(cli.TasksPrint, 'more_tasks', more_tasks)]
        rsps = responses.RequestsMock()
        context.extend([rsps, to_devnull()])
        with ExitStack() as stack:
            for cm in context:
                stack.enter_context(cm)
            rsps.add(
                responses.GET,
                url='https://habitica.com/api/v3/tasks/user?type=testdomain',
                content_type='application/json',
                match_querystring=True,
                json=dict(data=user_tasks))
            instance, retcode = cli.TasksChange.invoke(
                *arguments_strings, config_filename=self.file.name)
            self.assertIsNotNone(instance)
            self.assertIsNone(retcode)
            self.assertTrue(cli.TasksChange.op.called)
            self.assertTrue(cli.TasksChange.log_op.called)
            task_id_calls = [call(x) for x in task_ids]
            cli.TasksChange.op.assert_has_calls(task_id_calls)
            cli.TasksChange.log_op.assert_has_calls(task_id_calls)
            self.assertTrue(cli.TasksChange.domain_print.called)
            cli.TasksChange.domain_print.assert_has_calls([call()])
            self.assertTrue(cli.prettify.called)
