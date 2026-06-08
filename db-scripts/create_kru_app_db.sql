-- Main Application Database Setup
-- 
-- Creates a dedicated application database (kru_app_db) matching the .env configuration:
-- DATABASE_NAME=kru_app_db
-- DATABASE_USER=kru_app
-- DATABASE_PASSWORD=kruApp2026
--
-- This script:
-- 1. Creates kru_app_db database (if not exists)
-- 2. Creates kru_app schema in kru_app_db
-- 3. Creates kru_app user (if not exists)
-- 4. Grants all privileges on kru_app schema to kru_app user
-- 5. Creates required PostgreSQL extensions (vector, uuid-ossp) as superuser
-- 6. Sets kru_app as the default schema (with public in search path for pgvector)
--
-- Extensions (created as superuser):
-- - vector: pgvector extension for semantic search (requires CREATE EXTENSION privilege)
-- - uuid-ossp: UUID generation functions
--
-- Usage:
-- psql -h localhost -p 5432 -U postgres -f db-scripts/create_kru_app_db.sql

-- 1. Create application database (if not exists)
CREATE DATABASE kru_app_db
    WITH
    OWNER = postgres
    ENCODING = 'UTF8'
    LOCALE_PROVIDER = 'libc'
    CONNECTION LIMIT = -1
    IS_TEMPLATE = False;

-- 2. Create application user (if not exists)
-- Note: Must be run as postgres superuser to ensure user doesn't already exist
DO
$$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_user WHERE usename = 'kru_app') THEN
        CREATE USER kru_app WITH PASSWORD 'kruApp2026';
    END IF;
END
$$;

-- 3. Grant connection privileges on kru_app_db to kru_app user
GRANT CONNECT ON DATABASE kru_app_db TO kru_app;

-- 4. Connect to kru_app_db and create schema + grant privileges
-- This requires connecting to the application database
\c kru_app_db

-- 5. Create PostgreSQL extensions (MUST be done as superuser before migrations)
-- These extensions are required by the application and migrations
-- Note: Only superuser can create extensions; migrations will use 'CREATE EXTENSION IF NOT EXISTS'
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 6. Create schema (if not exists)
CREATE SCHEMA IF NOT EXISTS kru_app AUTHORIZATION kru_app;

-- 7. Grant all privileges on kru_app schema to kru_app user
GRANT USAGE ON SCHEMA kru_app TO kru_app;
GRANT CREATE ON SCHEMA kru_app TO kru_app;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA kru_app TO kru_app;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kru_app TO kru_app;

-- 8. Grant extension privileges to kru_app user
-- Allow the user to use the extensions in their schema
GRANT USAGE ON SCHEMA public TO kru_app;

-- 9. Set default privileges for future tables and sequences
ALTER DEFAULT PRIVILEGES FOR USER postgres IN SCHEMA kru_app GRANT ALL PRIVILEGES ON TABLES TO kru_app;
ALTER DEFAULT PRIVILEGES FOR USER postgres IN SCHEMA kru_app GRANT ALL PRIVILEGES ON SEQUENCES TO kru_app;

-- 10. Set the default search path for kru_app user
-- WARNING: We MUST include 'public' so pgvector extensions work correctly!
ALTER USER kru_app SET search_path TO kru_app, public;
