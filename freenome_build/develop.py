import os
import logging
import yaml

from freenome_build.util import build_package, run_and_log, norm_abs_join_path, change_directory
from freenome_build.github import repo_name
from freenome_build import version_utils

logger = logging.getLogger(__file__)  # noqa: invalid-name


def get_package_name_from_meta_yaml(path):
    with open(norm_abs_join_path(path, './conda-build/meta.yaml')) as ifp:
        data_template = ifp.read()
        # replace the VERSION template with 0, because we don't actually care
        # about the version to get the package name, but we need to yaml to be parseable
        data = yaml.load(data_template.replace("{{ VERSION }}", "0"))
        return data['package']['name']


def setup_development_environment(path):
    version = version_utils.version(path)
    logging.debug('version: %s', version)

    # get package name
    try:
        package_name = get_package_name_from_meta_yaml(path)
    except FileNotFoundError:
        with change_directory(path):
            package_name = repo_name().replace("_", "-")

    logging.debug('package name: %s', package_name)

    # build the package.
    # ( we need to do this to install the dependencies -- which is super hacky but required
    #   because of the jinja templating -- see https://github.com/conda/conda/issues/5126   )
    output_file_path = build_package(path, version=version, skip_existing=False)
    logger.debug('output build to %s', output_file_path)

    # conda install this package, which installs all of the dependencies
    logger.debug("installing package at '%s'", output_file_path)
    # extract the local path from the return output_file_path, which is of the form:
    # /tmp/nboley/conda/linux-64/balrog-10-0.tar.bz2
    local_channel = "file://" + os.path.split(os.path.split(output_file_path)[0])[0]
    run_and_log(f"conda install {package_name}=={version} --only-deps --yes -c {local_channel}")
    # python setup.py develop $PATH
    run_and_log("python {} develop".format(norm_abs_join_path(path, "./setup.py")))


def add_develop_subparser(subparsers):
    develop_subparser = subparsers.add_parser(
        'develop', help='initialize a development environment')
    develop_subparser.required = True
    develop_subparser.add_argument('path', default='.')


def develop_main(args):
    setup_development_environment(args.path)
