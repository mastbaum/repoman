import os
from setuptools import setup

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup(
    name = "repoman",
    version = "0.5",
    author = "Andy Mastbaum",
    author_email = "amastbaum@gmail.com",
    description = ("post-commit actions for github repos"),
    license = "BSD",
    keywords = "wsgi git github",
    url = "http://github.com/mastbaum/repoman",
    long_description=read('README.md'),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Server",
        "License :: OSI Approved :: BSD License",
    ],

    packages=['repoman', 'repoman/handlers'],
    scripts=['bin/repoman.wsgi'],
)

