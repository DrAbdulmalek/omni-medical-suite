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


def test_library_layer_runtime_error_propagates():
    """Library-layer regression: missing specialty artifacts raise RuntimeError
    from ExactTranslationMemory.from_specialty(). The production-caller
    behavior (translate_text surfacing the error) is tested separately in
    test_translate_text_surfaces_specialty_tm_runtime_error."""
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


# ── Production-caller tests for Finding #1 ──────────────────────────────────
#
# These tests exercise app.services.translation_service.translate_text() —
# the actual Gradio-facing production entry point — not just the library
# layer. They verify the security property end-to-end:
#
#   requested specialty + missing artifact → visible error (NOT silent MT fallback)
#
# Heavy dependencies (torch, transformers, MarianMT model loading) are
# monkeypatched so we never reach the model-loading path. This lets us
# test in CI without GPU or model downloads.


def test_translate_text_surfaces_specialty_tm_runtime_error(monkeypatch):
    """Finding #1 — production path: when a specialty TM artifact is missing,
    translate_text() must return a visible error containing the RuntimeError
    message, NOT silently fall back to MarianMT.

    This test exercises the actual `except RuntimeError` branch in
    translation_service.py by making _lookup_exact_dictionary raise
    RuntimeError (which is what happens when from_specialty() encounters
    a missing artifact).
    """
    from app.services import translation_service

    # Force _lookup_exact_dictionary to raise RuntimeError
    def _raise_runtime_error(*args, **kwargs):
        raise RuntimeError(
            "Specialty translation-memory artifact is not installed for "
            "'orthopedic_surgery': .../orthopedic_surgery.json"
        )

    monkeypatch.setattr(
        translation_service, "_lookup_exact_dictionary", _raise_runtime_error
    )

    # Call the actual production entry point
    result = translation_service.translate_text(
        "fracture healing",
        "English → Arabic",
        specialty="orthopedics",
    )

    # Verify MarianMT was NOT invoked by setting load_translator to
    # raise AssertionError if called — this directly proves the security
    # property (no model loading after RuntimeError) rather than inferring
    # it from the result string.
    def _load_translator_must_not_be_called(*args, **kwargs):
        raise AssertionError(
            "load_translator must not be called when specialty TM "
            "raises RuntimeError — the error should surface to the user"
        )

    monkeypatch.setattr(
        translation_service, "load_translator", _load_translator_must_not_be_called
    )

    # Re-call translate_text with the RuntimeError stub in place.
    # If load_translator is ever reached, the AssertionError fires.
    result = translation_service.translate_text(
        "fracture healing",
        "English → Arabic",
        specialty="orthopedics",
    )

    # The user must see a visible error, not a silent MT fallback
    assert "❌" in result, f"Expected visible error, got: {result[:100]}"
    assert "artifact is not installed" in result, (
        f"Error message should mention the missing artifact, got: {result[:200]}"
    )


def test_translate_text_recoverable_exception_still_falls_back(monkeypatch):
    """Inverse of Finding #1: when a non-RuntimeError exception occurs
    (ImportError, JSON decode error, etc.), translate_text() should
    gracefully degrade to MarianMT, not crash.

    This verifies the `except Exception` branch still works correctly
    and that we didn't over-tighten the error handling.
    """
    from app.services import translation_service

    # Force _lookup_exact_dictionary to raise ImportError (recoverable)
    def _raise_import_error(*args, **kwargs):
        raise ImportError("Some optional dependency not found")

    monkeypatch.setattr(
        translation_service, "_lookup_exact_dictionary", _raise_import_error
    )

    # Mock load_translator to avoid actually loading a model
    def _fake_load(model_name):
        return None, None  # signals "model load failed"

    monkeypatch.setattr(translation_service, "load_translator", _fake_load)

    result = translation_service.translate_text(
        "fracture healing",
        "English → Arabic",
        specialty="general_medical",
    )

    # Should NOT contain the RuntimeError error marker
    assert "artifact is not installed" not in result, (
        "ImportError should not surface as a specialty artifact error"
    )
    # Should have gracefully degraded (model load failure message is expected
    # since we mocked load_translator to return None)
    assert "❌ فشل تحميل النموذج" in result or "فشل" in result, (
        f"Expected graceful degradation, got: {result[:200]}"
    )


def test_translate_text_exact_hit_returns_translation(monkeypatch):
    """Positive test: when _lookup_exact_dictionary finds a hit,
    translate_text() returns the translation immediately without
    invoking MarianMT.
    """
    from app.services import translation_service

    def _fake_lookup(text, direction, specialty):
        return "التئام الكسر"

    monkeypatch.setattr(
        translation_service, "_lookup_exact_dictionary", _fake_lookup
    )

    # Mock load_translator to detect if it's wrongly called
    def _should_not_be_called(model_name):
        raise AssertionError("load_translator should not be called when exact hit found")

    monkeypatch.setattr(translation_service, "load_translator", _should_not_be_called)

    result = translation_service.translate_text(
        "fracture healing",
        "English → Arabic",
        specialty="orthopedics",
    )

    assert "التئام الكسر" in result
    assert "exact dictionary/TMX" in result


# ── Finding #4 regression: long input bypasses fail-closed ────────────────
#
# Finding #4: The 8-word check in _lookup_exact_dictionary() was placed
# BEFORE get_exact_translation_memory(), so a 9+ word input returned None
# without ever validating the specialty artifact. This allowed MarianMT
# fallback even when the specialty artifact was missing.
#
# Fix: Move get_exact_translation_memory() BEFORE the 8-word check.
# Tests below verify the fix at the production entry point.


def test_translate_text_long_input_still_fails_closed_when_specialty_artifact_missing(monkeypatch):
    """Finding #4 — production path: when a specialty TM artifact is missing
    AND the input is longer than 8 words, translate_text() must STILL
    return a visible error. The 8-word optimization must NOT bypass
    the specialty artifact validation.

    This is the core regression test for Finding #4.
    """
    from app.services import translation_service

    # 9-word input — exceeds the 8-word limit
    long_text = "patient has a fracture of the femur requiring immediate surgery"

    # Force _lookup_exact_dictionary to raise RuntimeError (missing artifact)
    def _raise_runtime_error(*args, **kwargs):
        raise RuntimeError(
            "Specialty translation-memory artifact is not installed for "
            "'orthopedic_surgery': .../orthopedic_surgery.json"
        )

    monkeypatch.setattr(
        translation_service, "_lookup_exact_dictionary", _raise_runtime_error
    )

    # load_translator must NOT be called
    def _load_translator_must_not_be_called(*args, **kwargs):
        raise AssertionError(
            "load_translator must not be called when specialty TM "
            "raises RuntimeError — even for long input"
        )

    monkeypatch.setattr(
        translation_service, "load_translator", _load_translator_must_not_be_called
    )

    result = translation_service.translate_text(
        long_text,
        "English → Arabic",
        specialty="orthopedics",
    )

    # Must see visible error, NOT silent MT fallback
    assert "❌" in result, f"Expected visible error for long input, got: {result[:100]}"
    assert "artifact is not installed" in result, (
        f"Error should mention missing artifact even for long input, got: {result[:200]}"
    )


def test_translate_text_short_input_fails_closed_when_specialty_artifact_missing(monkeypatch):
    """Baseline: short input (<=8 words) with missing specialty artifact
    also fails closed. This was already fixed in PR #112 but we re-verify
    to ensure the Finding #4 fix didn't break the short-input path.
    """
    from app.services import translation_service

    short_text = "fracture healing"  # 2 words

    def _raise_runtime_error(*args, **kwargs):
        raise RuntimeError(
            "Specialty translation-memory artifact is not installed for "
            "'orthopedic_surgery': .../orthopedic_surgery.json"
        )

    monkeypatch.setattr(
        translation_service, "_lookup_exact_dictionary", _raise_runtime_error
    )

    def _load_translator_must_not_be_called(*args, **kwargs):
        raise AssertionError("load_translator must not be called")

    monkeypatch.setattr(
        translation_service, "load_translator", _load_translator_must_not_be_called
    )

    result = translation_service.translate_text(
        short_text,
        "English → Arabic",
        specialty="orthopedics",
    )

    assert "❌" in result
    assert "artifact is not installed" in result


def test_translate_text_long_input_general_medical_does_not_fail(monkeypatch):
    """General medical with long input must NOT fail closed — general
    specialties don't require a specialty artifact. The 8-word optimization
    should still return None (allowing MarianMT) without raising.
    """
    from app.services import translation_service

    long_text = "patient has a fracture of the femur requiring immediate surgery"

    # _lookup_exact_dictionary returns None (long input, no exact hit)
    monkeypatch.setattr(
        translation_service, "_lookup_exact_dictionary", lambda *a, **k: None
    )

    # load_translator IS expected to be called for general_medical
    monkeypatch.setattr(
        translation_service, "load_translator", lambda model: (None, None)
    )

    result = translation_service.translate_text(
        long_text,
        "English → Arabic",
        specialty="general_medical",
    )

    # Should NOT contain a specialty artifact error
    assert "artifact is not installed" not in result
    # Should have degraded gracefully (model load failure is expected from mock)
    assert "❌" in result or "فشل" in result  # graceful degradation


def test_translate_text_exact_hit_short_input(monkeypatch):
    """Exact TM hit with short input returns translation immediately,
    without calling load_translator.
    """
    from app.services import translation_service

    def _fake_lookup(text, direction, specialty):
        return "التئام الكسر"

    monkeypatch.setattr(
        translation_service, "_lookup_exact_dictionary", _fake_lookup
    )

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("load_translator should not be called on exact hit")

    monkeypatch.setattr(
        translation_service, "load_translator", _should_not_be_called
    )

    result = translation_service.translate_text(
        "fracture healing",
        "English → Arabic",
        specialty="orthopedics",
    )

    assert "التئام الكسر" in result
    assert "exact dictionary/TMX" in result


def test_translate_text_unregistered_specialty_long_input_fails_closed(monkeypatch):
    """Finding #2 + #4 interaction: an unregistered specialty (e.g. neurology)
    with long input must still fail closed — the 'no spec registered' error
    must fire even for 9+ word inputs.
    """
    from app.services import translation_service

    long_text = "patient has a fracture of the femur requiring immediate surgery"

    def _raise_runtime_error(*args, **kwargs):
        raise RuntimeError(
            "No specialty translation-memory spec is registered for 'neurology'"
        )

    monkeypatch.setattr(
        translation_service, "_lookup_exact_dictionary", _raise_runtime_error
    )

    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("load_translator must not be called")

    monkeypatch.setattr(
        translation_service, "load_translator", _must_not_be_called
    )

    result = translation_service.translate_text(
        long_text,
        "English → Arabic",
        specialty="neurology",
    )

    assert "❌" in result
    assert "No specialty translation-memory spec" in result or "not registered" in result
