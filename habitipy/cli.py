"""
    habitipy - tools and library for Habitica restful API
    command-line interface library using plumbum
"""
# pylint: disable=arguments-differ, attribute-defined-outside-init
# pylint: disable=invalid-name, logging-format-interpolation,too-few-public-methods
import warnings
import logging
import os
import json
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
CONTENT_JSON = local.path('~/.config/habitipy/content.json')
# TODO: add I18N
_ = lambda x: x  # NOQA: E731
CLASSES = [_("warrior"), _("rogue"), _("wizard"), _("healer")]  # noqa: Q000


@contextmanager
def umask(mask):
    'temporarily change umask'
    prev = os.umask(mask)
    try:
        yield
    finally:
        os.umask(prev)


def is_secure_file(fn):
    'checks if a file can be accessed only by the owner'
    st = os.stat(fn)
    return (st.st_mode & 0o777) == 0o600


secure_filestore = partial(umask, 0o077)


class SecurityError(ValueError):
    'Error fired when a secure file is stored in an insecure manner'
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


def get_content(api, rebuild_cache=False):
    'get content from server or cache'
    if hasattr(get_content, 'cache') and not rebuild_cache:
        return get_content.cache
    if not os.path.exists(CONTENT_JSON) or rebuild_cache:
        import locale
        content_endpoint = api.content.get
        try:
            # pylint: disable=protected-access
            loc = locale.getdefaultlocale()[0]
            server_lang = content_endpoint._node.params['query']['language']
            # handle something like 'ru_RU' not available - only 'ru'
            for lang in [loc, loc[:2]]:
                if lang in server_lang.possible_values:
                    loc = {'language': lang}
                    break
            else:
                loc = {}
        except (IndexError, KeyError):
            loc = {}
        get_content.cache = content = content_endpoint(**loc)
        with open(CONTENT_JSON, 'w') as f:
            json.dump(content, f)
        return content
    else:
        try:
            with open(CONTENT_JSON) as f:
                get_content.cache = content = json.load(f)
            return content
        except json.JSONDecodeError:
            return get_content(api, rebuild_cache=True)


class ApplicationWithApi(ConfiguredApplication):
    'Application with configured Habitica API'
    api = None  # type: Habitipy

    def main(self):
        super().main()
        self.api = Habitipy(self.config)


class HabiticaCli(ConfiguredApplication):  # pylint: disable=missing-docstring
    VERSION = '0.1'


@HabiticaCli.subcommand('status')  # pylint: disable=missing-docstring
class Status(ApplicationWithApi):
    DESCRIPTION = "Show HP, XP, GP, and more"  # noqa: Q000

    def main(self):
        super().main()
        user = self.api.user.get()
        for key in ['hp', 'mp', 'exp']:
            user['stats'][key] = round(user['stats'][key])
        user['stats']['class'] = _(user['stats']['class']).capitalize()
        user['food'] = sum(user['items']['food'].values())
        content = get_content(self.api)
        user['pet'] = user['items']['currentPet']
        user['pet'] = content['petInfo'][user['pet']]['text'] if user['pet'] else ''
        user['pet'] = "Pet: " + user['pet'] if user['pet'] else "No pet"  # noqa: Q000
        user['mount'] = user['items']['currentMount']
        user['mount'] = content['mountInfo'][user['mount']]['text'] if user['mount'] else ''
        user['mount'] = "Mount: " + user['mount'] if user['mount'] else "No mount"  # noqa: Q000
        level = "\nLevel {stats[lvl]} {stats[class]}\n".format(**user)  # noqa: Q000
        highlight = '-' * (len(level) - 2)
        level = highlight + level + highlight
        result = [
            level,
            "Health: {stats[hp]}/{stats[maxHealth]}",  # noqa: Q000
            "XP: {stats[exp]}/{stats[toNextLevel]}",  # noqa: Q000
            "Mana: {stats[mp]}/{stats[maxMP]}",  # noqa: Q000
            "{pet} ({food} food items)",  # noqa: Q000
            "{mount}"]  # noqa: Q000
        print('\n'.join(result).format(**user))


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
    domain = ''  # type: str
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
        number_format = '{{:{}d}}. '.format(ident_size - 2)
        indent = ' ' * ident_size
        if ident_size > termwidth:
            raise RuntimeError("Terminal too small")  # noqa: Q000
        for i, task in enumerate(tasks):
            i = number_format.format(i + 1)
            res = '\n'.join(wrap(
                self.domain_format(task),
                width=termwidth, initial_indent=i,
                subsequent_indent=indent))
            print(emojize(res) if emojize else res)


@HabiticaCli.subcommand('habits')  # pylint: disable=missing-docstring
class Habits(TasksPrint):
    DESCRIPTION = "List, up and down habit tasks"  # noqa: Q000
    domain = 'habits'
    def domain_format(self, habit):
        score = ScoreInfo(habit['value'])
        return "{} {text}".format(score, **habit)  # noqa: Q000


@HabiticaCli.subcommand('dailies')  # pylint: disable=missing-docstring
class Dailys(TasksPrint):
    DESCRIPTION = "List, up and down daily tasks"  # noqa: Q000
    domain = 'dailys'
    def domain_format(self, daily):
        score = ScoreInfo(daily['value'])
        check = 'X' if daily['completed'] else ' '
        res = "[{}] {} {text}".format(check, score, **daily)  # noqa: Q000
        if not daily['isDue']:
            res = colors.strikeout + colors.dark_gray | res  # pylint: disable=no-member
        return res


@HabiticaCli.subcommand('todos')  # pylint: disable=missing-docstring
class ToDos(TasksPrint):
    DESCRIPTION = "List, comlete, add or delete todo tasks"  # noqa: Q000
    domain = 'todos'
    def domain_format(self, todo):
        score = ScoreInfo(todo['value'])
        check = 'X' if todo['completed'] else ' '
        res = "[{}] {} {text}".format(check, score, **todo)  # noqa: Q000
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
        return [e - 1 if isinstance(e, int) else e for e in set(task_ids)]  # type: ignore


class TasksChange(ApplicationWithApi):
    'find all tasks specified by user and do self.op on them'
    domain = ''  # type: str
    noop = cli.Flag(
        ['--dry-run', '--noop'],
        help="If passed, won't actually change anything on habitipy server")  # noqa: Q000

    def main(self, *task_ids: TaskId):  # type: ignore
        super().main()
        task_id = []  # type: List[Union[str,int]]
        for tids in task_ids:
            task_id.extend(tids)
        if not task_id:
            self.log.error('No task_ids found!')
            return 1
        tasks = self.api.tasks.user.get(type=self.domain)
        task_uuids = [task['id'] for task in tasks]
        num_tasks = len(tasks)
        aliases = {task['alias']: task for task in tasks if 'alias' in task}
        self.changing_tasks = {}  # type: Dict[Union[str,int], Dict[str, Any]]
        for tid in task_id:
            if isinstance(tid, int):
                if tid >= 0 and tid <= num_tasks:
                    self.changing_tasks[task_uuids[tid]] = tasks[tid]
            elif isinstance(tid, str):
                if tid in task_uuids:
                    self.changing_tasks[tid] = tasks[task_uuids.index(tid)]
                elif tid in aliases:
                    self.changing_tasks[tid] = aliases[tid]
            self.log.error("Task id {} is invalid".format(tid))  # noqa: Q000
            return
        self.log.info("Parsed task ids {}".format(self.changing_tasks))  # noqa: Q000
        self.tasks = self.api.tasks
        for tid in self.changing_tasks:
            if self.noop:
                self.op(tid)
            res = self.log_op(tid)
            print(emojize(res) if emojize else res)
        self.domain_print()

    def validate(self, task):  # pylint: disable=no-self-use,unused-argument
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


class HabitsChange(TasksChange):  # pylint: disable=missing-docstring,abstract-method
    domain = 'habits'
    def domain_print(self):
        Habits.invoke(config_filename=self.config_filename)


@Habits.subcommand('up')  # pylint: disable=missing-docstring
class HabitsUp(HabitsChange):
    DESCRIPTION = "Up (+) a habit with task_id"  # noqa: Q000
    def op(self, tid):
        self.tasks[tid].score['up'].post()

    def validate(self, task):
        return task['up']

    def log_op(self, tid):
        print("Incremented habit {text}".format(**self.changing_tasks[tid]))  # noqa: Q000


@Habits.subcommand('down')  # pylint: disable=missing-docstring
class HabitsDown(HabitsChange):
    DESCRIPTION = "Down (-) a habit with task_id"  # noqa: Q000
    def op(self, tid):
        self.tasks[tid].score['down'].post()

    def validate(self, task):
        return task['down']

    def log_op(self, tid):
        'show a message to user on successful change of `tid`'
        print("Decremented habit {text}".format(**self.changing_tasks[tid]))  # noqa: Q000


class DailysChange(TasksChange):  # pylint: disable=missing-docstring,abstract-method
    domain = 'dailys'
    def domain_print(self):
        Dailys.invoke(config_filename=self.config_filename)


@Dailys.subcommand('done')  # pylint: disable=missing-docstring
class DailysUp(DailysChange):
    DESCRIPTION = "Check a dayly with task_id"  # noqa: Q000
    def op(self, tid):
        self.tasks[tid].score['up'].post()

    def log_op(self, tid):
        print("Completed daily {text}".format(**self.changing_tasks[tid]))  # noqa: Q000


@Dailys.subcommand('undo')  # pylint: disable=missing-docstring
class DailyDown(DailysChange):
    DESCRIPTION = "Uncheck a daily with task_id"  # noqa: Q000
    def op(self, tid):
        self.tasks[tid].score['down'].post()

    def log_op(self, tid):
        print("Unchecked daily {text}".format(**self.changing_tasks[tid]))  # noqa: Q000


class TodosChange(TasksChange):  # pylint: disable=missing-docstring,abstract-method
    domain = 'todos'
    def domain_print(self):
        ToDos.invoke(config_filename=self.config_filename)


@ToDos.subcommand('done')  # pylint: disable=missing-docstring
class TodosUp(TodosChange):
    DESCRIPTION = "Check a todo with task_id"  # noqa: Q000
    def op(self, tid):
        self.tasks[tid].score['up'].post()

    def log_op(self, tid):
        print("Completed todo {text}".format(**self.changing_tasks[tid]))  # noqa: Q000


@ToDos.subcommand('delete')  # pylint: disable=missing-docstring
class TodosDelete(TodosChange):
    DESCRIPTION = "Check a todo with task_id"  # noqa: Q000
    def op(self, tid):
        self.tasks[tid].delete()

    def log_op(self, tid):
        print("Deleted todo {text}".format(**self.changing_tasks[tid]))  # noqa: Q000


@ToDos.subcommand('add')  # pylint: disable=missing-docstring
class TodosAdd(ApplicationWithApi):
    DESCRIPTION = "Add a todo <todo>"  # noqa: Q000
    priority = cli.SwitchAttr(
        ['-p', '--priority'],
        cli.Set('0.1', '1', '1.5', '2'), default='1',
        help="Priority (complexity) of a todo")  # noqa: Q000

    def main(self, *todo: str):
        todo_str = ' '.join(todo)
        if not todo:
            self.log.error("Empty todo text!")  # noqa: Q000
            return 1
        super().main()
        self.api.tasks.user.post(type='todo', text=todo_str, priority=self.priority)
        print("Added todo '{}' with priority {}".format(todo_str, self.priority))  # noqa: Q000
        ToDos.invoke(config_filename=self.config_filename)


@HabiticaCli.subcommand('home')  # pylint: disable=missing-docstring
class Home(ConfiguredApplication):
    DESCRIPTION = "Open habitica site in browser"  # noqa: Q000
    def main(self):
        super().main()
        from webbrowser import open_new_tab
        HABITICA_TASKS_PAGE = '/#/tasks'
        home_url = '{}{}'.format(self.config['url'], HABITICA_TASKS_PAGE)
        print("Opening {}".format(home_url))  # noqa: Q000
        open_new_tab(home_url)


@HabiticaCli.subcommand('server')  # pylint: disable=missing-docstring
class Server(ApplicationWithApi):
    DESCRIPTION = "Check habitica server availability"  # noqa: Q000
    def main(self):
        super().main()
        try:
            ret = self.api.status.get()
            if isinstance(ret, dict) and ret['status'] == 'up':
                print("Habitica server {} online".format(self.config['url']))  # noqa: Q000
                return
        except (KeyError, requests.exceptions.ConnectionError):
            pass
        msg = "Habitica server {} offline or there is some issue with it"  # noqa: Q000
        print(msg.format(self.config['url']))
        return -1


subcommands_file = local.path(SUBCOMMANDS_JSON)
if subcommands_file.exists():
    try:
        with open(subcommands_file) as subcommands_file_obj:
            subcommands = json.load(subcommands_file_obj)
        del subcommands_file_obj
        for name, module in subcommands.items():
            HabiticaCli.subcommand(name, module)
            del name
            del module
        del subcommands
    except (AttributeError, json.JSONDecodeError) as error:
        warnings.warn('subcommands.json found, but it is invalid: {}'.format(error))
        del error
del subcommands_file

if __name__ == '__main__':
    HabiticaCli.run()
