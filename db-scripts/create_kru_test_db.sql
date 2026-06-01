
/*
# This is a temporary script. There will be two schemas 
# under one database. main_kru (main database) and test_kru for test.
*/

CREATE ROLE kru_test WITH
	LOGIN
	NOSUPERUSER
	CREATEDB
	CREATEROLE
	INHERIT
	NOREPLICATION
	NOBYPASSRLS
	CONNECTION LIMIT -1
	PASSWORD 'kruTest2026';

/*
CREATE DATABASE kru_test_db
    WITH
    OWNER = kru_test
    ENCODING = 'UTF8'
    LOCALE_PROVIDER = 'libc'
    CONNECTION LIMIT = -1
    IS_TEMPLATE = False;
*/