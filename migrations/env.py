"""
Alembic Environment Configuration
"""
from logging.config import fileConfig
from typing import Optional

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import models
from app.db.models.auth import Base as AuthBase
from app.db.models import Base  # Import your main Base from models

# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Add your model's MetaData object here for 'autogenerate' support
target_metadata = AuthBase.metadata

# Other models can be added here if they use a different Base
# target_metadata = [Base1.metadata, Base2.metadata, ...]

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
            process_revision_directives=lambda revision, context: process_revision_directives(revision, context)
        )

        with context.begin_transaction():
            context.run_migrations()

def process_revision_directives(revision, context):
    """
    Process revision directives for Alembic.
    This allows for custom processing of migration directives.
    """
    # Get the directive
    directive = getattr(revision, 'directive', None)

    if directive:
        # Handle specific directives if needed
        pass

    return revision

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()