"""
Application Configuration - Pydantic-based
"""
from typing import List, Optional
from pydantic import BaseSettings, validator, AnyHttpUrl

class AppConfig(BaseSettings):
    """Application configuration"""

    # Application
    APP_NAME: str = "Omni Medical Suite"
    APP_VERSION: str = "2.0.0"
    APP_DESCRIPTION: str = "Comprehensive Medical OCR and Text Processing Platform"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # development, staging, production

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # CORS
    CORS_ALLOW_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_DIR: str = "./logs"

    # Rate Limiting
    RATE_LIMIT: int = 100  # requests per minute
    RATE_LIMIT_BURST: int = 20

    # File Upload
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB
    UPLOAD_DIR: str = "./uploads"
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".webp"]
    TEMP_DIR: str = "./temp"

    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    PROMETHEUS_PORT: int = 9090

    # Security
    ENABLE_SECURITY_HEADERS: bool = True
    CSRF_ENABLED: bool = True

    # Database pool settings (used by session.py)
    POOL_SIZE: int = 20
    MAX_OVERFLOW: int = 10
    POOL_TIMEOUT: int = 30
    POOL_RECYCLE: int = 3600
    POOL_PRE_PING: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        if v not in ["development", "staging", "production"]:
            raise ValueError("ENVIRONMENT must be one of: development, staging, production")
        return v

    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of: {', '.join(valid_levels)}")
        return v.upper()

from functools import lru_cache

@lru_cache()
def get_app_config() -> AppConfig:
    """Get application configuration - cached for performance"""
    return AppConfig()