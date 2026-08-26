"""Production-call-graph and safety tests for PR #92.

These tests instantiate the real production spell checker and the real loader;
there are no mocks. Large generated artifacts are inspected when present, but
are never required to be committed to Git.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from packages.core.spell_checker import HybridSpellChecker
from packages.medical.medical_dictionary_loader import (
    MedicalDictionaryLoader,
    is_dangerous_key,
)

ROOT = Path(__file__).resolve().parents[1]
SAFE_OCR = ROOT / "data/dictionaries/ocr_corrections_safe.json"
MERGED = ROOT / "data/dictionaries/medical_glossary_merged.json"
MALEK_TERMS = ROOT / "data/dictionaries/malek_data_terms.json"


class TestProductionOCRCallGraph:
    """hf-space/app_core -> HybridSpellChecker -> safe OCR map is the real path."""

    def test_production_spell_checker_reads_safe_ocr_map(self):
        checker = HybridSpellChecker()
        assert checker._fixes_path.resolve() == SAFE_OCR.resolve()
        assert "باراسيتبمول" in checker._arabic_fixes

    @pytest.mark.parametrize(
        "text, expected",
        [
            ("ترامادول 0.5 mg", "ترامادول 0.5 mg"),
            ("لا يعطى ترامادول 0.5 mg", "لا يعطى ترامادول 0.5 mg"),
            ("باراسيتبمول 500 mg", "باراسيتامول 500 mg"),
            ("0.5", "0.5"),
            ("1.25", "1.25"),
            ("0.75", "0.75"),
            ("٠٫٥", "٠٫٥"),
            ("١٫٢٥", "١٫٢٥"),
        ],
    )
    def test_exact_medical_safety_cases(self, text, expected):
        assert HybridSpellChecker().correct_text(text) == expected

    def test_negation_is_not_rewritten(self):
        checker = HybridSpellChecker()
        text = "لا يعطى ترامادول 0.5 mg"
        assert checker.correct_text(text) == text
        assert checker.correct_text("لا يوجد ترامادول") == "لا يوجد ترامادول"

    def test_safe_ocr_map_has_no_dose_or_negation_keys(self):
        data = json.loads(SAFE_OCR.read_text(encoding="utf-8"))
        assert data
        for key in data:
            dangerous, reason = is_dangerous_key(key)
            assert not dangerous, f"Unsafe OCR key leaked: {key!r} ({reason})"


class TestDictionaryProvenance:
    def test_loader_records_source_provenance(self):
        loader = MedicalDictionaryLoader()
        # Real repository sources; this is an integration smoke test, not a mock.
        result = loader.load_unified_glossary(apply_safety=True)
        for source in result["sources"]:
            assert source["name"] in {
                "production_arabic_fixes",
                "arabic_medical_glossary",
                "malek_data_tmx",
            }
            assert source["path"]
            assert source["entries_loaded"] > 0

    def test_conflict_winner_uses_documented_priority(self, tmp_path):
        fixes = tmp_path / "fixes.json"
        fixes.write_text(json.dumps({"hello": "production"}), encoding="utf-8")
        glossary = tmp_path / "glossary.csv"
        glossary.write_text("en,ar,source,type,section,confidence\nhello,glossary,test,term,,high\n", encoding="utf-8")
        malek = tmp_path / "malek.json"
        malek.write_text(json.dumps({"entries": [{"en": "hello", "ar": "malek", "source": "x:file"}]}), encoding="utf-8")
        loader = MedicalDictionaryLoader(glossary, malek, fixes, tmp_path / "out")
        result = loader.load_unified_glossary()
        hello = [e for e in result["entries"] if e["key"] == "hello"]
        assert len(hello) == 1
        assert hello[0]["value"] == "production"
        assert hello[0]["source"] == "production_arabic_fixes"


class TestGeneratedArtifactAudit:
    """Audit the full 159,554-entry output whenever it is regenerated locally/CI."""

    @pytest.mark.skipif(not MERGED.exists(), reason="generated 96 MB artifact is intentionally git-ignored")
    def test_merged_dictionary_is_159554_and_safe(self):
        data = json.loads(MERGED.read_text(encoding="utf-8"))
        entries = data["entries"] if isinstance(data, dict) and "entries" in data else data
        assert len(entries) == 159_554
        normalized = [e["normalized_key"] for e in entries]
        assert len(normalized) == len(set(normalized))
        for e in entries:
            dangerous, reason = is_dangerous_key(e["key"])
            assert not dangerous, f"Unsafe merged entry: {e['key']!r} ({reason})"
            assert e.get("source"), f"Missing provenance: {e['key']!r}"

    @pytest.mark.skipif(not MALEK_TERMS.exists(), reason="malek_data extraction is private/regenerated and git-ignored")
    def test_malek_terms_has_no_obvious_pii_fields(self):
        data = json.loads(MALEK_TERMS.read_text(encoding="utf-8"))
        serialized = json.dumps(data, ensure_ascii=False).lower()
        for marker in ("@gmail.com", "@outlook.com", "@hotmail.com", "phone", "telephone"):
            assert marker not in serialized
        for entry in data.get("entries", []):
            assert set(entry).issubset({"en", "ar", "tuid", "source", "_file"})
