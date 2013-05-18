#!/usr/bin/env python

from distutils.core import setup

setup(name='xbrav',
      version='1.0',
      description='Python library for building embedded devices with the Raspberry Pi',
      author='XBrav',
      author_email='bryan.baker.xbrav@gmail.com',
      url='https://github.com/XBrav/py-ssd1325',
      license = 'LICENSE.txt',
      long_description=open('README.txt').read(),
      packages=['ssd1325'],
)
