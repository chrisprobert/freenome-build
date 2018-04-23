import os
import re
from setuptools import setup, find_packages

version_filepath = os.path.abspath('./VERSION')

with open(version_filepath, 'r') as fp:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                        fp.read(), re.MULTILINE).group(1)

if not version:
    raise RuntimeError('Cannot find version information')

setup(name='freenome-build',
      version=version,
      author='Nathan Boley',
      author_email='nathan.boley@freenome.com',
      description='',
      py_modules=['freenome_build'],
      install_requires=['conda>=4.3.16', 'conda-build>=2.1.5'],
      packages=find_packages())
