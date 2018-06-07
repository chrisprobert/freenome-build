import os
import setuptools

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

    setuptools.setup(
        name='freenome-build',
        version=version,
        description='Freenome build',
        url='https://github.com/freenome/freenome-build',
        author='Nathan Boley',
        author_email="nathan.boley@freenome.com",

        install_requires=reqs + ["pytest"],
        package_data={
            '': ['./VERSION'],
            'freenome_build': [
                './database_template/*',
                './database_template/*/*',
            ]
        },
        packages=setuptools.find_packages(),
        scripts=['bin/freenome-build']
    )


if __name__ == '__main__':
    main()
