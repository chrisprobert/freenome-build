import argparse
import logging
import os
import sys
import re
import subprocess
import conda
import conda_build.api

from freenome_build.constants import GCS_CONDA_BUILD_SCRIPT_URL
from freenome_build import github
from freenome_build import version_utils

LOCAL_CONDA_BUILD_SCRIPT = os.path.abspath('scripts/conda_build.sh')

logging.basicConfig(stream=sys.stderr, format='%(levelname)s\t%(asctime)-15s\t%(message)s')


def setup_development_environment(path='./', environment_name=None):
    # set the default environment name
    if environment_name is None:
        environment_name = github.environment_name()

    # build the package.
    # ( we need to do this to install the dependencies -- which is super hacky but required
    #   because of the jinja templating -- see https://github.com/conda/conda/issues/5126   )
    yaml_fpath = os.path.normpath(os.path.abspath(os.path.join(path, "conda-build/meta.yaml")))
    if not os.path.exists(yaml_fpath):
        raise ValueError("Could not find a yaml file at '{}'".format(yaml_fpath))
    output_file_paths = conda_build.api.build(
        [yaml_fpath,],
        skip_existing=True
    )
    print(output_file_paths)
    assert False



def repo_build_and_upload(path='./', upload=True, skip_existing=False,
                          repo_name=None):
    """

    Args:
        path (str): library path to install (default './')
        upload (bool): upload to freenome conda channel (default True)
        skip_existing (bool): do not build if existing build in local conda install (default False)
        repo_name (str): repo name to build (optional)

    Returns:
        None

    """
    if repo_name is None:
        repo_name = github.repo_name()

    # Set the environment variable VERSION so that
    # the jinja2 templating works for the conda-build
    version = version_utils.version(repo_name=repo_name)
    logging.debug('version: {}'.format(version))

    local_env = os.environ
    local_env['VERSION'] = version

    # build the package
    yaml_fpath = os.path.normpath(os.path.abspath(os.path.join(path, "conda-build/meta.yaml")))

    output_file_paths = conda_build.api.build(
        [yaml_fpath,],
        skip_existing=skip_existing
    )
    assert len(output_file_paths) == 1, "multiple file paths in conda build"

    if upload:
        upload_cmd = ['anaconda', '-t', local_env['ANACONDA_TOKEN'],
                      'upload', '--force', '-u', 'freenome', output_file_paths[0]]

        subprocess.check_call(upload_cmd, stdout=sys.stdout, stderr=sys.stderr)



def main():
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.cmd == 'develop':
        setup_development_environment()

    elif args.cmd == 'deploy':
        repo_build_and_upload(path=args.path,
                              upload=args.upload,
                              skip_existing=args.skip_existing)
    else:
        raise Exception('Unknown command: {}.'.format(args.cmd))


def parse_args():
    """build and parse args for freenome-build

    Returns:
        parsed args
    """
    parser = argparse.ArgumentParser('Freenome build manager')
    parser.add_argument('cmd', type=str, help='Command to run')

    deploy_args = parser.add_argument_group()
    deploy_args.add_argument('-u', '--upload', action='store_true', default=False,
                             dest='upload')
    deploy_args.add_argument('-p', '--path', action='store', default='./',
                             dest='path')
    deploy_args.add_argument('--debug', action='store_true', default=False,
                             dest='debug')
    deploy_args.add_argument('--skip', action='store_true', default=False,
                             dest='skip_existing')

    args = parser.parse_args()

    return args


if __name__ == '__main__':
    main()
