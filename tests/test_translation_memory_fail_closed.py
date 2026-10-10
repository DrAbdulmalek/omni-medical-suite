from pathlib import Path


def test_corrupted_specialty_tm_fails_closed_without_marianmt(monkeypatch, tmp_path: Path):
    from packages.medical import translation_memory
    from app.services import translation_service

    bad_artifact = tmp_path / "orthopedic_surgery.json"
    bad_artifact.write_text('{"entries": [', encoding="utf-8")

    monkeypatch.setattr(
        translation_memory.SpecialtyDictionaryRouter,
        "translation_memory_sources",
        lambda self, require_specialty_artifact=False: [bad_artifact],
    )

    marian_called = False

    def forbidden_marian_load(_model_name):
        nonlocal marian_called
        marian_called = True
        raise AssertionError("MarianMT must not be loaded after a specialty TM artifact error")

    monkeypatch.setattr(translation_service, "load_translator", forbidden_marian_load)
    translation_service.reset_lazy_cache()

    result = translation_service.translate_text(
        "fracture of the femoral neck",
        "English → Arabic",
        specialty="orthopedic_surgery",
    )

    assert result.startswith("❌ Specialty TM artifact is corrupted or unreadable:")
    assert "MarianMT" not in result
    assert marian_called is False
