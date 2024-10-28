""" habitipy - tools and library for Habitica restful API"""
import sys
from setuptools import setup

INSTALL_REQUIRES = [
    'plumbum',
    'requests',
    'setuptools',
]
if sys.version_info < (3, 5):
    INSTALL_REQUIRES.append('typing')

setup(
    name='habitipy',
    version='0.3.3',
    author='Pavel Pletenev',
    author_email='cpp.create@gmail.com',
    url='https://github.com/ASMfreaK/habitipy',
    license='MIT',
    description='tools and library for Habitica restful API (http://habitica.com)',
    packages=['habitipy'],
    install_requires=INSTALL_REQUIRES,
    package_data={
        'habitipy': [
            'apidoc.txt',
            '*.pyi',
            'i18n/*/LC_MESSAGES/*.mo'
        ]
    },
    entry_points={
        'console_scripts': [
            'habitipy = habitipy.cli:HabiticaCli',
        ],
    },
    extras_require={
        'emoji':  ['emoji'],
        'aio':  ['aiohttp']
    },
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Development Status :: 4 - Beta',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Utilities',
        'Topic :: Games/Entertainment',
        'Topic :: Internet',
        'Environment :: Console',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Intended Audience :: End Users/Desktop',
    ],
)
