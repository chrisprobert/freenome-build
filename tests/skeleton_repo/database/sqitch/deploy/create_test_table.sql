-- Deploy skeleton:create_test_table to pg

BEGIN;

SET ROLE freenome_build;

CREATE TABLE test (
    test text PRIMARY KEY
);

COMMIT;
