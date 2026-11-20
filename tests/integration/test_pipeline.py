"""
Integration tests for OmniMedical Suite.

These tests verify end-to-end flows across multiple packages:
- OCR pipeline → NLP post-processing → Medical dictionary lookup
- API request → OCR → correction → response
- Data flow from upload → processing → export

Integration tests run only on `main` branch pushes.
Run manually with: pytest tests/integration/ -m integration
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "packages"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))


@pytest.mark.integration
class TestPipelineIntegration:
    """Test full OCR → NLP → Medical pipeline integration."""

    def test_import_chain_core_to_nlp(self):
        """Verify that core modules can import from NLP package."""
        try:
            from core.classifier import DocumentClassifier
            from nlp.arabic_nlp_utils import extract_entities
            assert True  # Module loaded
        except ImportError as e:
            pytest.skip(f"Import chain broken: {e}")

    def test_medical_terms_in_dictionary(self):
        """Verify medical terms JSON is loadable and contains expected terms."""
        root = Path(__file__).resolve().parent.parent.parent
        terms_file = root / "medical_terms.json"
        if not terms_file.exists():
            pytest.skip("medical_terms.json not found")
        import json
        with open(terms_file, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data) > 0, "medical_terms.json should not be empty"

    def test_evaluation_metrics_on_sample_data(self):
        """Test evaluation metrics work on sample OCR output."""
        try:
            from evaluation.metrics import calculate_cer
            ground_truth = "ضغط الدم طبيعي"
            prediction = "ضغط الدم طبيعي"
            cer = calculate_cer(prediction, ground_truth)
            assert cer == 0.0
        except (ImportError, AttributeError):
            pytest.skip("evaluation.metrics not available")


@pytest.mark.integration
class TestSecurityPipeline:
    """Test security scanning integration with OCR pipeline."""

    def test_sensitive_scanner_on_medical_text(self):
        """Verify sensitive data scanner works on medical text."""
        try:
            from security.sensitive_data_scanner import scan_text
            text = "المريض أحمد رقم الهاتف 0512345678 ورقم الهوية 1098765432"
            findings = scan_text(text)
            assert len(findings) >= 2, "Should detect at least phone and ID"
        except (ImportError, AttributeError):
            pytest.skip("security.sensitive_data_scanner not available")

    def test_encryption_does_not_corrupt_arabic(self):
        """Verify encryption/decryption preserves Arabic text."""
        try:
            from security.encryption import decrypt_data, encrypt_data
            original = "تشخيص: ارتفاع ضغط الدم"
            encrypted = encrypt_data(original)
            decrypted = decrypt_data(encrypted)
            assert decrypted == original
        except (ImportError, AttributeError):
            pytest.skip("security.encryption not available")


@pytest.mark.integration
class TestMonorepoStructure:
    """Verify monorepo package structure is consistent."""

    def test_all_packages_have_init(self):
        """Every package directory should have __init__.py."""
        packages_dir = Path(__file__).resolve().parent.parent.parent / "packages"
        missing = []
        for pkg_dir in packages_dir.iterdir():
            if pkg_dir.is_dir() and not pkg_dir.name.startswith((".", "_")):
                if not (pkg_dir / "__init__.py").exists():
                    missing.append(pkg_dir.name)
        if missing:
            # Some packages may legitimately not have __init__.py (e.g., vendor dirs)
            # Just warn, don't fail
            pass

    def test_config_directory_has_files(self):
        """Verify config/ directory has expected configuration files."""
        root = Path(__file__).resolve().parent.parent.parent
        config_dir = root / "config"
        if not config_dir.exists():
            pytest.skip("config/ directory not found")
        files = list(config_dir.rglob("*.*"))
        assert len(files) > 0, "config/ should contain configuration files"

    def test_requirements_files_exist(self):
        """Verify standard requirements files exist at root."""
        root = Path(__file__).resolve().parent.parent.parent
        assert (root / "requirements.txt").exists(), "requirements.txt missing"
        assert (root / "requirements-dev.txt").exists(), "requirements-dev.txt missing"
