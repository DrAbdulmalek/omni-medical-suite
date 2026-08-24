"""Security configuration with fail-closed production validation."""
from functools import lru_cache

try:
    from pydantic.v1 import BaseSettings, root_validator, validator
except ImportError:
    from pydantic import BaseSettings, root_validator, validator


_INSECURE_SECRETS = {
    "CHANGE_ME_IN_PRODUCTION",
    "change_me_in_production",
    "changeme",
    "change-me",
    "secret",
    "password",
}


class SecurityConfig(BaseSettings):
    """Authentication, database and HTTP security configuration."""

    JWT_SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_ISSUER: str = "omni-medical-suite"
    JWT_AUDIENCE: str = "omni-medical-suite-api"

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "change_me_in_production"
    POSTGRES_DB: str = "omni_medical"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8080"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: list[str] = ["Authorization", "Content-Type", "Accept", "X-Request-ID"]

    ENABLE_SECURITY_HEADERS: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60
    MIN_PASSWORD_LENGTH: int = 12
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15

    API_KEY_HEADER: str = "X-API-Key"
    API_KEY_QUERY_PARAM: str = "api_key"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    @validator("POSTGRES_PASSWORD")
    @classmethod
    def validate_db_password(cls, value: str) -> str:
        if value in _INSECURE_SECRETS or len(value) < 12:
            raise ValueError("POSTGRES_PASSWORD must be a non-default secret of at least 12 characters")
        return value

    @validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if value in _INSECURE_SECRETS or len(value) < 32:
            raise ValueError("JWT_SECRET_KEY must be a unique secret of at least 32 characters")
        return value

    @root_validator
    def validate_security_policy(cls, values):
        environment = values.get("ENVIRONMENT")
        if environment in {"production", "staging"}:
            origins = values.get("CORS_ALLOW_ORIGINS") or []
            if "*" in origins and values.get("CORS_ALLOW_CREDENTIALS"):
                raise ValueError("Wildcard CORS origin cannot be combined with credentials")
        return values

    @classmethod
    def validate_config(cls, environment: str | None = None):
        """Fail closed for production/staging instead of logging a warning."""
        config = cls()
        if environment in {"production", "staging"}:
            # Field validators already reject default/weak secrets.
            if config.JWT_ALGORITHM not in {"HS256", "HS384", "HS512"}:
                raise ValueError("Unsupported JWT algorithm")
        return True


@lru_cache
def get_security_config() -> SecurityConfig:
    """Return cached validated security configuration."""
    config = SecurityConfig()
    # Avoid importing app config at module import time; this prevents a cycle.
    from app.config.app import get_app_config

    environment = get_app_config().ENVIRONMENT
    config.validate_config(environment)
    return config


validate_config = SecurityConfig.validate_config
