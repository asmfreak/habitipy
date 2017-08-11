"""
    habitipy - tools and library for Habitica restful API
    utility functions
"""
# pylint: disable=invalid-name,bad-whitespace
import os
import gettext
from contextlib import contextmanager
from functools import partial
from textwrap import dedent
import re
from typing import Tuple
# import logging
import pkg_resources
from plumbum import colors
try:
    from emoji import emojize
except ImportError:
    emojize = None
_progressed_regex_str = r'!\[[^]]*\]\(http://progressed\.io/bar/([0-9]{1,3})( *"[^"]*")\)'
_progressed_regex = re.compile(_progressed_regex_str)


def _progressed_bar(count, total=100, status='', bar_len=10):
    'render a progressed.io like progress bar'
    count = count if count <= total else total
    filled_len = int(round(bar_len * count / float(total)))
    percents = 100.0 * count / float(total)
    color = '#5cb85c'
    if percents < 30.0:
        color = '#d9534f'
    if percents < 70.0:
        color = '#f0ad4e'
    color = colors.fg(color)  # pylint: disable=no-member
    nc_color = colors.dark_gray  # pylint: disable=no-member
    percents = int(percents)
    progressbar = (color | ('█' * filled_len)) + (nc_color | ('█' * (bar_len - filled_len)))
    return progressbar + (color | (str(percents) + '% ' + status))


def progressed(string):
    'replace all links to progressed.io with progress bars'
    return _progressed_regex.sub(
        lambda m: _progressed_bar(int(m.group(1))),
        string)


def prettify(string):
    'replace markup emoji and progressbars with actual things'
    string = emojize(string, use_aliases=True) if emojize else string
    string = progressed(string)
    return string


@contextmanager
def umask(mask):
    'temporarily change umask'
    prev = os.umask(mask)
    try:
        yield
    finally:
        os.umask(prev)


secure_filestore = partial(umask, 0o077)


def is_secure_file(fn):
    'checks if a file can be accessed only by the owner'
    st = os.stat(fn)
    return (st.st_mode & 0o777) == 0o600


class SecurityError(ValueError):
    'Error fired when a secure file is stored in an insecure manner'
    pass


def assert_secure_file(file):
    'checks if a file is stored securely'
    if not is_secure_file(file):
        msg = """
        File {0} can be read by other users.
        This is not secure. Please run 'chmod 600 "{0}"'"""
        raise SecurityError(dedent(msg).replace('\n', ' ').format(file))
    return True


def get_translation_for(package_name: str) -> gettext.NullTranslations:
    'find and return gettext translation for package'
    localedir = None
    for localedir in pkg_resources.resource_filename(package_name, 'i18n'), None:
        localefile = gettext.find(package_name, localedir)
        if localefile:
            break
    else:
        pass
    return gettext.translation(package_name, localedir=localedir, fallback=True)


def get_translation_functions(package_name: str, names: Tuple[str, ...]=('gettext',)):
    'finds and installs translation functions for package'
    translation = get_translation_for(package_name)
    return [getattr(translation, x) for x in names]
