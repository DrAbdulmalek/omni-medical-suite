"""tests/test_pr94_production_engine_decision.py — Issue #94.

Production-path tests for engine-selection decision logging.

These tests exercise the REAL production selector (_select_ocr_result in
hf-space/app_core.py) — NOT EngineRouter. They mock only the OCR engine
outputs (paddle_text, tesseract_text) so the test is deterministic and
does not require heavy OCR dependencies (paddleocr, tesseract binaries).

Required cases (from issue #94):
    A. PaddleOCR >5 chars → selected, decision log exists, no PHI in inputs
    B. PaddleOCR ≤5 chars → Tesseract selected, reason explains fallback
    C. Neither produces text → no usable engine, fallback string preserved
    D. log_decision raising → selection still returns same result (never-fail)
    E. Regression: no raw OCR text / medical terms / patient data in logs
"""
from __future__ import annotations

import io
import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Production path: tests/security/test_medical_behavior.py uses the same path
sys.path.insert(0, str(ROOT))
# hf-space must come AFTER ROOT so packages/core/spell_checker.py is found
# from the canonical location, but app_core is found from hf-space/.
HF_SPACE = ROOT / "hf-space"
if str(HF_SPACE) not in sys.path:
    sys.path.append(str(HF_SPACE))


def _capture_decision_logs() -> io.StringIO:
    """Attach a StringIO handler to the decision_log logger and return it."""
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(logging.Formatter("%(message)s"))
    dl_logger = logging.getLogger("app.decision_log")
    dl_logger.addHandler(handler)
    dl_logger.setLevel(logging.INFO)
    return buf


def _get_logged_decisions(buf: io.StringIO) -> list[dict]:
    """Parse JSON-lines decision logs from the StringIO buffer."""
    decisions = []
    for line in buf.getvalue().strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            decisions.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return decisions


class TestSelectOcrResultPaddleSelected:
    """Case A: PaddleOCR produces >5 characters → PaddleOCR selected."""

    def test_paddle_selected_when_text_exceeds_threshold(self):
        from app_core import _select_ocr_result

        buf = _capture_decision_logs()
        try:
            raw_text, conf, engine_info = _select_ocr_result(
                paddle_text="مرحبا بالعالم هذا نص طويل",
                paddle_details=[{"confidence": 0.95}, {"confidence": 0.90}],
                tesseract_text="short fallback",
                tess_conf=0.80,
            )
        finally:
            logging.getLogger("app.decision_log").handlers.clear()

        # Selection result: PaddleOCR text wins
        assert raw_text == "مرحبا بالعالم هذا نص طويل"
        # Confidence is the average of paddle_details confidences
        assert conf == pytest.approx(0.925, abs=0.01)
        # engine_info includes PaddleOCR
        assert "PaddleOCR" in engine_info

        # Decision log was emitted
        decisions = _get_logged_decisions(buf)
        assert len(decisions) == 1
        d = decisions[0]
        assert d["decision"] == "engine_selection"
        assert d["outcome"] == ["PaddleOCR"]
        assert any("PaddleOCR" in r for r in d["reasons"])

    def test_no_ocr_text_in_logged_inputs(self):
        """Regression: no OCR text, medical terms, or PHI in decision log inputs."""
        from app_core import _select_ocr_result

        # Use text that contains medical terms + patient-like identifiers
        sensitive_paddle_text = "المريض أحمد يحتاج ترامادول 0.5 mg - ID:12345"
        sensitive_tesseract_text = "patient: ahmed, drug: tramadol, dose: 0.5mg"

        buf = _capture_decision_logs()
        try:
            _select_ocr_result(
                paddle_text=sensitive_paddle_text,
                paddle_details=[{"confidence": 0.9}],
                tesseract_text=sensitive_tesseract_text,
                tess_conf=0.8,
            )
        finally:
            logging.getLogger("app.decision_log").handlers.clear()

        decisions = _get_logged_decisions(buf)
        assert len(decisions) == 1
        d = decisions[0]
        inputs_json = json.dumps(d["inputs"], ensure_ascii=False)

        # NO raw OCR text may appear in inputs
        assert sensitive_paddle_text not in inputs_json
        assert sensitive_tesseract_text not in inputs_json
        # NO medical terms may appear in inputs
        for term in ("ترامادول", "tramadol", "ahmed", "أحمد", "0.5mg", "0.5 mg", "patient"):
            assert term not in inputs_json.lower(), f"PHI/medical term {term!r} leaked into inputs: {inputs_json}"
        # Inputs contain ONLY operational metadata
        assert set(d["inputs"].keys()) == {
            "paddle_available",
            "paddle_text_length",
            "tesseract_available",
            "tesseract_text_length",
            "selection_rule",
        }


class TestSelectOcrResultTesseractFallback:
    """Case B: PaddleOCR ≤5 chars → Tesseract selected."""

    def test_tesseract_selected_when_paddle_too_short(self):
        from app_core import _select_ocr_result

        buf = _capture_decision_logs()
        try:
            raw_text, conf, engine_info = _select_ocr_result(
                paddle_text="abc",  # stripped length 3 ≤ 5
                paddle_details=[{"confidence": 0.5}],
                tesseract_text="هذا النص من tesseract",
                tess_conf=0.85,
            )
        finally:
            logging.getLogger("app.decision_log").handlers.clear()

        # Tesseract text wins (paddle too short)
        assert raw_text == "هذا النص من tesseract"
        # Note: selected_confidence still uses paddle_details because the
        # original inline logic checks "if paddle_text and paddle_details"
        # (paddle_text="abc" is truthy, paddle_details is non-empty).
        # This is the PRESERVED behavior — the helper does not change it.
        assert conf == 0.5
        assert "Tesseract" in engine_info

        decisions = _get_logged_decisions(buf)
        assert len(decisions) == 1
        d = decisions[0]
        assert d["outcome"] == ["Tesseract"]
        assert any("Tesseract" in r for r in d["reasons"])
        assert "PaddleOCR" in d.get("skipped", [])

    def test_tesseract_selected_when_paddle_empty(self):
        from app_core import _select_ocr_result

        buf = _capture_decision_logs()
        try:
            raw_text, conf, engine_info = _select_ocr_result(
                paddle_text="",
                paddle_details=[],
                tesseract_text="tesseract output here",
                tess_conf=0.70,
            )
        finally:
            logging.getLogger("app.decision_log").handlers.clear()

        assert raw_text == "tesseract output here"
        decisions = _get_logged_decisions(buf)
        d = decisions[0]
        assert d["outcome"] == ["Tesseract"]
        assert d["inputs"]["paddle_available"] is False


class TestSelectOcrResultNoEngine:
    """Case C: Neither engine produces text → fallback string."""

    def test_fallback_string_when_neither_produces_text(self):
        from app_core import _select_ocr_result

        buf = _capture_decision_logs()
        try:
            raw_text, conf, engine_info = _select_ocr_result(
                paddle_text="",
                paddle_details=[],
                tesseract_text="",
                tess_conf=0.0,
            )
        finally:
            logging.getLogger("app.decision_log").handlers.clear()

        # Fallback string preserved
        assert raw_text == "[لم يتم اكتشاف نص]"
        assert conf == 0.0
        assert engine_info == {}

        decisions = _get_logged_decisions(buf)
        assert len(decisions) == 1
        d = decisions[0]
        assert d["outcome"] == []
        assert any("No OCR engine" in r for r in d["reasons"])


class TestSelectOcrResultLoggingNeverFails:
    """Case D: log_decision raising → selection still returns same result."""

    def test_selection_unaffected_by_logging_failure(self):
        from app_core import _select_ocr_result
        from app.core import decision_log

        # Make log_decision raise — selection must still work
        with patch.object(decision_log, "log_decision", side_effect=RuntimeError("logging broken")):
            raw_text, conf, engine_info = _select_ocr_result(
                paddle_text="this is a long enough paddle text",
                paddle_details=[{"confidence": 0.92}],
                tesseract_text="short",
                tess_conf=0.5,
            )

        # Selection result is correct despite logging failure
        assert raw_text == "this is a long enough paddle text"
        assert conf == 0.92
        assert "PaddleOCR" in engine_info

    def test_selection_unaffected_by_import_failure(self):
        """If the decision_log module can't be imported, selection still works."""
        from app_core import _select_ocr_result

        # Simulate import failure by making the module unimportable
        import builtins
        original_import = builtins.__import__

        def blocked_import(name, *args, **kwargs):
            if name == "app.core.decision_log" or name == "app.core":
                raise ImportError("simulated import failure")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=blocked_import):
            raw_text, conf, engine_info = _select_ocr_result(
                paddle_text="paddle output is long enough",
                paddle_details=[{"confidence": 0.88}],
                tesseract_text="tess",
                tess_conf=0.6,
            )

        assert raw_text == "paddle output is long enough"
        assert conf == 0.88


class TestSelectOcrResultBehaviorPreserved:
    """Verify the refactor preserves the exact previous inline behavior."""

    def test_paddle_5_chars_boundary_not_selected(self):
        """PaddleOCR text of exactly 5 chars (stripped) should NOT be selected
        (the rule is strictly >5, not >=5)."""
        from app_core import _select_ocr_result

        # Exactly 5 chars after strip → NOT selected (rule is >5)
        raw_text, _, _ = _select_ocr_result(
            paddle_text="abcde",  # len 5, not >5
            paddle_details=[{"confidence": 0.9}],
            tesseract_text="tesseract fallback",
            tess_conf=0.7,
        )
        assert raw_text == "tesseract fallback"

    def test_paddle_6_chars_boundary_selected(self):
        """PaddleOCR text of 6 chars (stripped) SHOULD be selected."""
        from app_core import _select_ocr_result

        raw_text, _, _ = _select_ocr_result(
            paddle_text="abcdef",  # len 6, >5
            paddle_details=[{"confidence": 0.9}],
            tesseract_text="tesseract fallback",
            tess_conf=0.7,
        )
        assert raw_text == "abcdef"

    def test_confidence_calculation_paddle(self):
        """selected_confidence = mean of paddle_details confidences when paddle selected."""
        from app_core import _select_ocr_result

        _, conf, _ = _select_ocr_result(
            paddle_text="long paddle text",
            paddle_details=[{"confidence": 0.80}, {"confidence": 0.90}, {"confidence": 1.0}],
            tesseract_text="tess",
            tess_conf=0.5,
        )
        assert conf == pytest.approx(0.9, abs=0.01)  # (0.8+0.9+1.0)/3

    def test_confidence_calculation_tesseract(self):
        """selected_confidence uses tess_conf only when paddle_text is falsy
        or paddle_details is empty. This is the preserved behavior."""
        from app_core import _select_ocr_result

        # Case 1: paddle_text is non-empty but short → confidence still uses
        # paddle_details (original logic: "if paddle_text and paddle_details")
        _, conf1, _ = _select_ocr_result(
            paddle_text="ab",  # truthy
            paddle_details=[{"confidence": 0.99}],  # non-empty
            tesseract_text="tesseract output",
            tess_conf=0.77,
        )
        assert conf1 == 0.99  # paddle_details confidence, NOT tess_conf

        # Case 2: paddle_text is empty → confidence uses tess_conf
        _, conf2, _ = _select_ocr_result(
            paddle_text="",  # falsy
            paddle_details=[],  # empty
            tesseract_text="tesseract output",
            tess_conf=0.77,
        )
        assert conf2 == 0.77  # tess_conf

    def test_engine_info_populated_correctly(self):
        from app_core import _select_ocr_result

        # tess_conf=85.0 represents 85% (the original code formats with :.0f)
        _, _, engine_info = _select_ocr_result(
            paddle_text="paddle output here",
            paddle_details=[{"confidence": 0.9}, {"confidence": 0.8}],
            tesseract_text="tess output",
            tess_conf=85.0,  # 85% — formatted as "confidence 85%"
        )
        assert "PaddleOCR" in engine_info
        assert "2 lines" in engine_info["PaddleOCR"]
        assert "Tesseract" in engine_info
        assert "85%" in engine_info["Tesseract"]


class TestNoPhiInDecisionLogs:
    """Regression: no PHI/medical/raw-OCR in decision log inputs."""

    @pytest.mark.parametrize("paddle_text,tesseract_text,patient_data", [
        ("المريض يحتاج ترامادول 0.5 mg", "patient needs tramadol", "ترامادول"),
        ("اسم المريض: أحمد", "patient name: ahmed", "أحمد"),
        ("الجرعة 1.25 ml يومياً", "dose 1.25 ml daily", "1.25 ml"),
        ("لا يعطى باراسيتامول 500 mg", "do not give paracetamol", "باراسيتامول"),
    ])
    def test_no_patient_data_leaked_into_inputs(self, paddle_text, tesseract_text, patient_data):
        from app_core import _select_ocr_result

        buf = _capture_decision_logs()
        try:
            _select_ocr_result(
                paddle_text=paddle_text,
                paddle_details=[{"confidence": 0.9}],
                tesseract_text=tesseract_text,
                tess_conf=0.8,
            )
        finally:
            logging.getLogger("app.decision_log").handlers.clear()

        decisions = _get_logged_decisions(buf)
        assert len(decisions) == 1
        d = decisions[0]
        inputs_json = json.dumps(d["inputs"], ensure_ascii=False)
        assert patient_data not in inputs_json, (
            f"Patient data {patient_data!r} leaked into decision log inputs: {inputs_json}"
        )
