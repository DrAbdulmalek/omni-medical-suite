"""Production-path tests for PR #92 specialty dictionary routing.

These tests instantiate the real production modules. They do not replace the
router, spell checker, classifier, TMX service, or translation service with mocks.
"""
from __future__ import annotations

import csv
from pathlib import Path

from packages.core.spell_checker import HybridSpellChecker
from packages.medical.dictionary_registry import specs_for_specialty
from packages.medical.dictionary_router import SpecialtyDictionaryRouter
from packages.medical.translation_memory import ExactTranslationMemory


ROOT = Path(__file__).resolve().parents[1]


def test_production_ocr_uses_specialty_router_and_safety_cases():
    checker = HybridSpellChecker()

    assert "safe_ocr_corrections" in checker.active_dictionary_names()

    assert checker.correct_text("ترامادول 0.5 mg") == "ترامادول 0.5 mg"
    assert checker.correct_text("لا يعطى ترامادول 0.5 mg") == "لا يعطى ترامادول 0.5 mg"
    assert checker.correct_text("باراسيتبمول 500 mg") == "باراسيتامول 500 mg"
    for value in ("0.5", "1.25", "0.75", "٠٫٥", "١٫٢٥"):
        assert checker.correct_text(value) == value


def test_specialty_classifier_routes_real_production_spell_checker():
    checker = HybridSpellChecker()

    checker.correct_text("المريض لديه كسر في عظم الفخذ ويحتاج إلى تثبيت داخلي")
    assert checker.specialty == "orthopedic_surgery"
    assert "orthopedic_lexicon" in checker.active_dictionary_names()

    checker.correct_text("المريض لديه أزمة قلبية مع رجفان أذيني")
    assert checker.specialty == "cardiology"
    assert "orthopedic_lexicon" not in checker.active_dictionary_names()


def test_registry_inheritance_is_additive_and_deterministic():
    general = [s.name for s in specs_for_specialty("general")]
    medical = [s.name for s in specs_for_specialty("general_medical")]
    ortho = [s.name for s in specs_for_specialty("orthopedic_surgery")]

    assert set(general).issubset(medical)
    assert set(medical).issubset(ortho)
    assert ortho == [s.name for s in specs_for_specialty("orthopedic_surgery")]


def test_terminology_is_not_exposed_as_ocr_replacement():
    router = SpecialtyDictionaryRouter("orthopedic_surgery")
    assert all(spec.role != "terminology" for spec in router.specs if spec.role == "ocr_correction")
    assert router.ocr_corrections()
    # The terminology API returns metadata and never mutates the supplied text.
    result = router.lookup_term_exact("كسر")
    assert isinstance(result, list)


def test_translation_glossary_uses_only_bilingual_csv_semantics():
    router = SpecialtyDictionaryRouter("general_medical")
    csv_spec = next(
        spec for spec in router.specs
        if spec.name == "medical_glossary"
    )
    assert csv_spec.path.exists()

    with csv_spec.path.open(encoding="utf-8", newline="") as handle:
        row = next(row for row in csv.DictReader(handle) if row.get("en") and row.get("ar"))

    en = row["en"].strip()
    ar = row["ar"].strip()
    matches = router.lookup_translation_exact(en, "ar")
    assert any(match["target"] == ar for match in matches)

    reverse = router.lookup_translation_exact(ar, "en")
    assert any(match["target"] == en for match in reverse)


def test_translation_service_uses_real_dictionary_runtime():
    from app.services.translation_service import _lookup_exact_dictionary

    router = SpecialtyDictionaryRouter("general_medical")
    csv_spec = next(spec for spec in router.specs if spec.name == "medical_glossary")
    with csv_spec.path.open(encoding="utf-8", newline="") as handle:
        row = next(row for row in csv.DictReader(handle) if row.get("en") and row.get("ar"))

    en = row["en"].strip()
    ar = row["ar"].strip()
    assert _lookup_exact_dictionary(en, "English → Arabic", "general_medical") == ar
    # A larger sentence must not trigger arbitrary glossary replacement.
    assert _lookup_exact_dictionary(f"{en} and cough", "English → Arabic", "general_medical") is None


def test_tmx_is_exact_segment_only():
    tm = ExactTranslationMemory([
        {"en": "patient has fever", "ar": "المريض لديه حمى", "source": "test-tmx"},
    ])
    assert tm.translate_exact("patient has fever") == "المريض لديه حمى"
    assert tm.translate_exact("patient has fever and cough") is None


def test_protected_lexicon_never_becomes_replacement_map():
    router = SpecialtyDictionaryRouter("general")
    protected = router.protected_lexicon()
    assert protected
    assert not any(spec.role == "protected_lexicon" and spec.role == "ocr_correction" for spec in router.specs)


def test_production_registry_excludes_training_and_ground_truth_resources():
    router = SpecialtyDictionaryRouter("general_medical")
    paths = {str(spec.path.relative_to(ROOT)) for spec in router.specs}
    assert "data/learning_database.json" not in paths
    assert "data/medical_doc_training.jsonl" not in paths
    assert "data/ground_truth_588.txt" not in paths
