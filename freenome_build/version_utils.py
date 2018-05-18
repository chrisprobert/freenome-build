import logging
import os
import re

from freenome_build import github


def version(path, repo_name=None):
    """Return version id

    Args:
        repo_name: repo name (optional)

    Returns:
        (str): version id
    """
    if repo_name is None:
        repo_name = github.repo_name()

    version_from_init = get_version_from_init(path, repo_name)
    version_from_version_file = get_version_from_version_file(path)

    assert version_from_init or version_from_version_file, "Version file cannot be found"
    assert (version_from_init is not None) ^ (version_from_version_file is not None), "Multiple version files found"

    if version_from_init:
        return version_from_init
    elif version_from_version_file:
        return version_from_version_file
    else:
        raise FileNotFoundError("Version file cannot be found.")


def get_version_from_init(path, repo_name=None):
    """get version from init in repo with directory structure:

    lib_name
    lib_name/lib_name
    lib_name/lib_name/__init__.py

    Args:
        repo_name: repo name

    Returns:
        (str): version id

    """
    if repo_name is None:
        return None

    repo_init_filepath = os.path.abspath(os.path.join(path, './{}/__init__.py'.format(repo_name)))
    logging.debug('repo_init_filepath: {}'.format(repo_init_filepath))

    if os.path.exists(repo_init_filepath):
        with open(repo_init_filepath, 'r') as fp:
            # returns string following "__version__ = "
            search = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                               fp.read(), re.MULTILINE)
            version = search.group(1) if search is not None else None

        return version


def get_version_from_version_file(path):
    """get version from a VERSION file in the repo

    {PATH}/VERSION

    Returns:
        (str): version id

    """
    version_filepath = os.path.abspath(os.path.join(path, './VERSION'))
    logging.debug('version_filepath: {}'.format(version_filepath))

    if os.path.exists(version_filepath):
        with open(version_filepath, 'r') as fp:
            version = fp.read().strip()
        logging.debug("Found version: '{}'".format(version))
        return version
