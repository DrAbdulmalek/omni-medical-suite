from pathlib import Path

import pytest

from packages.medical.translation_memory import ExactTranslationMemory

ROOT = Path(__file__).resolve().parents[1]
MALEK_TERMS = ROOT / "data" / "dictionaries" / "malek_data_terms.json"


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


@pytest.mark.skipif(
    not MALEK_TERMS.exists(),
    reason="malek_data_terms.json is git-ignored and regenerated only when the malek_data 7z archive is available",
)
def test_tm_provenance_is_preserved_for_specialty_source():
    """Every TM entry must have non-empty provenance (source attribution).
    The category may be 'translation_memory' or any other category the source
    TMX file assigned (e.g., 'vascular_complications', 'glossary_term').

    Skipped when ``data/dictionaries/malek_data_terms.json`` is absent — that
    file is git-ignored and regeneratable via ``scripts/setup_medical_dictionaries.py``.
    In a fresh CI clone without the private malek_data archive, the TMX index
    is intentionally empty."""
    tm = ExactTranslationMemory.from_specialty("orthopedic_surgery")
    found_any = False
    for bucket in tm._index.values():
        for entry in bucket:
            found_any = True
            # Provenance MUST be non-empty (source attribution is required)
            assert entry["provenance"], \
                f"Entry missing provenance: {entry}"
            # Category MUST be non-empty (defaults to 'translation_memory' if missing)
            assert entry["category"], \
                f"Entry missing category: {entry}"
    # Sanity: the TM index must have at least some entries
    assert found_any, "Specialty TM index is empty"
