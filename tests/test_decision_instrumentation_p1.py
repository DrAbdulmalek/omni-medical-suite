"""Tests for P1-3 — instrument RTL/dedup/field_extractor with log_decision()."""

from __future__ import annotations

import io
import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def captured_logs():
    """Capture log_decision output from the 'app.decision_log' logger."""
    from app.core.decision_log import _logger

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.setLevel(logging.INFO)
    _logger.addHandler(handler)
    try:
        yield stream
    finally:
        _logger.removeHandler(handler)


def _parse_log_lines(text: str) -> list[dict]:
    """Parse each non-empty line of `text` as JSON."""
    import json

    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ---------------------------------------------------------------------------
# RTL fixer instrumentation
# ---------------------------------------------------------------------------
class TestRtlInstrumentation:
    def test_rtl_fix_emits_decision(self, captured_logs):
        from src.ocr.rtl_utils import ArabicRTLFixer

        rtl = ArabicRTLFixer()
        rtl.analyze_and_fix("hello world", force=True)
        entries = _parse_log_lines(captured_logs.getvalue())
        rtl_entries = [e for e in entries if e.get("decision") == "rtl_fix"]
        assert len(rtl_entries) >= 1
        e = rtl_entries[-1]
        assert e["outcome"] in ("fixed", "unchanged")
        assert "reversal_ratio" in " ".join(e["reasons"])
        assert "inputs" in e
        assert "reversal_threshold" in e["inputs"]

    def test_rtl_fix_arabic_text(self, captured_logs):
        from src.ocr.rtl_utils import ArabicRTLFixer

        rtl = ArabicRTLFixer()
        # Arabic text with reversed tokens — should trigger fix
        rtl.analyze_and_fix("مرحبا بكم", force=True)
        entries = _parse_log_lines(captured_logs.getvalue())
        rtl_entries = [e for e in entries if e.get("decision") == "rtl_fix"]
        assert len(rtl_entries) >= 1


# ---------------------------------------------------------------------------
# Field extractor instrumentation
# ---------------------------------------------------------------------------
class TestFieldExtractorInstrumentation:
    def test_extract_fields_emits_decision(self, captured_logs):
        from src.ocr.field_extractor import ArabicMedicalFieldExtractor

        ext = ArabicMedicalFieldExtractor()
        ext.extract_fields("Patient Name: Ahmed")
        entries = _parse_log_lines(captured_logs.getvalue())
        fe_entries = [e for e in entries if e.get("decision") == "field_extraction"]
        assert len(fe_entries) >= 1
        e = fe_entries[-1]
        # P1-3: outcome should be a dict (not stringified) after the fix
        assert isinstance(e["outcome"], dict)
        assert "extracted_count" in e["outcome"]
        assert "has_medications" in e["outcome"]
        assert "medications_count" in e["outcome"]

    def test_no_labels_matched_emits_skipped(self, captured_logs):
        from src.ocr.field_extractor import ArabicMedicalFieldExtractor

        ext = ArabicMedicalFieldExtractor()
        ext.extract_fields("random text with no labels")
        entries = _parse_log_lines(captured_logs.getvalue())
        fe_entries = [e for e in entries if e.get("decision") == "field_extraction"]
        assert len(fe_entries) >= 1
        e = fe_entries[-1]
        assert e["outcome"]["extracted_count"] == 0
        assert "no_labels_matched" in e.get("skipped", [])


# ---------------------------------------------------------------------------
# Dedup instrumentation
# ---------------------------------------------------------------------------
class TestDedupInstrumentation:
    def test_deduplicate_emits_decision(self, captured_logs):
        from src.ocr.deduplication import WeightedMedicalDeduplicator

        dedup = WeightedMedicalDeduplicator()
        result = dedup.deduplicate(["Patient: A", "Patient: A"])
        entries = _parse_log_lines(captured_logs.getvalue())
        dedup_entries = [e for e in entries if e.get("decision") == "dedup_batch"]
        assert len(dedup_entries) >= 1
        e = dedup_entries[-1]
        # P1-3: outcome should be a dict
        assert isinstance(e["outcome"], dict)
        assert e["outcome"]["input_count"] == 2
        assert e["outcome"]["unique_count"] == result["unique_count"]
        assert "duplicate_threshold" in " ".join(e["reasons"])

    def test_dedup_no_duplicates(self, captured_logs):
        from src.ocr.deduplication import WeightedMedicalDeduplicator

        dedup = WeightedMedicalDeduplicator()
        dedup.deduplicate(["Patient Name: Ahmed", "Patient Name: Ali"])
        entries = _parse_log_lines(captured_logs.getvalue())
        dedup_entries = [e for e in entries if e.get("decision") == "dedup_batch"]
        assert len(dedup_entries) >= 1
        e = dedup_entries[-1]
        assert e["outcome"]["duplicate_count"] == 0


# ---------------------------------------------------------------------------
# _coerce_outcome dict handling (P1-3 fix)
# ---------------------------------------------------------------------------
class TestCoerceOutcomeDict:
    def test_dict_outcome_passes_through(self):
        from app.core.decision_log import _coerce_outcome

        result = _coerce_outcome({"a": 1, "b": "two"})
        assert isinstance(result, dict)
        assert result == {"a": 1, "b": "two"}

    def test_dict_with_nested_values(self):
        from app.core.decision_log import _coerce_outcome

        result = _coerce_outcome({"count": 5, "items": ["x", "y"]})
        assert isinstance(result, dict)
        assert result["count"] == 5
        assert result["items"] == ["x", "y"]

    def test_list_outcome_still_works(self):
        from app.core.decision_log import _coerce_outcome

        result = _coerce_outcome(["EasyOCR", "Tesseract"])
        assert result == ["EasyOCR", "Tesseract"]

    def test_string_outcome_still_works(self):
        from app.core.decision_log import _coerce_outcome

        assert _coerce_outcome("EasyOCR") == "EasyOCR"

    def test_int_outcome_still_works(self):
        from app.core.decision_log import _coerce_outcome

        assert _coerce_outcome(42) == 42


# ---------------------------------------------------------------------------
# Backward compat: existing decision_log tests still pass
# ---------------------------------------------------------------------------
class TestDecisionLogBackwardCompat:
    def test_existing_log_decision_api(self, captured_logs):
        from app.core.decision_log import log_decision

        result = log_decision(
            decision="test",
            outcome="ok",
            reasons=["smoke"],
        )
        assert result["decision"] == "test"
        assert result["outcome"] == "ok"
        entries = _parse_log_lines(captured_logs.getvalue())
        assert any(e["decision"] == "test" for e in entries)
