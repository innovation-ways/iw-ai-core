"""Alembic environment configuration.

Reads the database URL from orch.config (which loads .env from the repo root).
Supports both online migration (direct DB connection) and offline mode
(generates a SQL script without connecting to the DB).
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy import text as sa_text

from orch.config import get_db_url
from orch.db.models import Base

# ---------------------------------------------------------------------------
# Alembic Config object (gives access to values in alembic.ini)
# ---------------------------------------------------------------------------

config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the sqlalchemy.url from alembic.ini with the value from .env
config.set_main_option("sqlalchemy.url", get_db_url())

# Metadata for autogenerate support
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline migrations (generate SQL script, no DB connection needed)
# ---------------------------------------------------------------------------


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures context with a URL rather than an Engine.
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
# Online migrations (direct DB connection)
# ---------------------------------------------------------------------------


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        # Alembic hardcodes VARCHAR(32) for version_num in version_table_impl,
        # but several of this project's revision IDs exceed 32 chars
        # (e.g. 'add_section_guides_snapshot_to_jobs'). Pre-create the table
        # with VARCHAR(64) so alembic finds an existing-but-wider column.
        connection.execute(
            sa_text(
                "CREATE TABLE IF NOT EXISTS alembic_version ("
                "version_num VARCHAR(64) NOT NULL PRIMARY KEY)"
            )
        )
        connection.commit()

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
