from datetime import datetime, timezone

import pytest
from jose import jwt

from app.core.security.tokens import create_access_token, create_refresh_token, hash_refresh_token


def test_refresh_token_is_opaque_and_only_hash_is_deterministic():
    token_a, digest_a, expires_a = create_refresh_token()
    token_b, digest_b, expires_b = create_refresh_token()

    assert token_a != token_b
    assert digest_a == hash_refresh_token(token_a)
    assert digest_b == hash_refresh_token(token_b)
    assert digest_a != token_a
    assert expires_a > datetime.now(timezone.utc)
    assert expires_b > datetime.now(timezone.utc)


def test_access_token_has_required_claims():
    token = create_access_token(123)
    from app.config import get_security_config

    config = get_security_config()
    claims = jwt.decode(
        token,
        config.JWT_SECRET_KEY,
        algorithms=[config.JWT_ALGORITHM],
        issuer=config.JWT_ISSUER,
        audience=config.JWT_AUDIENCE,
    )

    assert claims["sub"] == "123"
    assert claims["type"] == "access"
    assert claims["iss"] == config.JWT_ISSUER
    assert claims["aud"] == config.JWT_AUDIENCE
    assert "jti" in claims
    assert "iat" in claims
    assert "exp" in claims


def test_access_token_rejects_wrong_audience(monkeypatch):
    token = create_access_token(123)
    from app.config import get_security_config

    config = get_security_config()
    with pytest.raises(Exception):
        jwt.decode(
            token,
            config.JWT_SECRET_KEY,
            algorithms=[config.JWT_ALGORITHM],
            issuer=config.JWT_ISSUER,
            audience="wrong-audience",
        )
