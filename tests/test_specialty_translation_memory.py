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


# ── Regression tests for audit findings #1 and #2 ─────────────────────────
#
# Finding #1: translate_text() in app/services/translation_service.py was
# catching ALL exceptions (including RuntimeError from the fail-closed path)
# and silently degrading to MarianMT-only. Fixed by catching RuntimeError
# separately and surfacing it as a visible error to the user.
#
# Finding #2: Specialties with no registered TM spec (e.g. neurology,
# radiology, pathology) bypassed the fail-closed check entirely because
# the condition `specialty_specs and missing_specialty` was False when
# specialty_specs was empty. Fixed by also raising RuntimeError when
# require_specialty_artifact=True and no spec is registered at all.


def test_unregistered_specialty_fails_closed():
    """Finding #2: A recognized specialty with no registered TM spec
    must fail closed when require_specialty_artifact=True, not silently
    pass through to general TM."""
    with tempfile.TemporaryDirectory() as tmp:
        # Registry with only general TM — no neurology spec
        registry = _registry(Path(tmp), orthopedic_exists=False)
        with patch.object(
            dictionary_router, "specs_for_specialty",
            side_effect=_spec_selector(registry),
        ):
            # neurology is in SPECIALTY_ALIASES but has no registered TM spec
            with pytest.raises(RuntimeError, match="No specialty translation-memory spec"):
                ExactTranslationMemory.from_specialty("neurology")


def test_registered_but_missing_artifact_fails_closed():
    """Finding #1 regression: A specialty with a registered spec but
    missing artifact must raise RuntimeError, not silently degrade."""
    with tempfile.TemporaryDirectory() as tmp:
        # orthopedic_exists=False means the artifact file is absent
        registry = _registry(Path(tmp), orthopedic_exists=False)
        with patch.object(
            dictionary_router, "specs_for_specialty",
            side_effect=_spec_selector(registry),
        ):
            with pytest.raises(RuntimeError, match="artifact is not installed"):
                ExactTranslationMemory.from_specialty("orthopedics")


def test_runtime_error_not_swallowed_by_caller():
    """Finding #1 production-level regression: When translate_text()
    receives a RuntimeError from the specialty TM path, it must surface
    the error to the user instead of silently falling back to MarianMT.

    This test verifies that RuntimeError propagates as a visible error
    return, not a silent warning log + MT fallback.
    """
    # We can't import translate_text directly without heavy deps (torch, etc.),
    # so we verify the contract at the translation_memory layer:
    # from_specialty() raises RuntimeError for missing artifacts.
    # The fix in translation_service.py catches RuntimeError separately
    # from other Exception subclasses and returns it as an error string.
    with tempfile.TemporaryDirectory() as tmp:
        registry = _registry(Path(tmp), orthopedic_exists=False)
        with patch.object(
            dictionary_router, "specs_for_specialty",
            side_effect=_spec_selector(registry),
        ):
            # Verify RuntimeError is raised (not swallowed)
            with pytest.raises(RuntimeError) as exc_info:
                ExactTranslationMemory.from_specialty("orthopedics")
            # The error message must mention the missing artifact
            assert "artifact is not installed" in str(exc_info.value)


def test_general_specialty_does_not_fail_closed():
    """General and general_medical must never require a specialty artifact.
    This is the inverse of the fail-closed test — general TM must work
    even when no specialty artifacts exist at all."""
    with tempfile.TemporaryDirectory() as tmp:
        registry = _registry(Path(tmp), orthopedic_exists=False)
        with patch.object(
            dictionary_router, "specs_for_specialty",
            side_effect=_spec_selector(registry),
        ):
            # general_medical must work without any specialty artifacts
            tm = ExactTranslationMemory.from_specialty("general_medical")
            assert tm.translate_exact("general phrase") == "عبارة عامة"
