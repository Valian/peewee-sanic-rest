from io import open

from setuptools import find_packages, setup

with open('peewee_sanic_rest/__init__.py', 'r') as f:
    for line in f:
        if line.startswith('__version__'):
            version = line.strip().split('=')[1].strip(' \'"')
            break
    else:
        version = '0.0.1'

with open('README.rst', 'r', encoding='utf-8') as f:
    readme = f.read()

REQUIRES = [
    "peewee_async",
    "marshmallow_peewee",
    "sanic"
]

setup(
    name='peewee-sanic-rest',
    version=version,
    description='',
    long_description=readme,
    author='Valian',
    author_email='jakub.skalecki@gmail.com',
    maintainer='Valian',
    maintainer_email='jakub.skalecki@gmail.com',
    url='https://github.com/_/peewee-sanic-rest',
    license='MIT',

    keywords=[
        'peewee',
        'sanic',
        'rest',
        'crud',
    ],

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: Implementation :: CPython',
    ],

    install_requires=REQUIRES,
    tests_require=['coverage', 'pytest'],

    packages=find_packages(),
)
