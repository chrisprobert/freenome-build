import os
import re
import contextlib
import subprocess
import logging

import conda_build.api
from conda_build.config import Config as CondaBuildConfig


logger = logging.getLogger(__file__)  # noqa: invalid-name


class YamlNotFoundError(Exception):
    pass


def norm_abs_join_path(*paths):
    return os.path.normpath(os.path.abspath(os.path.join(*paths)))


def get_yaml_path(repo_path):
    yaml_fpath = norm_abs_join_path(repo_path, "conda-build/meta.yaml")
    if not os.path.exists(yaml_fpath):
        raise YamlNotFoundError(f"Could not find a meta.yaml file at '{yaml_fpath}'")
    else:
        return yaml_fpath


def run_and_log(cmd, input=None):
    logger.info(f"Running '{cmd}'")

    proc = subprocess.run(
        cmd, shell=True, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    if proc.stderr:
        logger.info(f"Ran '{cmd}'\nSTDERR:\n{proc.stderr.decode().strip()}")
    if proc.stdout:
        logger.info(f"Ran '{cmd}'\nSTDOUT:\n{proc.stdout.decode().strip()}")

    # raise an excpetion if the return code was non-zero
    proc.check_returncode()

    return proc


@contextlib.contextmanager
def change_directory(path):
    """A context manager which changes the working directory to the given
    path, and then changes it back to its previous value on exit.

    """
    prev_cwd = os.getcwd()
    os.chdir(path)
    yield
    os.chdir(prev_cwd)


def get_git_repo_name(path):
    with change_directory(path):
        proc = subprocess.run(
            "git config --get remote.origin.url",
            shell=True, stdout=subprocess.PIPE, check=True
        )
        res = proc.stdout.decode().strip()
        # extract the basename, and then strip '.git' off of the end
        return os.path.basename(res)[:-4]


def build_package_from_meta_yaml(path, version, skip_existing=False):
    # Set the environment variable VERSION so that
    # the jinja2 templating works for the conda-build
    local_env = os.environ
    local_env['VERSION'] = version

    # build the package
    yaml_fpath = get_yaml_path(path)
    output_file_paths = conda_build.api.build(
        [yaml_fpath, ],
        skip_existing=skip_existing,
        config=CondaBuildConfig(anaconda_upload=False, quiet=True)
    )
    if len(output_file_paths) == 0:
        raise RuntimeError('No package was built.')
    assert len(output_file_paths) == 1, \
        "multiple file paths in conda build: {}".format(str(output_file_paths))
    return output_file_paths[0]


def build_package_using_distutils(path):
    proc = subprocess.run(
        "python setup.py bdist_conda",
        shell=True, check=True, stdout=subprocess.PIPE
    )
    upload_pat = "# \$ anaconda upload (\S+)$"
    build_output = proc.stdout.decode()
    for line in build_output.splitlines():
        res = re.findall(upload_pat, line)
        if res:
            assert len(res) == 1
            return res[0]

    logger.debug('STDOUT: {}'.format(build_output))
    raise ValueError('Could not extract package file from stdout.')


def build_package(path, version, skip_existing=False):
    try:
        yaml_path = get_yaml_path(path)
    except YamlNotFoundError:
        yaml_path = None

    # if we can't find the yaml file, install using disttools bdist_conda
    if yaml_path is None:
        return build_package_using_distutils(path)
    else:
        return build_package_from_meta_yaml(path=path, version=version, skip_existing=skip_existing)
