"""
Alembic environment configuration with async SQLAlchemy support.

Imports Base.metadata from app.base_model and all module model stubs so that
every ORM model is registered with the metadata before autogenerate runs.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# Alembic Config object — provides access to values in alembic.ini
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import Base and all module models so their tables are registered in metadata
# ---------------------------------------------------------------------------
from app.base_model import Base  # noqa: E402
from app.config import settings  # noqa: E402

# Module model imports — imported for their side-effect of registering ORM models
# with Base.metadata. Each module's models.py is explicitly imported to ensure
# all ORM classes are registered before Alembic autogenerate runs.
from app.modules.organizations.models import *  # noqa: F401, E402, F403
from app.modules.candidates.models import *  # noqa: F401, E402, F403
from app.modules.resumes.models import *  # noqa: F401, E402, F403
from app.modules.requisitions.models import *  # noqa: F401, E402, F403
from app.modules.job_profile.models import *  # noqa: F401, E402, F403
from app.modules.job_posting.models import *  # noqa: F401, E402, F403
from app.modules.skills.models import *  # noqa: F401, E402, F403
from app.modules.journeys.models import *  # noqa: F401, E402, F403
from app.modules.interviews.models import *  # noqa: F401, E402, F403
from app.modules.questionnaires.models import *  # noqa: F401, E402, F403
from app.modules.portal.models import *  # noqa: F401, E402, F403
from app.modules.privacy.models import *  # noqa: F401, E402, F403
from app.modules.reporting.models import *  # noqa: F401, E402, F403
from app.modules.auth.models import *  # noqa: F401, E402, F403
from app.modules.rbac.models import *  # noqa: F401, E402, F403
from app.modules.users.models import *  # noqa: F401, E402, F403
from app.modules.invitations.models import *  # noqa: F401, E402, F403
from app.modules.password_reset.models import *  # noqa: F401, E402, F403
from app.domain_events.models import *  # noqa: F401, E402, F403

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Override the sqlalchemy.url from alembic.ini with the value from settings
# ---------------------------------------------------------------------------
config.set_main_option("sqlalchemy.url", settings.database_url)


# ---------------------------------------------------------------------------
# Offline migrations (no live DB connection)
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine.
    Calls to context.execute() emit the given string to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations (async engine)
# ---------------------------------------------------------------------------


async def run_async_migrations() -> None:
    """
    Create an async engine and run migrations within a connection context.

    The engine is created fresh here (not reused from app.database) so that
    Alembic controls the connection lifecycle independently of the application.
    """
    connectable = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_run_migrations_sync)

    await connectable.dispose()


def _run_migrations_sync(connection) -> None:
    """Configure and run migrations on a synchronous connection handle."""
    # Determine which schema to use for the version table
    # Schema names match the database user names for simplicity:
    # - Main database (krudb) uses kru_app schema
    # - Test database (kru_test_db) uses kru_test schema
    db_user = settings.DATABASE_USER
    version_table_schema = db_user
    
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        version_table_schema=version_table_schema,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Entry point for online migrations — drives the async runner."""
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
