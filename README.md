Habitipy
========
[![PyPI](https://img.shields.io/pypi/v/habitipy.svg)](https://pypi.python.org/pypi/habitipy) [![PyPI](https://img.shields.io/pypi/pyversions/habitipy.svg)](https://pypi.python.org/pypi/habitipy) [![PyPI](https://img.shields.io/pypi/l/habitipy.svg)](https://pypi.python.org/pypi/habitipy) [![Say Thanks!](https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg)](https://saythanks.io/to/ASMfreaK)

A set of scripts to interact with [Habitica](http://habitica.com):

1. Python wrapper for the RESTful Habitica API (`habitica.api.Habitipy` class)
2. Command-line interface with subcommands (e.g. `> habitipy todos`)

| Version | CI | Coverage |
| ---- | ---- | ----- |
| Master |  [![Build Status](https://api.travis-ci.org/ASMfreaK/habitipy.svg?branch=master)](https://travis-ci.org/ASMfreaK/habitipy) | [![Codecov](https://img.shields.io/codecov/c/github/ASMfreaK/habitipy.svg)](https://codecov.io/gh/ASMfreaK/habitipy)  |
| Stable (v0.3.1) | [![Build Status](https://api.travis-ci.org/ASMfreaK/habitipy.svg?branch=v0.3.1)](https://travis-ci.org/ASMfreaK/habitipy)|  |

Features
--------

* Access to your Habitica account from command line
* Colorful output
* Easy and intuitive subcommands syntax
* Pluggable and extendable architecture
* API with built-in help


Install
-------

Habitipy comes in two main versions: basic an emoji. If don't want emoji on your terminal you are free to to with just only:
`$ pip install habitipy`

If you want something like `:thumbsup:` to be converted to actual emoji unicode symbols before it will be printed to terminal, you should use this command:
`$ pip install habitipy[emoji]`

In both cases you should put `sudo` in front of command, if you are installing `habitipy` package to system directory. To install `habitipy` just for you, use
`$ pip install --user habitipy`

And the last, but not the least thing about installation - if you want bleeding edge development version (potentially unstable!), you should clone the repository and install `habitipy`
```
    $ git clone https://github.com/ASMfreaK/habitipy
    $ pip install -e habitipy
```

Configuration
-------------

Most configuration of `habitipy` is done in `~/.config/habitipy/config`.
You can run any habitica command - this file will be created for you with default settings. You should replace default `login` and `password` with the corresponding user id and API key from [your Habitica's API settings](https://habitica.com/#/options/settings/api).

You can replace `url` as needed, for example if you're self-hosting a Habitica server.

Lastly, you should not change access rights of the config to anything other then `600` - this ensures that  your credentials are kept secret from other users of your system. This is enforced by `habitipy` cli command.

There is also configuration options:
* `show_numbers` - enables printing task numbers in commands like `habitipy dailies` or `habitipy todo`. Valid 'true' values are `True`, `y`, `1`, anything else is considered 'false' .
* `show_style` - controls the output of a task score and it's completeness. Valid values are: `wide`, `narrow` and `ascii`. Do try each for yourself.

It you have other tools using plumbum's `Application` class you want to integrate under `habitipy` cli command you can state them in `~/.config/habitipy/subcommands.json` like this:
```json
{"subcommand_name":"package.module.SubcommandClass"}
```
Using the above configuration, on startup `habitipy` will import `SubcommandClass` `package.module` and add a new subcommand with `subcommand_name` to `habitipy`.

API
---

Habitica restful API is accessible through `habitipy.api.Habitipy` class. API as long as other useful functions are exposed from top-level of `habitipy` package to ease the usage, so you can `from habitipy import Habitipy`.
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
`habitipy` command is meant to be internationalized. It is done using Python's standard library's `gettext` module. If you want `habitipy` to be translated to your language please read [contributing guidelines](./CONTRIBUTING.md).

Thanks
------

Many thanks to the following excellent projects:

- [plumbum](https://plumbum.readthedocs.io/en/latest/)
- [requests](https://github.com/kennethreitz/requests)

And to the original author of [habitica]https://github.com/philadams/habitica).
