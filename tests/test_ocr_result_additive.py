"""Backward-compatibility + trail tests for the additive OCRResult fields.

Proves that the v1.1 provenance/fallback additions to
``packages/omni_ocr/adapter.py`` never break pre-existing construction
shapes or serialization consumers, and that the attempt trail behaves
exactly as documented.
"""

from packages.omni_ocr.adapter import OCRResult, UnifiedOCR

_OLD_KEYS = {
    "text", "confidence", "engine", "word_count",
    "processing_time", "words", "error",
}
_NEW_KEYS = {
    "provenance", "attempts", "fallback_used", "script_kind", "normalization",
}


class _StubOCR(UnifiedOCR):
    """Stubbed chain — injects synthetic dispatch outcomes, no engines."""

    def __init__(self, outcomes, **kwargs):
        super().__init__(cache_max_size=0, **kwargs)
        self._outcomes = list(outcomes)

    def _dispatch(self, engine_id, pil_image, file_path, languages):
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class TestBackwardCompatibility:
    """Pre-existing usage shapes keep working unchanged."""

    def test_old_style_construction(self):
        result = OCRResult(
            text="hello", confidence=0.9, engine="tesseract", word_count=1,
        )
        assert result.success is True
        assert result.fallback_used is False
        assert result.attempts == []
        assert result.provenance is None

    def test_to_dict_old_keys_unchanged(self):
        payload = OCRResult(text="x").to_dict()
        assert _OLD_KEYS.issubset(set(payload.keys()))
        assert set(payload.keys()) == _OLD_KEYS | _NEW_KEYS

    def test_to_dict_json_safe_with_new_fields(self):
        import json

        result = OCRResult(text="x", attempts=[{"engine": "e", "ok": True}])
        payload = json.loads(json.dumps(result.to_dict()))
        assert payload["attempts"] == [{"engine": "e", "ok": True}]

    def test_legacy_test_still_green(self):
        """Mirror of the pre-existing legacy tests on OCRResult defaults."""
        result = OCRResult()
        assert result.text == ""
        assert result.error == ""
        assert result.success is False


class TestAttemptTrail:
    """Fallback trail semantics across success and failure paths."""

    def _image(self):
        import PIL.Image

        return PIL.Image.new("RGB", (8, 8), "white")

    def test_recovery_marks_fallback_used(self):
        first = OCRResult(engine="first_stub", error="boom")
        second = OCRResult(
            text="recovered", confidence=0.8, engine="second_stub", word_count=1,
        )
        ocr = _StubOCR([first, second], engine_order=["first_stub", "second_stub"])
        result = ocr.process_image(self._image(), use_cache=False)

        assert result.success is True
        assert result.engine == "second_stub"
        assert result.fallback_used is True
        assert [a["engine"] for a in result.attempts] == [
            "first_stub", "second_stub",
        ]
        assert result.attempts[0]["ok"] is False
        assert result.attempts[1]["ok"] is True
        assert result.attempts[0]["duration_ms"] >= 0
        assert result.provenance["winning_engine"] == "second_stub"
        assert result.provenance["engine_order"] == ["first_stub", "second_stub"]

    def test_first_engine_win_keeps_fallback_false(self):
        winner = OCRResult(text="direct", confidence=1.0, engine="only", word_count=1)
        ocr = _StubOCR([winner], engine_order=["only"])
        result = ocr.process_image(self._image(), use_cache=False)

        assert result.success is True
        assert result.fallback_used is False
        assert len(result.attempts) == 1
        assert result.provenance["winning_engine"] == "only"

    def test_all_engines_fail_trail_recorded(self):
        ocr = _StubOCR(
            [RuntimeError("e1 exploded"), RuntimeError("e2 exploded")],
            engine_order=["e1", "e2"],
        )
        result = ocr.process_image(self._image(), use_cache=False)

        assert result.success is False
        assert result.engine == "none"
        assert result.fallback_used is False  # nothing won; no fallback used
        assert len(result.attempts) == 2
        assert result.provenance["winning_engine"] is None
        assert "e1: e1 exploded" in result.error

    def test_empty_text_counts_as_engine_failure(self):
        blank = OCRResult(engine="blank")  # no text -> not success
        winner = OCRResult(text="ok", confidence=0.5, engine="next", word_count=1)
        ocr = _StubOCR([blank, winner], engine_order=["blank", "next"])
        result = ocr.process_image(self._image(), use_cache=False)

        assert result.success is True
        assert result.attempts[0]["error"] == "no text produced"
        assert result.fallback_used is True
