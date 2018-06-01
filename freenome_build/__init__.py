import os
import sys
import logging

logging.basicConfig(
    stream=sys.stderr, format='%(levelname)s\t%(asctime)-15s\t%(message)s', level=logging.DEBUG
)


def _get_version():
    """Load version from VERSION file.

    VERSION is stored in the base of the repo, but is copied into the module
    directory when building the distribution. Therefore we need to look for the
    VERSION file in two locations: one directory up and in the current directory.
    """

    def _get_version_from_file_or_none(version_fname):
        try:
            with open(version_fname) as fp:
                return fp.read().strip()
        except FileNotFoundError:
            return None

    develop_version = _get_version_from_file_or_none(
        os.path.join(os.path.dirname(__file__), "../VERSION"))
    packaged_version = _get_version_from_file_or_none(
        os.path.join(os.path.dirname(__file__), "./VERSION"))
    if develop_version is not None:
        assert packaged_version is None or packaged_version == develop_version, \
            "VERSION files must match if they both exist"
        return develop_version
    elif packaged_version is not None:
        assert develop_version is None or packaged_version == develop_version, \
            "VERSION files must match if they both exist"
        return packaged_version
    else:
        raise RuntimeError("Can not find VERSION file.")


__version__ = _get_version()
