"""
Security Configuration - Pydantic-based (compatible with v1 and v2)
"""
from functools import lru_cache

try:
    from pydantic.v1 import BaseSettings, validator  # Pydantic v2 with v1 compat
except ImportError:
    from pydantic import BaseSettings, validator  # Pydantic v1


class SecurityConfig(BaseSettings):
    """Security configuration"""

    # JWT
    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ISSUER: str = "omni-medical-suite"
    JWT_AUDIENCE: str = "omni-medical-suite-api"

    # PostgreSQL (used by session.py for DB URI)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "change_me_in_production"
    POSTGRES_DB: str = "omni_medical"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # CORS (used by main.py middleware)
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    # Security Headers
    ENABLE_SECURITY_HEADERS: bool = True

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # Password Policy
    MIN_PASSWORD_LENGTH: int = 8
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    # API Keys
    API_KEY_HEADER: str = "X-API-Key"
    API_KEY_QUERY_PARAM: str = "api_key"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @validator("POSTGRES_PASSWORD")
    @classmethod
    def validate_db_password(cls, v):
        if len(v) < 8:
            raise ValueError("POSTGRES_PASSWORD must be at least 8 characters")
        return v

    @validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v):
        if v == "CHANGE_ME_IN_PRODUCTION":
            import logging
            logging.getLogger(__name__).warning(
                "JWT_SECRET_KEY is using default value. Change it in production!"
            )
        return v

    @classmethod
    def validate_config(cls):
        """Validate all security configurations"""
        import logging
        logger = logging.getLogger(__name__)
        errors = []

        if cls().JWT_SECRET_KEY == "CHANGE_ME_IN_PRODUCTION":
            errors.append("JWT_SECRET_KEY must be changed from default")

        if cls().POSTGRES_PASSWORD == "change_me_in_production":
            errors.append("POSTGRES_PASSWORD must be changed from default")

        if errors:
            for error in errors:
                logger.error(f"Security config error: {error}")
            raise ValueError(f"Security configuration errors: {', '.join(errors)}")

        return True


@lru_cache
def get_security_config() -> SecurityConfig:
    """Get security configuration - cached for performance"""
    return SecurityConfig()


# Alias for backward compatibility
validate_config = SecurityConfig.validate_config
