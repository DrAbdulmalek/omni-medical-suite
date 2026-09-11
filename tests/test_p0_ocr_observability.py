"""P0-B acceptance tests — fail-visible OCR (no silent fallbacks).

Contract under test (see PR body / task spec):
  1. A PaddleOCR exception is surfaced as status "error" — never a silent
     ("", []) that masquerades as a successful empty scan.
  2. "unavailable" ≠ "error" ≠ "empty" — the three failure modes are
     distinguishable.
  3. Paddle 0..1 confidences are converted to percent (0..100) exactly once
     at the service boundary.
  4. Both engines failing/empty is a FAILURE (no fabricated document, no
     placeholder fed into correction, explicit user-visible error).
  5. The len>5 heuristic keeps working and records fallback_used.
  6. correction failures surface as correction_failed=True.
  7. Double correction is gone: exactly ONE correct_text() call on every
     production path (HF Space / mobile / review service).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[1]


class _BoomPaddle:
    """PaddleOCR stand-in whose .ocr() always raises."""

    def ocr(self, *args, **kwargs):
        raise RuntimeError("paddle exploded (simulated)")


class _FakePaddle:
    """PaddleOCR stand-in returning a fixed raw 0..1-confidence result."""

    def __init__(self, lines):
        self._lines = lines

    def ocr(self, *args, **kwargs):
        return [self._lines]


def _load_ocr_service():
    import app.services.ocr_service as ocr

    return ocr


def _load_hitl():
    import app.gradio_full_hitl as hitl

    return hitl


# ---------------------------------------------------------------------------
# Engine status contract
# ---------------------------------------------------------------------------


def test_paddle_exception_is_not_silent_success(monkeypatch):
    """A crashing engine must surface status='error', not ("", [])."""
    ocr = _load_ocr_service()
    monkeypatch.setattr(ocr, "get_paddle_ocr", lambda: _BoomPaddle())
    image = np.zeros((16, 16, 3), dtype=np.uint8)
    text, details, status = ocr._run_paddle_ocr(image)
    assert text == "" and details == []
    assert status == "error"


def test_paddle_unavailable_is_distinct_from_error(monkeypatch):
    """Not-installed is 'unavailable', not 'error' and not an empty success."""
    ocr = _load_ocr_service()
    monkeypatch.setattr(ocr, "get_paddle_ocr", lambda: None)
    image = np.zeros((16, 16, 3), dtype=np.uint8)
    text, _, status = ocr._run_paddle_ocr(image)
    assert text == ""
    assert status == "unavailable"


def test_paddle_ran_but_empty_is_distinct_status(monkeypatch):
    """Engine ran fine and found nothing → 'empty', not 'error'/'unavailable'."""
    ocr = _load_ocr_service()
    monkeypatch.setattr(ocr, "get_paddle_ocr", lambda: _FakePaddle([]))
    image = np.zeros((16, 16, 3), dtype=np.uint8)
    text, _, status = ocr._run_paddle_ocr(image)
    assert text == ""
    assert status == "empty"


def test_paddle_confidence_is_percent_at_service_boundary(monkeypatch):
    """Paddle's 0..1 confidences are converted once to 0..100 percent."""
    ocr = _load_ocr_service()
    paddle = _FakePaddle([
        [[[0, 0], [1, 0], [1, 1], [0, 1]], ("باراسيتامول", 0.87)],
        [[[0, 0], [1, 0], [1, 1], [0, 1]], ("500", 0.95)],
    ])
    monkeypatch.setattr(ocr, "get_paddle_ocr", lambda: paddle)
    image = np.zeros((16, 16, 3), dtype=np.uint8)
    text, details, status = ocr._run_paddle_ocr(image)
    assert status == "ok"
    assert "باراسيتامول" in text
    confs = [d["confidence"] for d in details]
    assert all(0.0 <= c <= 100.0 for c in confs)
    assert any(abs(c - 87.0) < 0.01 for c in confs)


# ---------------------------------------------------------------------------
# full_process fail-visible behavior (HITL production path)
# ---------------------------------------------------------------------------


def _patch_hitl_engines(monkeypatch, hitl, ocr, paddle_result, tesseract_result):
    """Force full_process onto deterministic engines (module-level names,
    exactly as the production code resolves them)."""
    monkeypatch.setattr(
        hitl, "_run_paddle_ocr", lambda img: paddle_result, raising=True
    )
    monkeypatch.setattr(
        hitl, "_run_tesseract", lambda img: tesseract_result, raising=True
    )
    # Neutral spell checker so correction is deterministic in tests.
    fake_checker = MagicMock()
    fake_checker.apply_ocr_corrections.side_effect = lambda text, corrections: (text, [])
    fake_checker.correct_text.side_effect = lambda text: text
    monkeypatch.setattr(ocr, "get_spell_checker", lambda: fake_checker)
    return fake_checker


def test_both_engines_empty_is_failure_not_document(monkeypatch):
    """Both engines empty → corrected/raw are EMPTY strings, the status is a
    failure with a user-visible error, and nothing clean is fabricated."""
    ocr = _load_ocr_service()
    hitl = _load_hitl()
    _patch_hitl_engines(monkeypatch, hitl, ocr,
                        ("", [], "empty"), ("", 0.0, "empty"))
    image = np.full((32, 32, 3), 200, dtype=np.uint8)
    cleaned, corrected, raw_text, entities, status_str, ocr_status = hitl.full_process(image)
    assert corrected == ""
    assert raw_text == ""
    assert ocr_status["selected_engine"] == "none"
    assert bool(ocr_status["user_visible_error"])
    assert "فشل" in status_str or "❌" in status_str


def test_placeholder_never_reaches_correction(monkeypatch):
    """The '[لم يتم اكتشاف نص]' placeholder must never be corrected into a
    fake document — it must not appear anywhere in the outputs."""
    ocr = _load_ocr_service()
    hitl = _load_hitl()
    _patch_hitl_engines(monkeypatch, hitl, ocr,
                        ("", [], "error"), ("", 0.0, "unavailable"))
    image = np.full((32, 32, 3), 200, dtype=np.uint8)
    _, corrected, raw_text, _, _, ocr_status = hitl.full_process(image)
    assert "[لم يتم اكتشاف نص]" not in (corrected or "")
    assert "[لم يتم اكتشاف نص]" not in (raw_text or "")
    assert ocr_status["paddle_status"] == "error"
    assert ocr_status["tesseract_status"] == "unavailable"


def test_len5_heuristic_records_fallback_used(monkeypatch):
    """Paddle returns text but <= 5 chars → Tesseract selected and the
    fallback is recorded in the structured status (heuristic preserved)."""
    ocr = _load_ocr_service()
    hitl = _load_hitl()
    _patch_hitl_engines(monkeypatch, hitl, ocr,
                        ("ab", [{"line": 1, "text": "ab", "confidence": 90.0}], "ok"),
                        ("هذا نص أطول من خمسة أحرف", 88.0, "ok"))
    image = np.full((32, 32, 3), 200, dtype=np.uint8)
    _, corrected, raw_text, _, _, ocr_status = hitl.full_process(image)
    assert ocr_status["selected_engine"] == "tesseract"
    assert ocr_status["fallback_used"] is True
    assert "len<=5" in (ocr_status["fallback_reason"] or "")
    assert "أطول" in raw_text


def test_correction_failed_surfaced(monkeypatch):
    """When the correction stage blows up, correction_failed=True is surfaced
    instead of silently presenting unchecked text."""
    ocr = _load_ocr_service()
    hitl = _load_hitl()
    _patch_hitl_engines(monkeypatch, hitl, ocr,
                        ("", [], "unavailable"),
                        ("هذا نص أطول من خمسة أحرف", 88.0, "ok"))
    # Replace the checker with one whose correct_text raises.
    boom_checker = MagicMock()
    boom_checker.apply_ocr_corrections.side_effect = lambda text, corrections: (text, [])
    boom_checker.correct_text.side_effect = RuntimeError("checker exploded")
    monkeypatch.setattr(ocr, "get_spell_checker", lambda: boom_checker)

    # Force the _with_status variant to see the internal failure path.
    corrected, changes, correction_failed = ocr._auto_correct_ocr_with_status("نص تجريبي")
    # Internal per-stage errors are non-fatal by contract; the variant must
    # agree with the canonical output.
    canonical, canonical_changes = ocr._auto_correct_ocr("نص تجريبي")
    assert corrected == canonical

    # A true unexpected failure of the canonical function is flagged.
    monkeypatch.setattr(ocr, "_auto_correct_ocr",
                        MagicMock(side_effect=RuntimeError("normalization exploded")))
    _, _, failed = ocr._auto_correct_ocr_with_status("نص تجريبي")
    assert failed is True


# ---------------------------------------------------------------------------
# Double-correction removal (B2)
# ---------------------------------------------------------------------------


def test_no_second_correct_text_after_auto_correct(monkeypatch):
    """correct_text() must be called exactly ONCE on each production path:
    the canonical _auto_correct_ocr internals. The extra post-calls in
    hf-space/app_core.py, mobile/server.py and review_service.py are gone."""

    # Static contract: per-file call counts. The lowercase pattern
    # "checker.correct_text(" matches only real calls, never docstring
    # mentions of HybridSpellChecker.correct_text().
    expectations = {
        "app/services/ocr_service.py": ("checker.correct_text(", 1),   # canonical
        "hf-space/app_core.py": ("checker.correct_text(", 1),          # canonical copy
        "packages/core/mobile/server.py": (".correct_text(", 0),        # extra removed
        "app/services/review_service.py": (".correct_text(", 0),        # extra removed
    }
    for rel, (pattern, expected) in expectations.items():
        src = (REPO_ROOT / rel).read_text(encoding="utf-8")
        count = src.count(pattern)
        assert count == expected, f"{rel}: expected {expected} '{pattern}', got {count}"

    # Behavioral contract on the HF Space path (gradio-independent core).
    spec = importlib.util.spec_from_file_location(
        "app_core_p0b", REPO_ROOT / "hf-space" / "app_core.py"
    )
    app_core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_core)

    calls = {"n": 0}

    class CountingChecker:
        def apply_ocr_corrections(self, text, corrections):
            return text, []

        def correct_text(self, text):
            calls["n"] += 1
            return text

    monkeypatch.setattr(app_core, "spell_checker", CountingChecker(), raising=True)
    monkeypatch.setattr(app_core, "_run_paddle_ocr",
                        lambda img: ("", [], "unavailable"), raising=True)
    monkeypatch.setattr(app_core, "_run_tesseract",
                        lambda img: ("هذا نص أطول من خمسة أحرف", 88.0, "ok"), raising=True)
    monkeypatch.setattr(app_core, "proofreader", None, raising=True)
    monkeypatch.setattr(app_core, "ner", None, raising=True)

    image = np.full((32, 32, 3), 200, dtype=np.uint8)
    app_core.full_process(image)
    assert calls["n"] == 1, f"HF Space path called correct_text {calls['n']} times, expected 1"


def test_mobile_process_marks_failure_when_both_engines_empty(monkeypatch):
    """Mobile /process: both engines empty → top-level status 'failure' with
    ocr_status diagnostics (mobile server shares the production pipeline).
    Skipped when Flask is not installed (e.g. CI without the mobile deps)."""
    pytest.importorskip("flask")
    pytest.importorskip("PIL")
    monkeypatch.setenv("OMNI_MOBILE_DB_DIR", str(REPO_ROOT / "data"))

    server_spec = importlib.util.spec_from_file_location(
        "mobile_server_p0b", REPO_ROOT / "packages" / "core" / "mobile" / "server.py"
    )
    server = importlib.util.module_from_spec(server_spec)
    server_spec.loader.exec_module(server)
    assert server.HAS_APP_SERVICES, "app.services.* must be importable in the test env"

    ocr = _load_ocr_service()
    monkeypatch.setattr(server, "_run_paddle_ocr", lambda img: ("", [], "empty"))
    monkeypatch.setattr(server, "_run_tesseract", lambda img: ("", 0.0, "error"))
    monkeypatch.setattr(ocr, "get_spell_checker", lambda: None)

    client = server.app.test_client()
    import io

    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", (32, 32), (200, 200, 200)).save(buf, format="PNG")
    buf.seek(0)
    resp = client.post("/process", data={"image": (buf, "x.png")})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "failure"
    assert body["result"]["ocr_status"]["selected_engine"] == "none"
    assert body["result"]["corrected_text"] == ""
