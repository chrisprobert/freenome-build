try:
    from pip.download import PipSession
    from pip.req import parse_requirements
except ImportError:
    from pip._internal.download import PipSession
    from pip._internal.req import parse_requirements

import os
import re
from setuptools import setup, find_packages

version_filepath = os.path.abspath('./VERSION')

with open(version_filepath, 'r') as fp:
    # returns string following "__version__ = "
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                        fp.read(), re.MULTILINE).group(1)

if not version:
    raise RuntimeError('Cannot find version information')

install_reqs = parse_requirements("update_requirements.txt", session=PipSession())
reqs = [str(ir.req) for ir in install_reqs if ir.req]

setup(name='freenome-build',
      version=version,
      description='Freenome build',
      install_requires=install_reqs,
      include_package_data=True,
      packages=find_packages(),
      entry_points={
          'console_scripts': [
              'freenome_build = freenome_build.freenome_build:main'
          ]
      })
