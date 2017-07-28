from setuptools import setup, find_packages

with open('README.md') as f:
    readme = f.read()

setup(
    name='habitipy',
    version='0.1.1',
    author='Phil Adams',
    author_email='philadams.net@gmail.com',
    url='https://github.com/philadams/habitica',
    license='LICENSE.txt',
    description='Commandline interface to Habitica (http://habitica.com)',
    long_description=readme,
    packages=['habitipy'],
    # console_scripts=[],
    install_requires=[
        'plumbum',
        'requests',
    ],
    entry_points={ 
        'console_scripts': [
            'habitipy = habitipy.cli:HabiticaCli',
        ],
    },
)
