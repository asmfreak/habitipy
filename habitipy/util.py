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
from typing import Tuple
import logging
import pkg_resources


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
        logging.getLogger(__name__).warning('Translation for your language not found. ')
    return gettext.translation(package_name, localedir=localedir, fallback=True)


def get_translation_functions(package_name: str, names: Tuple[str, ...]=('gettext',)):
    'finds and installs translation functions for package'
    translation = get_translation_for(package_name)
    return [getattr(translation, x) for x in names]
