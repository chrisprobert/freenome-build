import os
from setuptools import setup, find_packages
import distutils.command.bdist_conda

try:
    from pip.download import PipSession
    from pip.req import parse_requirements
except ImportError:
    from pip._internal.download import PipSession
    from pip._internal.req import parse_requirements


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
          distclass=distutils.command.bdist_conda.CondaDistribution,
          description='Freenome build',
          install_requires=reqs,
          include_package_data=True,
          package_data={'freenome_build': ['database_template/*', 'database_template/*/*']},
          packages=find_packages(),
          scripts=['bin/freenome-build'])


if __name__ == '__main__':
    main()
