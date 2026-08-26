from packages.medical.translation_memory import ExactTranslationMemory


def test_specialty_tm_is_selected_from_registry_not_all_sources():
    general = ExactTranslationMemory.from_specialty("general")
    medical = ExactTranslationMemory.from_specialty("general_medical")
    ortho = ExactTranslationMemory.from_specialty("orthopedic_surgery")
    # General-language routing must not silently ingest medical TMX.
    assert not general.contains_exact("fracture") or general.translate_exact("fracture") is None
    # Medical/orthopedic contexts are allowed to use the medical TMX source.
    assert isinstance(medical._index, dict)
    assert isinstance(ortho._index, dict)


def test_specialty_tm_remains_exact_match_only():
    tm = ExactTranslationMemory.from_specialty("orthopedic_surgery")
    arbitrary = "patient has a fracture of the femur"
    assert tm.translate_exact(arbitrary) is None


def test_tm_provenance_is_preserved_for_specialty_source():
    tm = ExactTranslationMemory.from_specialty("orthopedic_surgery")
    for bucket in tm._index.values():
        for entry in bucket:
            assert entry["provenance"]
            assert entry["category"] == "translation_memory"
