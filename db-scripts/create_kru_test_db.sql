-- Test Database Setup
-- 
-- Creates a dedicated test database (kru_test_db) matching the .env configuration:
-- TEST_DATABASE_NAME=kru_test_db
-- TEST_DATABASE_USER=kru_test
-- TEST_DATABASE_PASSWORD=kruTest2026
--
-- This script:
-- 1. Creates kru_test_db database (if not exists)
-- 2. Creates kru_test schema in kru_test_db
-- 3. Creates kru_test user (if not exists)
-- 4. Grants all privileges on kru_test schema to kru_test user
-- 5. Creates required PostgreSQL extensions (vector, uuid-ossp) as superuser
-- 6. Sets kru_test as the default schema (with public in search path for pgvector)
--
-- Extensions (created as superuser):
-- - vector: pgvector extension for semantic search (requires CREATE EXTENSION privilege)
-- - uuid-ossp: UUID generation functions
--
-- Usage:
-- psql -h localhost -p 5432 -U postgres -f db-scripts/create_kru_test_db.sql

-- 1. Create test database (if not exists)
CREATE DATABASE kru_test_db
    WITH
    OWNER = postgres
    ENCODING = 'UTF8'
    LOCALE_PROVIDER = 'libc'
    CONNECTION LIMIT = -1
    IS_TEMPLATE = False;

-- 2. Create test user (if not exists)
-- Note: Must be run as postgres superuser to ensure user doesn't already exist
DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_user WHERE usename = 'kru_test') THEN
        CREATE USER kru_test WITH PASSWORD 'kruTest2026';
    END IF;
END
$$;

-- 3. Grant connection privileges on kru_test_db to kru_test user
GRANT CONNECT ON DATABASE kru_test_db TO kru_test;

-- 4. Connect to kru_test_db and create schema + grant privileges
-- This requires connecting to the test database
\c kru_test_db

-- 5. Create PostgreSQL extensions (MUST be done as superuser before migrations)
-- These extensions are required by the application and migrations
-- Note: Only superuser can create extensions; migrations will use 'CREATE EXTENSION IF NOT EXISTS'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 6. Create schema (if not exists)
CREATE SCHEMA IF NOT EXISTS kru_test AUTHORIZATION kru_test;

-- 7. Grant all privileges on kru_test schema to kru_test user
GRANT USAGE ON SCHEMA kru_test TO kru_test;
GRANT CREATE ON SCHEMA kru_test TO kru_test;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA kru_test TO kru_test;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kru_test TO kru_test;

-- 8. Grant extension privileges to kru_test user
-- Allow the user to use the extensions in their schema
GRANT USAGE ON SCHEMA public TO kru_test;

-- 9. Set default privileges for future tables and sequences
ALTER DEFAULT PRIVILEGES FOR USER postgres IN SCHEMA kru_test GRANT ALL PRIVILEGES ON TABLES TO kru_test;
ALTER DEFAULT PRIVILEGES FOR USER postgres IN SCHEMA kru_test GRANT ALL PRIVILEGES ON SEQUENCES TO kru_test;

-- 10. Set the default search path for kru_test user
-- WARNING: We MUST include 'public' so pgvector extensions work correctly!
ALTER USER kru_test SET search_path TO kru_test, public;
