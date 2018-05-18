try:
    from pip.download import PipSession
    from pip.req import parse_requirements
except ImportError:
    from pip._internal.download import PipSession
    from pip._internal.req import parse_requirements

import os
from setuptools import setup, find_packages

VERSION_FILEPATH = os.path.abspath(os.path.join(os.path.dirname(__file__), './VERSION'))

def get_version():
    if not os.path.exists(VERSION_FILEPATH):
        raise RuntimeError(f"Can not find version file at '{VERSION_FILEPATH}'")

    with open(VERSION_FILEPATH, 'r') as fp:
        return fp.read().strip()

def main():
    version = get_version()
    install_reqs = parse_requirements("update_requirements.txt", session=PipSession())
    reqs = [str(ir.req) for ir in install_reqs if ir.req]

    setup(name='freenome-build',
          version=version,
          description='Freenome build',
          install_requires=reqs,
          include_package_data=True,
          packages=find_packages(),
          entry_points={
              'console_scripts': [
                  'freenome-build = freenome_build.freenome_build:main'
              ]
          })

if __name__ == '__main__':
    main()
