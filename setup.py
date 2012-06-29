#!/usr/bin/env python
from distutils.core import setup

setup(
    name = "fccv",
    url = "http://bitbucket.org/fairview/fccv/",
    author = "Fairview Computing LLC",
    author_email = "john@fairviewcomputing.com",
    license = "MIT License",
    description = "Chainable, customizable validation for Django comments.",
    packages = ['fccv'],
    package_data={'fccv': ['fixtures/*.json']},
    version = "1.0.1"
)
