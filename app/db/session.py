"""
Database Session Management - Production Ready with Alembic
"""
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_app_config, get_security_config

# Database engine
engine = None
AsyncSessionLocal = None

def get_db_config_uri():
    """Get database connection URI from config"""
    security_config = get_security_config()
    return (
        f"postgresql+asyncpg://{security_config.POSTGRES_USER}:"
        f"{security_config.POSTGRES_PASSWORD}@{security_config.POSTGRES_HOST}:"
        f"{security_config.POSTGRES_PORT}/{security_config.POSTGRES_DB}"
    )

def init_db():
    """Initialize database engine and session factory"""
    global engine, AsyncSessionLocal

    db_config = get_app_config()

    # Create async engine
    engine = create_async_engine(
        get_db_config_uri(),
        pool_size=db_config.POOL_SIZE,
        max_overflow=db_config.MAX_OVERFLOW,
        pool_timeout=db_config.POOL_TIMEOUT,
        pool_recycle=db_config.POOL_RECYCLE,
        pool_pre_ping=db_config.POOL_PRE_PING,
        echo=db_config.DEBUG,
        future=True
    )

    # Create async session factory
    async_session = sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False
    )

    AsyncSessionLocal = asynccontextmanager(async_session)

    print("✅ Database engine initialized")

async def get_db():
    """Dependency to get database session"""
    if AsyncSessionLocal is None:
        init_db()

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()

async def close_db():
    """Close database connections"""
    global engine, AsyncSessionLocal

    if AsyncSessionLocal:
        AsyncSessionLocal = None

    if engine:
        await engine.dispose()
        engine = None

    print("✅ Database connections closed")

async def health_check():
    """Check database health"""
    if AsyncSessionLocal is None:
        init_db()

    async with AsyncSessionLocal() as session:
        try:
            # Use text() for SQLAlchemy 2.0 compatibility
            await session.execute(text("SELECT 1"))
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            print(f"❌ Database health check failed: {e}")
            return False

# Initialize on import
init_db()
