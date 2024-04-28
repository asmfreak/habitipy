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
from math import ceil
from typing import Tuple
# import logging
import pkg_resources
from plumbum import colors
try:
    from emoji import emojize
except ImportError:
    emojize = None  # type: ignore


def progressed_bar(
        count,
        total=100, status=None, suffix=None,
        width=None, bar_len=10):
    """render a progressed.io like progress bar"""
    status = status or ''
    suffix = suffix or '%'
    assert isinstance(count, int)
    max_width = 60 if status == '' else 90
    width = max_width if width is None else width
    bar_len = ceil(bar_len * width / max_width)
    count_normalized = count if count <= total else total
    filled_len = int(round(bar_len * count_normalized / float(total)))
    percents = 100.0 * count / float(total)
    color = '#5cb85c'
    if percents < 30.0:
        color = '#d9534f'
    if percents < 70.0:
        color = '#f0ad4e'
    text_color = colors.fg(color)
    bar_color = text_color + colors.bg(color)
    nc_color = colors.dark_gray
    progressbar = (colors.bg('#428bca') | status) if status else ''
    progressbar += (bar_color | ('█' * filled_len))
    progressbar += (nc_color | ('█' * (bar_len - filled_len)))
    progressbar += (text_color | (str(count) + suffix))
    return progressbar


_progressed_regex_str = r"""
!
\[[^]]*\]
\(\s*(http://progressed\.io/bar|https://progress-bar.dev)/(?P<progress>[0-9]{1,3})/?
(
\?((
(title=(?P<title>[^&) "]*))
|(scale=(?P<scale>[^&) "]*))
|(suffix=(?P<suffix>[^&) "]*))
|(width=(?P<width>[^&) "]*))
)&*)*
){0,1}
\s*("[^"]*")*\)
"""
_progressed_regex = re.compile(_progressed_regex_str, re.VERBOSE)


def _progressed_match(m, bar_len=10):
    progress = m['progress']
    scale = m['scale']
    width = m['width']
    progress = int(progress) if progress is not None else 0
    scale = int(scale) if scale is not None else 100
    width = int(width)  if width is not None else 100
    return progressed_bar(
        progress, total=scale,
        status=m['title'], suffix=m['suffix'],
        width=width,
        bar_len=bar_len)


def progressed(string):
    """
    helper function to replace all links to progressed.io with progress bars

    # Example
    ```python
    from habitipy.util import progressed
    text_from_habitica = 'Write thesis ![progress](http://progressed.io/bar/0 "progress")'
    print(progressed(text_from_habitica))
    ```
    ```
    Write thesis ██████████0%
    ```
    """
    return _progressed_regex.sub(_progressed_match, string)


def prettify(string):
    """
    replace markup emoji and progressbars with actual things

    # Example
    ```python
    from habitipy.util import prettify
    print(prettify('Write thesis :book: ![progress](http://progressed.io/bar/0 "progress")'))
    ```
    ```
    Write thesis 📖 ██████████0%
    ```
    """
    try:
        string = emojize(string, language="alias") if emojize else string
        string = progressed(string)
    except Exception as error:
        warnings.warn('Failed to prettify string: {}'.format(error))
        pass
    return string


@contextmanager
def umask(mask):
    """
    temporarily change umask

    # Arguments
    mask : a umask (invese of chmod argument)

    # Example
    ```python
    with umask(0o077), open('yay.txt') as f:
        f.write('nyaroo~n')

    ```

    `yay.txt` will be written with 600 file mode
    """
    prev = os.umask(mask)
    try:
        yield
    finally:
        os.umask(prev)


secure_filestore = partial(umask, 0o077)


def is_secure_file(fn):
    """checks if a file can be accessed only by the owner"""
    st = os.stat(fn)
    return (st.st_mode & 0o777) == 0o600


class SecurityError(ValueError):
    """Error fired when a secure file is stored in an insecure manner"""


def assert_secure_file(file):
    """checks if a file is stored securely"""
    if not is_secure_file(file):
        msg = """
        File {0} can be read by other users.
        This is not secure. Please run 'chmod 600 "{0}"'"""
        raise SecurityError(dedent(msg).replace('\n', ' ').format(file))
    return True


def get_translation_for(package_name: str) -> gettext.NullTranslations:
    """find and return gettext translation for package"""
    localedir = None
    for localedir in pkg_resources.resource_filename(package_name, 'i18n'), None:
        localefile = gettext.find(package_name, localedir)  # type: ignore
        if localefile:
            break
    else:
        pass
    return gettext.translation(package_name, localedir=localedir, fallback=True)  # type: ignore


def get_translation_functions(package_name: str, names: Tuple[str, ...] = ('gettext',)):
    """finds and installs translation functions for package"""
    translation = get_translation_for(package_name)
    return [getattr(translation, x) for x in names]
