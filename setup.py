#!/usr/bin/env python
from setuptools import setup, find_packages

requirements = [
    line.strip()
    for line in open("requirements.txt", "r", encoding="utf-8").readlines()
    if line.strip() and not line.lstrip().startswith("#")
]

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name = "sippy",
    version = "2.3.0",
    packages = find_packages(),

    install_requires = requirements,
    include_package_data=True,

    entry_points = {
        'console_scripts': [
            'b2bua_simple = sippy.b2bua_simple:main_func',
            'b2bua_radius = sippy.b2bua:main_func',
            'b2bua = sippy.b2bua:main_func',
            ],
        },

    long_description = long_description,
    long_description_content_type = "text/markdown",

    # meta-data for upload to PyPi
    author = "Sippy Software, Inc.",
    author_email = "sobomax@sippysoft.com",
    description = "RFC3261 SIP Stack and Back-to-Back User Agent (B2BUA)",
    license = "BSD",
    keywords = "sip,b2bua,voip,rfc3261,sippy",
    url = "http://www.b2bua.org/",
    classifiers = [
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX',
        'Programming Language :: Python'
    ],
)
