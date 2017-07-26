import warnings
import logging
import os
from bisect import bisect
from contextlib import contextmanager
from functools import partial
from textwrap import dedent, wrap
from plumbum import local, cli, colors
import requests
from .api import Habitipy

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
        warnings.warn("Your creditentials may be unconfigured.")
    return config


class ConfiguredApplication(cli.Application):
    'Application with config'
    config = cli.SwitchAttr(
        ['-c', '--config'], argtype=cli.ExistingFile, default=DEFAULT_CONF,
        argname='CONFIG', help="Use CONFIG for config")
    verbose = cli.Flag(
        ['-v', '--verbose'], help = "Verbose output - log everything.", excludes=['-s','--silent'])
    silence_level = cli.CountOf(
        ['-s', '--silent'], help="Make program more silent", excludes=['-v', '--verbose'])
    def main(self):
        self.config = load_conf(self.config)
        self.log = logging.getLogger(str(self.__class__).split("'")[1])
        self.log.addHandler(logging.StreamHandler())
        if self.verbose:
            self.log.setLevel(logging.DEBUG)
        else:
            base_level = logging.INFO
            self.log.setLevel(base_level + 10 * self.silence_level)


class ApplicationWithApi(ConfiguredApplication):
    'Application with configured Habitica API'
    api = None

    def main(self):
        super().main()
        self.api = Habitipy(self.config)




class HabiticaCli(ConfiguredApplication):
    VERSION = '0.1'

@HabiticaCli.subcommand('status')
class Status(ApplicationWithApi):
    """Show HP, XP, GP, and more"""
    def main(self):
        super().main()
        user = self.api.user.get()


class TasksPrint(ApplicationWithApi):
    'Put all tasks from `domain` to print'
    domain = None
    def domain_format(self, task):
        'format task for domain'
        raise NotImplementedError()

    @staticmethod
    def qualitative_task_score_from_value(value):
        'task value/score info: http://habitica.wikia.com/wiki/Task_Value'
        scores = ['*', '**', '***', '****', '*****', '******', '*******']
        colors_ = ['Red3', 'Red1', 'DarkOrange', 'Gold3A', 'LightCyan3', 'Cyan1']
        breakpoints = [-20, -10, -1, 1, 5, 10]
        index = bisect(breakpoints, value)
        return scores[index], colors.fg(colors_[index])

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
            i = number_format.format(i)
            print('\n'.join(wrap(
                self.domain_format(task),
                width=termwidth, initial_indent=i,
                subsequent_indent=indent)))

@HabiticaCli.subcommand('habits')
class Habits(TasksPrint):
    'List, up and down habit tasks'
    domain = 'habits'
    def domain_format(self, habit):
        return ''

@HabiticaCli.subcommand('dailies')
class Dailys(ApplicationWithApi):
    'List, up and down daily tasks'
    def main(self):
        if self.nested_command:
            return
        super().main()
        print("Ok")

@HabiticaCli.subcommand('todos')
class ToDos(ApplicationWithApi):
    'List, up and down todo tasks'
    def main(self):
        if self.nested_command:
            return
        super().main()
        print("Ok")

@cli.Predicate
def TaskId(tids):
    """
    handle task-id formats such as:
        habitica todos done 3 taskalias_or_uuid
        habitica todos done 1,2,3,taskalias_or_uuid
        habitica todos done 2 3
        habitica todos done 1-3,4 8
    """
    task_ids = []
    for bit in tids.split(','):
        try:
            if '-' in bit:
                start, stop = [int(e) for e in bit.split('-')]
                task_ids.extend(range(start, stop + 1))
            else:
                task_ids.append(int(bit))
        except ValueError:
            task_ids.append(bit)
    return [e - 1 if isinstance(e, int) else e for e in set(task_ids)]

class TasksChange(ApplicationWithApi):
    domain = None
    def main(self, task_id: TaskId, *more_task_ids: TaskId):
        super().main()
        for mt in more_task_ids:
            task_id.extend(mt)
        tasks = self.api.tasks.user.get(type=self.domain)
        task_ids = [task['id'] for task in tasks]
        num_tasks = len(tasks)
        aliases = [task['alias'] for task in tasks if 'alias' in task]
        to_change = []
        for tid in task_id:
            if isinstance(tid, int):
                if tid < 0 or tid >= num_tasks:
                    print("Task id {} invalid".format(tid))
                to_change.append(task_ids[tid])
            elif isinstance(tid, str):
                if tid in task_ids or tid in aliases:
                    to_change.append(tid)
            else:
                print("Task id {} invalid".format(tid))
        for tid in to_change:
            self.op(tid)

    def op(self, tid):
        raise NotImplementedError

@Habits.subcommand('up')
class HabitsUp(TasksChange):
    'Up (+) a habit with task_id'
    domain='habits'
    def op(self, tid):
        self.tasks[tid].score['up'].post()

@Habits.subcommand('down')
class HabitsDown(TasksChange):
    'Down (-) a habit with task_id'
    domain='habits'
    def op(self, tid):
        self.tasks[tid].score['down'].post()

@Dailys.subcommand('done')
class DailysUp(TasksChange):
    "Check a dayly with task_id"
    domain='dailys'
    def op(self, tid):
        self.tasks[tid].score['up'].post()

@Dailys.subcommand('undo')
class DailyDown(TasksChange):
    "Uncheck a daily with task_id"
    domain='dailys'
    def op(self, tid):
        self.tasks[tid].score['down'].post()

@ToDos.subcommand('done')
class TodosUp(TasksChange):
    "Check a todo with task_id"
    domain='todos'
    def op(self, tid):
        self.tasks[tid].score['up'].post()

@ToDos.subcommand('delete')
class TodosUp(TasksChange):
    "Check a todo with task_id"
    domain='todos'
    def op(self, tid):
        self.tasks[tid].delete()

@HabiticaCli.subcommand('home')
class Home(ConfiguredApplication):
    "Open habitica site in browser"
    def main(self):
        super().main()
        from webbrowser import open_new_tab
        HABITICA_TASKS_PAGE = '/#/tasks'
        home_url = '{}{}'.format(self.config['url'], HABITICA_TASKS_PAGE)
        self.log.info("Opening %s", home_url)
        open_new_tab(home_url)

@HabiticaCli.subcommand('server')
class Server(ApplicationWithApi):
    "Check habitica server availability"
    def main(self):
        super().main()
        try:
            ret = self.api.status.get()
            if isinstance(ret, dict) and ret['status'] == 'up':
                self.log.info("Habitica server {} online".format(self.config['url']))
                return
        except (KeyError, requests.exceptions.ConnectionError):
            pass
        msg = "Habitica server {} offline or there is some issue with it"
        self.log.info(msg.format(self.config['url']))
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

"""
     dailies                 List daily tasks
     dailies done            Mark daily <task-id> complete
     dailies undo            Mark daily <task-id> incomplete
     todos                   List todo tasks
     todos done <task-id>    Mark one or more todo <task-id> completed
     todos add <task>        Add todo with description <task>
     todos delete <task-id>  Delete one or more todo <task-id>
     server                  Show status of Habitica service
"""
