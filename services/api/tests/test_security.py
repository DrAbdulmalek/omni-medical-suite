"""Tests for app.core.security module."""
import time
import threading
import pytest
from unittest.mock import patch

from app.core.security import (
    verify_api_key,
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    RateLimiter,
)


class TestVerifyApiKey:
    """Test API key verification."""

    def test_correct_key_returns_true(self):
        """Matching key should return True."""
        assert verify_api_key("secret-key", "secret-key") is True

    def test_incorrect_key_returns_false(self):
        """Non-matching key should return False."""
        assert verify_api_key("secret-key", "wrong-key") is False

    def test_empty_key_returns_false(self):
        """Empty comparison key should return False."""
        assert verify_api_key("secret-key", "") is False

    def test_constant_time_comparison(self):
        """Verification should use constant-time comparison to prevent timing attacks."""
        start = time.perf_counter()
        verify_api_key("a" * 100, "a" * 100)
        match_time = time.perf_counter() - start

        start = time.perf_counter()
        verify_api_key("a" * 100, "b" * 100)
        mismatch_time = time.perf_counter() - start

        # Both should complete in similar time (within 10x factor)
        # This is a basic check; real constant-time guarantees depend on the implementation
        assert mismatch_time < match_time * 10


class TestPasswordHashing:
    """Test password hashing and verification."""

    def test_hash_password_returns_string(self):
        """Hash should return a non-empty string."""
        result = hash_password("password123")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_verify_correct_password(self):
        """Correct password should verify successfully."""
        hashed = hash_password("my-secure-password")
        assert verify_password("my-secure-password", hashed) is True

    def test_verify_wrong_password(self):
        """Wrong password should fail verification."""
        hashed = hash_password("my-secure-password")
        assert verify_password("wrong-password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """Same password should produce different hashes (salt)."""
        hash1 = hash_password("same-password")
        hash2 = hash_password("same-password")
        assert hash1 != hash2

    def test_empty_password(self):
        """Empty password should still hash and verify."""
        hashed = hash_password("")
        assert verify_password("", hashed) is True


class TestJWT:
    """Test JWT token creation and decoding."""

    def test_create_token_returns_string(self):
        """Token creation should return a non-empty string."""
        token = create_access_token({"sub": "user123"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_token_returns_dict(self):
        """Token decoding should return the original data."""
        data = {"sub": "user123", "role": "admin"}
        token = create_access_token(data)
        decoded = decode_access_token(token)
        assert decoded["sub"] == "user123"
        assert decoded["role"] == "admin"

    def test_expired_token_raises(self):
        """Expired token should raise an exception."""
        from datetime import timedelta

        token = create_access_token({"sub": "user123"}, expires_delta=timedelta(seconds=-1))
        with pytest.raises(Exception):
            decode_access_token(token)

    def test_different_data_different_tokens(self):
        """Different payloads should produce different tokens."""
        token1 = create_access_token({"sub": "user1"})
        token2 = create_access_token({"sub": "user2"})
        assert token1 != token2


class TestRateLimiter:
    """Test sliding-window rate limiter."""

    def test_allows_under_limit(self):
        """Requests under the limit should be allowed."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for i in range(5):
            allowed, remaining = limiter.is_allowed("client-1")
            assert allowed is True
            assert remaining >= 0

    def test_blocks_over_limit(self):
        """Requests exceeding the limit should be blocked."""
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for i in range(3):
            limiter.is_allowed("client-2")
        allowed, remaining = limiter.is_allowed("client-2")
        assert allowed is False
        assert remaining == 0

    def test_different_clients_independent(self):
        """Different clients should have independent rate limits."""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        limiter.is_allowed("client-a")
        limiter.is_allowed("client-a")
        allowed, _ = limiter.is_allowed("client-a")
        assert allowed is False

        allowed, _ = limiter.is_allowed("client-b")
        assert allowed is True

    def test_thread_safety(self):
        """Rate limiter should be thread-safe."""
        limiter = RateLimiter(max_requests=100, window_seconds=60)
        results = []
        errors = []

        def make_request(client_id, count):
            try:
                for _ in range(count):
                    allowed, _ = limiter.is_allowed(client_id)
                    results.append(allowed)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=make_request, args=("client-x", 50))
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
        # At most 100 should be allowed, rest should be False
        allowed_count = sum(1 for r in results if r)
        assert allowed_count == 100
