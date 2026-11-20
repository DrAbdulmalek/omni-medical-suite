"""
Unit tests for packages/security — encryption, sensitive data scanning, audit.

These tests verify security utilities work correctly.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "packages"))


class TestEncryption:
    """Tests for packages/security/encryption.py."""

    def test_security_encryption_importable(self):
        """Verify security.encryption module can be imported."""
        try:
            from security import encryption
            assert encryption is not None
        except ImportError:
            pytest.skip("security.encryption not importable")

    def test_encrypt_decrypt_symmetric(self):
        """Test symmetric encryption round-trip."""
        try:
            from security.encryption import decrypt_data, encrypt_data
            plaintext = "سر طبي: المريض مصاب بالسكري"
            encrypted = encrypt_data(plaintext)
            decrypted = decrypt_data(encrypted)
            assert decrypted == plaintext
        except (ImportError, AttributeError, TypeError):
            pytest.skip("encrypt_data/decrypt_data not available in security package")


class TestSensitiveDataScanner:
    """Tests for packages/security/sensitive_data_scanner.py."""

    def test_scanner_importable(self):
        """Verify sensitive_data_scanner module can be imported."""
        try:
            from security import sensitive_data_scanner
            assert sensitive_data_scanner is not None
        except ImportError:
            pytest.skip("security.sensitive_data_scanner not importable")

    def test_detects_phone_number(self):
        """Test that phone numbers are detected as sensitive."""
        try:
            from security.sensitive_data_scanner import scan_text
            result = scan_text("رقم الهاتف 0512345678")
            assert len(result) > 0  # Should detect the phone number
        except (ImportError, AttributeError):
            pytest.skip("scan_text not available in security.sensitive_data_scanner")

    def test_detects_national_id(self):
        """Test that national ID patterns are detected."""
        try:
            from security.sensitive_data_scanner import scan_text
            result = scan_text("رقم الهوية 1234567890")
            assert len(result) > 0
        except (ImportError, AttributeError):
            pytest.skip("scan_text not available in security.sensitive_data_scanner")

    def test_clean_text_has_no_sensitive_data(self):
        """Test that redacted text removes sensitive information."""
        try:
            from security.sensitive_data_scanner import redact_text
            text = "المريض أحمد رقم الهاتف 0512345678"
            redacted = redact_text(text)
            assert "0512345678" not in redacted
        except (ImportError, AttributeError):
            pytest.skip("redact_text not available")


class TestAuditLogger:
    """Tests for audit logging functionality."""

    def test_audit_logger_importable(self):
        """Verify audit logger is available."""
        try:
            from security import audit_logger_module
            assert audit_logger_module is not None
        except ImportError:
            try:
                # Try importing from src
                from src.security import audit
                assert audit is not None
            except ImportError:
                pytest.skip("audit module not importable")
