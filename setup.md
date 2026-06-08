# TalentKru.ai Server — Local Development Setup

This guide provides step-by-step instructions for setting up and running the TalentKru.ai server locally using **uv**, **poetry**, and **invoke** for dependency management and task automation.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Environment Configuration](#environment-configuration)
4. [Database Setup](#database-setup)
5. [PostgreSQL Command-Line Client (psql)](#postgresql-command-line-client-(psql))
6. [pgAdmin Web UI](#pgadmin-web-ui)
7. [Running the Application](#running-the-application)
8. [Available Tasks](#available-tasks)
9. [Troubleshooting](#troubleshooting)

---

## Prerequisites

Before you begin, ensure you have the following installed on your system:

- **pyenv** — Python version manager (recommended)
- **Python 3.12+** — Required by the project
- **Docker & Docker Compose** — For running PostgreSQL locally
- **Git** — For version control

### macOS Installation

If you don't have these tools installed, use Homebrew:

```bash
# Install pyenv (Python version manager)
brew install pyenv

# Install Docker Desktop (includes Docker and Docker Compose)
brew install --cask docker

# Verify installations
pyenv --version
docker --version
docker-compose --version
```

### Step 1: Install and Configure pyenv

#### 1a. Install pyenv (if not already installed)

```bash
# Install pyenv using Homebrew
brew install pyenv

# Verify installation
pyenv --version
```

#### 1b. Configure Your Shell

Add pyenv to your shell configuration file (`.zshrc` for zsh, `.bash_profile` for bash):

```bash
# For zsh (default on macOS Monterey and later)
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc

# For bash
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bash_profile
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bash_profile
echo 'eval "$(pyenv init -)"' >> ~/.bash_profile

# Reload your shell configuration
exec $SHELL
```

#### 1c. Verify pyenv Setup

```bash
# Check if pyenv is properly configured
pyenv --version

# List available Python versions
pyenv versions

# List installable Python versions
pyenv install --list | grep "3.12"
```

### Step 2: Install Python 3.12 with pyenv

```bash
# Install Python 3.12 (latest stable version)
pyenv install 3.12.0

# Verify installation
pyenv versions

# You should see output like:
#   system
#   3.12.0
```

### Step 3: Set Python Version for the Project

Navigate to the project directory and set the local Python version:

```bash
# Navigate to the project directory
cd talentKru-server

# Set Python 3.12 as the local version for this project
pyenv local 3.12.0

# Verify the version is set
pyenv local

# Verify Python is using the correct version
python --version  # Should show Python 3.12.0
```

This creates a `.python-version` file in the project root that tells pyenv which Python version to use.

### Step 4: Install Docker Desktop

```bash
# Install Docker Desktop (includes Docker and Docker Compose)
brew install --cask docker

# Start Docker Desktop (if not already running)
open /Applications/Docker.app

# Verify Docker is running
docker --version
docker-compose --version
```

---

## Installation

### Step 1: Install `uv` (Python Package Manager)

`uv` is a fast, modern Python package manager that we'll use alongside poetry.

```bash
# Install uv using pip
pip install uv

# Verify installation
uv --version
```

For more details, see the [uv installation guide](https://docs.astral.sh/uv/getting-started/installation/).

### Step 2: Install `poetry` (Dependency Management)

Poetry manages project dependencies and virtual environments.

```bash
# Install poetry using uv
uv pip install poetry

# Verify installation
poetry --version
```

### Step 3: Install `invoke` (Task Runner)

Invoke is a task runner that automates common development tasks.

```bash
# Install invoke using poetry
poetry add invoke --group dev

# Verify installation
uv run invoke --version
```

### Step 4: Clone and Navigate to the Project

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd talentKru-server

# Verify you're in the correct directory
pwd  # Should end with /talentKru-server
```

### Step 5: Verify Python Version

```bash
# Verify pyenv is using the correct Python version
python --version  # Should show Python 3.12.x

# If not, set it again
pyenv local 3.12.0
```

### Step 6: Install Project Dependencies

```bash
# Install all dependencies (including dev dependencies)
uv sync

# Verify installation
uv show  # Lists all installed packages
```

---

## Environment Configuration

### Step 1: Create `.env` File

The application requires environment variables for database connection, security keys, and other settings.

```bash
# Copy the example environment file
cp .env.example .env

# Edit the .env file with your local configuration
nano .env  # or use your preferred editor
```

### Step 2: Configure Required Variables

Edit `.env` and set the following **required** variables:

```env
# Database Configuration
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=talentkru
DATABASE_USER=talentkru
DATABASE_PASSWORD=talentkru_secret

# Security Keys (must be at least 32 characters)
JWT_SIGNING_KEY=your_jwt_signing_key_min_32_chars_long
ENCRYPTION_KEY=your_encryption_key_min_32_chars_long

# Storage Backend (local for development)
STORAGE_BACKEND=local
STORAGE_LOCAL_PATH=/data/resumes

# Agent API Key (for internal agent requests)
AGENT_API_KEY=your_agent_api_key_min_32_chars

# Metrics Authentication
METRICS_USERNAME=metrics
METRICS_PASSWORD=metrics_password_min_32_chars

# Application Version
APP_VERSION=0.1.0
```

**Note:** For local development, you can use simple placeholder values for security keys. For production, use strong, randomly generated keys.

### Step 3: Create Local Data Directory

```bash
# Create the directory for storing resumes locally
mkdir -p /data/resumes

# Verify the directory was created
ls -la /data/resumes
```

---

## Database Setup

### Step 1: Start PostgreSQL with Invoke

```bash
# Start the PostgreSQL database container
uv run invoke db-start

# Verify the database is running
docker ps  # Should show the PostgreSQL container
```

The database will be available at `localhost:5432` with credentials from your `.env` file.

### Step 2: Initialize Database Users and Schemas

PostgreSQL extensions (vector, uuid-ossp) are now pre-created as superuser during initialization.

```bash
# Initialize main app database users, schemas, and extensions
uv run invoke db-init-users

# Initialize test database users, schemas, extensions, and migrations
uv run invoke db-init-test
```

These tasks:
- Create database users (`kru_app`, `kru_test`)
- Create schemas (`kru_app`, `kru_test`)
- Create PostgreSQL extensions as superuser (`vector`, `uuid-ossp`)
- Grant necessary privileges to application users
- Set default schema for users

### Step 3: Run Database Migrations

Alembic manages database schema migrations.

#### For Application Database

```bash
# Run all pending migrations to app database
uv run invoke migrate

# Verify migrations were applied
uv run invoke db-status

# Get current migration version
uv run alembic current
```

#### For Test Database

```bash
# Run all pending migrations to test database
uv run invoke migrate-test

# Verify test database migrations were applied
TEST_DATABASE_HOST=localhost \
TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db \
TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026 \
uv run alembic current
```

#### Direct Alembic Commands (Advanced)

```bash
# Apply migrations to app database directly
uv run alembic upgrade head

# Apply migrations to test database directly
TEST_DATABASE_HOST=localhost \
TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db \
TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026 \
DATABASE_HOST=localhost \
DATABASE_PORT=5432 \
DATABASE_NAME=kru_test_db \
DATABASE_USER=kru_test \
DATABASE_PASSWORD=kruTest2026 \
uv run alembic upgrade head

# Downgrade app database by 1 migration
uv run alembic downgrade -1

# Downgrade test database by 1 migration
TEST_DATABASE_HOST=localhost \
TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db \
TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026 \
uv run alembic downgrade -1

# Rollback all migrations (development only)
uv run alembic downgrade base

# Create a new migration after model changes
uv run invoke db-revision --message "Add new_column to users table"
```

### Step 4: Verify Database Connection

```bash
# Test the application database connection
uv run invoke db-check

# Connect to app database via psql
psql -h localhost -p 5432 -U kru_app -d kru_app_db

# Connect to test database via psql
psql -h localhost -p 5432 -U kru_test -d kru_test_db
```

You should see output confirming both database connections are successful.

### Step 5: Verify Extensions Are Created

```bash
# Check vector extension in app database
psql -h localhost -U postgres -d kru_app_db -c "\dx vector"

# Check vector extension in test database
psql -h localhost -U postgres -d kru_test_db -c "\dx vector"

# Check uuid-ossp extension in both databases
psql -h localhost -U postgres -d kru_app_db -c "\dx uuid-ossp"
psql -h localhost -U postgres -d kru_test_db -c "\dx uuid-ossp"
```

Expected output shows both extensions installed:
```
             List of installed extensions
  Name  | Version |   Schema   |              Description              
--------+---------+------------+---------------------------------------
 vector | 0.7.0   | public     | vector data type for similarity search
```

---

## PostgreSQL Command-Line Client (psql)

The `psql` utility allows you to connect to PostgreSQL directly from your terminal for running queries and managing the database.

### Step 1: Install psql

On macOS, install the PostgreSQL client tools using Homebrew:

```bash
# Install libpq (includes psql)
brew install libpq

# Verify installation
psql --version
```

### Step 2: Add psql to Your PATH

Add the libpq binary directory to your shell's PATH so you can run `psql` from anywhere:

```bash
# For zsh (default on macOS Monterey and later)
echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# For bash
echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >> ~/.bash_profile
source ~/.bash_profile

# Verify psql is now accessible
which psql  # Should show /opt/homebrew/opt/libpq/bin/psql
```

### Step 3: Connect to the Database

You can connect to PostgreSQL using either the application user or the admin user.

#### Connect as the Application User

Use the application credentials created for your project:

```bash
# Using command-line arguments
psql -h localhost -p 5432 -U talentkru_app -d krudb

# Or using a connection string
psql postgresql://talentkru_app@localhost:5432/krudb
```

#### Connect as the Admin User

Use the default PostgreSQL admin credentials:

```bash
# Using command-line arguments
psql -h localhost -p 5432 -U postgres -d krudb
```

### Step 4: Common psql Commands

Once connected, you can run SQL queries and commands:

```sql
-- List all databases
\l

-- Connect to a specific database
\c krudb

-- List all tables in the current schema
\dt

-- Describe a specific table
\d table_name

-- List all schemas
\dn

-- Show current user
\conninfo

-- Exit psql
\q
```

### Example: Querying the Database

```bash
# Connect as the application user
psql -h localhost -p 5432 -U talentkru_app -d krudb

# Once connected, run a query
SELECT * FROM talentkru.users LIMIT 5;

# Exit
\q
```

---

## pgAdmin Web UI

pgAdmin4 is a browser-based database management tool. Use it to inspect tables, run queries, and manage your local PostgreSQL instance.

### Step 1: Configure pgAdmin Environment Variables

Add the following to your `.env` file (copy from `.env.example` if not already present):

```env
PGADMIN_DEFAULT_EMAIL=admin@example.com
PGADMIN_DEFAULT_PASSWORD=your_pgadmin_password
PGADMIN_CONTAINER_NAME=local-pgadmin4
PGADMIN_PORT=8080
```

### Step 2: Start pgAdmin

```bash
uv run invoke db-admin-start
```

Once started, open your browser and navigate to **http://localhost:8080**.

### Step 3: Log In

Use the credentials you set in `.env`:

| Field    | Value                          |
|----------|--------------------------------|
| Email    | `PGADMIN_DEFAULT_EMAIL`        |
| Password | `PGADMIN_DEFAULT_PASSWORD`     |

### Step 4: Register the Database Server

After logging in, register your local PostgreSQL instance:

1. In the left panel, right-click **Servers → Register → Server…**
2. On the **General** tab, enter a name (e.g. `TalentKru Local`)
3. Switch to the **Connection** tab and fill in:

| Field                | Value                                                                 |
|----------------------|-----------------------------------------------------------------------|
| Host name/address    | `host.docker.internal` (pgAdmin runs in Docker) or `localhost`        |
| Port                 | `5432`                                                                |
| Maintenance database | `postgres`                                                            |
| Username             | `postgres`                                                            |
| Password             | value of `PG_ADMIN_PASSWORD` in your `.env`                          |
| Service              | *(leave blank)*                                                       |

4. Click **Save**. The server will appear in the left panel and you can start browsing databases and running queries.

> **Tip:** Use `host.docker.internal` as the host when pgAdmin is running inside Docker (which it is when started via `invoke db-admin-start`). If you ever run pgAdmin outside Docker, use `localhost` instead.

### Step 5: Stop pgAdmin

```bash
uv run invoke db-admin-stop
```

---

## Running the Application

### Option 1: Run with Invoke (Recommended)

```bash
# Start the development server
uv run invoke dev

# The server will be available at http://localhost:8000
```

### Option 2: Run with Uvicorn Directly

```bash
# Activate the poetry virtual environment
# Or activate virtualenv from .venv/bin

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Exit the virtual environment when done
exit
```

### Option 3: Run with Docker Compose

```bash
# Start both the database and application
docker-compose up

# The server will be available at http://localhost:8000
# The database will be available at localhost:5432
```

---

## Available Tasks

Invoke provides convenient shortcuts for common development tasks. View all available tasks:

```bash
uv run invoke --list
```

### Common Database Tasks

| Task | Command | Description |
|------|---------|-------------|
| **Start Database** | `uv run invoke db-start` | Start the PostgreSQL container |
| **Stop Database** | `uv run invoke db-stop` | Stop the PostgreSQL container (data persists) |
| **Remove Database** | `uv run invoke db-remove` | Remove PostgreSQL container and volume (deletes all data) |
| **Init App Database** | `uv run invoke db-init-users` | Create app DB, users, schemas, and extensions |
| **Init Test Database** | `uv run invoke db-init-test` | Create test DB, users, schemas, extensions, and migrations |
| **Check Connection** | `uv run invoke db-check` | Test database connection |
| **Database Status** | `uv run invoke db-status` | Show current migration status of app database |
| **Apply Migrations** | `uv run invoke migrate` | Apply all pending migrations to app database |
| **Apply Test Migrations** | `uv run invoke migrate-test` | Apply all pending migrations to test database |
| **Rollback Migration** | `uv run invoke migrate-down` | Rollback last migration from app database |
| **Reset Migrations** | `uv run invoke migrate-reset` | Downgrade all and re-apply all migrations (app DB) |
| **Reset Test Migrations** | `uv run invoke migrate-reset-test` | Downgrade all and re-apply all migrations (test DB) |
| **Create Migration** | `uv run invoke db-revision --message "..."` | Create new migration after model changes |
| **Start pgAdmin** | `uv run invoke db-admin-start` | Start pgAdmin4 web interface (port 8080) |
| **Stop pgAdmin** | `uv run invoke db-admin-stop` | Stop pgAdmin4 |

### Common Application Tasks

| Task | Command | Description |
|------|---------|-------------|
| **Start Dev Server** | `uv run invoke dev` | Run the FastAPI server with auto-reload |
| **Run Tests** | `uv run invoke test` | Run the test suite with pytest |
| **Run Tests with Coverage** | `uv run invoke test-cov` | Run tests and generate coverage report |
| **Watch Tests** | `uv run invoke test-watch` | Run tests in watch mode (re-run on changes) |
| **Lint Code** | `uv run invoke lint` | Check code style with ruff |
| **Format Code** | `uv run invoke format` | Auto-format code with ruff |
| **Format Check** | `uv run invoke format-check` | Check if code needs formatting |
| **Type Check** | `uv run invoke type-check` | Run type checking with mypy |
| **Full Check** | `uv run invoke check` | Run all checks (lint, format-check, type-check) |
| **Clean Cache** | `uv run invoke clean` | Clean Python cache files |
| **Show Dependencies** | `uv run invoke show-deps` | Show all installed dependencies |
| **Setup Dev Environment** | `uv run invoke dev-setup` | Start DB and apply migrations (quick setup) |
| **Complete Setup** | `uv run invoke setup` | Install deps, start DB, migrate (full setup) |

### Example: Running Tests

```bash
# Run all tests
uv run invoke test

# Run tests with coverage report
uv run invoke test-cov

# Run tests for a specific module
uv run invoke test --path tests/modules/auth/
```

### Example: Code Quality

```bash
# Check code style
uv run invoke lint

# Auto-format code
uv run invoke format
```

---

## Accessing the Application

Once the server is running, you can access:

- **API Documentation (Swagger UI):** http://localhost:8000/docs
- **Alternative API Docs (ReDoc):** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health
- **OpenAPI Schema:** http://localhost:8000/openapi.json

### Example: Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

---

## Stopping Services

### Stop the Development Server

```bash
# If running with invoke dev or uvicorn
Press Ctrl+C in the terminal
```

### Stop the Database

```bash
# Stop PostgreSQL container (data persists in volume)
uv run invoke db-stop

# Remove PostgreSQL container and optionally volume
uv run invoke db-remove
```

### Stop pgAdmin

```bash
# Stop pgAdmin4 container
uv run invoke db-admin-stop
```

### Stop All Services

```bash
# Quick teardown of development environment
uv run invoke dev-teardown

# This stops the PostgreSQL container (data persists)
# To also remove the container and volume, run:
uv run invoke db-remove
```

---

## Database Setup Reference

### Complete Setup Commands

#### Fresh Start (First Time)

```bash
# Step 1: Start PostgreSQL
uv run invoke db-start

# Step 2: Create app database (with extensions)
uv run invoke db-init-users

# Step 3: Create test database (with extensions and migrations)
uv run invoke db-init-test

# Step 4: Apply migrations to app database
uv run invoke migrate

# Step 5: Verify both databases
uv run invoke db-status
uv run db-check
```

#### Quick Development Setup

```bash
# All-in-one setup command
uv run invoke dev-setup  # Starts DB and applies migrations

# Or manual quick setup
uv run invoke db-start
uv run invoke db-init-users
uv run invoke db-init-test
uv run invoke migrate
uv run invoke migrate-test
```

### Migration Workflows

#### Working with Migrations

```bash
# View pending migrations
uv run alembic history --verbose

# Apply all pending migrations to app DB
uv run invoke migrate

# Apply all pending migrations to test DB
uv run invoke migrate-test

# Rollback 1 migration from app DB
uv run alembic downgrade -1

# Rollback 1 migration from test DB
TEST_DATABASE_HOST=localhost \
TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db \
TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026 \
uv run alembic downgrade -1

# Rollback all migrations and re-apply (app DB)
uv run invoke migrate-reset

# Rollback all migrations and re-apply (test DB)
uv run invoke migrate-reset-test
```

#### Creating and Testing Migrations

```bash
# 1. Modify your SQLAlchemy models in app/modules/*/models.py

# 2. Generate migration
uv run invoke db-revision --message "Brief description of change"

# 3. Review the migration file in alembic/versions/

# 4. Test forward application
uv run invoke migrate

# 5. Test rollback
uv run alembic downgrade -1

# 6. Test re-apply
uv run alembic upgrade +1

# 7. Do the same for test database
uv run invoke migrate-test
TEST_DATABASE_HOST=localhost TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026 uv run alembic downgrade -1
TEST_DATABASE_HOST=localhost TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026 uv run alembic upgrade +1
```

### Environment Variables for Test Database

When running alembic commands directly on the test database, set these environment variables:

```bash
export TEST_DATABASE_HOST=localhost
export TEST_DATABASE_PORT=5432
export TEST_DATABASE_NAME=kru_test_db
export TEST_DATABASE_USER=kru_test
export TEST_DATABASE_PASSWORD=kruTest2026

# Now you can use alembic commands
uv run alembic current
uv run alembic upgrade head
uv run alembic downgrade -1
```

Or use inline environment variables:

```bash
TEST_DATABASE_HOST=localhost \
TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db \
TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026 \
uv run alembic current
```

### Alembic Direct Commands

| Command | App DB | Test DB |
|---------|--------|---------|
| View current version | `uv run alembic current` | `TEST_DB_VARS uv run alembic current` |
| View history | `uv run alembic history -v` | `TEST_DB_VARS uv run alembic history -v` |
| Apply all pending | `uv run alembic upgrade head` | `TEST_DB_VARS uv run alembic upgrade head` |
| Rollback 1 | `uv run alembic downgrade -1` | `TEST_DB_VARS uv run alembic downgrade -1` |
| Rollback all | `uv run alembic downgrade base` | `TEST_DB_VARS uv run alembic downgrade base` |
| Create migration | `uv run invoke db-revision --message "..."` | (Uses app DB) |

Where `TEST_DB_VARS` = 
```bash
TEST_DATABASE_HOST=localhost \
TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db \
TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026
```

### psql Commands for Both Databases

```bash
# Connect to app database as app user
psql -h localhost -p 5432 -U kru_app -d kru_app_db

# Connect to test database as test user
psql -h localhost -p 5432 -U kru_test -d kru_test_db

# Connect as admin to app database
psql -h localhost -p 5432 -U postgres -d kru_app_db

# Connect as admin to test database
psql -h localhost -p 5432 -U postgres -d kru_test_db

# Useful psql commands
\l              # List all databases
\dt             # List all tables in current schema
\dn             # List all schemas
\dx             # List installed extensions
\conninfo       # Show current connection info
\d table_name   # Describe a table
\q              # Quit psql
```

### PostgreSQL Extension Verification

```bash
# Check vector extension in app database
psql -h localhost -U postgres -d kru_app_db -c "\dx vector"

# Check vector extension in test database
psql -h localhost -U postgres -d kru_test_db -c "\dx vector"

# Check uuid-ossp in app database
psql -h localhost -U postgres -d kru_app_db -c "\dx uuid-ossp"

# Check uuid-ossp in test database
psql -h localhost -U postgres -d kru_test_db -c "\dx uuid-ossp"

# List all extensions
psql -h localhost -U postgres -d kru_app_db -c "\dx"
```

---

## Troubleshooting

### Issue: pyenv Not Found

**Problem:** `pyenv: command not found`

**Solution:**
```bash
# Verify pyenv is installed
brew list pyenv

# If not installed, install it
brew install pyenv

# Add pyenv to your shell configuration
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc

# Reload your shell
exec $SHELL

# Verify installation
pyenv --version
```

### Issue: Python Version Not Switching

**Problem:** `python --version` shows wrong version even after `pyenv local 3.12.0`

**Solution:**
```bash
# Verify .python-version file exists in project root
cat .python-version  # Should show 3.12.0

# Verify pyenv is properly initialized in your shell
echo $PYENV_ROOT  # Should show /Users/username/.pyenv

# Reload your shell
exec $SHELL

# Verify the correct Python is being used
which python  # Should show path with .pyenv
python --version  # Should show Python 3.12.x

# If still not working, reinstall Python 3.12
pyenv uninstall 3.12.0
pyenv install 3.12.0
pyenv local 3.12.0
```

### Issue: Python 3.12 Installation Fails

**Problem:** `BUILD FAILED` when running `pyenv install 3.12.0`

**Solution:**
```bash
# Install required build dependencies
brew install openssl readline sqlite3 xz zlib

# Try installing again
pyenv install 3.12.0

# If still failing, check the build logs
pyenv install -v 3.12.0  # Verbose output shows what went wrong
```

### Issue: Database Connection Refused

**Problem:** `psycopg2.OperationalError: could not connect to server`

**Solution:**
```bash
# Verify PostgreSQL is running
docker ps  # Should show the PostgreSQL container

# Check database logs
docker logs local-postgresql-db  # Or your PG_CONTAINER_NAME

# Restart the database
uv run invoke db-stop
uv run invoke db-start

# Verify connection
uv run invoke db-check
```

### Issue: Port Already in Use

**Problem:** `Address already in use` when starting the server

**Solution:**
```bash
# Find the process using port 8000
lsof -i :8000

# Kill the process (replace PID with the actual process id)
kill -9 <PID>

# Or use a different port
uvicorn app.main:app --port 8001
```

### Issue: Migration Errors

**Problem:** `alembic.util.exc.CommandError: Can't locate revision identified by` or `DuplicateTableError`

**Solution:**
```bash
# Check migration status
uv run invoke db-status

# For app database:
# Reset the database (WARNING: This deletes all data)
uv run invoke db-remove  # Choose 'y' to remove volume
uv run invoke db-start
uv run invoke db-init-users
uv run invoke migrate

# For test database:
# Reset the test database
uv run invoke db-remove  # Removes both app and test
uv run invoke db-start
uv run invoke db-init-users
uv run invoke db-init-test
```

### Issue: Extension Permission Error

**Problem:** `asyncpg.exceptions.InsufficientPrivilegeError: permission denied to create extension "vector"`

**Solution:**
```bash
# Extensions are now pre-created as superuser during db-init
# If you still get this error, reinitialize:

uv run invoke db-init-users  # Creates extensions in app DB as superuser
uv run invoke db-init-test   # Creates extensions in test DB as superuser
uv run invoke migrate        # Apply migrations
uv run invoke migrate-test   # Apply test migrations

# Verify extensions exist:
psql -h localhost -U postgres -d kru_app_db -c "\dx"
psql -h localhost -U postgres -d kru_test_db -c "\dx"
```

### Issue: Test Database Not Initialized

**Problem:** `psycopg2.OperationalError: FATAL: database "kru_test_db" does not exist`

**Solution:**
```bash
# Initialize test database (creates DB, schema, user, extensions, migrations)
uv run invoke db-init-test

# Verify test database exists
psql -h localhost -U postgres -l | grep kru_test_db

# Verify migrations were applied
TEST_DATABASE_HOST=localhost \
TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db \
TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026 \
uv run alembic current
```

### Issue: Migration Rollback/Re-apply Not Working

**Problem:** Can't rollback or re-apply migrations

**Solution:**
```bash
# For app database - full reset
uv run invoke migrate-reset  # Downgrades all, then re-applies all

# For test database - full reset
uv run invoke migrate-reset-test  # Downgrades all, then re-applies all

# Or manually step by step
uv run alembic current           # Check current version
uv run alembic downgrade base    # Rollback all
uv run alembic upgrade head      # Re-apply all
```

### Issue: Virtual Environment Issues

**Problem:** `poetry: command not found` or dependency conflicts

**Solution:**
```bash
# Verify you're using the correct Python version
python --version  # Should show Python 3.12.x

# Reinstall poetry
uv pip install --force-reinstall poetry

# Clear poetry cache
poetry cache clear . --all

# Reinstall dependencies
uv sync --no-cache

# Verify installation
uv show
```

### Issue: Docker Not Running

**Problem:** `Cannot connect to Docker daemon`

**Solution:**
```bash
# Start Docker Desktop (macOS)
open /Applications/Docker.app

# Or start Docker service (Linux)
sudo systemctl start docker

# Verify Docker is running
docker ps
```

---

## Development Workflow

### Managing Python Versions with pyenv

```bash
# View all installed Python versions
pyenv versions

# Install a new Python version
pyenv install 3.12.0

# Set Python version globally (affects all projects)
pyenv global 3.12.0

# Set Python version for current project (creates .python-version file)
pyenv local 3.12.0

# Uninstall a Python version
pyenv uninstall 3.12.0

# Verify which Python is being used
which python
python --version
```

### Typical Development Session

```bash
# 1. Navigate to the project (pyenv automatically switches to 3.12.0)
cd talentKru-server

# 2. Verify correct Python version is active
python --version  # Should show Python 3.12.x

# 3. Start the database
uv run invoke db-start

# 4. Initialize app and test databases (includes extensions)
uv run invoke db-init-users
uv run invoke db-init-test

# 5. Apply migrations to both databases
uv run invoke migrate           # App DB
uv run invoke migrate-test      # Test DB

# 6. Start the development server
uv run invoke dev

# 7. In another terminal, run tests as you develop
uv run invoke test

# 8. Check code quality
uv run invoke lint
uv run invoke format-check

# 9. When done, stop the server (Ctrl+C) and database
uv run invoke db-stop
```

### Testing Migrations Locally

```bash
# Full roundtrip: forward → rollback → re-apply

# 1. Apply all migrations to app database
uv run invoke migrate

# 2. Check current migration version
uv run invoke db-status

# 3. Rollback the latest migration (app DB)
uv run alembic downgrade -1

# 4. Verify it rolled back
uv run alembic current  # Should show previous migration

# 5. Re-apply the migration
uv run alembic upgrade +1

# 6. Verify it applied successfully
uv run invoke db-status  # Should show latest migration

# Same for test database:
uv run invoke migrate-test                                          # Apply
TEST_DATABASE_HOST=localhost TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026 uv run alembic current          # Check
TEST_DATABASE_HOST=localhost TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026 uv run alembic downgrade -1     # Rollback
TEST_DATABASE_HOST=localhost TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026 uv run alembic upgrade +1       # Re-apply
```

### Creating Database Migrations

When you modify SQLAlchemy models, you need to create a database migration:

```bash
# After modifying models in app/modules/*/models.py, create a new migration
uv run invoke db-revision --message "Add new_column to users table"

# This creates a new file in alembic/versions/ with the migration
# Review the generated migration file for correctness

# Apply the migration to app database
uv run invoke migrate

# Apply the migration to test database
uv run invoke migrate-test

# Verify it applied to both
uv run invoke db-status  # App DB
uv run invoke migrate-reset-test  # Test DB migration status
```

### Migration Best Practices

```bash
# Test your migration by running it forward and backward
uv run invoke migrate                # Forward to app DB
uv run alembic downgrade -1         # Rollback from app DB
uv run alembic upgrade +1           # Re-apply to app DB

# Do the same for test database
uv run invoke migrate-test                    # Forward to test DB
TEST_DATABASE_HOST=localhost \
TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db \
TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026 \
uv run alembic downgrade -1                   # Rollback from test DB
TEST_DATABASE_HOST=localhost \
TEST_DATABASE_PORT=5432 \
TEST_DATABASE_NAME=kru_test_db \
TEST_DATABASE_USER=kru_test \
TEST_DATABASE_PASSWORD=kruTest2026 \
uv run alembic upgrade +1                     # Re-apply to test DB
```

For detailed migration patterns, see `.kiro/steering/tech.md` (Database Management section) and `SCHEMA_EVOLUTION_GUIDELINES.md`.

### Running Specific Tests

```bash
# Run all tests (uses test database)
uv run invoke test

# Run tests with coverage report
uv run invoke test-cov

# Run tests in watch mode (re-runs on changes)
uv run invoke test-watch

# Run tests for a specific module
uv run invoke test --path tests/modules/auth/

# Run a specific test file
uv run invoke test --path tests/modules/auth/test_router.py

# Run a specific test function
uv run invoke test --path tests/modules/auth/test_router.py::test_login

# Run tests matching a pattern
uv run pytest -k "test_candidate" -v

# Run tests with verbose output
uv run pytest -v tests/

# Run tests with print statements visible
uv run pytest -s tests/
```

**Note:** All tests use the `kru_test_db` test database. Ensure you've run `uv run invoke db-init-test` before running tests.

---

## Additional Resources

- **FastAPI Documentation:** https://fastapi.tiangolo.com/
- **SQLAlchemy Documentation:** https://docs.sqlalchemy.org/
- **Alembic Documentation:** https://alembic.sqlalchemy.org/
- **Poetry Documentation:** https://python-poetry.org/docs/
- **uv Documentation:** https://docs.astral.sh/uv/
- **Invoke Documentation:** http://docs.pyinvoke.org/

---

## Next Steps

1. ✅ Complete the setup steps above
2. 📖 Read the [README.md](./README.md) for project overview
3. 🏗️ Review the [design documentation](./docs/) for architecture details
4. 🧪 Run the test suite to verify everything works
5. 🚀 Start developing!

---

## Support

If you encounter issues not covered in this guide:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review Docker and PostgreSQL logs: `docker-compose logs`
3. Verify your `.env` configuration matches the database credentials
4. Ensure all prerequisites are installed and up to date

Happy coding! 🚀
