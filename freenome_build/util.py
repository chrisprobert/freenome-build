import os
import contextlib
import subprocess
import logging
import yaml
import jinja2

import conda_build.api
from conda_build.config import Config as CondaBuildConfig

from freenome_build.version_utils import version

logger = logging.getLogger(__file__)  # noqa: invalid-name


def norm_abs_join_path(*paths):
    return os.path.normpath(os.path.abspath(os.path.join(*paths)))


class CondaMetaYaml:
    def __init__(self, repo_path):
        self.version = version(repo_path)
        with open(norm_abs_join_path(repo_path, './conda-build/meta.yaml')) as ifp:
            self._template = jinja2.Template(ifp.read())
            self._data = yaml.load(
                self._template.render(
                    VERSION=self.version,
                    PY_VER='3'
                )
            )

    @property
    def package_name(self):
        return self._data['package']['name']

    @property
    def requirements(self):
        return self._data['requirements']


def get_yaml_path(repo_path):
    yaml_fpath = norm_abs_join_path(repo_path, "conda-build/meta.yaml")
    if not os.path.exists(yaml_fpath):
        raise ValueError(f"Could not find a meta.yaml file at '{yaml_fpath}'")
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


def build_package(path, version, skip_existing=False):
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
    assert len(output_file_paths) == 1, "multiple file paths in conda build"

    return output_file_paths[0]
