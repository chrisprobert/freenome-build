# Database Template

## Local testing Database

### Quick Start

Start a test database
```
freenome-build test-db start
```

Stop a test database
```
freenome-build test-db stop
```

Connect to the test database:
```
freenome-build test-db connect
```

#### Commands that we should add

Insert test data into the test database
```
freenome-build db insert-test-data
```

### Database Management Template Scripts

There are 3 basic commands that need to be run to use the testing database. We need to be able to initialize the database with the correct structure, insert test data, and drop test data. This directory contains default scripts that perform these actions, and serve both as a sensible default and a template if more control is needed.

#### Database Setup
Initialize a database. This is where extensions should be loaded, users should be added, permissions should be set, and migrations should be run.

This attempts to execute the following scripts in this order:

Database initialization:
1) run `$REPO/database/setup.sql` as the DB owner
2) `setup.sql` from `database_template/scripts/` in this repo

Database migrations:
1) `$REPO/database/migrate` __Not Implemented__
2) run `sqitch --engine pg deploy db:pg://{dbuser}@{host}:{port}/{dbname}` from `$REPO/database/sqitch`

#### Test Data Insertion
This inserts the test data into the database. Note that this does *not* reset the data first. In a real test script, you need to reset the database and then insert the test data.

This attempts to execute the following scripts in this order:
1) execute `$REPO/database/insert_test_data`
2) run `$REPO/database/insert_test_data.sql` as the DB owner

#### Database Reset
This should remove all non-migration data from the database.

This attempts to execute the database setup scripts in the following order:
1) `$REPO/database/drop` in `$DATABASE_SETUP_SCRIPTS`
2) run `$REPO/database/drop.sql` as the database owner
3) `drop` in this directory __Not Implemented__
The `drop` script in this directory:
   - drops the database
   - runs the database setup script

**Note: The speed of this could be significantly increased by creating a template database the first time, and reloading from the template in subsequent resets.**
