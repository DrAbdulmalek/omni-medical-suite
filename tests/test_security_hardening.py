"""Regression tests for authentication and security hardening."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from jose import jwt

from app.config.security import SecurityConfig
from app.core.security.dependencies import _decode_access_token


class _Config:
    JWT_SECRET_KEY = "x" * 64
    JWT_ALGORITHM = "HS256"
    JWT_ISSUER = "omni-medical-suite"
    JWT_AUDIENCE = "omni-medical-suite-api"


def test_production_rejects_default_jwt_secret(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
    monkeypatch.setenv("POSTGRES_PASSWORD", "a" * 32)
    with pytest.raises(ValueError, match="JWT_SECRET_KEY"):
        SecurityConfig.validate_config("production")


def test_production_rejects_default_database_password(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET_KEY", "x" * 64)
    monkeypatch.setenv("POSTGRES_PASSWORD", "change_me_in_production")
    with pytest.raises(ValueError, match="POSTGRES_PASSWORD"):
        SecurityConfig.validate_config("production")


def test_development_defaults_are_allowed():
    assert SecurityConfig.validate_config("development") is True


def test_access_token_requires_expiration(monkeypatch):
    monkeypatch.setattr("app.core.security.dependencies.get_security_config", lambda: _Config())
    token = jwt.encode(
        {
            "sub": "1",
            "iss": _Config.JWT_ISSUER,
            "aud": _Config.JWT_AUDIENCE,
        },
        _Config.JWT_SECRET_KEY,
        algorithm=_Config.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        _decode_access_token(token)
    assert exc.value.status_code == 401


def test_access_token_rejects_wrong_audience(monkeypatch):
    monkeypatch.setattr("app.core.security.dependencies.get_security_config", lambda: _Config())
    token = jwt.encode(
        {
            "sub": "1",
            "iss": _Config.JWT_ISSUER,
            "aud": "wrong-audience",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        _Config.JWT_SECRET_KEY,
        algorithm=_Config.JWT_ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        _decode_access_token(token)
    assert exc.value.status_code == 401
