-- Runs once, the first time the Postgres volume is created.
-- A separate database for tests, so tests can wipe it freely.
CREATE DATABASE vyayam_test;
