"""Async database engine and session lifecycle."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_app_config, get_security_config

engine = None
AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None


def get_db_config_uri() -> str:
    """Build the PostgreSQL URI from validated configuration."""
    config = get_security_config()
    return (
        f"postgresql+asyncpg://{config.POSTGRES_USER}:"
        f"{config.POSTGRES_PASSWORD}@{config.POSTGRES_HOST}:"
        f"{config.POSTGRES_PORT}/{config.POSTGRES_DB}"
    )


def init_db() -> None:
    """Create the engine and session factory exactly once."""
    global engine, AsyncSessionLocal
    if engine is not None and AsyncSessionLocal is not None:
        return

    config = get_app_config()
    engine = create_async_engine(
        get_db_config_uri(),
        pool_size=config.POOL_SIZE,
        max_overflow=config.MAX_OVERFLOW,
        pool_timeout=config.POOL_TIMEOUT,
        pool_recycle=config.POOL_RECYCLE,
        pool_pre_ping=config.POOL_PRE_PING,
        echo=config.DEBUG,
    )
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


async def get_db():
    """FastAPI dependency yielding one transaction-scoped AsyncSession."""
    if AsyncSessionLocal is None:
        init_db()
    assert AsyncSessionLocal is not None

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_db() -> None:
    """Dispose all database connections during application shutdown."""
    global engine, AsyncSessionLocal
    current_engine = engine
    engine = None
    AsyncSessionLocal = None
    if current_engine is not None:
        await current_engine.dispose()


async def health_check() -> bool:
    """Return whether PostgreSQL is reachable."""
    if AsyncSessionLocal is None:
        init_db()
    assert AsyncSessionLocal is not None

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
