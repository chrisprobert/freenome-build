import os
import time
import subprocess
import logging
import psycopg2

from freenome_build.util import norm_abs_join_path, change_directory, get_git_repo_name, run_and_log

logger = logging.getLogger(__file__)  # noqa: invalid-name

DEFAULT_TEST_DB_PORT = 3333
DEFAULT_TEST_DB_HOST = 'localhost'

# the maximum amount of time in seconds to wait for the DB to come up before raising an error
MAX_DB_WAIT_TIME = 10


class ContainerDoesNotExistError(Exception):
    pass


def _execute_sql_script(sql_script_path, dbuser, dbname, host, port):
    pass


def _setup_db(image_name, repo_path, host, port):
    # check if 'setup' exists in repo_path/database/
    repo_setup_sql_path = norm_abs_join_path(repo_path, "./database/setup.sql")
    if os.path.exists(repo_setup_sql_path):
        with open(repo_setup_sql_path) as ifp:
            setup_sql = ifp.read()
    # if this doesn't exist, revert to the default
    else:
        setup_sql_template_path = norm_abs_join_path(
            os.path.dirname(__file__), "./database_template/scripts/setup.sql")
        logger.debug(f"The repo at '{repo_path}' does not contain './database/setup.sql'."
                     f"\nDefaulting to {setup_sql_template_path} with "
                     f"USER='{image_name}', DATABASE='{image_name}'")
        # get the new database password from the environment
        if 'PGPASSWORD' not in os.environ:
            raise ValueError("PGPASSWORD must be in the environment to setup a new database.")
        with open(setup_sql_template_path) as ifp:
            setup_sql = ifp.read().format(
                PGUSER=image_name, PGDATABASE=image_name, PGPASSWORD=os.environ['PGPASSWORD']
            )

    # execute the setup.sql script
    run_and_log(f"psql -h {host} -p {port} -U postgres", input=setup_sql.encode())

    return


def _run_migrations(repo_path, host, port, dbname, dbuser):
    # check if 'migrate' exists in repo_path/database/
    repo_migrate_path = norm_abs_join_path(repo_path, "./database/migrate")
    if os.path.exists(repo_migrate_path):
        # TODO -- add support for running this script
        raise NotImplementedError("We have not implemented running migrate from the repo.")

    logger.info(f"The repo at '{repo_path}' does not contain './database/migrate' script"
                "\nDefaulting to running sqitch migrations in './database/sqitch'")
    sqitch_path = norm_abs_join_path(repo_path, "./database/sqitch")
    if not os.path.exists(sqitch_path):
        raise RuntimeError(
            f"Sqitch migration files must exist at '{sqitch_path}' "
            "if a migration script is not provided.")

    with change_directory(sqitch_path):
        try:
            run_and_log(
                f"sqitch --engine pg deploy db:pg://postgres@{host}:{port}/{dbname}")
        except subprocess.CalledProcessError as inst:
            # we don't care if there's nothing to deploy
            if inst.stderr.decode().strip() == 'Nothing to deploy (empty plan)':
                pass
            else:
                raise
    return


def _insert_test_data(repo_path, host, port, dbuser, dbname):
    # check if 'migrate' exists in repo_path/database/
    repo_insert_test_data_path = norm_abs_join_path(
        repo_path, "./database/insert_test_data")
    if os.path.exists(repo_insert_test_data_path):
        # TODO -- add support for running this script
        raise NotImplementedError("We have not implemented running insert_test_data from the repo.")
    else:
        logger.debug(
            f"The repo at '{repo_path}' does not contain './database/insert_test_data' script")

    repo_insert_test_data_sql_path = norm_abs_join_path(
        repo_path, "./database/insert_test_data.sql")
    if os.path.exists(repo_insert_test_data_sql_path):
        logger.info(f"Inserting data in '{repo_insert_test_data_sql_path}'.")
        with open(repo_insert_test_data_sql_path) as ifp:
            run_and_log(
                f"psql -h {host} -p {port} -U {dbuser} {dbname}",
                input=ifp.read().encode()
            )
        return
    else:
        logger.info(
            f"The repo at '{repo_path}' does not contain './database/insert_test_data.sql' script")

    raise ValueError(f"'{repo_path}' does not contain an insert test data script or sql file.")


def _wait_for_db_cluster_to_start(host, port, max_wait_time=MAX_DB_WAIT_TIME, recheck_interval=0.2):
    conn_str = f"dbname=postgres user=postgres host={host} port={port}"
    for _ in range(int(max_wait_time/recheck_interval)+1):
        try:
            with psycopg2.connect(conn_str) as _: # noqa
                # we just want to see if we can connect, so if we do then connect
                logger.debug(f"Database at '{conn_str}' is up!")
                return
        except psycopg2.OperationalError:
            logger.debug(f"DB cluster at '{conn_str}' is not yet up.")
            time.sleep(recheck_interval)
            continue

    raise RuntimeError(f"Aborting because the DB did not start within {MAX_DB_WAIT_TIME} seconds.")


def stop_test_database(project_name, host=DEFAULT_TEST_DB_HOST, port=DEFAULT_TEST_DB_PORT):
    if host != 'localhost':
        raise NotImplementedError('Non localhost test databases are not supported.')
    image_name = f"{project_name}_{port}"
    cmd = f"docker kill {image_name}"
    try:
        run_and_log(cmd)
    except subprocess.CalledProcessError as inst:
        # if this is an error because the container already exists, then raise
        # a custom error type
        pat = (f"Error response from daemon: Cannot kill container:"
               f" {image_name}: No such container: {image_name}")
        if inst.stderr.decode().strip() == pat:
            raise ContainerDoesNotExistError(inst)
        # otherwise just propogate the error
        else:
            raise

    cmd = f"docker rm -f {image_name}"
    run_and_log(cmd)


def start_test_database(
        repo_path, project_name, host=DEFAULT_TEST_DB_HOST, port=DEFAULT_TEST_DB_PORT):
    """Start a test database in a docker container.

    This starts a new test database in a docker container. This function:
    1) builds the postgres server docker image
    2) starts the docker container on port 'port'
    3) waits for the database cluster to start
    4) runs the DB setup script
       - create a new db user $dbname
       - create a new db $dbname owned by $dbname
    5) runs the database migrations
    """
    # TODO (nb): add a check to ensure that 'port' is free
    # host is always localhost because we are running it in a local Docker container
    if host != 'localhost':
        raise NotImplementedError('Non localhost test databases are not supported.')

    # set the path to the Postgres Dockerfile
    docker_file_path = norm_abs_join_path(repo_path, "./database/Dockerfile")
    # if the repo doesn't have a Dockerfile in the database sub-directory, then
    # default to the template Dockerfile
    if not os.path.exists(docker_file_path):
        docker_file_path = norm_abs_join_path(
            os.path.dirname(__file__), "./database_template/Dockerfile")
        logger.info(f"Setting DB docker file path to '{docker_file_path}'")

    docker_file_dir = os.path.dirname(docker_file_path)

    # build
    cmd = f"docker build --rm -t {project_name}:latest {docker_file_dir}"
    run_and_log(cmd)

    # starting-db
    cmd = f"docker run -d -p {port}:5432 --name {project_name}_{port} {project_name}:latest"
    run_and_log(cmd)
    # the database cluster needs some time to start, so try to connect periodically until we can
    _wait_for_db_cluster_to_start(host, port)

    # setup-db
    # we need to connect to the 'postgres' database to create a new database
    _setup_db(project_name, repo_path, host, port)

    # run-migrations
    _run_migrations(
        repo_path=repo_path, host=host, port=port, dbname=project_name, dbuser=project_name)

    # insert test data
    _insert_test_data(
        repo_path=repo_path, host=host, port=port, dbname=project_name, dbuser=project_name)

    # log the connection command
    connection_cmd = f"psql -h {host} -p {port} -U {project_name} {project_name}"
    logger.info(f"Database is up! You can connect by running:\n{connection_cmd}")


def start_test_database_main(args):
    if args.force:
        # if the container does not exist then we don't need to stop anything
        try:
            stop_test_database(args.project_name, args.host, args.port)
        except ContainerDoesNotExistError:
            pass
    start_test_database(args.path, args.project_name, args.host, args.port)


def stop_test_database_main(args):
    stop_test_database(args.project_name, args.host, args.port)


def connect_to_test_db_main(project_name, host, port):
    connection_cmd = f"psql -h {host} -p {port} -U {project_name} {project_name}"
    logger.debug(f"Running '{connection_cmd}'")
    proc = subprocess.Popen(connection_cmd, shell=True)
    proc.wait()


def add_db_subparser(subparsers):
    database_parser = subparsers.add_parser('test-db', help='manage the test database')
    database_parser.required = True
    database_parser.add_argument('--path', default='.')
    database_parser.add_argument(
        '--port', default=DEFAULT_TEST_DB_PORT,
        help='Port on which to start the test db. Default: %(default)s'
    )
    database_parser.add_argument(
        '--host', default=DEFAULT_TEST_DB_HOST,
        help='Teste DB host. Default: %(default)s'
    )
    database_parser.add_argument(
        '--project-name',
        default=None,
        help='The name of the project.\n'
             'This is assumed to be the name of the database and the database owner.\n'
             'Default: The name of the git repo at $PATH with - replaced with _'
    )

    # add the subparsers
    database_subparsers = database_parser.add_subparsers(dest='test_db_command')
    database_subparsers.required = True

    # Start a test DB
    start_test_db_parser = database_subparsers.add_parser('start', help='start a test database')
    start_test_db_parser.add_argument(
        '--force', '-f', action='store_true', default=False,
        help='Start the test database even if it means stopping an already existing '
             'docker container of the same name.'
    )

    # Stop the test db
    database_subparsers.add_parser('stop', help='stop the test database')

    # Connect to a test db
    database_subparsers.add_parser('connect', help='Connect to the test database.')


def db_main(args):
    # normalize the path
    args.path = norm_abs_join_path(args.path)

    # set the project name to the name of the git repo at args.path
    if args.project_name is None:
        args.project_name = get_git_repo_name(args.path).replace('-', '_')
        logger.info(f"Setting project name to '{args.project_name}'")

    if args.test_db_command == 'connect':
        connect_to_test_db_main(args.project_name, args.host, args.port)
    elif args.test_db_command == 'start':
        start_test_database_main(args)
    elif args.test_db_command == 'stop':
        stop_test_database_main(args)
    else:
        raise ValueError(f"Unrecognized DB subcommand '{args.test_db_command}'")
