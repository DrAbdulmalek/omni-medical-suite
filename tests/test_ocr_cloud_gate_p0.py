"""P0 regression tests: cloud gate + invented-confidence isolation.

Covers the grok-audit P0 findings for ``packages/omni_ocr/adapter.py``:

1. ``OMNI_ALLOW_CLOUD_OCR`` fail-closed gate (literal ``true`` only).
2. MISTRAL removed from ``_DEFAULT_ENGINE_ORDER`` (explicit opt-in only).
3. ``_run_mistral`` refuses to touch the network/tempfiles when the gate
   is closed, and its skip reason surfaces in the all-engines-failed
   summary (no silent swallow).
4. Invented ``confidence = 0.9`` replaced by ``0.0`` +
   ``confidence_is_estimate=True``.
5. Provenance fields (``pdf_sha256``, ``model``, ``cloud``,
   ``cost_estimate_usd``) defaulted and populated.
"""

from unittest.mock import MagicMock, patch

import pytest

from packages.omni_ocr.adapter import (
    _CLOUD_GATE_ENV,
    _DEFAULT_ENGINE_ORDER,
    OCRResult,
    UnifiedOCR,
)


def _tiny_image():
    """Minimal PIL image for adapter tests (no OCR backend needed)."""
    from PIL import Image

    return Image.new("RGB", (4, 4), color=(255, 255, 255))


class TestCloudGate:
    """Fail-closed semantics of the OMNI_ALLOW_CLOUD gate."""

    @pytest.mark.parametrize(
        "value,allowed",
        [
            (None, False),
            ("", False),
            ("false", False),
            ("0", False),
            ("1", False),
            ("yes", False),
            ("TRUE", True),
            (" true ", True),
        ],
    )
    def test_gate_values(self, monkeypatch, value, allowed):
        if value is None:
            monkeypatch.delenv(_CLOUD_GATE_ENV, raising=False)
        else:
            monkeypatch.setenv(_CLOUD_GATE_ENV, value)
        from packages.omni_ocr.adapter import _cloud_allowed

        assert _cloud_allowed() is allowed

    def test_mistral_not_in_default_order(self):
        """Cloud engine must never run by default (fail-closed default)."""
        assert "mistral" not in [e for e in _DEFAULT_ENGINE_ORDER]

    def test_adapter_default_order_excludes_mistral(self):
        adapter = UnifiedOCR(cache_max_size=0)
        assert "mistral" not in adapter.engine_order


class TestGateBlocksMistral:
    """_run_mistral must fail closed before any cloud side effect."""

    def _make_adapter(self):
        return UnifiedOCR(engine_order=["mistral"], cache_max_size=0)

    def test_gate_closed_no_load_no_network(self, monkeypatch):
        monkeypatch.delenv(_CLOUD_GATE_ENV, raising=False)
        adapter = self._make_adapter()

        with patch.object(adapter, "_load_mistral") as mock_load:
            result = adapter._run_mistral(
                pil_image=None, file_path=None, languages=None
            )

        mock_load.assert_not_called()  # never even imported the client
        assert result.error
        assert "cloud disabled" in result.error
        assert result.cloud is False
        assert result.model == "mistral-ocr-3"

    def test_gate_closed_error_surfaces_in_summary(self, monkeypatch):
        """Skip reason must reach the all-engines-failed summary."""
        monkeypatch.delenv(_CLOUD_GATE_ENV, raising=False)
        adapter = UnifiedOCR(engine_order=["mistral"], cache_max_size=0)

        with patch.object(adapter, "_load_mistral"):
            result = adapter.process_image(image=_tiny_image())

        assert not result.success
        assert "cloud disabled" in (result.error or "")

    def test_gate_closed_still_hashes_input(self, monkeypatch, tmp_path):
        """Provenance amendment: pdf_sha256 computed even when denied."""
        monkeypatch.delenv(_CLOUD_GATE_ENV, raising=False)
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.7 provenance-check")
        adapter = self._make_adapter()

        with patch.object(adapter, "_load_mistral"):
            result = adapter._run_mistral(
                pil_image=None, file_path=str(f), languages=None
            )

        import hashlib

        assert result.pdf_sha256 == hashlib.sha256(
            b"%PDF-1.7 provenance-check"
        ).hexdigest()

    def test_gate_open_missing_key_still_fails_cleanly(self, monkeypatch):
        """Gate open + no API key -> clean engine error, no crash."""
        monkeypatch.setenv(_CLOUD_GATE_ENV, "true")
        monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
        adapter = self._make_adapter()
        adapter._mistral_loaded = True
        adapter._mistral_ocr = None  # simulate unavailable client

        result = adapter._run_mistral(
            pil_image=None, file_path=None, languages=None
        )
        assert result.error
        assert "not available" in result.error


class TestInventedConfidenceIsolated:
    """Mistral success path must not fabricate a confidence score."""

    def _run_success(self, monkeypatch):
        monkeypatch.setenv(_CLOUD_GATE_ENV, "true")
        adapter = UnifiedOCR(engine_order=["mistral"], cache_max_size=0)

        fake_engine = MagicMock()
        fake_engine.ocr_document.return_value = {
            "pages": [{"markdown": "# Hello\n\nWorld"}]
        }
        adapter._mistral_loaded = True
        adapter._mistral_ocr = fake_engine

        with patch(
            "packages.omni_ocr.adapter._compute_input_sha256",
            return_value="deadbeef",
        ):
            result = adapter._run_mistral(
                pil_image=_tiny_image(), file_path=None, languages=None
            )
        return result

    def test_confidence_zero_and_flagged(self, monkeypatch):
        result = self._run_success(monkeypatch)
        assert result.success  # text is real and usable
        assert result.confidence == 0.0
        assert result.confidence_is_estimate is True

    def test_provenance_fields_populated(self, monkeypatch):
        result = self._run_success(monkeypatch)
        assert result.cloud is True
        assert result.model == "mistral-ocr-3"
        assert result.pdf_sha256 == "deadbeef"
        assert result.cost_estimate_usd is None

    def test_to_dict_includes_provenance(self, monkeypatch):
        result = self._run_success(monkeypatch)
        d = result.to_dict()
        for key in (
            "confidence_is_estimate",
            "pdf_sha256",
            "model",
            "cloud",
            "cost_estimate_usd",
        ):
            assert key in d


class TestBackwardCompatibility:
    """New OCRResult fields must be safe defaults for old callers."""

    def test_default_construction(self):
        r = OCRResult()
        assert r.confidence_is_estimate is False
        assert r.pdf_sha256 == ""
        assert r.model == ""
        assert r.cloud is False
        assert r.cost_estimate_usd is None

    def test_existing_engines_unflagged(self, monkeypatch):
        """Local engines keep real confidence and cloud=False."""
        monkeypatch.delenv(_CLOUD_GATE_ENV, raising=False)
        r = OCRResult(
            text="x", confidence=0.83, engine="tesseract"
        )
        assert r.cloud is False
        assert r.confidence_is_estimate is False
