from packages.medical.translation_memory import ExactTranslationMemory


def test_translation_memory_is_exact_not_substring_replacement():
    tm = ExactTranslationMemory([
        {"en": "heart", "ar": "قلب", "source": "test:tmx"},
        {"en": "heart rate", "ar": "معدل ضربات القلب", "source": "test:tmx"},
    ])
    assert tm.translate_exact("heart") == "قلب"
    assert tm.translate_exact("heart rate") == "معدل ضربات القلب"
    assert tm.translate_exact("patient has heart disease") is None
    assert tm.translate_exact("my heart") is None


def test_translation_memory_never_rewrites_arbitrary_text():
    tm = ExactTranslationMemory([
        {"en": "tramadol", "ar": "ترامادول", "source": "malek_data:file.tmx"},
    ])
    text = "tramadol 0.5 mg"
    assert tm.translate_exact(text) is None
    assert text == "tramadol 0.5 mg"


def test_translation_memory_preserves_provenance():
    tm = ExactTranslationMemory([
        {"en": "fracture", "ar": "كسر", "source": "arabic_medical_glossary:source.csv", "category": "glossary_term"},
    ])
    match = tm.lookup_exact("fracture")
    assert len(match) == 1
    assert match[0]["provenance"] == "arabic_medical_glossary:source.csv"
    assert match[0]["category"] == "glossary_term"
