"""Regression tests for PR #92 OCR source separation.

These tests pin the intended architecture:
- audited safe OCR corrections come from the registry/router;
- critical drug-name OCR fixes remain a small, explicit audited application map;
- neither source is applied with whole-string substring replacement;
- terminology/TM sources are not treated as OCR replacement maps.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_safe_ocr_source_is_loaded_by_production_checker():
    from packages.core.spell_checker import HybridSpellChecker

    safe = json.loads(
        (ROOT / "data/dictionaries/ocr_corrections_safe.json").read_text(encoding="utf-8")
    )
    checker = HybridSpellChecker()
    assert checker._arabic_fixes
    # A known audited safe correction must be available to the production checker.
    assert "الاستااذ" in checker._arabic_fixes
    assert checker._arabic_fixes["الاستااذ"] == safe["الاستااذ"]


def test_ocr_correction_is_exact_token_and_preserves_punctuation():
    from packages.core.spell_checker import HybridSpellChecker

    checker = HybridSpellChecker()
    corrected, changes = checker.apply_ocr_corrections(
        "الاستااذ، والالفل. والاسمالات", checker._arabic_fixes
    )
    assert corrected == "الأستاذ، والألف. والاسمالات"
    assert [c["from"] for c in changes] == ["الاستااذ", "الالفل"]
    assert "والاسمالات" in corrected


def test_critical_drug_correction_remains_explicit_and_exact_token():
    import app_core

    assert app_core.OCR_CORRECTIONS["باراسيتبمول"] == "باراسيتامول"
    out, changes = app_core._auto_correct_ocr("باراسيتبمولات باراسيتبمول،")
    assert "باراسيتبمولات" in out
    assert "باراسيتامول،" in out
    assert all(c["type"] in {"ocr_fix", "spell_check"} for c in changes)


def test_safe_ocr_map_does_not_become_terminology_or_tm_replacement():
    from packages.medical.dictionary_router import SpecialtyDictionaryRouter

    router = SpecialtyDictionaryRouter("general_medical")
    assert not hasattr(router, "replace_text")
    assert router.lookup_term_exact("الاستااذ") is None
    assert router.lookup_translation_exact("الاستااذ") is None


@pytest.mark.parametrize(
    "text",
    [
        "باراسيتبمولات",
        "ترامادول 0.5 mg",
        "لا يعطى ترامادول 0.5 mg",
        "0.5",
        "١٫٢٥",
    ],
)
def test_critical_ocr_path_never_uses_substring_replacement(text):
    import app_core

    out, _ = app_core._auto_correct_ocr(text)
    if text == "باراسيتبمولات":
        assert out == text
    else:
        assert out == text
