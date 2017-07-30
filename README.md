Habitipy
========
A set of scripts to interact with [Habitica](http://habitica.com):

1. Python wrapper for the RESTful Habitica API (`habitica.api.Habitipy` class)
2. Command-line interface with subcommands (e.g. `> habitipy todos`)

Install
-------

`pip install habitipy`.

I push to pip fairly frequently, but if you'd like to be on the bleeding edge,
clone this project and install it by hand:

    > git clone https://github.com/philadams/habitica
    > pip install -e habitica

Configure
---------

You'll need to let the tool know how to connect to your Habitica account. To do
this, you'll need to add the following credentials section in the file
`~/.config/habitipy/config` (you may need to create the folder(s) and file):

    [habitipy]
    url = https://habitica.com
    login = USER_ID
    password = API_KEY

There's a template for this file at `auth.cfg.sample`.

Replace USER\_ID and API\_KEY with the corresponding tokens from [your Habitica
settings>API page](https://habitica.com/#/options/settings/api).

You can replace `url` as needed, for example if you're self-hosting a Habitica server.

Lastly, remember to `chmod 600 ~/.config/habitica/auth.cfg` to keep your
credentials secret. This is enforced by `habitipy` cli command.

Usage
-----

What's my character's status?

    > habitica status
    --------------
    Level 83 Rogue
    --------------
    Health: 50/50
    XP: 904/2690
    Mana: 133/218
    Pet: Gryphon-Base (11 food items)
    Mount: FlyingPig-Base

Show me my todo items:

    > habitica todos
    [ ]  1 update habitica README with example instructions
    [ ]  2 vacuum the car
    [ ]  3 read Bell and Jofish "Designing technology for domestic spaces"
    [ ]  4 order new contact lenses
    [ ]  5 complete Keppi project report and share with Geri
    [ ]  6 set up dinner with friends at Agava for Saturday night

Complete a todo:

    > habitica todos done 1
    marked todo 'update habitica README with example instructions' complete
    [ ] 1 vacuum the car
    [ ] 2 read Bell and Jofish "Designing technology for domestic spaces"
    [ ] 3 order new contact lenses
    [ ] 4 complete Keppi project report and share with Geri
    [ ] 5 make reservation at Agava for Saturday night

Complete multiple todos. All `done`, `undo`, `up`, `down` commands can take one
or more tasks as arguments, using either comma-separated lists or ranges or
both:

    > habitica todos done 1,3-5
    marked todo 'update habitica README with example instructions' complete
    marked todo 'vacuum the car' complete
    marked todo 'order new contact lenses' complete
    marked todo 'complete Keppi project report and share with Geri' complete
    marked todo 'make reservation at Agava for Saturday night' complete
    [ ] 1 read Bell and Jofish "Designing technology for domestic spaces"

Add a new (hard!) todo. By default `--difficulty=easy`:

    > habitica todos add finish dissertation --difficulty=hard
    added new todo 'finish dissertation'
    [ ] 1 finish dissertation
    [ ] 2 read Bell and Jofish "Designing technology for domestic spaces"

Show me my habits, and how well I'm doing with each:

    > habitica habits
    [*******] 1 commit code
    [****] 2 drink water
    [******] 3 encourage others

Record improvement with some habits:

    > habitica habits up 2,3
    incremented task 'drink water'
    incremented task 'encourage others'
    [*******] 1 commit code
    [****] 2 drink water
    [******] 3 encourage others

Show me my dailies and each daily's state:

    > habitica dailies
    [ ] 1 pushups (5x20)
    [ ] 2 clean dishes before bed
    [x] 3 2x90mins writing

Complete a daily task:

    > habitica dailies done 1
    marked daily 'pushups (5x20)' completed
    [x] 1 pushups (5x20)
    [ ] 2 clean dishes before bed
    [x] 3 2x90mins writing

Is the Habitica server up?

    > habitica server
    Habitica server is up

Help
----

Via `habitica --help`:

    Habitica command-line interface.

    Usage: habitica [--version] [--help]
                    <command> [<args>...] [--difficulty=<d>]
                    [--verbose | --debug] [--checklists]

    Options:
      -h --help         Show this screen
      --version         Show version
      --difficulty=<d>  (easy | medium | hard) [default: easy]
      --verbose         Show some logging information
      --debug           Some all logging information
      -c --checklists   Toggle displaying checklists on or off

    The habitica commands are:
      status                  Show HP, XP, GP, and more
      habits                  List habit tasks
      habits up <task-id>     Up (+) habit <task-id>
      habits down <task-id>   Down (-) habit <task-id>
      dailies                 List daily tasks
      dailies done            Mark daily <task-id> complete
      dailies undo            Mark daily <task-id> incomplete
      todos                   List todo tasks
      todos done <task-id>    Mark one or more todo <task-id> completed
      todos add <task>        Add todo with description <task>
      todos delete <task-id>  Delete one or more todo <task-id>
      server                  Show status of Habitica service
      home                    Open tasks page in default browser

    For `habits up|down`, `dailies done|undo`, `todos done`, and `todos
    delete`, you can pass one or more <task-id> parameters, using either
    comma-separated lists or ranges or both. For example, `todos done
    1,3,6-9,11`.

    To show checklists with "todos" and "dailies" permanently, set
    'checklists' in your auth.cfg file to `checklists = true`.

API
---

Habitica restfull API is accessible through `habitipy.api.Habitipy` class. API as long as other useful functions are exposed from top-level of `habitipy` package to ease the usage, so you can `from habitipy import Habitipy`.
It is using parsed [apiDoc from Habitica](https://habitica.com/apidoc) by downloading and parsing latest source from [Habitica's Github repository](https://github.com/HabitRPG/habitica). This enables you with API endpoint completion and documentation from `ipython` console. Here is an example:

```python
In [1]: from habitipy import Habitipy, load_conf,DEFAULT_CONF
In [2]: api = Habitipy(load_conf(DEFAULT_CONF))
In [3]: api.
     api.approvals     api.debug         api.models        api.tags          
     api.challenges    api.group         api.notifications api.tasks         
     api.content       api.groups        api.reorder-tags  api.user          
     api.coupons       api.hall          api.shops                           
     api.cron          api.members       api.status                          
 In [84]: api.user.get?
 Signature:   api.user.get(**kwargs)
 Type:        Habitipy
 String form: <habitipy.api.Habitipy object at 0x7fa6fd7966d8>
 File:        ~/projects/python/habitica/habitipy/api.py
 Docstring:  
 {get} /api/v3/user Get the authenticated user's profile

 responce params:
 "data" of type "object"
```

From other Python consoles you can just run:

```python
>>> dir(api)
['__call__', '__class__', '__delattr__', '__dict__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__', '__getattr__', '__getattribute__', '__getitem__', '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__', '__lt__', '__module__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__', '__weakref__', '_apis', '_conf', '_current', '_is_request', '_make_apis_dict', '_make_headers', '_node', 'approvals', 'challenges', 'content', 'coupons', 'cron', 'debug', 'group', 'groups', 'hall', 'members', 'models', 'notifications', 'reorder-tags', 'shops', 'status', 'tags', 'tasks', 'user']
>>> print(api.user.get.__doc__)
{get} /api/v3/user Get the authenticated user's profile

responce params:
"data" of type "object"

```

If you are planning to create some cli tool on top of `habitipy`, you can use preconfigured class with enabled logging `habitipy.cli.ApplicationWithApi`. This class is using [`plumbum`'s Application class](http://plumbum.readthedocs.io/en/latest/cli.html#command-line-interface-cli). Here is an example of such subclass:

```python
from habitipy import ApplicationWithApi

class MyCliTool(ApplicationWithApi):
    """Tool to print json data about user"""
    def main(self):
        super().main()
        print(self.api.user.get())

```
The `super().main()` line is critical - all initialization takes place here.


I18N
----
`habitipy` command is meant to be internationalized. It is done using Python's standard library's `gettext` module.

Shell completion
----------------

Thanks to [mohsend](https://github.com/mohsend), habitica now has shell completion! Basically, you'll want to add the following to your `~/.profile`:

    if [ -f PATH_TO_SITE_PACKAGES/habitica/shell_completion.sh ]; then
        . PATH_TO_SITE_PACKAGES/habitica/shell_completion.sh
    fi

You can find your site-packages path with `python -c 'import habitica; print
habitica.__path__[0]'`.

Thanks
------

Many thanks to the following excellent projects:

- [plumbum]()
- [requests](https://github.com/kennethreitz/requests)

And to the original author of [habitica]().
