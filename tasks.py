"""
TalentKru.ai Server - Invoke Tasks

This module defines all development tasks using Invoke.
Run 'invoke --list' to see all available tasks.
Run 'invoke <task-name>' to execute a task.
"""

import os
import sys
import subprocess
from pathlib import Path
from invoke import task, Collection
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent


# ============================================================================
# Helper Functions
# ============================================================================


def get_env_var(var_name, default=None):
    """Get environment variable value."""
    value = os.getenv(var_name, default)
    if value is None:
        raise ValueError(f"Environment variable '{var_name}' is not set")
    return value


def execute_sql_script(host, port, user, password, database, script_path):
    """Execute SQL script against PostgreSQL database."""
    script_path = Path(script_path)
    if not script_path.exists():
        raise FileNotFoundError(f"SQL script not found: {script_path}")

    # Read SQL script
    with open(script_path, "r") as f:
        sql_commands = f.read()

    # Execute SQL using psql
    env = os.environ.copy()
    env["PGPASSWORD"] = password

    try:
        result = subprocess.run(
            [
                "psql",
                "-h",
                host,
                "-p",
                str(port),
                "-U",
                user,
                "-d",
                database,
                "-f",
                str(script_path),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"❌ Error executing SQL script: {result.stderr}")
            raise RuntimeError(f"SQL execution failed: {result.stderr}")

        print(f"✅ SQL script executed successfully")
        if result.stdout:
            print(result.stdout)

    except subprocess.TimeoutExpired:
        raise RuntimeError("SQL script execution timed out")
    except FileNotFoundError:
        raise RuntimeError(
            "psql command not found. Please install PostgreSQL client tools."
        )


# ============================================================================
# Development Tasks
# ============================================================================


@task(help={"port": "Port to run the server on (default: 8000)"})
def dev(c, port=8000):
    """Start the FastAPI development server with auto-reload."""
    print(f"🚀 Starting development server on port {port}...")
    c.run(
        f"uvicorn app.main:app --reload --host 0.0.0.0 --port {port}",
        pty=True,
    )


@task
def dev_quiet(c):
    """Start the development server in quiet mode."""
    print("🚀 Starting development server (quiet mode)...")
    c.run("uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")


# ============================================================================
# Testing Tasks
# ============================================================================


@task(
    help={
        "path": "Path to test file or directory (default: all tests)",
        "verbose": "Verbose output",
        "coverage": "Generate coverage report",
    }
)
def test(c, path="", verbose=False, coverage=False):
    """Run the test suite with pytest."""
    cmd = "pytest"
    if path:
        cmd += f" {path}"
    if verbose:
        cmd += " -v"
    if coverage:
        cmd += " --cov=app --cov-report=html --cov-report=term-missing"

    print(f"🧪 Running tests...")
    c.run(cmd, pty=True)


@task
def test_cov(c):
    """Run tests with coverage report."""
    print("🧪 Running tests with coverage...")
    c.run(
        "pytest --cov=app --cov-report=html --cov-report=term-missing",
        pty=True,
    )


@task
def test_watch(c):
    """Run tests in watch mode (re-runs on file changes)."""
    print("👀 Running tests in watch mode...")
    c.run("pytest-watch", pty=True)


# ============================================================================
# Code Quality Tasks
# ============================================================================


@task
def lint(c):
    """Check code style and quality with Ruff."""
    print("🔍 Checking code style...")
    c.run("ruff check app tests", pty=True)


@task
def format(c):
    """Auto-format code with Ruff."""
    print("✨ Formatting code...")
    c.run("ruff format app tests", pty=True)


@task
def format_check(c):
    """Check if code is properly formatted."""
    print("🔍 Checking code formatting...")
    c.run("ruff format --check app tests", pty=True)


@task
def type_check(c):
    """Run type checking with mypy."""
    print("🔍 Running type checks...")
    c.run("python -m mypy app", pty=True)


@task
def check(c):
    """Run all code quality checks (lint, format-check, test)."""
    print("🔍 Running all checks...")
    lint(c)
    format_check(c)
    test(c)
    print("✅ All checks passed!")


# ============================================================================
# Database Tasks
# ============================================================================


@task
def migrate(c):
    """Apply all pending database migrations."""
    print("📦 Applying database migrations...")
    c.run("alembic upgrade head", pty=True)


@task
def migrate_down(c):
    """Rollback the last database migration."""
    print("⬇️  Rolling back last migration...")
    c.run("alembic downgrade -1", pty=True)


@task
def db_status(c):
    """Show current database migration status."""
    print("📊 Checking database migration status...")
    c.run("alembic current", pty=True)


@task
def db_check(c):
    """Test database connection."""
    print("🔗 Testing database connection...")

    try:
        # Get database configuration from .env
        db_host = get_env_var("DATABASE_HOST", "localhost")
        db_port = get_env_var("DATABASE_PORT", "5432")
        db_name = get_env_var("DATABASE_NAME")
        db_user = get_env_var("DATABASE_USER")
        db_password = get_env_var("DATABASE_PASSWORD")

        print(f"   Host: {db_host}")
        print(f"   Port: {db_port}")
        print(f"   Database: {db_name}")
        print(f"   User: {db_user}")
        print()

        # Test connection using psql
        print("⏳ Attempting to connect...")
        env = os.environ.copy()
        env["PGPASSWORD"] = db_password

        result = subprocess.run(
            [
                "psql",
                "-h",
                db_host,
                "-p",
                str(db_port),
                "-U",
                db_user,
                "-d",
                db_name,
                "-c",
                "SELECT version();",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            print("✅ Database connection successful!")
            print()
            print("📊 PostgreSQL Version:")
            # Extract version from output
            for line in result.stdout.split("\n"):
                if "PostgreSQL" in line:
                    print(f"   {line.strip()}")
            return
        else:
            print("❌ Database connection failed!")
            print()
            print("Error:")
            print(result.stderr)
            sys.exit(1)

    except (ValueError, RuntimeError) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("❌ Connection timeout - database is not responding")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ Error: psql command not found")
        print("   Please install PostgreSQL client tools:")
        print("   macOS: brew install postgresql")
        print("   Ubuntu/Debian: sudo apt-get install postgresql-client")
        sys.exit(1)


@task(help={"message": "Migration description"})
def db_revision(c, message=""):
    """Create a new database migration."""
    if not message:
        print("❌ Error: Migration message is required")
        print("Usage: invoke db-revision --message 'Your migration description'")
        sys.exit(1)
    print(f"📝 Creating migration: {message}")
    c.run(f'alembic revision --autogenerate -m "{message}"', pty=True)


# ============================================================================
# PostgreSQL Docker Tasks
# ============================================================================


@task
def db_start(c):
    """Start PostgreSQL container (reads PG_* from .env)."""
    print("🚀 Starting PostgreSQL container...")

    try:
        # Get PostgreSQL configuration from .env
        pg_container_name = get_env_var("PG_CONTAINER_NAME", "local-postgresql-db")
        pg_image = get_env_var("PG_IMAGE", "pgvector/pgvector:pg17")
        pg_database_name = get_env_var("PG_DATABASE_NAME", "krudb")
        pg_port = get_env_var("PG_PORT", "5432")
        pg_volume_name = get_env_var("PG_VOLUME_NAME", "krudb_data")
        pg_admin_password = get_env_var("PG_ADMIN_PASSWORD")
        postgresql_data_dir = get_env_var("POSTGRESQL_DATA_DIR")

        print(f"   Container Name: {pg_container_name}")
        print(f"   Image: {pg_image}")
        print(f"   Database: {pg_database_name}")
        print(f"   Port: {pg_port}")
        print(f"   Volume: {pg_volume_name}")
        print()

        # Check if container already exists
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if pg_container_name in result.stdout:
            print(f"⚠️  Container '{pg_container_name}' already exists")

            # Check if it's running
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if pg_container_name in result.stdout:
                print("✅ Container is already running")
                return
            else:
                print("🔄 Starting existing container...")
                subprocess.run(
                    ["docker", "start", pg_container_name],
                    check=True,
                    capture_output=True,
                )
                print("✅ Container started")
                return

        # Create volume if it doesn't exist
        result = subprocess.run(
            ["docker", "volume", "ls", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if pg_volume_name not in result.stdout:
            print(f"📦 Creating Docker volume: {pg_volume_name}")
            subprocess.run(
                ["docker", "volume", "create", pg_volume_name],
                check=True,
                capture_output=True,
            )

        # Start the container
        print("⏳ Starting container...")
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                pg_container_name,
                "-e",
                f"POSTGRES_PASSWORD={pg_admin_password}",
                "-e",
                f"POSTGRES_DB={pg_database_name}",
                "-p",
                f"{pg_port}:5432",
                "-v",
                f"{pg_volume_name}:{postgresql_data_dir}",
                pg_image,
            ],
            check=True,
            capture_output=True,
        )

        print("✅ PostgreSQL container started successfully")
        print()
        print("📝 Connection details:")
        print("   Host: localhost")
        print(f"   Port: {pg_port}")
        print(f"   Database: {pg_database_name}")
        print("   Admin User: postgres")
        print("   Admin Password: (from PG_ADMIN_PASSWORD in .env)")
        print()
        print("⏳ Waiting for PostgreSQL to be ready...")

        # Wait for PostgreSQL to be ready
        import time

        max_attempts = 30
        for attempt in range(max_attempts):
            try:
                result = subprocess.run(
                    ["docker", "exec", pg_container_name, "pg_isready", "-U", "postgres"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    print("✅ PostgreSQL is ready!")
                    return
            except subprocess.TimeoutExpired:
                pass

            if attempt < max_attempts - 1:
                print(f"   Attempt {attempt + 1}/{max_attempts}...")
                time.sleep(1)
            else:
                print("❌ PostgreSQL failed to start within timeout")
                sys.exit(1)

    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker error: {e.stderr if e.stderr else e}")
        sys.exit(1)


@task
def db_stop(c):
    """Stop PostgreSQL container."""
    print("🛑 Stopping PostgreSQL container...")

    try:
        pg_container_name = get_env_var("PG_CONTAINER_NAME", "local-postgresql-db")
        print(f"   Container Name: {pg_container_name}")
        print()

        # Check if container exists
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if pg_container_name not in result.stdout:
            print(f"⚠️  Container '{pg_container_name}' does not exist")
            return

        # Check if it's running
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if pg_container_name in result.stdout:
            print("⏳ Stopping container...")
            subprocess.run(
                ["docker", "stop", pg_container_name],
                check=True,
                capture_output=True,
            )
            print("✅ Container stopped")
        else:
            print("ℹ️  Container is not running")

    except (ValueError, RuntimeError) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker error: {e.stderr if e.stderr else e}")
        sys.exit(1)


@task
def db_remove(c):
    """Remove PostgreSQL container and optionally volume."""
    print("🗑️  Removing PostgreSQL container and volume...")

    try:
        pg_container_name = get_env_var("PG_CONTAINER_NAME", "local-postgresql-db")
        pg_volume_name = get_env_var("PG_VOLUME_NAME", "krudb_data")

        print(f"   Container Name: {pg_container_name}")
        print(f"   Volume Name: {pg_volume_name}")
        print()

        # Stop container if running
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if pg_container_name in result.stdout:
            print("⏳ Stopping container...")
            subprocess.run(
                ["docker", "stop", pg_container_name],
                check=True,
                capture_output=True,
            )

        # Remove container if exists
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if pg_container_name in result.stdout:
            print("🗑️  Removing container...")
            subprocess.run(
                ["docker", "rm", pg_container_name],
                check=True,
                capture_output=True,
            )
            print("✅ Container removed")
        else:
            print("ℹ️  Container does not exist")

        # Ask about removing volume
        print()
        print("⚠️  WARNING: Removing the volume will delete all database data!")
        response = input(f"Do you want to remove the volume '{pg_volume_name}'? (y/N) ")

        if response.lower() == "y":
            result = subprocess.run(
                ["docker", "volume", "ls", "--format", "{{.Name}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if pg_volume_name in result.stdout:
                print("🗑️  Removing volume...")
                subprocess.run(
                    ["docker", "volume", "rm", pg_volume_name],
                    check=True,
                    capture_output=True,
                )
                print("✅ Volume removed")
            else:
                print("ℹ️  Volume does not exist")
        else:
            print("ℹ️  Volume preserved")

        print()
        print("✅ Cleanup complete")

    except (ValueError, RuntimeError) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker error: {e.stderr if e.stderr else e}")
        sys.exit(1)


@task
def db_init_users(c):
    """Initialize main database users and schemas from create_user.sql."""
    print("👤 Initializing database users and schemas...")

    try:
        # Get database connection details from .env
        db_host = get_env_var("DATABASE_HOST", "localhost")
        db_port = get_env_var("DATABASE_PORT", "5432")
        db_admin_user = "postgres"
        db_admin_password = get_env_var("PG_ADMIN_PASSWORD")
        db_name = get_env_var("DATABASE_NAME")

        # Execute the SQL script
        sql_script = PROJECT_ROOT / "db-scripts" / "create_user.sql"
        execute_sql_script(
            db_host, db_port, db_admin_user, db_admin_password, db_name, sql_script
        )

        print("✅ Database users and schemas initialized successfully!")

    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


@task
def db_init_test(c):
    """Initialize test database with test users in the same PostgreSQL instance."""
    print("🧪 Initializing test database...")

    try:
        # Get test database configuration from .env
        test_db_host = get_env_var("TEST_DATABASE_HOST", "localhost")
        test_db_port = get_env_var("TEST_DATABASE_PORT", "5432")
        test_db_name = get_env_var("TEST_DATABASE_NAME")
        test_db_user = get_env_var("TEST_DATABASE_USER")
        test_db_password = get_env_var("TEST_DATABASE_PASSWORD")

        # Get PostgreSQL admin credentials
        pg_admin_password = get_env_var("PG_ADMIN_PASSWORD")

        print(f"📍 Using existing PostgreSQL instance")
        print(f"   Host: {test_db_host}")
        print(f"   Port: {test_db_port}")
        print()

        # Test connection to PostgreSQL
        print("🔗 Testing connection to PostgreSQL...")
        env = os.environ.copy()
        env["PGPASSWORD"] = pg_admin_password

        result = subprocess.run(
            [
                "psql",
                "-h",
                test_db_host,
                "-p",
                str(test_db_port),
                "-U",
                "postgres",
                "-c",
                "SELECT 1",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            print(f"❌ Error: Cannot connect to PostgreSQL")
            print(f"   {result.stderr}")
            print()
            print("💡 Make sure PostgreSQL is running:")
            print("   uv run invoke db-start")
            sys.exit(1)

        print("✅ Connected to PostgreSQL")
        print()

        # Create test database if it doesn't exist
        print(f"📦 Creating test database '{test_db_name}' if not exists...")
        result = subprocess.run(
            [
                "psql",
                "-h",
                test_db_host,
                "-p",
                str(test_db_port),
                "-U",
                "postgres",
                "-c",
                f"CREATE DATABASE {test_db_name};",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Ignore error if database already exists
        if result.returncode != 0 and "already exists" not in result.stderr:
            print(f"⚠️  Warning: {result.stderr.strip()}")
        else:
            print(f"✅ Test database ready")

        print()

        # Create test database users and schemas
        print("👤 Creating test database users and schemas...")

        # Create test users and schemas
        sql_commands = f"""
        -- Create test user if not exists
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_user WHERE usename = '{test_db_user}') THEN
                CREATE USER {test_db_user} WITH PASSWORD '{test_db_password}';
            END IF;
        END
        $$;
        
        -- Grant connection privileges
        GRANT CONNECT ON DATABASE {test_db_name} TO {test_db_user};
        
        -- Create test schema if not exists
        -- Schema name matches the user name for simplicity
        CREATE SCHEMA IF NOT EXISTS {test_db_user} AUTHORIZATION {test_db_user};
        
        -- Set search path
        ALTER USER {test_db_user} SET search_path TO {test_db_user}, public;
        """

        result = subprocess.run(
            [
                "psql",
                "-h",
                test_db_host,
                "-p",
                str(test_db_port),
                "-U",
                "postgres",
                "-d",
                test_db_name,
                "-c",
                sql_commands,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"❌ Error creating test users: {result.stderr}")
            sys.exit(1)

        print("✅ Test database users and schemas created successfully!")
        print()

        # Apply migrations to test database
        print("📦 Applying migrations to test database...")
        env = os.environ.copy()
        env["DATABASE_HOST"] = test_db_host
        env["DATABASE_PORT"] = str(test_db_port)
        env["DATABASE_NAME"] = test_db_name
        env["DATABASE_USER"] = test_db_user
        env["DATABASE_PASSWORD"] = test_db_password

        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            print(f"⚠️  Warning: Migration may have issues: {result.stderr}")
        else:
            print("✅ Migrations applied successfully!")

        print()
        print("✅ Test database initialization complete!")
        print(f"   Host: {test_db_host}")
        print(f"   Port: {test_db_port}")
        print(f"   Database: {test_db_name}")
        print(f"   User: {test_db_user}")

    except (ValueError, RuntimeError, FileNotFoundError) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


# ============================================================================
# pgAdmin Docker Tasks
# ============================================================================


@task
def db_admin_start(c):
    """Start pgAdmin4 container (reads PGADMIN_* from .env)."""
    print("🚀 Starting pgAdmin4 container...")

    try:
        pgadmin_email = get_env_var("PGADMIN_DEFAULT_EMAIL")
        pgadmin_password = get_env_var("PGADMIN_DEFAULT_PASSWORD")
        pgadmin_container_name = get_env_var("PGADMIN_CONTAINER_NAME", "local-pgadmin4")
        pgadmin_port = get_env_var("PGADMIN_PORT", "8080")

        print(f"   Container Name: {pgadmin_container_name}")
        print(f"   Port: {pgadmin_port}")
        print(f"   Email: {pgadmin_email}")
        print()

        # Check if container already exists
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if pgadmin_container_name in result.stdout:
            print(f"⚠️  Container '{pgadmin_container_name}' already exists")

            # Check if it's running
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if pgadmin_container_name in result.stdout:
                print("✅ Container is already running")
            else:
                print("🔄 Starting existing container...")
                subprocess.run(
                    ["docker", "start", pgadmin_container_name],
                    check=True,
                    capture_output=True,
                )
                print("✅ Container started")

            print()
            print(f"🌐 pgAdmin4 available at: http://localhost:{pgadmin_port}")
            print(f"   Login email: {pgadmin_email}")
            return

        # Run new container
        print("⏳ Starting container...")
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                pgadmin_container_name,
                "-p",
                f"{pgadmin_port}:80",
                "-e",
                f"PGADMIN_DEFAULT_EMAIL={pgadmin_email}",
                "-e",
                f"PGADMIN_DEFAULT_PASSWORD={pgadmin_password}",
                "dpage/pgadmin4",
            ],
            check=True,
            capture_output=True,
        )

        print("✅ pgAdmin4 container started successfully")
        print()
        print(f"🌐 pgAdmin4 available at: http://localhost:{pgadmin_port}")
        print(f"   Login email: {pgadmin_email}")
        print("   Login password: (from PGADMIN_DEFAULT_PASSWORD in .env)")

    except (ValueError, RuntimeError) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker error: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr or e}")
        sys.exit(1)


@task
def db_admin_stop(c):
    """Stop pgAdmin4 container."""
    print("🛑 Stopping pgAdmin4 container...")

    try:
        pgadmin_container_name = get_env_var("PGADMIN_CONTAINER_NAME", "local-pgadmin4")
        print(f"   Container Name: {pgadmin_container_name}")
        print()

        # Check if container exists
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if pgadmin_container_name not in result.stdout:
            print(f"⚠️  Container '{pgadmin_container_name}' does not exist")
            return

        # Check if it's running
        result = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if pgadmin_container_name in result.stdout:
            print("⏳ Stopping container...")
            subprocess.run(
                ["docker", "stop", pgadmin_container_name],
                check=True,
                capture_output=True,
            )
            print("✅ Container stopped")
        else:
            print("ℹ️  Container is not running")

    except (ValueError, RuntimeError) as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker error: {e.stderr.decode() if isinstance(e.stderr, bytes) else e.stderr or e}")
        sys.exit(1)


# ============================================================================
# Utility Tasks
# ============================================================================


@task
def clean(c):
    """Clean up Python cache files and compiled bytecode."""
    print("🧹 Cleaning up cache files...")
    c.run(
        "find . -type d -name __pycache__ -exec rm -rf {} + && "
        "find . -type f -name '*.pyc' -delete",
        pty=True,
    )


# ============================================================================
# Dependency Management Tasks (uv)
# ============================================================================


@task
def sync(c):
    """Sync project dependencies using uv."""
    print("📦 Syncing dependencies with uv...")
    c.run("uv sync", pty=True)


@task
def sync_no_dev(c):
    """Sync only production dependencies (no dev)."""
    print("📦 Syncing production dependencies...")
    c.run("uv sync --no-dev", pty=True)


@task(help={"package": "Package name to add"})
def add(c, package=""):
    """Add a new dependency using uv."""
    if not package:
        print("❌ Error: Package name is required")
        print("Usage: invoke add --package package_name")
        sys.exit(1)
    print(f"📦 Adding package: {package}")
    c.run(f"uv add {package}", pty=True)


@task(help={"package": "Package name to add as dev dependency"})
def add_dev(c, package=""):
    """Add a new dev dependency using uv."""
    if not package:
        print("❌ Error: Package name is required")
        print("Usage: invoke add-dev --package package_name")
        sys.exit(1)
    print(f"📦 Adding dev package: {package}")
    c.run(f"uv add --dev {package}", pty=True)


@task
def lock_upgrade(c):
    """Update all dependencies to latest versions."""
    print("🔄 Upgrading dependencies...")
    c.run("uv lock --upgrade", pty=True)


@task
def lock_refresh(c):
    """Refresh lock file without upgrading versions."""
    print("🔄 Refreshing lock file...")
    c.run("uv lock", pty=True)


@task
def cache_clean(c):
    """Clean uv cache."""
    print("🧹 Cleaning uv cache...")
    c.run("uv cache clean", pty=True)


@task
def show_deps(c):
    """Show all installed dependencies."""
    print("📚 Installed dependencies:")
    c.run("uv pip list", pty=True)


# Legacy aliases for backwards compatibility
@task
def install(c):
    """Install project dependencies (alias for sync)."""
    print("📦 Installing dependencies...")
    sync(c)


@task
def install_dev(c):
    """Install project dependencies including dev (alias for sync)."""
    print("📦 Installing dependencies (including dev)...")
    sync(c)


@task
def update(c):
    """Update all dependencies (alias for lock-upgrade)."""
    print("🔄 Updating dependencies...")
    lock_upgrade(c)


# ============================================================================
# Workflow Tasks (Composite Tasks)
# ============================================================================


@task
def setup(c):
    """Complete setup: install deps, start DB, apply migrations."""
    print("⚙️  Setting up project...")
    install_dev(c)
    db_start(c)
    migrate(c)
    print("✅ Setup complete!")


@task
def dev_setup(c):
    """Quick development setup: start DB and apply migrations."""
    print("⚙️  Setting up development environment...")
    db_start(c)
    migrate(c)
    print("✅ Development setup complete!")
    print("🚀 Run 'invoke dev' to start the development server")


@task
def dev_teardown(c):
    """Stop development services."""
    print("🛑 Tearing down development environment...")
    db_stop(c)
    print("✅ Development environment stopped")


@task
def reset_db(c):
    """Reset database: remove container, start fresh, apply migrations."""
    print("🔄 Resetting database...")
    db_remove(c)
    db_start(c)
    migrate(c)
    print("✅ Database reset complete!")


# ============================================================================
# Documentation Tasks
# ============================================================================


@task
def docs(c):
    """Show available tasks and their descriptions."""
    print("\n" + "=" * 80)
    print("TalentKru.ai Server - Available Tasks")
    print("=" * 80 + "\n")

    tasks_info = {
        "Dependency Management (uv)": [
            ("sync", "Sync all dependencies (including dev)"),
            ("sync-no-dev", "Sync only production dependencies"),
            ("add --package PKG", "Add a new dependency"),
            ("add-dev --package PKG", "Add a new dev dependency"),
            ("lock-upgrade", "Upgrade all dependencies to latest"),
            ("lock-refresh", "Refresh lock file"),
            ("cache-clean", "Clean uv cache"),
            ("show-deps", "Show all installed dependencies"),
        ],
        "Development": [
            ("dev [--port PORT]", "Start FastAPI dev server with auto-reload"),
            ("dev-quiet", "Start dev server in quiet mode"),
        ],
        "Testing": [
            ("test [--path PATH] [--verbose] [--coverage]", "Run test suite"),
            ("test-cov", "Run tests with coverage report"),
            ("test-watch", "Run tests in watch mode"),
        ],
        "Code Quality": [
            ("lint", "Check code style with Ruff"),
            ("format", "Auto-format code"),
            ("format-check", "Check code formatting"),
            ("type-check", "Run type checking"),
            ("check", "Run all checks (lint, format-check, test)"),
        ],
        "Database": [
            ("migrate", "Apply pending migrations"),
            ("migrate-down", "Rollback last migration"),
            ("db-status", "Show migration status"),
            ("db-check", "Test database connection"),
            ("db-revision --message MSG", "Create new migration"),
        ],
        "PostgreSQL Docker": [
            ("db-start", "Start PostgreSQL container"),
            ("db-stop", "Stop PostgreSQL container"),
            ("db-remove", "Remove PostgreSQL container"),
            ("db-init-users", "Initialize main database users and schemas"),
            ("db-init-test", "Initialize test database with test users"),
        ],
        "pgAdmin": [
            ("db-admin-start", "Start pgAdmin4 container"),
            ("db-admin-stop", "Stop pgAdmin4 container"),
        ],
        "Utilities": [
            ("clean", "Clean cache files"),
        ],
        "Workflows": [
            ("setup", "Complete setup (install, DB, migrations)"),
            ("dev-setup", "Quick dev setup (DB, migrations)"),
            ("dev-teardown", "Stop development services"),
            ("reset-db", "Reset database"),
        ],
    }

    for category, tasks_list in tasks_info.items():
        print(f"\n{category}:")
        print("-" * 80)
        for task_name, description in tasks_list:
            print(f"  invoke {task_name:<40} {description}")

    print("\n" + "=" * 80)
    print("Examples:")
    print("  uv run invoke sync                # Sync dependencies")
    print("  uv run invoke dev                 # Start development server")
    print("  uv run invoke test                # Run all tests")
    print("  uv run invoke check               # Run all checks")
    print("  uv run invoke db-start            # Start PostgreSQL")
    print("  uv run invoke dev-setup           # Setup development environment")
    print("=" * 80 + "\n")


# ============================================================================
# Collection Configuration
# ============================================================================

# Create namespace for better organization
ns = Collection()

# Dependency Management (uv)
ns.add_task(sync)
ns.add_task(sync_no_dev, name="sync-no-dev")
ns.add_task(add)
ns.add_task(add_dev, name="add-dev")
ns.add_task(lock_upgrade, name="lock-upgrade")
ns.add_task(lock_refresh, name="lock-refresh")
ns.add_task(cache_clean, name="cache-clean")

# Development
ns.add_task(dev)
ns.add_task(dev_quiet, name="dev-quiet")

# Testing
ns.add_task(test)
ns.add_task(test_cov, name="test-cov")
ns.add_task(test_watch, name="test-watch")

# Code Quality
ns.add_task(lint)
ns.add_task(format)
ns.add_task(format_check, name="format-check")
ns.add_task(type_check, name="type-check")
ns.add_task(check)

# Database
ns.add_task(migrate)
ns.add_task(migrate_down, name="migrate-down")
ns.add_task(db_status, name="db-status")
ns.add_task(db_check, name="db-check")
ns.add_task(db_revision, name="db-revision")

# PostgreSQL Docker
ns.add_task(db_start, name="db-start")
ns.add_task(db_stop, name="db-stop")
ns.add_task(db_remove, name="db-remove")
ns.add_task(db_init_users, name="db-init-users")
ns.add_task(db_init_test, name="db-init-test")

# pgAdmin Docker
ns.add_task(db_admin_start, name="db-admin-start")
ns.add_task(db_admin_stop, name="db-admin-stop")

# Utilities
ns.add_task(clean)
ns.add_task(install)
ns.add_task(install_dev, name="install-dev")
ns.add_task(update)
ns.add_task(show_deps, name="show-deps")

# Workflows
ns.add_task(setup)
ns.add_task(dev_setup, name="dev-setup")
ns.add_task(dev_teardown, name="dev-teardown")
ns.add_task(reset_db, name="reset-db")

# Documentation
ns.add_task(docs)
