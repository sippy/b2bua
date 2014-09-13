#!/usr/bin/env python2
from setuptools import setup, find_packages

setup(
    name = "sippy",
    version = "1.1-dev",
    packages = find_packages(),

    install_requires = [
        'twisted>=14.0'
        ],

    package_data = {
        '': ['dictionary', '*.md']
        },
    test_suite = 'tests',

    entry_points = {
        'console_scripts': [
            'b2bua_simple = sippy.b2bua_simple:main_func',
            'b2bua_radius = sippy.b2bua_radius:main_func',
            ],
        },

    # meta-data for upload to PyPi
    author = "Sippy Software, Inc.",
    author_email = "sales@sippysoft.com",
    description = "SIP RFC3261 Back-to-back User Agent (B2BUA)",
    license = "BSD",
    keywords = "sip b2bua voip rfc3261 sippy",
    url = "http://www.b2bua.org/",
)
