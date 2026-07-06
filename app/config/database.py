"""
Database Configuration - Pydantic-based
"""
from typing import Optional
try:
    from pydantic.v1 import BaseSettings, validator  # Pydantic v2 with v1 compat
except ImportError:
    from pydantic import BaseSettings, validator  # Pydantic v1
from sqlalchemy import text

class DatabaseConfig(BaseSettings):
    """Database configuration"""

    # PostgreSQL
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "omni_medical"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Connection Pool
    POOL_SIZE: int = 20
    MAX_OVERFLOW: int = 10
    POOL_TIMEOUT: int = 30
    POOL_RECYCLE: int = 3600
    POOL_PRE_PING: bool = True

    # SQLAlchemy
    SQLALCHEMY_ECHO: bool = False
    SQLALCHEMY_FUTURE: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @validator("POOL_SIZE", "MAX_OVERFLOW", "POOL_TIMEOUT", "POOL_RECYCLE")
    @classmethod
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError("Value must be positive")
        return v

    @validator("POSTGRES_PASSWORD")
    @classmethod
    def validate_db_password(cls, v):
        if len(v) < 8:
            raise ValueError("POSTGRES_PASSWORD must be at least 8 characters")
        return v

    def get_database_uri(self) -> str:
        """Get database connection URI"""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:"
            f"{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

from functools import lru_cache

@lru_cache()
def get_db_config() -> DatabaseConfig:
    """Get database configuration - cached for performance"""
    return DatabaseConfig()