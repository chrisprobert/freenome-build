## Database Management Template Scripts

There are 3 basic commands that need to be run to use the testing database. We need to be able to initialize the database with the correct structure, insert test data, and drop test data. This directory contains default scripts that perform these actions, and serve both as a sensible default and a template if more control is needed.

### Database Setup
Initialize a database. This is where extensions should be loaded, users should be added, permissions should be set, and migrations should be run.

This attempts to execute the following scripts in this order:

# One of these scripts must be in $REPO/database
Database initialization:
1) `setup.sql` in `$REPO/database`
2) `setup.sql` from this directory

Database migrations:
1) `migrate` in `$REPO/database`
# XXX - start running migrate from this directory?
2) run `sqitch --engine pg deploy db:pg://{dbuser}@{host}:{port}/{dbname}` from `$REPO/database/sqitch`

### Test Data Insertion
This inserts the test data into the database. Note that this does *not* reset the data first. In a real test script, you need to reset the database and then insert the test data.

This attempts to execute the following scripts in this order:
1) execute `insert_test_data` in `$REPO/database`
2) run `insert_test_data.sql` in `$REPO/database` as the DB owner

### Database Reset
This should remove all non-migration data from the database.

This attempts to execute the database setup scripts in the following order:
1) `drop` in `$DATABASE_SETUP_SCRIPTS`
2) `drop.sql` in `$DATABASE_SETUP_SCRIPTS`
3) `drop` in this directory
The `drop` script in this directory:
   - drops the database
   - runs the database setup script

**Note: The speed of this could be significantly increased by creating a template database the first time, and reloading from the template in subsequent resets.**
