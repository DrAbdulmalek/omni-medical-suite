from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import packages.medical.dictionary_router as dictionary_router
import pytest

from packages.medical.dictionary_registry import DictionarySpec, canonical_specialty
from packages.medical.dictionary_router import SpecialtyDictionaryRouter
from packages.medical.translation_memory import ExactTranslationMemory


def _registry(root: Path, *, orthopedic_exists: bool) -> tuple[DictionarySpec, ...]:
    general = root / "general.json"
    general.write_text(
        json.dumps({"entries": [{"en": "general phrase", "ar": "عبارة عامة"}]}),
        encoding="utf-8",
    )
    orthopedic = root / "orthopedic_surgery.json"
    if orthopedic_exists:
        orthopedic.write_text(
            json.dumps(
                {
                    "specialty": "orthopedic_surgery",
                    "entries": [{"en": "fracture healing", "ar": "التئام الكسر"}],
                }
            ),
            encoding="utf-8",
        )
    return (
        DictionarySpec(
            "general_tm", general, "general_medical",
            "translation_memory", "entries_json", "loaded", "test general TM",
        ),
        DictionarySpec(
            "orthopedic_tm", orthopedic, "orthopedic_surgery",
            "translation_memory", "entries_json", "optional_artifact",
            "test orthopedic TM",
        ),
    )


def _spec_selector(registry: tuple[DictionarySpec, ...]):
    def select(specialty: str | None):
        canonical = canonical_specialty(specialty)
        if canonical == "general":
            allowed = {"general"}
        elif canonical == "general_medical":
            allowed = {"general", "general_medical"}
        else:
            allowed = {"general", "general_medical", canonical}
        return [spec for spec in registry if spec.specialty in allowed]
    return select


def test_specialty_aliases_match_generated_namespace():
    assert canonical_specialty("orthopedics") == "orthopedic_surgery"
    assert canonical_specialty("cardiology") == "cardiovascular"
    assert canonical_specialty("general_surgery") == "surgery_general"


def test_missing_specialty_artifact_fails_closed():
    with tempfile.TemporaryDirectory() as tmp:
        registry = _registry(Path(tmp), orthopedic_exists=False)
        with patch.object(
            dictionary_router, "specs_for_specialty",
            side_effect=_spec_selector(registry),
        ):
            router = SpecialtyDictionaryRouter("orthopedics")
            missing = router.missing_translation_memory_artifacts()
            assert len(missing) == 1
            assert missing[0].specialty == "orthopedic_surgery"
            with pytest.raises(RuntimeError, match="Specialty translation-memory artifact"):
                ExactTranslationMemory.from_specialty("orthopedics")


def test_available_specialty_artifact_is_discovered_end_to_end():
    with tempfile.TemporaryDirectory() as tmp:
        registry = _registry(Path(tmp), orthopedic_exists=True)
        with patch.object(
            dictionary_router, "specs_for_specialty",
            side_effect=_spec_selector(registry),
        ):
            router = SpecialtyDictionaryRouter("orthopedics")
            sources = router.translation_memory_sources(require_specialty_artifact=True)
            assert len(sources) == 2

            tm = ExactTranslationMemory.from_specialty("orthopedics")
            assert tm.translate_exact("fracture healing") == "التئام الكسر"
            assert tm.translate_exact("patient has a fracture of the femur") is None


def test_general_translation_memory_does_not_require_specialty_artifact():
    with tempfile.TemporaryDirectory() as tmp:
        registry = _registry(Path(tmp), orthopedic_exists=False)
        with patch.object(
            dictionary_router, "specs_for_specialty",
            side_effect=_spec_selector(registry),
        ):
            tm = ExactTranslationMemory.from_specialty("general_medical")
            assert tm.translate_exact("general phrase") == "عبارة عامة"
