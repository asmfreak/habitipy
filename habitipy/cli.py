"""
    habitipy - tools and library for Habitica restful API
    command-line interface library using plumbum
"""
# pylint: disable=arguments-differ, attribute-defined-outside-init,ungrouped-imports
# pylint: disable=invalid-name, logging-format-interpolation,too-few-public-methods
import warnings
import logging
import os
import json
import uuid
from bisect import bisect
from collections.abc import Mapping
from itertools import chain
from textwrap import dedent
from typing import List, Union, Dict, Any  # pylint: disable=unused-import
import pkg_resources
from plumbum import local, cli, colors
import requests
from .api import Habitipy
from .util import assert_secure_file, secure_filestore
from .util import get_translation_functions, get_translation_for
from .util import prettify

try:
    from json import JSONDecodeError  # type: ignore
except ImportError:
    JSONDecodeError = ValueError  # type: ignore


DEFAULT_CONF = '~/.config/habitipy/config'
SUBCOMMANDS_JSON = '~/.config/habitipy/subcommands.json'
CONTENT_JSON = local.path('~/.config/habitipy/content.json')
_, ngettext = get_translation_functions('habitipy', names=('gettext', 'ngettext'))
CLASSES = [_("warrior"), _("rogue"), _("wizard"), _("healer")]  # noqa: Q000
YES_ANSWERS = ('yes', 'y', 'true', 'True', '1')
CHECK_MARK_STYLES = ('wide', 'narrow', 'ascii')
CHECK = {
    'wide': colors.green | '✔ ',
    'narrow': colors.green | '✔',
    'ascii': '[X]'
}
UNCHECK = {
    'wide': colors.red | '✖ ',
    'narrow': colors.red | '✖',
    'ascii': '[ ]'
}


def is_uuid(u):
    """validator for plumbum prompt"""
    if isinstance(u, str) and u.replace('-', '') == uuid.UUID(u).hex:
        return u
    return False


def load_conf(configfile, config=None):
    """Get authentication data from the AUTH_CONF file."""
    default_login = 'your-login-for-api-here'
    default_password = 'your-password-for-api-here'
    config = config or {}
    configfile = local.path(configfile)
    if not configfile.exists():
        configfile.dirname.mkdir()
    else:
        assert_secure_file(configfile)
    with secure_filestore(), cli.Config(configfile) as conf:
        config['url'] = conf.get('habitipy.url', 'https://habitica.com')
        config['login'] = conf.get('habitipy.login', default_login)
        config['password'] = conf.get('habitipy.password', default_password)
        if config['login'] == default_login or config['password'] == default_password:
            if cli.terminal.ask(
                    _("""Your creditentials are invalid. Do you want to enter them now?"""),
                    default=True):
                msg = _("""
                You can get your login information at
                https://habitica.com/#/options/settings/api
                Both your user id and API token should look like this:
                xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
                where 'x' is a number between 0-9 or a character a-f.
                """)
                print(dedent(msg))
                msg = _("""Please enter your login (user ID)""")
                config['login'] = cli.terminal.prompt(msg, validator=is_uuid)
                msg = _("""Please enter your password (API token)""")
                config['password'] = cli.terminal.prompt(msg, validator=is_uuid)
                conf.set('habitipy.login', config['login'])
                conf.set('habitipy.password', config['password'])
                print(dedent(_("""
                Your creditentials are securely stored in
                {configfile}
                You can edit that file later if you need.
                """)).format(configfile=configfile))
        config['show_numbers'] = conf.get('habitipy.show_numbers', 'y')
        config['show_numbers'] = config['show_numbers'] in YES_ANSWERS
        config['show_style'] = conf.get('habitipy.show_style', 'wide')
        if config['show_style'] not in CHECK_MARK_STYLES:
            config['show_style'] = 'wide'
    return config


class ConfiguredApplication(cli.Application):
    """Application with config"""
    config_filename = cli.SwitchAttr(
        ['-c', '--config'], argtype=local.path, default=DEFAULT_CONF,
        argname='CONFIG',
        help=_("Use file CONFIG for config"))  # noqa: Q000
    verbose = cli.Flag(
        ['-v', '--verbose'],
        help=_("Verbose output - log everything."),  # noqa: Q000
        excludes=['-s', '--silent'])
    silence_level = cli.CountOf(
        ['-s', '--silent'],
        help=_("Make program more silent"),  # noqa: Q000
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


class Content(Mapping):
    """Caching class for Habitica content data"""
    _cache = None

    def __init__(self, api, rebuild_cache=False, path=None):
        self._api = api
        self._path = []
        self._rebuild_cache = rebuild_cache
        self._path = path
        self._obj = None
        self._resolve_path()

    def __getitem__(self, i):
        try:
            ret = self._obj[i]
            if isinstance(ret, (list, dict)):
                return Content(self._api, self._rebuild_cache, [*self._path, i])
            return ret
        except (KeyError, IndexError):
            if self._rebuild_cache:
                raise
            self._rebuild_cache = True
            self._resolve_path()
            return self.__getitem__(i)

    def __iter__(self):
        if self._obj:
            yield from iter(self._obj)

    def __len__(self):
        if self._obj:
            return len(self._obj)
        return 0

    def _resolve_path(self):
        if self._path is None:
            self._path = []
        self._obj = self._get()
        for e in self._path:
            self._obj = self._obj[e]

    def _get(self):
        """get content from server or cache"""
        if Content._cache and not self._rebuild_cache:
            return Content._cache
        if not os.path.exists(CONTENT_JSON) or self._rebuild_cache:
            content_endpoint = self._api.content.get
            # pylint: disable=protected-access
            server_lang = content_endpoint._node.params['query']['language']
            Content._cache = content_endpoint(**next((
                {'language': lang}
                for lang in chain(
                    Content._lang_from_translation(),
                    Content._lang_from_locale())
                if lang in server_lang.possible_values
            ), {}))  # default
            with open(CONTENT_JSON, 'w') as f:
                json.dump(Content._cache, f)
            return Content._cache
        try:
            with open(CONTENT_JSON) as f:
                Content._cache = json.load(f)
            return Content._cache
        except JSONDecodeError:
            self._rebuild_cache = True
            return self._get()

    @staticmethod
    def _lang_from_translation():
        try:
            yield get_translation_for('habitipy').info()['language']
        except KeyError:
            pass

    @staticmethod
    def _lang_from_locale():
        import locale
        try:
            loc = locale.getdefaultlocale()[0]
            if loc:
                # handle something like 'ru_RU' not available - only 'ru'
                yield loc
                yield loc[:2]
        except IndexError:
            pass


class ApplicationWithApi(ConfiguredApplication):
    """Application with configured Habitica API"""
    api = None  # type: Habitipy

    def main(self):
        super().main()
        self.api = Habitipy(self.config)


class HabiticaCli(ConfiguredApplication):  # pylint: disable=missing-docstring
    DESCRIPTION = _("tools and library for Habitica restful API")  # noqa: Q000
    VERSION = pkg_resources.get_distribution('habitipy').version
    def main(self):
        if self.nested_command:
            return
        super().main()
        self.log.error(_("No subcommand given, exiting"))  # noqa: Q000


@HabiticaCli.subcommand('status')  # pylint: disable=missing-docstring
class Status(ApplicationWithApi):
    DESCRIPTION = _("Show HP, XP, GP, and more")  # noqa: Q000

    def main(self):
        super().main()
        user = self.api.user.get()
        for key in ['hp', 'mp', 'exp']:
            user['stats'][key] = round(user['stats'][key])
        user['stats']['class'] = _(user['stats']['class']).capitalize()
        user['food'] = sum(user['items']['food'].values())
        content = Content(self.api)
        user['pet'] = user['items']['currentPet'] if 'currentPet' in user['items'] else None
        user['pet'] = content['petInfo'][user['pet']]['text'] if user['pet'] else ''
        user['pet'] = _("Pet: ") + user['pet'] if user['pet'] else _("No pet")  # noqa: Q000
        user['mount'] = user['items'].get('currentMount', None)
        user['mount'] = content['mountInfo'][user['mount']]['text'] if user['mount'] else ''
        if user['mount']:
            user['mount'] = _("Mount: ") + user['mount']  # noqa: Q000
        else:
            user['mount'] = _("No mount")  # noqa: Q000
        level = _("\nLevel {stats[lvl]} {stats[class]}\n").format(**user)  # noqa: Q000
        highlight = '-' * (len(level) - 2)
        level = highlight + level + highlight
        result = [
            level,
            colors.red | _("Health: {stats[hp]}/{stats[maxHealth]}"),  # noqa: Q000
            colors.yellow | _("XP: {stats[exp]}/{stats[toNextLevel]}"),  # noqa: Q000
            colors.blue | _("Mana: {stats[mp]}/{stats[maxMP]}"),  # noqa: Q000
            colors.light_yellow | _("GP: {stats[gp]:.2f}"),  # noqa: Q000
            '{pet} ' + ngettext(
                "({food} food item)",   # noqa: Q000
                "({food} food items)",  # noqa: Q000
                user['food']),
            '{mount}']
        quest = self.quest_info(user)
        if quest:
            result.append(quest)
        print('\n'.join(result).format(**user))

    def quest_info(self, user):
        """Get current quest info or return None"""
        key = user['party']['quest'].get('key', None)
        if '_id' not in user['party'] or key is None:
            return None
        for refresh in False, True:
            content = Content(self.api, refresh)
            quest = content['quests'].get(key, None)
            if quest:
                break
        else:
            self.log.warning(dedent(_(
                """Quest {} not found in Habitica's content.
                Please file an issue to https://github.com/ASMfreaK/habitipy/issues
                """)).format(key))
            return None
        for quest_type, quest_template in (
                ('collect', _("""
                Quest: {quest[text]} (collect-type)
                {user[party][quest][progress][collectedItems]} quest items collected
                """)),
                ('boss', _("""
                Quest: {quest[text]} (boss)
                {user[party][quest][progress][up]:.1f} damage will be dealt to {quest[boss][name]}
                """))):
            if quest_type in quest:
                try:
                    return dedent(quest_template.format(quest=quest, user=user))[1:-1]
                except KeyError:
                    self.log.warning(dedent(_(
                        """Something went wrong when formatting quest {}.
                        Please file an issue to https://github.com/ASMfreaK/habitipy/issues
                        """)).format(key))
                    return None
        self.log.warning(dedent(_(
            """Quest {} isn't neither a collect-type or a boss-type.
            Please file an issue to https://github.com/ASMfreaK/habitipy/issues
            """)).format(key))


class ScoreInfo:
    """task value/score info: http://habitica.wikia.com/wiki/Task_Value"""

    scores = {
        'wide': ['▁', '▂', '▃', '▄', '▅', '▆', '▇'],
        'narrow': ['▁', '▂', '▃', '▄', '▅', '▆', '▇'],
        'ascii': ['*', '**', '***', '****', '*****', '******', '*******']
    }

    colors_ = ['Red3', 'Red1', 'DarkOrange', 'Gold3A', 'Green', 'LightCyan3', 'Cyan1']
    breakpoints = [-20, -10, -1, 1, 5, 10]

    def __new__(cls, style, value):
        index = bisect(cls.breakpoints, value)
        score = cls.scores[style][index]
        score_col = colors.fg(cls.colors_[index])
        if style == 'ascii':
            max_scores_len = max(map(len, cls.scores[style]))
            score = '[' + score.center(max_scores_len) + ']'
            # score = '⎡' + score.center(cls.max_scores_len) + '⎤'
        return score_col | score

    @classmethod
    def color(cls, value):
        """task value/score color"""
        index = bisect(cls.breakpoints, value)
        return colors.fg(cls.colors_[index])


class TasksPrint(ApplicationWithApi):
    """Put all tasks from `domain` to print"""
    domain = ''  # type: str
    more_tasks = []  # type: List[Dict[str, Any]]
    def domain_format(self, task):
        """format task for domain"""
        raise NotImplementedError()

    def main(self):
        if self.nested_command:
            return
        super().main()
        tasks = self.api.tasks.user.get(type=self.domain)
        tasks.extend(self.more_tasks)
        habits_len = len(tasks)
        ident_size = len(str(habits_len)) + 2
        number_format = '{{:{}d}}. '.format(ident_size - 2)
        for i, task in enumerate(tasks):
            i = number_format.format(i + 1) if self.config['show_numbers'] else ''
            res = i + prettify(self.domain_format(task))
            print(res)


@HabiticaCli.subcommand('habits')  # pylint: disable=missing-docstring
class Habits(TasksPrint):
    DESCRIPTION = _("List, up and down habit tasks")  # noqa: Q000
    domain = 'habits'
    def domain_format(self, habit):
        score = ScoreInfo(self.config['show_style'], habit['value'])
        return _("{0} {text}").format(score, **habit)  # noqa: Q000


@HabiticaCli.subcommand('dailies')  # pylint: disable=missing-docstring
class Dailys(TasksPrint):
    DESCRIPTION = _("List, check, uncheck daily tasks")  # noqa: Q000
    domain = 'dailys'
    def domain_format(self, daily):
        score = ScoreInfo(self.config['show_style'], daily['value'])
        check = CHECK if daily['completed'] else UNCHECK
        check = check[self.config['show_style']]
        checklist_done = len(list(filter(lambda x: x['completed'], daily['checklist'])))
        checklist = \
            ' {}/{}'.format(
                checklist_done,
                len(daily['checklist'])
            ) if daily['checklist'] else ''
        res = _("{0}{1}{text}{2}").format(check, score, checklist, **daily)  # noqa: Q000
        if not daily['isDue']:
            res = colors.strikeout + colors.dark_gray | res
        return res


@HabiticaCli.subcommand('todos')  # pylint: disable=missing-docstring
class ToDos(TasksPrint):
    DESCRIPTION = _("List, comlete, add or delete todo tasks")  # noqa: Q000
    domain = 'todos'
    def domain_format(self, todo):
        score = ScoreInfo(self.config['show_style'], todo['value'])
        check = CHECK if todo['completed'] else UNCHECK
        check = check[self.config['show_style']]
        checklist_done = len(list(filter(lambda x: x['completed'], todo['checklist'])))
        checklist = \
            ' {}/{}'.format(
                checklist_done,
                len(todo['checklist'])
            ) if todo['checklist'] else ''
        res = _("{1}{0}{text}{2}").format(check, score, checklist, **todo)  # noqa: Q000
        return res


def get_additional_rewards(api):
    """returns list of non-user rewards (potion, armoire, gear)"""
    c = Content(api)
    tasks = [c[i] for i in ['potion', 'armoire']]
    tasks.extend(api.user.inventory.buy.get())
    for task in tasks:
        task['id'] = task['alias'] = task['key']
    return tasks


@HabiticaCli.subcommand('rewards')  # pylint: disable=missing-docstring
class Rewards(TasksPrint):
    DESCRIPTION = _("List, buy and add rewards")  # noqa: Q000
    domain = 'rewards'

    def main(self):
        if self.nested_command:
            return
        ApplicationWithApi.main(self)
        self.more_tasks = get_additional_rewards(self.api)
        super().main()

    def domain_format(self, reward):
        score = colors.yellow | _("{value} gp").format(**reward)  # noqa: Q000
        return _("{} {text}").format(score, **reward)  # noqa: Q000


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
        return [e - 1 if isinstance(e, int) else e for e in task_ids]  # type: ignore


class TasksChange(ApplicationWithApi):
    """find all tasks specified by user and do self.op on them"""
    domain = ''  # type: str
    noop = cli.Flag(
        ['--dry-run', '--noop'],
        help=_("If passed, won't actually change anything on habitipy server"),  # noqa: Q000
        default=False)
    more_tasks = []  # type: List[Dict[str, Any]]
    ids_can_overlap = False
    NO_TASK_ID = _("No task_ids found!")  # noqa: Q000
    TASK_ID_INVALID = _("Task id {} is invalid")  # noqa: Q000
    PARSED_TASK_IDS = _("Parsed task ids {}")  # noqa: Q000
    def main(self, *task_ids: TaskId):  # type: ignore
        super().main()
        task_id = []  # type: List[Union[str,int]]
        for tids in task_ids:
            task_id.extend(tids)
        if not task_id:
            self.log.error(self.NO_TASK_ID)
            return 1
        tasks = self.api.tasks.user.get(type=self.domain)
        assert isinstance(tasks, list)
        tasks.extend(self.more_tasks)
        task_uuids = [task['id'] for task in tasks]
        num_tasks = len(tasks)
        aliases = {task['alias']: task for task in tasks if 'alias' in task}
        self.changing_tasks = {}  # type: Dict[Union[str], Dict[str, Any]]
        changing_tasks_ids = []  # type: List[str]
        for tid in task_id:
            if isinstance(tid, int):
                if 0 <= tid <= num_tasks:
                    changing_tasks_ids.append(task_uuids[tid])
                    self.changing_tasks[task_uuids[tid]] = tasks[tid]
                    continue
            elif isinstance(tid, str):
                if tid in task_uuids:
                    changing_tasks_ids.append(tid)
                    self.changing_tasks[tid] = tasks[task_uuids.index(tid)]
                    continue
                elif tid in aliases:
                    t_id = aliases[tid]['id']
                    changing_tasks_ids.append(t_id)
                    self.changing_tasks[t_id] = aliases[tid]
                    continue
            self.log.error(self.TASK_ID_INVALID.format(tid))
            return 1
        idstr = ' '.join(self.changing_tasks.keys())
        self.log.info(self.PARSED_TASK_IDS.format(idstr))  # noqa: Q000
        self.tasks = self.api.tasks
        if not self.ids_can_overlap:
            changing_tasks_ids = list(set(changing_tasks_ids))
        for tid in changing_tasks_ids:
            if not self.noop:
                self.op(tid)
            res = self.log_op(tid)
            print(prettify(res))
        self.domain_print()

    def validate(self, task):  # pylint: disable=no-self-use,unused-argument
        """check if task is valid for the operation"""
        return True

    def op(self, tid):
        """operation to be done on task with `tid`"""
        raise NotImplementedError

    def log_op(self, tid):
        """return a message to show user on successful change of `tid`"""
        raise NotImplementedError

    def domain_print(self):
        """show domain to user again"""
        raise NotImplementedError


class HabitsChange(TasksChange):  # pylint: disable=missing-docstring,abstract-method
    domain = 'habits'
    ids_can_overlap = True
    def domain_print(self):
        Habits.invoke(config_filename=self.config_filename)


@Habits.subcommand('add')  # pylint: disable=missing-docstring
class HabitsAdd(ApplicationWithApi):
    DESCRIPTION = _("Add a habit <habit>")  # noqa: Q000
    priority = cli.SwitchAttr(
        ['-p', '--priority'],
        cli.Set('0.1', '1', '1.5', '2'), default='1',
        help=_("Priority (complexity) of a habit"))  # noqa: Q000
    direction = cli.SwitchAttr(
        ['-d', '--direction'],
        cli.Set('positive', 'negative', 'both'), default='both',
        help=_("positive/negative/both"))  # noqa: Q000

    def main(self, *habit: str):
        habit_str = ' '.join(habit)
        if not habit_str:
            self.log.error(_("Empty habit text!"))  # noqa: Q000
            return 1
        super().main()
        self.api.tasks.user.post(
            type='habit', text=habit_str,
            priority=self.priority, up=(self.direction != 'negative'),
            down=(self.direction != 'positive'))

        res = _("Added habit '{}' with priority {} and direction {}").format(  # noqa: Q000
            habit_str, self.priority, self.direction)
        print(prettify(res))
        Habits.invoke(config_filename=self.config_filename)
        return None


@Habits.subcommand('delete')  # pylint: disable=missing-docstring
class HabitsDelete(HabitsChange):
    DESCRIPTION = _("Delete a habit with task_id")  # noqa: Q000
    def op(self, tid):
        self.tasks[tid].delete()

    def log_op(self, tid):
        return _("Deleted habit {text}").format(**self.changing_tasks[tid])  # noqa: Q000


@Habits.subcommand('up')  # pylint: disable=missing-docstring
class HabitsUp(HabitsChange):
    DESCRIPTION = _("Up (+) a habit with task_id")  # noqa: Q000
    def op(self, tid):
        self.tasks[tid].score['up'].post()

    def validate(self, task):
        return task['up']

    def log_op(self, tid):
        return _("Incremented habit {text}").format(**self.changing_tasks[tid])  # noqa: Q000


@Habits.subcommand('down')  # pylint: disable=missing-docstring
class HabitsDown(HabitsChange):
    DESCRIPTION = _("Down (-) a habit with task_id")  # noqa: Q000
    def op(self, tid):
        self.tasks[tid].score['down'].post()

    def validate(self, task):
        return task['down']

    def log_op(self, tid):
        """show a message to user on successful change of `tid`"""
        return _("Decremented habit {text}").format(**self.changing_tasks[tid])  # noqa: Q000


class DailysChange(TasksChange):  # pylint: disable=missing-docstring,abstract-method
    domain = 'dailys'
    def domain_print(self):
        Dailys.invoke(config_filename=self.config_filename)


@Dailys.subcommand('done')  # pylint: disable=missing-docstring
class DailysUp(DailysChange):
    DESCRIPTION = _("Check a dayly with task_id")  # noqa: Q000
    def op(self, tid):
        self.tasks[tid].score['up'].post()

    def log_op(self, tid):
        return _("Completed daily {text}").format(**self.changing_tasks[tid])  # noqa: Q000


@Dailys.subcommand('undo')  # pylint: disable=missing-docstring
class DailyDown(DailysChange):
    DESCRIPTION = _("Uncheck a daily with task_id")  # noqa: Q000
    def op(self, tid):
        self.tasks[tid].score['down'].post()

    def log_op(self, tid):
        return _("Unchecked daily {text}").format(**self.changing_tasks[tid])  # noqa: Q000


class TodosChange(TasksChange):  # pylint: disable=missing-docstring,abstract-method
    domain = 'todos'
    def domain_print(self):
        ToDos.invoke(config_filename=self.config_filename)


@ToDos.subcommand('done')  # pylint: disable=missing-docstring
class TodosUp(TodosChange):
    DESCRIPTION = _("Check a todo with task_id")  # noqa: Q000
    def op(self, tid):
        self.tasks[tid].score['up'].post()

    def log_op(self, tid):
        return _("Completed todo {text}").format(**self.changing_tasks[tid])  # noqa: Q000


@ToDos.subcommand('delete')  # pylint: disable=missing-docstring
class TodosDelete(TodosChange):
    DESCRIPTION = _("Delete a todo with task_id")  # noqa: Q000
    def op(self, tid):
        self.tasks[tid].delete()

    def log_op(self, tid):
        return _("Deleted todo {text}").format(**self.changing_tasks[tid])  # noqa: Q000


@ToDos.subcommand('add')  # pylint: disable=missing-docstring
class TodosAdd(ApplicationWithApi):
    DESCRIPTION = _("Add a todo <todo>")  # noqa: Q000
    priority = cli.SwitchAttr(
        ['-p', '--priority'],
        cli.Set('0.1', '1', '1.5', '2'), default='1',
        help=_("Priority (complexity) of a todo"))  # noqa: Q000

    def main(self, *todo: str):
        todo_str = ' '.join(todo)
        if not todo_str:
            self.log.error(_("Empty todo text!"))  # noqa: Q000
            return 1
        super().main()
        self.api.tasks.user.post(type='todo', text=todo_str, priority=self.priority)
        res = _("Added todo '{}' with priority {}").format(todo_str, self.priority)  # noqa: Q000
        print(prettify(res))
        ToDos.invoke(config_filename=self.config_filename)
        return 0


RewardId = TaskId


@Rewards.subcommand('buy')  # pylint: disable=missing-docstring
class RewardsBuy(TasksChange):
    DESCRIPTION = _("Buy a reward with reward_id")  # noqa: Q000
    domain = 'rewards'
    ids_can_overlap = True
    NO_TASK_ID = _("No reward_ids found!")  # noqa: Q000
    TASK_ID_INVALID = _("Reward id {} is invalid")  # noqa: Q000
    PARSED_TASK_IDS = _("Parsed reward ids {}")  # noqa: Q000
    def main(self, *reward_id: RewardId):
        ApplicationWithApi.main(self)
        self.more_tasks = get_additional_rewards(self.api)
        super().main(*reward_id)

    def op(self, tid):
        t = self.changing_tasks[tid]
        if t['type'] != 'rewards':
            self.api.user.buy[t['key']].post()
        else:
            self.tasks[tid].score['up'].post()

    def log_op(self, tid):
        return _("Bought reward {text}").format(**self.changing_tasks[tid])  # noqa: Q000

    def domain_print(self):
        Rewards.invoke(config_filename=self.config_filename)


@Rewards.subcommand('add')  # pylint: disable=missing-docstring
class RewardsAdd(ApplicationWithApi):
    DESCRIPTION = _("Add a reward <reward>")  # noqa: Q000
    cost = cli.SwitchAttr(
        ['--cost'], default='10',
        help=_("Cost of a reward (gp)"))  # noqa: Q000

    def main(self, *reward: str):
        todo_str = ' '.join(reward)
        if not todo_str:
            self.log.error(_("Empty reward text!"))  # noqa: Q000
            return 1
        super().main()
        self.api.tasks.user.post(type='reward', text=todo_str, value=self.cost)
        res = _("Added reward '{}' with cost {}").format(todo_str, self.cost)  # noqa: Q000
        print(prettify(res))
        Rewards.invoke(config_filename=self.config_filename)
        return 0


@HabiticaCli.subcommand('home')  # pylint: disable=missing-docstring
class Home(ConfiguredApplication):
    DESCRIPTION = _("Open habitica site in browser")  # noqa: Q000
    def main(self):
        super().main()
        from webbrowser import open_new_tab
        HABITICA_TASKS_PAGE = '/#/tasks'
        home_url = '{}{}'.format(self.config['url'], HABITICA_TASKS_PAGE)
        print(_("Opening {}").format(home_url))  # noqa: Q000
        open_new_tab(home_url)


@HabiticaCli.subcommand('server')  # pylint: disable=missing-docstring
class Server(ApplicationWithApi):
    DESCRIPTION = _("Check habitica server availability")  # noqa: Q000
    def main(self):
        super().main()
        try:
            ret = self.api.status.get()
            if isinstance(ret, dict) and ret['status'] == 'up':
                print(_("Habitica server {} online").format(self.config['url']))  # noqa: Q000
                return 0
        except (KeyError, requests.exceptions.ConnectionError):
            pass
        msg = _("Habitica server {} offline or there is some issue with it")  # noqa: Q000
        print(msg.format(self.config['url']))
        return -1


@HabiticaCli.subcommand('spells')  # pylint: disable=missing-docstring
class Spells(ApplicationWithApi):
    DESCRIPTION = _("Prints all available spells")  # noqa: Q000
    def main(self):
        if self.nested_command:
            return
        super().main()
        user = self.api.user.get()
        content = Content(self.api)
        user_level = user['stats']['lvl']
        if user_level < 10:
            print(_("Your level is too low. Come back on level 10 or higher"))  # noqa: Q000
        user_class = user['stats']['class']
        user_spells = [
            v for k, v in content['spells'][user_class].items()
            if user_level > v['lvl']
        ]
        print(_("You are a {} of level {}").format(_(user_class), user_level))  # noqa: Q000
        for spell in sorted(user_spells, key=lambda x: x['lvl']):
            msg = _("[{key}] {text} ({mana}:droplet:) - {notes}").format(**spell)  # noqa: Q000
            print(msg)


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
    except (AttributeError, JSONDecodeError) as error:
        warnings.warn('subcommands.json found, but it is invalid: {}'.format(error))
        del error
del subcommands_file

if __name__ == '__main__':
    HabiticaCli.run()
