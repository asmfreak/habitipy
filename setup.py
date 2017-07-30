""" habitipy - tools and library for Habitica restful API"""
from setuptools import setup

with open('README') as f:
    README = f.read()

setup(
    name='habitipy',
    version='0.1.2',
    author='Pavel Pletenev',
    author_email='cpp.create@gmail.com',
    url='',
    license='LICENSE.txt',
    description='Commandline interface to Habitica (http://habitica.com)',
    long_description=README,
    packages=['habitipy'],
    install_requires=[
        'plumbum',
        'requests',
    ],
    package_data={
        '': ['README'],
        'habitipy': [
            '*.pyi'
        ]
    },
    entry_points={
        'console_scripts': [
            'habitipy = habitipy.cli:HabiticaCli',
        ],
    },
    extras_require={
        'emoji':  ['emoji'],
    },
)
