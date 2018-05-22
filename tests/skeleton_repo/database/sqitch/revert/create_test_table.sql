-- Revert skeleton:create_test_table from pg

BEGIN;

DROP TABLE test;

COMMIT;
