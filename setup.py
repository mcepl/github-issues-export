# coding: utf-8
from setuptools import setup


setup(
    name='github-issues-export',
    version="0.2.0",
    license="GPLv3",
    description='exports github issues to file to be imported to bugzilla',
    author=u'Matěj Cepl',
    author_email='mcepl@cepl.eu',
    url='https://github.com/mcepl/github-issues-export',
    install_requires=['setuptools', 'urllib2_prior_auth'],
    classifiers=[
        "Programming Language :: Python :: 2.7",
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: GNU General Public License v3 " +
            "or later (GPLv3)",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Bug Tracking",
    ]
)
