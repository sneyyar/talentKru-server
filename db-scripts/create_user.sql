-- 1. Create the users (Roles) with strong passwords
CREATE USER talentkru_app WITH PASSWORD 'kruApp2026';
CREATE USER talentkru_test WITH PASSWORD 'kruTest2026';

-- 2. Grant both users the ability to connect to your database
GRANT CONNECT ON DATABASE krudb TO talentkru_app;
GRANT CONNECT ON DATABASE krudb TO talentkru_test;

-- 3. Create the schemas and make the respective users the owners
CREATE SCHEMA talentkru_main AUTHORIZATION talentkru_app;
CREATE SCHEMA talentkru_test AUTHORIZATION talentkru_test;

-- 4. Set the default search paths
-- WARNING: We MUST include 'public' so pgvector keeps working!
ALTER USER talentkru_app SET search_path TO talentkru_main, public;
ALTER USER talentkru_test SET search_path TO talentkru_test, public;
