# TalentKru.ai Server — Local Development Setup

This guide provides step-by-step instructions for setting up and running the TalentKru.ai server locally using **uv**, **poetry**, and **poe** for dependency management and task automation.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Environment Configuration](#environment-configuration)
4. [Database Setup](#database-setup)
5. [Running the Application](#running-the-application)
6. [Available Tasks](#available-tasks)
7. [Troubleshooting](#troubleshooting)

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

### Step 3: Install `poe` (Task Runner)

Poe is a task runner that automates common development tasks.

```bash
# Install poe using uv
uv pip install poethepoet

# Verify installation
poe --version
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
poetry install

# Verify installation
poetry show  # Lists all installed packages
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

### Step 1: Start PostgreSQL with Docker Compose

```bash
# Start the PostgreSQL database service
docker-compose up -d postgres

# Verify the database is running
docker-compose ps

# Check database health
docker-compose logs postgres
```

The database will be available at `localhost:5432` with credentials from your `.env` file.

### Step 2: Run Database Migrations

Alembic manages database schema migrations.

```bash
# Run all pending migrations
poe migrate

# Verify migrations were applied
poe db-status
```

### Step 3: Verify Database Connection

```bash
# Test the database connection
poe db-check
```

You should see output confirming the database connection is successful.

---

## Running the Application

### Option 1: Run with Poe (Recommended)

```bash
# Start the development server
poe dev

# The server will be available at http://localhost:8000
```

### Option 2: Run with Uvicorn Directly

```bash
# Activate the poetry virtual environment
poetry shell

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

Poe provides convenient shortcuts for common development tasks. View all available tasks:

```bash
poe --help
```

### Common Tasks

| Task | Command | Description |
|------|---------|-------------|
| **Start Dev Server** | `poe dev` | Run the FastAPI server with auto-reload |
| **Run Tests** | `poe test` | Run the test suite with pytest |
| **Run Tests with Coverage** | `poe test-cov` | Run tests and generate coverage report |
| **Lint Code** | `poe lint` | Check code style with ruff |
| **Format Code** | `poe format` | Auto-format code with ruff |
| **Database Migrations** | `poe migrate` | Apply pending database migrations |
| **Database Status** | `poe db-status` | Show current migration status |
| **Database Check** | `poe db-check` | Test database connection |
| **Type Check** | `poe type-check` | Run type checking with mypy (if configured) |

### Example: Running Tests

```bash
# Run all tests
poe test

# Run tests with coverage report
poe test-cov

# Run tests for a specific module
poe test tests/modules/auth/
```

### Example: Code Quality

```bash
# Check code style
poe lint

# Auto-format code
poe format
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
# If running with poe dev or uvicorn
Press Ctrl+C in the terminal

# If running with Docker Compose
docker-compose down
```

### Stop Only the Database

```bash
# Stop PostgreSQL without removing data
docker-compose stop postgres

# Stop and remove the database container (data persists in volume)
docker-compose down postgres
```

### Stop All Services

```bash
# Stop all services and remove containers (data persists in volumes)
docker-compose down

# Stop all services and remove everything including volumes
docker-compose down -v
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
docker-compose ps

# Check database logs
docker-compose logs postgres

# Restart the database
docker-compose restart postgres

# Verify connection with psql
docker-compose exec postgres psql -U talentkru -d talentkru -c "SELECT 1"
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

**Problem:** `alembic.util.exc.CommandError: Can't locate revision identified by`

**Solution:**
```bash
# Check migration status
poe db-status

# Reset the database (WARNING: This deletes all data)
docker-compose down -v postgres
docker-compose up -d postgres

# Re-run migrations
poe migrate
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
poetry install --no-cache

# Verify installation
poetry show
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
docker-compose up -d postgres

# 4. Start the development server
poe dev

# 5. In another terminal, run tests as you develop
poe test

# 6. Check code quality
poe lint

# 7. When done, stop the server (Ctrl+C) and database
docker-compose down
```

### Creating Database Migrations

```bash
# After modifying models, create a new migration
alembic revision --autogenerate -m "Add new_column to users table"

# Review the generated migration file in alembic/versions/

# Apply the migration
poe migrate
```

### Running Specific Tests

```bash
# Run tests for a specific module
poe test tests/modules/auth/

# Run a specific test file
poe test tests/modules/auth/test_router.py

# Run a specific test function
poe test tests/modules/auth/test_router.py::test_login
```

---

## Additional Resources

- **FastAPI Documentation:** https://fastapi.tiangolo.com/
- **SQLAlchemy Documentation:** https://docs.sqlalchemy.org/
- **Alembic Documentation:** https://alembic.sqlalchemy.org/
- **Poetry Documentation:** https://python-poetry.org/docs/
- **uv Documentation:** https://docs.astral.sh/uv/
- **Poe Documentation:** https://poethepoet.naivelyoptimistic.com/

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
