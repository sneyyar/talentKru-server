-- 1. Create the users (Roles) with strong passwords
CREATE USER kru_app WITH PASSWORD 'kruApp2026';
CREATE USER kru_test WITH PASSWORD 'kruTest2026';

-- 2. Grant both users the ability to connect to your database
GRANT CONNECT ON DATABASE krudb TO kru_app;
GRANT CONNECT ON DATABASE krudb TO kru_test;

-- 3. Create the schemas and make the respective users the owners
-- Schema names match the user names for simplicity
CREATE SCHEMA kru_app AUTHORIZATION kru_app;
CREATE SCHEMA kru_test AUTHORIZATION kru_test;

-- 4. Set the default search paths
-- WARNING: We MUST include 'public' so pgvector keeps working!
ALTER USER kru_app SET search_path TO kru_app, public;
ALTER USER kru_test SET search_path TO kru_test, public;
