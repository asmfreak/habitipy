"""
    habitipy - tools and library for Habitica restful API
"""
import logging
from .api import Habitipy
from .cli import load_conf, DEFAULT_CONF
logging.getLogger(__name__).addHandler(logging.NullHandler())
