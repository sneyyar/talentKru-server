# Database Setup Guide

**Last Updated:** June 7, 2026

## Overview

This guide covers the complete setup process for TalentKru.ai databases using the new refactored database scripts. The system uses **two separate databases** (`kru_app_db` and `kru_test_db`) running in a **single PostgreSQL instance**.

## Architecture

```
PostgreSQL Docker Container (single instance)
├── kru_app_db (Main application database)
│   ├── kru_app schema
│   ├── kru_app user (app connections)
│   └── All application tables and migrations
│
└── kru_test_db (Test database)
    ├── kru_test schema
    ├── kru_test user (test connections)
    └── Same schema as app (migrations applied separately)
```

## Prerequisites

- Docker installed and running
- PostgreSQL client tools (`psql`) installed locally
- Python 3.12+ with `uv` package manager
- `.env` file properly configured (see below)

## Environment Configuration

Update `.env` with the following database settings:

```env
# Main Application Database
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=kru_app_db
DATABASE_USER=kru_app
DATABASE_PASSWORD=kruApp2026

# Test Database
TEST_DATABASE_HOST=localhost
TEST_DATABASE_PORT=5432
TEST_DATABASE_NAME=kru_test_db
TEST_DATABASE_USER=kru_test
TEST_DATABASE_PASSWORD=kruTest2026

# PostgreSQL Container Configuration
PG_CONTAINER_NAME=local-postgresql-db
PG_IMAGE=pgvector/pgvector:pg17
PG_DATABASE_NAME=kru_app_db        # Updated to match main database
PG_PORT=5432
PG_VOLUME_NAME=krudb_data
PG_ADMIN_PASSWORD=adminA11         # Change this to a strong password
POSTGRESQL_DATA_DIR=/path/to/postgresql/data

# pgAdmin (optional)
PGADMIN_DEFAULT_EMAIL=admin@talentkru.ai
PGADMIN_DEFAULT_PASSWORD=adminA11
PGADMIN_CONTAINER_NAME=local-pgadmin4
PGADMIN_PORT=8080
```

## Quick Start (First Time Setup)

Follow these steps in order:

### 1. Start PostgreSQL Container

```bash
uv run invoke db-start
```

**Output:**
```
🚀 Starting PostgreSQL container...
   Container Name: local-postgresql-db
   Image: pgvector/pgvector:pg17
   Database: kru_app_db
   Port: 5432
   Volume: krudb_data

⏳ Starting container...
✅ PostgreSQL container started successfully
✅ PostgreSQL is ready!
```

### 2. Initialize Main Application Database

```bash
uv run invoke db-init-users
```

**What it does:**
- Creates `kru_app_db` database (if not exists)
- Creates `kru_app` user with credentials from `.env`
- Creates `kru_app` schema
- Grants all privileges to `kru_app` user
- Sets search path: `kru_app, public`

**Output:**
```
👤 Initializing database users and schemas...
✅ SQL script executed successfully
✅ Database users and schemas initialized successfully!
```

### 3. Apply Migrations to Main Database

```bash
uv run invoke migrate
```

**What it does:**
- Reads `alembic/versions/` directory
- Applies all pending migrations to `kru_app_db`
- Uses `DATABASE_*` environment variables for connection

**Output:**
```
📦 Applying database migrations...
INFO [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO [alembic.runtime.migration] Will assume transactional DDL is supported by the platform
INFO [alembic.runtime.migration] Running stamp_revision -> ...
```

### 4. Initialize Test Database

```bash
uv run invoke db-init-test
```

**What it does:**
- Creates `kru_test_db` database (if not exists)
- Creates `kru_test` user with credentials from `.env`
- Creates `kru_test` schema
- Grants all privileges to `kru_test` user
- Sets search path: `kru_test, public`
- **Automatically applies migrations** to test database

**Output:**
```
🧪 Initializing test database...
✅ Connected to PostgreSQL
✅ Test database ready
👤 Creating test database users and schemas...
✅ Test database users and schemas created successfully!
📦 Applying migrations to test database...
✅ Migrations applied successfully!
✅ Test database initialization complete!
```

## Complete Setup Command

You can run the complete setup in one go with:

```bash
# Recommended: Run in sequence
uv run invoke db-start && \
uv run invoke db-init-users && \
uv run invoke migrate && \
uv run invoke db-init-test
```

Or run individual setup task:

```bash
# One-liner setup (if available)
uv run invoke setup
```

## Database Tasks Reference

### Main Application Database Tasks

| Command | Purpose |
|---------|---------|
| `uv run invoke db-start` | Start PostgreSQL Docker container |
| `uv run invoke db-init-users` | Create app database, user, and schema |
| `uv run invoke migrate` | Apply pending migrations to app database |
| `uv run invoke migrate-down` | Rollback last migration from app database |
| `uv run invoke db-status` | Show current migration status of app database |
| `uv run invoke db-check` | Test connection to app database |

### Test Database Tasks

| Command | Purpose |
|---------|---------|
| `uv run invoke db-init-test` | Create test database, user, schema, and apply migrations |
| `uv run invoke migrate-test` | Apply pending migrations to test database only |

### Docker Container Tasks

| Command | Purpose |
|---------|---------|
| `uv run invoke db-stop` | Stop PostgreSQL container |
| `uv run invoke db-remove` | Remove PostgreSQL container and volume |
| `uv run invoke db-admin-start` | Start pgAdmin4 web UI (http://localhost:8080) |
| `uv run invoke db-admin-stop` | Stop pgAdmin4 container |

## Detailed Task Documentation

### `db-init-users`

**Purpose:** Initialize main application database

**What it runs:**
- `db-scripts/create_kru_app_db.sql` (via legacy `create_user.sql`)

**Connection details:**
```
Host:     DATABASE_HOST (default: localhost)
Port:     DATABASE_PORT (default: 5432)
User:     postgres (admin)
Password: PG_ADMIN_PASSWORD
Database: DATABASE_NAME (kru_app_db)
```

**Idempotent:** ✅ Yes (uses `IF NOT EXISTS` for user/schema creation)

### `migrate`

**Purpose:** Apply migrations to main application database

**Environment variables used:**
- `DATABASE_HOST`
- `DATABASE_PORT`
- `DATABASE_NAME`
- `DATABASE_USER`
- `DATABASE_PASSWORD`

**Idempotent:** ✅ Yes (Alembic tracks applied migrations)

### `db-init-test`

**Purpose:** Initialize test database with automatic migration

**What it does:**
1. Tests PostgreSQL connection
2. Creates `TEST_DATABASE_NAME` database
3. Creates `TEST_DATABASE_USER` user
4. Creates schema and grants privileges
5. Automatically runs `migrate-test`

**Environment variables used:**
- `TEST_DATABASE_HOST`
- `TEST_DATABASE_PORT`
- `TEST_DATABASE_NAME`
- `TEST_DATABASE_USER`
- `TEST_DATABASE_PASSWORD`
- `PG_ADMIN_PASSWORD`

**Idempotent:** ✅ Yes (all components use `IF NOT EXISTS`)

### `migrate-test`

**Purpose:** Apply migrations to test database only

**Environment variables used:**
- `TEST_DATABASE_HOST`
- `TEST_DATABASE_PORT`
- `TEST_DATABASE_NAME`
- `TEST_DATABASE_USER`
- `TEST_DATABASE_PASSWORD`

**Idempotent:** ✅ Yes (Alembic tracks applied migrations)

**Note:** Usually called automatically by `db-init-test`, but can be run independently if needed.

## Database Setup Scripts

### `db-scripts/create_kru_app_db.sql`

**Creates:**
- Database: `kru_app_db`
- User: `kru_app` (password: `kruApp2026`)
- Schema: `kru_app`
- Grants: All privileges on schema to user

**Usage:**
```bash
psql -h localhost -p 5432 -U postgres -f db-scripts/create_kru_app_db.sql
```

### `db-scripts/create_kru_test_db.sql`

**Creates:**
- Database: `kru_test_db`
- User: `kru_test` (password: `kruTest2026`)
- Schema: `kru_test`
- Grants: All privileges on schema to user

**Usage:**
```bash
psql -h localhost -p 5432 -U postgres -f db-scripts/create_kru_test_db.sql
```

### `db-scripts/create_user.sql`

**Purpose:** Legacy reference documentation

**Status:** Deprecated (replaced by separate scripts above)

## Troubleshooting

### PostgreSQL not running

```bash
# Check if container exists and is running
docker ps | grep local-postgresql-db

# Start container if stopped
uv run invoke db-start

# View container logs
docker logs local-postgresql-db
```

### Connection refused

```bash
# Test PostgreSQL connection
uv run invoke db-check

# Verify credentials in .env
cat .env | grep DATABASE_
cat .env | grep TEST_DATABASE_
```

### Migration issues

```bash
# Check current migration status
uv run invoke db-status

# View available migrations
ls alembic/versions/

# Manually check test database status
psql -h localhost -p 5432 -U postgres -d kru_test_db -c "SELECT version();"
```

### Permissions issues

```bash
# Verify schema permissions
psql -h localhost -p 5432 -U postgres -d kru_app_db -c "\dn+"

# Check user privileges
psql -h localhost -p 5432 -U postgres -d kru_app_db -c "\du+"
```

### Reset everything

```bash
# Warning: This deletes all data!
uv run invoke db-remove

# Then restart from step 1
uv run invoke db-start
uv run invoke db-init-users
uv run invoke migrate
uv run invoke db-init-test
```

## Development Workflow

### Daily Development

```bash
# Terminal 1: Start dev server
uv run invoke dev

# Terminal 2: Run tests (uses test database)
uv run invoke test-watch

# Terminal 3: Check code quality
uv run invoke lint
```

### Creating Migrations

```bash
# Create new migration (tracks model changes)
uv run invoke db-revision --message "Add users table"

# Review generated migration
cat alembic/versions/001_add_users_table.py

# Apply to main database
uv run invoke migrate

# Apply to test database
uv run invoke migrate-test
```

### Running Tests

```bash
# Run all tests (uses kru_test_db)
uv run invoke test

# Run with coverage
uv run invoke test-cov

# Run specific test file
uv run pytest tests/test_auth_service.py -v

# Run in watch mode
uv run invoke test-watch
```

## Database Isolation

The separate database approach provides:

✅ **Complete isolation** - App and test data never mix  
✅ **Parallel execution** - Tests can run without affecting app  
✅ **Easy cleanup** - Drop test database without touching app data  
✅ **Realistic testing** - Test database has identical schema to production  
✅ **Single container** - Simplified Docker management  

## Performance Considerations

### Connection Pooling

Both databases use SQLAlchemy connection pooling:
- `StaticPool` for tests (per-session isolation)
- Regular `QueuePool` for app (connection reuse)

### Indexes

Both databases share the same migration history, ensuring:
- Identical schema structure
- Same indexes and constraints
- Consistent query performance

## Related Documentation

- [Testing Guide](.kiro/steering/test.md)
- [Tech Stack Guide](.kiro/steering/tech.md)
- [Project Structure](.kiro/steering/structure.md)
- [Database Migrations](alembic/README.md)
