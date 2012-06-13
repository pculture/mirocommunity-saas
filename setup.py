#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name='MiroCommunity-SAAS',
      version='1.9',
      description="Public Miro Community files specific to the service PCF "
      			  "provides.",
      author='Participatory Culture Foundation',
      author_email='dev@mirocommunity.org',
      url='http://www.mirocommunity.org/',
      packages=find_packages(),
      include_package_data=True,
      classifiers=[
          'Environment :: Web Environment',
          'Framework :: Django',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Multimedia :: Sound/Audio',
          'Topic :: Multimedia :: Video',
      ],
      platforms=['OS Independent'],)
