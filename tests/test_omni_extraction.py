"""Contract tests for the isolated omni_extraction package.

These tests run in the MAIN runtime where ``xberg`` is deliberately NOT
installed.  They therefore prove the fail-closed contract: engine
absence must be loud (``ExtractionError``), never a silent empty result.
"""

import hashlib
import os

import pytest


class TestPackageContract:
    """Package surface, pins, and import hygiene."""

    def test_package_importable(self):
        from packages import omni_extraction

        assert omni_extraction.__version__ == "1.0.0"

    def test_pin_recorded(self):
        from packages.omni_extraction import XBERG_PIN

        assert XBERG_PIN == "1.2.6"

    def test_public_api_exports(self):
        from packages.omni_extraction import (
            ExtractionError,
            ExtractionResult,
            ProvenanceRecord,
            XbergExtractor,
            build_provenance,
        )

        assert callable(build_provenance)
        assert issubclass(ExtractionError, RuntimeError)


class TestExtractionResult:
    """Result shape and success semantics."""

    def test_defaults_are_fail_visible(self):
        from packages.omni_extraction import ExtractionResult

        result = ExtractionResult()
        assert result.success is False  # empty by default == not success
        assert result.provenance is None

    def test_success_semantics(self):
        from packages.omni_extraction import ExtractionResult

        assert ExtractionResult(text="hello").success is True
        assert ExtractionResult(djot="# title").success is True
        assert ExtractionResult(text="   ").success is False

    def test_to_dict_json_safe(self):
        import json

        from packages.omni_extraction import ExtractionResult

        result = ExtractionResult(text="t", confidence=0.5, table_count=2)
        payload = json.loads(json.dumps(result.to_dict()))
        assert payload["text"] == "t"
        assert payload["table_count"] == 2
        assert "raw" not in payload  # opaque object never serialized

    def test_confidence_coercion_guard(self):
        from packages.omni_extraction.extractor import _document_to_result
        from packages.omni_extraction.provenance import ProvenanceRecord

        class FakeDoc:
            content = "abc"
            djot = None
            confidence = "not-a-number"

        result = _document_to_result(FakeDoc(), ProvenanceRecord())
        assert result.confidence is None
        assert result.text == "abc"


class TestProvenance:
    """Provenance records must be complete and trustworthy."""

    def test_record_shape(self):
        from packages.omni_extraction import ProvenanceRecord

        record = ProvenanceRecord()
        payload = record.to_dict()
        assert set(payload.keys()) == {
            "tool", "tool_version", "path", "binary_sha256",
            "allow_network", "offline_env", "input_sha256",
            "duration_ms", "notes", "extra",
        }
        assert payload["tool"] == "xberg"
        assert payload["path"] == "library"

    def test_sha256_file_matches_hashlib(self, tmp_path):
        from packages.omni_extraction.provenance import sha256_file

        target = tmp_path / "doc.bin"
        target.write_bytes(b"synthetic-bytes-0123456789")
        expected = hashlib.sha256(target.read_bytes()).hexdigest()
        assert sha256_file(str(target)) == expected

    def test_build_provenance_hashes_input_and_times_call(self, tmp_path):
        from packages.omni_extraction.provenance import build_provenance

        doc = tmp_path / "doc.txt"
        doc.write_text("synthetic")
        started = __import__("time").perf_counter()
        record = build_provenance(
            path="library",
            input_path=str(doc),
            started_at=started,
            tool_version="1.2.6",
        )
        assert record.input_sha256 == hashlib.sha256(b"synthetic").hexdigest()
        assert record.duration_ms is not None and record.duration_ms >= 0
        assert record.tool_version == "1.2.6"


class TestFailClosed:
    """Engine absence must be loud in the main runtime."""

    def test_library_path_unavailable_in_main_env(self):
        from packages.omni_extraction import XbergExtractor

        extractor = XbergExtractor(engine_path="library")
        # xberg is intentionally NOT in the main dependency set.
        if _xberg_really_installed():  # pragma: no cover - isolated envs
            pytest.skip("xberg present in this env; fail-closed path N/A")
        assert extractor.is_available() is False

    def test_extract_raises_not_silent(self, tmp_path):
        from packages.omni_extraction import ExtractionError, XbergExtractor

        extractor = XbergExtractor(engine_path="library")
        if _xberg_really_installed():  # pragma: no cover
            pytest.skip("xberg present in this env; fail-closed path N/A")
        doc = tmp_path / "synthetic.txt"
        doc.write_text("no-phi synthetic content")
        with pytest.raises(ExtractionError):
            extractor.extract_file(str(doc))

    def test_cli_path_missing_binary_is_loud(self, tmp_path):
        from packages.omni_extraction import ExtractionError, XbergExtractor

        extractor = XbergExtractor(
            engine_path="cli",
            cli_binary=str(tmp_path / "definitely-missing-binary"),
        )
        assert extractor.is_available() is False
        doc = tmp_path / "synthetic.txt"
        doc.write_text("no-phi")
        with pytest.raises(ExtractionError):
            extractor.extract_file(str(doc))

    def test_unknown_engine_path_rejected(self):
        from packages.omni_extraction import XbergExtractor

        with pytest.raises(ValueError):
            XbergExtractor(engine_path="carrier-pigeon")

    def test_offline_mode_does_not_leak_env(self, tmp_path, monkeypatch):
        """Offline posture must mark the run, not leak env mutations."""
        from packages.omni_extraction import ExtractionError, XbergExtractor

        monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
        extractor = XbergExtractor(engine_path="library", allow_network=False)
        assert extractor._offline_env is True
        doc = tmp_path / "synthetic.txt"
        doc.write_text("no-phi synthetic content")
        if _xberg_really_installed():  # pragma: no cover - isolated envs
            pytest.skip("xberg present in this env; env-leak path N/A")
        with pytest.raises(ExtractionError):
            extractor.extract_file(str(doc))
        # Even on failure, the env must not be permanently mutated.
        assert "HF_HUB_OFFLINE" not in os.environ


def _xberg_really_installed() -> bool:
    try:
        import xberg  # noqa: F401

        return True
    except Exception:
        return False
