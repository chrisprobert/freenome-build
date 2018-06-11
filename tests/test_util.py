import tempfile
from freenome_build.util import run_and_log


def test_run_and_log():
    run_and_log('echo HELLO')


def test_run_and_log_with_bytes_input():
    run_and_log('cat', input=b'BYTES')


def test_run_and_log_with_str_input():
    run_and_log('cat', input='STRING')


def test_run_and_log_with_file_input():
    with tempfile.TemporaryFile() as ofp:
        ofp.write(b"FILE")
        run_and_log('cat', input=ofp)


def test_run_and_log_lots_of_data():
    """ensure that we don't get a dead lock when there is lots of output"""
    with tempfile.NamedTemporaryFile() as ofp:
        ofp.write(b'a'*100000000)
        ofp.flush()
        run_and_log(f'cat {ofp.name}')
