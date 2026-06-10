"""
packages/core/database_manager.py
====================================
مدير قاعدة البيانات الموحّد
دُمجت نسختا core/ + omni-core/ هنا

يدعم:
  - PostgreSQL (للإنتاج) عبر asyncpg + SQLAlchemy
  - SQLite (للتطوير) مع WAL mode
  - Connection pooling قابل للضبط
  - Health check تلقائي
  - Migration runner (Alembic)
"""

from __future__ import annotations

import os
import logging
from contextlib import contextmanager, asynccontextmanager
from typing import Optional, Generator, AsyncGenerator, Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """يقرأ DATABASE_URL ويُحدد نوع قاعدة البيانات وإعدادات الـ pool."""

    def __init__(self, url: Optional[str] = None):
        self.url = url or os.environ.get("DATABASE_URL", "file:./db/omni-medical.db")
        self._parsed = urlparse(self.url.replace("file:", "sqlite:///", 1) if self.url.startswith("file:") else self.url)

    @property
    def is_sqlite(self) -> bool:
        return self._parsed.scheme in ("sqlite", "sqlite+aiosqlite")

    @property
    def is_postgres(self) -> bool:
        return self._parsed.scheme in ("postgresql", "postgresql+asyncpg", "postgres")

    @property
    def pool_size(self) -> int:
        return 1 if self.is_sqlite else int(os.environ.get("DB_POOL_SIZE", "10"))

    @property
    def max_overflow(self) -> int:
        return 0 if self.is_sqlite else int(os.environ.get("DB_MAX_OVERFLOW", "20"))

    @property
    def sqlalchemy_url(self) -> str:
        if self.url.startswith("file:"):
            path = self.url.replace("file:", "", 1).lstrip("./")
            return f"sqlite:///{path}"
        if self.url.startswith("postgresql://") or self.url.startswith("postgres://"):
            return self.url.replace("postgres://", "postgresql://", 1)
        return self.url

    def validate(self) -> None:
        if self.is_sqlite:
            logger.warning(
                "⚠️  Using SQLite — suitable for development only. "
                "Set DATABASE_URL to a PostgreSQL URL for production."
            )
        elif self.is_postgres:
            logger.info("✅ PostgreSQL configured")
        else:
            raise ValueError(f"Unsupported DATABASE_URL scheme: {self._parsed.scheme}")


class DatabaseManager:
    """
    مدير قاعدة البيانات.

    الاستخدام:
        db = DatabaseManager()
        with db.session() as session:
            session.execute(...)

        # أو للـ async:
        async with db.async_session() as session:
            await session.execute(...)
    """

    _instance: Optional["DatabaseManager"] = None

    def __init__(self, url: Optional[str] = None):
        self.config = DatabaseConfig(url)
        self.config.validate()
        self._engine = None
        self._async_engine = None
        self._SessionLocal = None
        self._AsyncSessionLocal = None

    # ── Singleton ─────────────────────────────────────────────

    @classmethod
    def get_instance(cls, url: Optional[str] = None) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = cls(url)
        return cls._instance

    # ── Sync ──────────────────────────────────────────────────

    def _get_sync_engine(self):
        if self._engine is None:
            try:
                from sqlalchemy import create_engine, event
                kwargs: dict[str, Any] = {
                    "pool_size": self.config.pool_size,
                    "max_overflow": self.config.max_overflow,
                    "pool_pre_ping": True,
                }
                if self.config.is_sqlite:
                    kwargs = {"connect_args": {"check_same_thread": False}}
                self._engine = create_engine(self.config.sqlalchemy_url, **kwargs)

                # WAL mode للـ SQLite — يسمح بقراءات متزامنة
                if self.config.is_sqlite:
                    @event.listens_for(self._engine, "connect")
                    def set_sqlite_pragma(conn, _):
                        conn.execute("PRAGMA journal_mode=WAL")
                        conn.execute("PRAGMA synchronous=NORMAL")
                        conn.execute("PRAGMA foreign_keys=ON")

            except ImportError:
                raise RuntimeError("SQLAlchemy not installed: pip install sqlalchemy")
        return self._engine

    @contextmanager
    def session(self) -> Generator:
        """Context manager للجلسات المتزامنة مع rollback تلقائي عند الخطأ."""
        try:
            from sqlalchemy.orm import sessionmaker
        except ImportError:
            raise RuntimeError("SQLAlchemy not installed")

        if self._SessionLocal is None:
            from sqlalchemy.orm import sessionmaker
            self._SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self._get_sync_engine(),
            )

        session = self._SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ── Async ─────────────────────────────────────────────────

    def _get_async_engine(self):
        if self._async_engine is None:
            try:
                from sqlalchemy.ext.asyncio import create_async_engine
            except ImportError:
                raise RuntimeError("SQLAlchemy[asyncio] not installed")

            async_url = self.config.sqlalchemy_url
            if "sqlite:///" in async_url:
                async_url = async_url.replace("sqlite:///", "sqlite+aiosqlite:///")
            elif "postgresql://" in async_url:
                async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")

            kwargs: dict[str, Any] = {"pool_pre_ping": True}
            if not self.config.is_sqlite:
                kwargs["pool_size"] = self.config.pool_size
                kwargs["max_overflow"] = self.config.max_overflow

            self._async_engine = create_async_engine(async_url, **kwargs)
        return self._async_engine

    @asynccontextmanager
    async def async_session(self) -> AsyncGenerator:
        """Context manager للجلسات غير المتزامنة."""
        try:
            from sqlalchemy.ext.asyncio import AsyncSession
            from sqlalchemy.orm import sessionmaker
        except ImportError:
            raise RuntimeError("SQLAlchemy[asyncio] not installed")

        if self._AsyncSessionLocal is None:
            self._AsyncSessionLocal = sessionmaker(
                self._get_async_engine(),
                class_=AsyncSession,
                expire_on_commit=False,
            )

        async with self._AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # ── Health Check ──────────────────────────────────────────

    def health_check(self) -> dict:
        """فحص الاتصال بقاعدة البيانات."""
        try:
            engine = self._get_sync_engine()
            with engine.connect() as conn:
                from sqlalchemy import text
                conn.execute(text("SELECT 1"))
            return {"status": "ok", "url": self._safe_url()}
        except Exception as exc:
            return {"status": "error", "error": str(exc), "url": self._safe_url()}

    async def async_health_check(self) -> dict:
        """فحص الاتصال غير المتزامن."""
        try:
            engine = self._get_async_engine()
            async with engine.connect() as conn:
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
            return {"status": "ok", "url": self._safe_url()}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    # ── Migration ─────────────────────────────────────────────

    def run_migrations(self, alembic_cfg_path: str = "alembic.ini") -> None:
        """شغّل migrations باستخدام Alembic."""
        try:
            from alembic.config import Config
            from alembic import command
            alembic_cfg = Config(alembic_cfg_path)
            command.upgrade(alembic_cfg, "head")
            logger.info("✅ Database migrations applied")
        except ImportError:
            logger.warning("Alembic not installed — run migrations manually")
        except Exception as exc:
            logger.error(f"Migration failed: {exc}")
            raise

    # ── Cleanup ───────────────────────────────────────────────

    def dispose(self) -> None:
        """أغلق جميع connections في الـ pool."""
        if self._engine:
            self._engine.dispose()
        DatabaseManager._instance = None

    async def async_dispose(self) -> None:
        if self._async_engine:
            await self._async_engine.dispose()

    def _safe_url(self) -> str:
        """إخفاء كلمة المرور في الـ URL عند الطباعة."""
        url = self.config.sqlalchemy_url
        if "@" in url:
            scheme_end = url.index("://") + 3
            at_pos = url.index("@")
            credentials = url[scheme_end:at_pos]
            if ":" in credentials:
                user = credentials.split(":")[0]
                url = url[:scheme_end] + user + ":***@" + url[at_pos + 1:]
        return url
