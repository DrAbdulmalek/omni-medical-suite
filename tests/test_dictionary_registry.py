from packages.medical.dictionary_registry import (
    DICTIONARY_REGISTRY,
    NON_DICTIONARY_RESOURCES,
    canonical_specialty,
    protected_terms_for_specialty,
    registry_manifest,
    specs_for_specialty,
)
from packages.medical.dictionary_router import SpecialtyDictionaryRouter


def test_registry_covers_all_dictionary_like_sources():
    names = {s.name for s in DICTIONARY_REGISTRY}
    assert {
        "arabic_ocr_fixes",
        "safe_ocr_corrections",
        "general_correction_seed",
        "medical_dictionary",
        "orthopedic_lexicon",
        "medical_glossary",
        "malek_tmx",
        "translation_rules",
    } <= names
    assert "data/learning_database.json" in NON_DICTIONARY_RESOURCES
    assert "data/medical_doc_training.jsonl" in NON_DICTIONARY_RESOURCES


def test_specialty_selection_adds_orthopedic_terms_without_using_ortho_as_ocr_map():
    general = {s.name for s in specs_for_specialty("general_medical")}
    ortho = {s.name for s in specs_for_specialty("orthopedic_surgery")}
    assert "medical_dictionary" in general
    assert "orthopedic_lexicon" not in general
    assert "orthopedic_lexicon" in ortho
    assert "safe_ocr_corrections" in ortho
    assert next(s for s in DICTIONARY_REGISTRY if s.name == "orthopedic_lexicon").role == "terminology"


def test_router_uses_orthopedic_lexicon_as_exact_lookup_and_protection():
    router = SpecialtyDictionaryRouter("orthopedic surgery")
    assert router.specialty == "orthopedic_surgery"
    protected = router.protected_terms()
    assert "كسر" in protected
    matches = router.lookup_term_exact("كسر")
    assert matches
    assert all(m["dictionary"] == "orthopedic_lexicon" for m in matches)


def test_router_does_not_expose_terminology_as_replacement_map():
    router = SpecialtyDictionaryRouter("orthopedic_surgery")
    assert not hasattr(router, "replace_text")
    assert router.lookup_term_exact("المريض لديه كسر") == []


def test_general_and_orthopedic_ocr_maps_are_the_same_audited_layer():
    general = SpecialtyDictionaryRouter("general")
    ortho = SpecialtyDictionaryRouter("orthopedic_surgery")
    assert general.ocr_corrections().get("باراسيتبمول") == "باراسيتامول"
    assert ortho.ocr_corrections().get("باراسيتبمول") == "باراسيتامول"


def test_manifest_is_deterministic_and_records_roles():
    first = registry_manifest()
    second = registry_manifest()
    assert first == second
    assert {x["role"] for x in first} >= {"ocr_correction", "terminology", "translation_memory", "translation_rule"}


def test_specialty_aliases():
    assert canonical_specialty("ortho") == "orthopedic_surgery"
    assert canonical_specialty("medicine") == "general_medical"
