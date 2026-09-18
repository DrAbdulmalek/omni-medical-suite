"""TASK 005 - OCRResult contract v1.1 tests (backward-compatible extension)."""
import dataclasses
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from packages.omni_ocr.adapter import OCRResult  # noqa: E402

CONTRACT_VERSION = OCRResult.CONTRACT_VERSION  # class attribute, not module-level

OLD_KEYS = {"text", "confidence", "engine", "word_count", "processing_time", "words", "error"}
NEW_KEYS = {
    "contract_version", "blocks", "lines", "characters", "language", "script",
    "page", "engine_version", "model", "model_version", "provenance",
    "warnings", "fallback_status",
}


def test_v10_positional_construction_unchanged():
    # v1.0 positional order must remain: text, confidence, engine, word_count, ...
    r = OCRResult("hello", 0.9, "tesseract", 1, 0.5, [], None, "")
    assert r.text == "hello" and r.confidence == 0.9 and r.engine == "tesseract"
    assert r.word_count == 1 and r.processing_time == 0.5 and r.error == ""


def test_new_fields_default_safe():
    r = OCRResult()
    assert r.blocks == [] and r.lines == [] and r.characters == []
    assert r.language == "" and r.script == "" and r.page is None
    assert r.engine_version == "" and r.model == "" and r.model_version == ""
    assert r.provenance == {} and r.warnings == [] and r.fallback_status == "none"


def test_to_dict_backward_compatible():
    d = OCRResult("نص", 0.8, "easyocr").to_dict()
    assert OLD_KEYS <= set(d), "old keys must remain"
    assert NEW_KEYS <= set(d), "new keys must exist"
    assert d["contract_version"] == "1.1" == CONTRACT_VERSION
    # old key types unchanged
    assert isinstance(d["words"], list) and isinstance(d["confidence"], float)


def test_round_trip_serialization():
    r = OCRResult(
        text="الكلية", confidence=0.93, engine="TrOCR", word_count=1,
        language="ar", script="arab", page=1, fallback_status="none",
        provenance={"router_profile": "balanced"},
    )
    d = r.to_dict()
    assert d["text"] == "الكلية" and d["language"] == "ar" and d["script"] == "arab"
    assert d["provenance"]["router_profile"] == "balanced"
    # new fields are dataclass fields (not ClassVar), old count + 13
    field_names = [f.name for f in dataclasses.fields(OCRResult)]
    assert len(field_names) == 8 + 12


def test_contract_version_is_classvar_not_field():
    assert "CONTRACT_VERSION" not in [f.name for f in dataclasses.fields(OCRResult)]
