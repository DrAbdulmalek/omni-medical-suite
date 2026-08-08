"""OmniMedical Suite - Alembic environment configuration."""
import sys
import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from alembic import context

# Add project root to path so app modules are importable
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Import Base from the correct location
from app.db.models.auth import Base

# Alembic Config object
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# MetaData target for autogenerate support
target_metadata = Base.metadata


def _get_database_url() -> str:
    """Get database URL from alembic config or default."""
    # 1. Read alembic.ini directly (most reliable)
    ini_path = os.path.join(PROJECT_ROOT, "alembic.ini")
    if os.path.exists(ini_path):
        import configparser
        parser = configparser.ConfigParser()
        parser.read(ini_path)
        if parser.has_option("alembic", "sqlalchemy.url"):
            url = parser.get("alembic", "sqlalchemy.url")
            if url and url.startswith(("sqlite", "postgresql", "mysql")):
                return url

    # 2. Environment variable (only if valid SQLAlchemy URL)
    url = os.environ.get("DATABASE_URL", "")
    if url and url.startswith(("sqlite", "postgresql", "mysql")):
        return url

    # 3. Default to SQLite
    db_path = os.path.join(PROJECT_ROOT, "data", "omni_medical.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    return f"sqlite:///{db_path}"


# Set the URL so Alembic knows about it
SQLALCHEMY_URL = _get_database_url()
config.set_main_option("sqlalchemy.url", SQLALCHEMY_URL)


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
    connectable = create_engine(SQLALCHEMY_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()