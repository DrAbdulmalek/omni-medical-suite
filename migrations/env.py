"""OmniMedical Suite - Alembic environment configuration."""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool
from sqlalchemy.engine import make_url

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from app.db.models.auth import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_database_url() -> str:
    """Resolve the migration database without silently falling back to SQLite in production."""
    environment = os.environ.get("APP_ENV", os.environ.get("ENVIRONMENT", "development")).lower()

    url = os.environ.get("DATABASE_URL", "").strip()
    if not url and environment in {"production", "prod", "staging"}:
        user = os.environ.get("POSTGRES_USER", "").strip()
        password = os.environ.get("POSTGRES_PASSWORD", "").strip()
        host = os.environ.get("POSTGRES_HOST", "").strip()
        port = os.environ.get("POSTGRES_PORT", "5432").strip()
        database = os.environ.get("POSTGRES_DB", "").strip()
        if all((user, password, host, database)):
            url = (
                f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"
            )
        else:
            raise RuntimeError(
                "DATABASE_URL or complete POSTGRES_* settings are required for production/staging migrations."
            )

    if not url:
        ini_url = config.get_main_option("sqlalchemy.url") or ""
        # The repository's SQLite URL is a development fallback, not an override
        # for an explicitly configured PostgreSQL environment.
        if ini_url and not ini_url.startswith("%"):
            url = ini_url.strip()

    if not url:
        if environment in {"production", "prod", "staging"}:
            raise RuntimeError("A PostgreSQL database URL is required for production/staging migrations.")
        url = "sqlite:///data/omni_medical.db"

    try:
        parsed = make_url(url)
    except Exception as exc:
        raise RuntimeError("DATABASE_URL is not a valid SQLAlchemy database URL") from exc

    if parsed.drivername in {"sqlite", "sqlite+pysqlite"} and environment in {"production", "prod", "staging"}:
        raise RuntimeError("SQLite is not permitted for production/staging migrations")
    if parsed.drivername.startswith("postgresql"):
        return url
    if parsed.drivername not in {"sqlite", "sqlite+pysqlite"}:
        raise RuntimeError(f"Unsupported migration database driver: {parsed.drivername}")
    return url


SQLALCHEMY_URL = _get_database_url()
config.set_main_option("sqlalchemy.url", SQLALCHEMY_URL)


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    connectable = create_engine(SQLALCHEMY_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
