import os
import sys
from setuptools import setup


def get_version():
    if not os.path.exists(VERSION_FILEPATH):
        raise RuntimeError(f"Can not find version file at '{VERSION_FILEPATH}'")

    with open(VERSION_FILEPATH, 'r') as fp:
        return fp.read().strip()

def main():
    setup(name='freenome_build',
          version=get_version(),
          install_requires=meta_data.requirements['build'],
          run_requires=meta_data.requirements['run'],
          package_data={'freenome-build': 'database_template/**'},
          packages=['freenome_build', ],
          scripts=['bin/freenome-build'])


if __name__ == '__main__':
    main()
