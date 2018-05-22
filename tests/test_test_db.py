import os
import subprocess

from freenome_build.db import start_test_database, stop_test_database

DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "./skeleton_repo/"))


def test_db_cli():
    """Check that we can start, connect to, and stop a test db."""
    initial_wd = os.getcwd()
    os.chdir(DB_DIR)
    try:
        start_cmd = "PGPASSWORD=password freenome-build test-db start -f"
        subprocess.run(start_cmd, shell=True, check=True)
        connect_cmd = "freenome-build test-db connect"
        proc = subprocess.run(
            connect_cmd, shell=True, check=True, stdout=subprocess.PIPE,
            input=b"SELECT * FROM test; \q"
        )
        assert proc.stdout.strip() == b"test \n------\n test\n(1 row)"
        stop_cmd = "freenome-build test-db stop"
        subprocess.run(stop_cmd, shell=True, check=True)
    finally:
        os.chdir(initial_wd)


def test_db_module_interface():
    os.environ["PGPASSWORD"] = "password"
    # stop any database that already exists
    start_test_database(DB_DIR, "freenome_build")
    stop_test_database("freenome_build")
