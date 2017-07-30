"""
    habitipy - tools and library for Habitica restful API
    command-line interface library using plumbum
"""
# pylint: disable=arguments-differ, attribute-defined-outside-init
# pylint: disable=invalid-name, logging-format-interpolation
import warnings
import logging
import os
from bisect import bisect
from contextlib import contextmanager
from functools import partial
from textwrap import dedent, wrap
from typing import List, Union, Dict, Any  # pylint: disable=unused-import
from plumbum import local, cli, colors
import requests
from .api import Habitipy
try:
    from emoji import emojize
except ImportError:
    emojize = None
DEFAULT_CONF = '~/.config/habitipy/config'
SUBCOMMANDS_JSON = '~/.config/habitipy/subcommands.json'


@contextmanager
def umask(mask):
    'temporarily change umask'
    prev = os.umask(mask)
    try:
        yield
    finally:
        os.umask(prev)


def is_secure_file(fn):
    st = os.stat(fn)
    return (st.st_mode & 0o777) == 0o600

secure_filestore = partial(umask, 0o077)


class SecurityError(ValueError):
    pass


def load_conf(configfile, config=None):
    """Get authentication data from the AUTH_CONF file."""
    default_login = 'your-login-for-api-here'
    default_password = 'your-password-for-api-here'
    config = config or {}
    configfile = local.path(configfile)
    if not configfile.exists():
        configfile.dirname.mkdir()
    if configfile.exists() and not is_secure_file(configfile):
        msg = """
        File {0} can be read by other users.
        This is not secure. Please run 'chmod 600 "{0}"'"""
        raise SecurityError(dedent(msg).replace('\n', ' ').format(configfile))
    with secure_filestore(), cli.Config(configfile) as conf:
        config['url'] = conf.get('habitipy.url', 'https://habitica.com')
        config['login'] = conf.get('habitipy.login', default_login)
        config['password'] = conf.get('habitipy.password', default_password)

    if config['login'] == default_login or config['password'] == default_password:
        warnings.warn("Your creditentials may be unconfigured.")  # noqa: Q000
    return config


class ConfiguredApplication(cli.Application):
    'Application with config'
    config_filename = cli.SwitchAttr(
        ['-c', '--config'], argtype=cli.ExistingFile, default=DEFAULT_CONF,
        argname='CONFIG',
        help="Use file CONFIG for config")  # noqa: Q000
    verbose = cli.Flag(
        ['-v', '--verbose'],
        help="Verbose output - log everything.",  # noqa: Q000
        excludes=['-s', '--silent'])
    silence_level = cli.CountOf(
        ['-s', '--silent'],
        help="Make program more silent",  # noqa: Q000
        excludes=['-v', '--verbose'])

    def main(self):
        self.config = load_conf(self.config_filename)
        self.log = logging.getLogger(str(self.__class__).split("'")[1])
        self.log.addHandler(logging.StreamHandler())
        if self.verbose:
            self.log.setLevel(logging.DEBUG)
        else:
            base_level = logging.INFO
            self.log.setLevel(base_level + 10 * self.silence_level)


class ApplicationWithApi(ConfiguredApplication):
    'Application with configured Habitica API'
    api = None  # type: Habitipy

    def main(self):
        super().main()
        self.api = Habitipy(self.config)


class HabiticaCli(ConfiguredApplication):
    VERSION = '0.1'

@HabiticaCli.subcommand('status')
class Status(ApplicationWithApi):
    DESCRIPTION = "Show HP, XP, GP, and more"
    def main(self):
        super().main()
        user = self.api.user.get()

class ScoreInfo(object):
    'task value/score info: http://habitica.wikia.com/wiki/Task_Value'
    scores = ['*', '**', '***', '****', '*****', '******', '*******']
    max_scores_len = max(map(len, scores))
    colors_ = ['Red3', 'Red1', 'DarkOrange', 'Gold3A', 'Green', 'LightCyan3', 'Cyan1']
    breakpoints = [-20, -10, -1, 1, 5, 10]

    def __new__(cls, value):
        index = bisect(cls.breakpoints, value)
        score = cls.scores[index]
        score_col = colors.fg(cls.colors_[index])  # pylint: disable=no-member
        score = '[' + score.center(cls.max_scores_len) + ']'
        return score_col | score

class TasksPrint(ApplicationWithApi):
    'Put all tasks from `domain` to print'
    domain = '' # type: str
    def domain_format(self, task):
        'format task for domain'
        raise NotImplementedError()

    def main(self):
        if self.nested_command:
            return
        super().main()
        tasks = self.api.tasks.user.get(type=self.domain)
        termwidth = cli.terminal.get_terminal_size()[0]
        habits_len = len(tasks)
        ident_size = len(str(habits_len)) + 2
        number_format = '{{:{}d}}. '.format(ident_size-2)
        indent = ' ' * ident_size
        if ident_size > termwidth:
            raise RuntimeError("Terminal too small")
        for i, task in enumerate(tasks):
            i = number_format.format(i + 1)
            res = '\n'.join(wrap(
                self.domain_format(task),
                width=termwidth, initial_indent=i,
                subsequent_indent=indent))
            print(emojize(res) if emojize else res)

@HabiticaCli.subcommand('habits')  # pylint: disable=missing-docstring
class Habits(TasksPrint):
    DESCRIPTION = "List, up and down habit tasks"
    domain = 'habits'
    def domain_format(self, habit):
        score = ScoreInfo(habit['value'])
        return "{} {text}".format(score, **habit)

@HabiticaCli.subcommand('dailies')  # pylint: disable=missing-docstring
class Dailys(TasksPrint):
    DESCRIPTION = "List, up and down daily tasks"
    domain = 'dailys'
    def domain_format(self, daily):
        score = ScoreInfo(daily['value'])
        check = 'X' if daily['completed'] else ' '
        res = "[{}] {} {text}".format(check, score, **daily)
        if not daily['isDue']:
            res = colors.strikeout + colors.dark_gray | res
        return res

@HabiticaCli.subcommand('todos')  # pylint: disable=missing-docstring
class ToDos(TasksPrint):
    DESCRIPTION = "List, comlete, add or delete todo tasks"
    domain = 'todos'
    def domain_format(self, todo):
        score = ScoreInfo(todo['value'])
        check = 'X' if todo['completed'] else ' '
        res = "[{}] {} {text}".format(check, score, **todo)
        return res

class TaskId(List[Union[str, int]]):
    """
    handle task-id formats such as:
        habitica todos done 3 taskalias_or_uuid
        habitica todos done 1,2,3,taskalias_or_uuid
        habitica todos done 2 3
        habitica todos done 1-3,4 8
    """
    def __new__(cls, tids: str):
        task_ids = []  # type: List[Union[str, int]]
        for bit in tids.split(','):
            try:
                if '-' in bit:
                    start, stop = [int(e) for e in bit.split('-')]
                    task_ids.extend(range(start, stop + 1))
                else:
                    task_ids.append(int(bit))
            except ValueError:
                task_ids.append(bit)
        return [e - 1 if isinstance(e, int) else e for e in set(task_ids)] # type: ignore

class TasksChange(ApplicationWithApi):
    'find all tasks specified by user and do self.op on them'
    domain = '' # type: str
    noop = cli.Flag(
        ['--dry-run', '--noop'],
        help="If passed, won't actually change anything on habitipy server")  # noqa: Q000

    def main(self, task_id: TaskId, *more_task_ids: TaskId):  # type: ignore
        super().main()
        for mt in more_task_ids:
            task_id.extend(mt)
        tasks = self.api.tasks.user.get(type=self.domain)
        task_ids = [task['id'] for task in tasks]
        num_tasks = len(tasks)
        aliases = {task['alias']:task for task in tasks if 'alias' in task}
        self.changing_tasks = {}  # type: Dict[Union[str,int], Dict[str, Any]]
        for tid in task_id:
            if isinstance(tid, int):
                if tid >= 0 and tid <= num_tasks:
                    self.changing_tasks[task_ids[tid]] = tasks[tid]
            elif isinstance(tid, str):
                if tid in task_ids:
                    self.changing_tasks[tid] = tasks[task_ids.index(tid)]
                elif tid in aliases:
                    self.changing_tasks[tid] = aliases[tid]
            self.log.error("Task id {} is invalid".format(tid))
            return
        self.log.info("Parsed task ids {}".format(self.changing_tasks))
        self.tasks = self.api.tasks
        for tid in self.changing_tasks:
            if self.noop:
                self.op(tid)
            res = self.log_op(tid)
            print(emojize(res) if emojize else res)
        self.domain_print()

    def validate(self, task):
        'check if task is valid for the operation'
        return True

    def op(self, tid):
        'operation to be done on task with `tid`'
        raise NotImplementedError

    def log_op(self, tid):
        'return a message to show user on successful change of `tid`'
        raise NotImplementedError

    def domain_print(self):
        'show domain to user again'
        raise NotImplementedError


class HabitsChange(TasksChange):  # pylint: disable=missing-docstring
    domain = 'habits'
    def domain_print(self):
        Habits.invoke(config_filename=self.config_filename)


@Habits.subcommand('up')  # pylint: disable=missing-docstring
class HabitsUp(HabitsChange):
    DESCRIPTION = "Up (+) a habit with task_id"
    def op(self, tid):
        self.tasks[tid].score['up'].post()

    def validate(self, task):
        return task['up']

    def log_op(self, tid):
        print("Incremented habit {text}".format(**self.changing_tasks[tid]))


@Habits.subcommand('down')  # pylint: disable=missing-docstring
class HabitsDown(HabitsChange):
    DESCRIPTION = "Down (-) a habit with task_id"
    def op(self, tid):
        self.tasks[tid].score['down'].post()

    def validate(self, task):
        return task['down']

    def log_op(self, tid):
        'show a message to user on successful change of `tid`'
        print("Decremented habit {text}".format(**self.changing_tasks[tid]))

class DailysChange(TasksChange):  # pylint: disable=missing-docstring
    domain = 'dailys'
    def domain_print(self):
        Dailys.invoke(config_filename=self.config_filename)

@Dailys.subcommand('done')  # pylint: disable=missing-docstring
class DailysUp(DailysChange):
    DESCRIPTION = "Check a dayly with task_id"
    def op(self, tid):
        self.tasks[tid].score['up'].post()

    def log_op(self, tid):
        print("Completed daily {text}".format(**self.changing_tasks[tid]))

@Dailys.subcommand('undo')  # pylint: disable=missing-docstring
class DailyDown(DailysChange):
    DESCRIPTION = "Uncheck a daily with task_id"
    def op(self, tid):
        self.tasks[tid].score['down'].post()

    def log_op(self, tid):
        print("Unchecked daily {text}".format(**self.changing_tasks[tid]))

class TodosChange(TasksChange):  # pylint: disable=missing-docstring
    domain = 'todos'
    def domain_print(self):
        ToDos.invoke(config_filename=self.config_filename)

@ToDos.subcommand('done')  # pylint: disable=missing-docstring
class TodosUp(TodosChange):
    DESCRIPTION = "Check a todo with task_id"
    def op(self, tid):
        self.tasks[tid].score['up'].post()

    def log_op(self, tid):
        print("Completed todo {text}".format(**self.changing_tasks[tid]))

@ToDos.subcommand('delete')  # pylint: disable=missing-docstring
class TodosDelete(TodosChange):
    DESCRIPTION = "Check a todo with task_id"
    def op(self, tid):
        self.tasks[tid].delete()

    def log_op(self, tid):
        print("Deleted todo {text}".format(**self.changing_tasks[tid]))

@ToDos.subcommand('add')  # pylint: disable=missing-docstring
class TodosAdd(ApplicationWithApi):
    DESCRIPTION = "Add a todo <todo>"
    def main(self):
        super().main()
        a = self.api.user.get()

@HabiticaCli.subcommand('home')  # pylint: disable=missing-docstring
class Home(ConfiguredApplication):
    DESCRIPTION = "Open habitica site in browser"
    def main(self):
        super().main()
        from webbrowser import open_new_tab
        HABITICA_TASKS_PAGE = '/#/tasks'
        home_url = '{}{}'.format(self.config['url'], HABITICA_TASKS_PAGE)
        self.log.info("Opening %s", home_url)
        open_new_tab(home_url)

@HabiticaCli.subcommand('server')  # pylint: disable=missing-docstring
class Server(ApplicationWithApi):
    DESCRIPTION = "Check habitica server availability"
    def main(self):
        super().main()
        try:
            ret = self.api.status.get()
            if isinstance(ret, dict) and ret['status'] == 'up':
                print("Habitica server {} online".format(self.config['url']))
                return
        except (KeyError, requests.exceptions.ConnectionError):
            pass
        msg = "Habitica server {} offline or there is some issue with it"
        print(msg.format(self.config['url']))
        return -1


sc = local.path(SUBCOMMANDS_JSON)
if sc.exists():
    import json
    try:
        with open(sc) as f:
            c = json.load(f)
        for name, mod in c:
            HabiticaCli.subcommand(name, mod)
    except json.JSONDecodeError as e:
        warnings.warn('subcommands.json found, but it is invalid: {}'.format(e))
del sc

if __name__ == '__main__':
    HabiticaCli.run()
