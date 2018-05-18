import os
import subprocess


def repo_name():
    """Return github repository name of current directory

    Returns:
        (str): repo name
    """
    return os.path.basename(
        subprocess.run(
            'git rev-parse --show-toplevel',
            shell=True,
            stdout=subprocess.PIPE
        ).stdout.strip().decode('utf8')).lower().replace('-', '_')


def environment_name():
    """Returns local environment name

    Returns:
        (str): environment name
    """
    return subprocess.run(
        'git describe --all HEAD^',
        shell=True,
        stdout=subprocess.PIPE
    ).stdout.strip().decode('utf8').replace('/', '__')
