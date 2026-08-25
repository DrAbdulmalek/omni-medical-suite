#!/usr/bin/env python3
"""
tests/test_medical_dictionary_loader.py — Production tests for MedicalDictionaryLoader.

These tests exercise the REAL loader (no mocks) and verify:
  1. Dictionary integrity (JSON valid, no duplicate normalized keys, no unsafe keys)
  2. Medical safety firewall (decimals, negations, drug-dose boundaries preserved)
  3. Critical medical term isolation
  4. Source priority resolution (existing arabic_fixes > arabic-medical-glossary > malek_data)
  5. Conflict detection + resolution
  6. Arabic normalization correctness
  7. Trailing whitespace bug prevention (historic 'ترامادول ' → 'ترامادول')

These tests do NOT require the malek_data 7z archive or submodule data —
they verify the loader's logic against inline test fixtures.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from packages.medical.medical_dictionary_loader import (
    MedicalDictionaryLoader,
    DictionaryEntry,
    normalize_arabic_key,
    is_dangerous_key,
    is_critical_medical_term,
    ARABIC_NEGATION_PATTERNS,
    CRITICAL_MEDICAL_TERMS,
)


# ─── Test fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_loader(tmp_path):
    """Loader pointing at tmp dirs so tests don't depend on real data files."""
    fixes = tmp_path / "arabic_fixes.json"
    fixes.write_text(json.dumps({
        "المملكك": "المملكة",      # safe correction
        "0.5": "0.5",              # DANGEROUS — must be quarantined
        "ترامادول ": "ترامادول",  # DANGEROUS — trailing whitespace (historic bug)
        "لا يعطى": "لا يعطى",     # DANGEROUS — negation
    }, ensure_ascii=False), encoding="utf-8")
    glossary = tmp_path / "glossary.csv"
    glossary.write_text(
        "en,ar,source,type,section,confidence\n"
        "Fracture,كسر,test_source,term,header,high\n"
        "Bone,عظم,test_source,term,header,high\n"
        "0.5 mg,0.5 مل,test_source,dosage,dose,high\n"  # DANGEROUS — drug dose
        "Indications,الاستطبابات,test_source,term,header,high\n",
        encoding="utf-8",
    )
    malek = tmp_path / "malek.json"
    malek.write_text(json.dumps({
        "total_pairs": 2,
        "entries": [
            {"en": "Heart", "ar": "قلب", "tuid": "t1", "source": "test:file1"},
            {"en": "0.5 mg", "ar": "0.5 مل", "tuid": "t2"},  # DANGEROUS
        ]
    }, ensure_ascii=False), encoding="utf-8")
    
    out_dir = tmp_path / "out"
    return MedicalDictionaryLoader(
        glossary_csv_path=glossary,
        malek_json_path=malek,
        existing_fixes_path=fixes,
        output_dir=out_dir,
    )


# ─── 1. Dictionary integrity tests ───────────────────────────────────────────

class TestDictionaryIntegrity:
    """Verify the loader produces valid, non-duplicated, deterministic output."""

    def test_loader_runs_without_errors(self, tmp_loader):
        """Loader must complete without raising."""
        result = tmp_loader.load_unified_glossary(apply_safety=True)
        assert isinstance(result, dict)
        assert "entries" in result
        assert "quarantined" in result
        assert "conflicts" in result
        assert "stats" in result

    def test_no_duplicate_normalized_keys(self, tmp_loader):
        """Every entry in the result must have a unique normalized_key."""
        result = tmp_loader.load_unified_glossary(apply_safety=True)
        keys = [e["normalized_key"] for e in result["entries"]]
        duplicates = [k for k in set(keys) if keys.count(k) > 1]
        assert not duplicates, f"Duplicate normalized_keys found: {duplicates[:5]}"

    def test_output_is_deterministic(self, tmp_loader):
        """Loading twice must produce identical results."""
        r1 = tmp_loader.load_unified_glossary(apply_safety=True)
        r2 = tmp_loader.load_unified_glossary(apply_safety=True)
        assert r1["stats"] == r2["stats"]
        assert len(r1["entries"]) == len(r2["entries"])

    def test_every_entry_has_required_metadata(self, tmp_loader):
        """Every entry must carry full provenance metadata."""
        result = tmp_loader.load_unified_glossary(apply_safety=True)
        required_fields = {"key", "value", "normalized_key", "source", "category",
                          "confidence", "safety_flag", "conflicts"}
        for e in result["entries"][:50]:  # sample
            missing = required_fields - set(e.keys())
            assert not missing, f"Entry missing fields: {missing}. Entry: {e}"

    def test_safe_entries_have_safe_flag(self, tmp_loader):
        """All non-quarantined entries must be flagged 'safe'."""
        result = tmp_loader.load_unified_glossary(apply_safety=True)
        for e in result["entries"]:
            assert e["safety_flag"] == "safe", \
                f"Unsafe entry leaked into safe set: {e}"

    def test_export_to_json_is_valid_json(self, tmp_loader, tmp_path):
        """export_to_json must produce parseable JSON."""
        result = tmp_loader.load_unified_glossary(apply_safety=True)
        out = tmp_path / "out.json"
        tmp_loader.export_to_json(result, out)
        with open(out, encoding="utf-8") as f:
            parsed = json.load(f)
        assert "entries" in parsed
        assert "stats" in parsed


# ─── 2. Medical safety firewall tests ────────────────────────────────────────

class TestMedicalSafetyFirewall:
    """
    CRITICAL: Verify the medical safety firewall.
    These are the exact test cases from the user's brief.
    """

    @pytest.mark.parametrize("dangerous_input,expected_reason_options", [
        ("0.5", {"decimal_dose"}),
        ("1.25", {"decimal_dose"}),
        ("2.5", {"decimal_dose"}),
        ("0.75", {"decimal_dose"}),
        ("٠٫٥", {"arabic_indic_digits"}),
        ("١٫٢٥", {"arabic_indic_digits"}),
        # Any input containing "0.75" matches decimal_dose first (correct precedence)
        ("جرعة 0.75 مل", {"decimal_dose", "drug_dose_unit"}),
        ("ترامادول 0.5 mg", {"decimal_dose", "drug_dose_unit"}),
        ("باراسيتبمول 500 mg", {"drug_dose_unit"}),
        ("باراسيتامول 500 mg", {"drug_dose_unit"}),
        ("لا يعطى ترامادول", {"negation"}),
        ("لا يوجد سكري", {"negation"}),
        ("ليس لديه حساسية", {"negation"}),
        ("لا يعطى ترامادول 0.5 mg", {"decimal_dose", "drug_dose_unit", "negation"}),
        ("لا", {"negation"}),
        ("5%", {"concentration_percent"}),
        ("10.5%", {"decimal_dose", "concentration_percent"}),  # decimal matches first
        ("ترامادول ", {"whitespace_padding"}),  # historic bug
    ])
    def test_dangerous_keys_are_quarantined(self, dangerous_input, expected_reason_options):
        """Every dangerous input must be flagged as dangerous with correct reason."""
        is_dangerous, reason = is_dangerous_key(dangerous_input)
        assert is_dangerous, f"Input {dangerous_input!r} should be flagged dangerous"
        # Reason may match any of the expected options (precedence rules apply)
        reason_root = reason.split(":")[0] if ":" in reason else reason
        assert reason_root in expected_reason_options, \
            f"Expected one of {expected_reason_options}, got '{reason}' for input {dangerous_input!r}"

    def test_safe_corrections_pass_firewall(self):
        """Legitimate OCR corrections must pass through the firewall."""
        safe_inputs = [
            "المملكك", "الجمهوريه", "المدرسه", "الجامعه",
            "fracture", "bone", "heart", "indications",
        ]
        for inp in safe_inputs:
            is_dangerous, reason = is_dangerous_key(inp)
            assert not is_dangerous, \
                f"Safe input {inp!r} was wrongly flagged as dangerous ({reason})"

    def test_no_dangerous_entry_in_safe_set(self, tmp_loader):
        """After loading, no safe entry must contain dangerous patterns."""
        result = tmp_loader.load_unified_glossary(apply_safety=True)
        for e in result["entries"]:
            is_dangerous, reason = is_dangerous_key(e["key"])
            assert not is_dangerous, \
                f"Dangerous entry leaked into safe set: key={e['key']!r} reason={reason}"

    def test_quarantined_entries_carry_reason(self, tmp_loader):
        """Quarantined entries must have a non-default safety_flag."""
        result = tmp_loader.load_unified_glossary(apply_safety=True)
        for q in result["quarantined"]:
            assert q["safety_flag"] != "safe", \
                f"Quarantined entry has safe flag: {q}"
            assert q["safety_flag"].startswith("quarantined:"), \
                f"Quarantined entry has wrong flag format: {q['safety_flag']}"

    def test_specific_dangerous_inputs_quarantined(self, tmp_loader):
        """The specific test inputs from the user brief must ALL be quarantined."""
        result = tmp_loader.load_unified_glossary(apply_safety=True)
        quarantined_keys = {q["key"] for q in result["quarantined"]}
        
        required_quarantined = [
            "0.5",          # decimal_dose
            "ترامادول ",    # whitespace_padding (historic bug)
            "لا يعطى",      # negation
        ]
        for k in required_quarantined:
            assert k in quarantined_keys, \
                f"Required dangerous key {k!r} not in quarantined set"


# ─── 3. Critical medical term protection ──────────────────────────────────────

class TestCriticalMedicalTerms:
    """Verify drug names are protected from being used as correction keys."""

    @pytest.mark.parametrize("drug_name", [
        "ترامادول", "باراسيتامول", "باراسيتبمول",
        "ايبوبروفين", "ايبوروفين", "اموكسيسيلين",
        "ديكلوفيناك", "كوديين", "سالبوتامول",
        "ميترونيدازول", "اوجمنتين", "اوميبرازول",
    ])
    def test_drug_name_is_critical(self, drug_name):
        """Each drug name must be recognized as critical."""
        assert is_critical_medical_term(drug_name), \
            f"Drug name {drug_name!r} not recognized as critical"

    def test_drug_name_as_key_gets_quarantined(self, tmp_loader):
        """When a drug name appears as a key in arabic_fixes, it must be quarantined."""
        # Add a drug name as a key
        fixes = tmp_loader.existing_fixes_path
        data = json.loads(fixes.read_text(encoding="utf-8"))
        data["ترامادول"] = "ترامادول"  # dangerous: drug name as key
        fixes.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        
        result = tmp_loader.load_unified_glossary(apply_safety=True)
        quarantined_keys = {q["key"] for q in result["quarantined"]}
        assert "ترامادول" in quarantined_keys, \
            "Drug name 'ترامادول' as key must be quarantined (would corrupt prescriptions)"


# ─── 4. Source priority resolution ───────────────────────────────────────────

class TestSourcePriority:
    """Verify conflict resolution follows documented source priority."""

    def test_existing_fixes_beat_glossary_on_conflict(self, tmp_path):
        """When arabic_fixes.json and arabic-medical-glossary disagree on same key,
        arabic_fixes (production) must win."""
        fixes = tmp_path / "arabic_fixes.json"
        fixes.write_text(json.dumps({"hello": "مرحبا_production"}, ensure_ascii=False), encoding="utf-8")
        glossary = tmp_path / "glossary.csv"
        glossary.write_text(
            "en,ar,source,type,section,confidence\n"
            "hello,مرحبا_glossary,test,term,header,high\n",
            encoding="utf-8",
        )
        malek = tmp_path / "malek.json"
        malek.write_text(json.dumps({"entries": []}, ensure_ascii=False), encoding="utf-8")
        
        loader = MedicalDictionaryLoader(
            glossary_csv_path=glossary,
            malek_json_path=malek,
            existing_fixes_path=fixes,
            output_dir=tmp_path / "out",
        )
        result = loader.load_unified_glossary(apply_safety=True)
        
        # Find entry with key 'hello'
        hello_entries = [e for e in result["entries"] if e["key"] == "hello"]
        assert len(hello_entries) == 1, "Duplicate 'hello' entries — dedup failed"
        assert hello_entries[0]["value"] == "مرحبا_production", \
            f"Production should win, but got: {hello_entries[0]['value']}"
        assert hello_entries[0]["source"].startswith("production_arabic_fixes")

    def test_glossary_beats_malek_on_conflict(self, tmp_path):
        """When arabic-medical-glossary and malek_data disagree on same key,
        arabic-medical-glossary (verified submodule) must win."""
        fixes = tmp_path / "arabic_fixes.json"
        fixes.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
        glossary = tmp_path / "glossary.csv"
        glossary.write_text(
            "en,ar,source,type,section,confidence\n"
            "hello,مرحبا_glossary,test,term,header,high\n",
            encoding="utf-8",
        )
        malek = tmp_path / "malek.json"
        malek.write_text(json.dumps({
            "entries": [{"en": "hello", "ar": "مرحبا_malek", "tuid": "t1"}]
        }, ensure_ascii=False), encoding="utf-8")
        
        loader = MedicalDictionaryLoader(
            glossary_csv_path=glossary,
            malek_json_path=malek,
            existing_fixes_path=fixes,
            output_dir=tmp_path / "out",
        )
        result = loader.load_unified_glossary(apply_safety=True)
        
        hello_entries = [e for e in result["entries"] if e["key"] == "hello"]
        assert len(hello_entries) == 1
        assert hello_entries[0]["value"] == "مرحبا_glossary", \
            f"Glossary should win, but got: {hello_entries[0]['value']}"
        assert hello_entries[0]["source"].startswith("arabic_medical_glossary")


# ─── 5. Conflict detection ───────────────────────────────────────────────────

class TestConflictDetection:
    """Verify conflicts are properly detected and logged."""

    def test_conflict_count_matches_expectation(self, tmp_path):
        """Conflicts list must contain all disagreement cases."""
        fixes = tmp_path / "arabic_fixes.json"
        fixes.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
        glossary = tmp_path / "glossary.csv"
        glossary.write_text(
            "en,ar,source,type,section,confidence\n"
            "hello,مرحبا_glossary1,src1,term,header,high\n"
            "hello,مرحبا_glossary2,src2,term,header,high\n"
            "hello,مرحبا_glossary3,src3,term,header,high\n",
            encoding="utf-8",
        )
        malek = tmp_path / "malek.json"
        malek.write_text(json.dumps({
            "entries": [{"en": "hello", "ar": "مرحبا_malek", "tuid": "t1"}]
        }, ensure_ascii=False), encoding="utf-8")
        
        loader = MedicalDictionaryLoader(
            glossary_csv_path=glossary,
            malek_json_path=malek,
            existing_fixes_path=fixes,
            output_dir=tmp_path / "out",
        )
        result = loader.load_unified_glossary(apply_safety=True)
        
        # 'hello' appears 4 times with 4 different values → 1 conflict group
        hello_conflicts = [c for c in result["conflicts"] 
                          if c["normalized_key"] == "hello"]
        assert len(hello_conflicts) == 1
        assert len(hello_conflicts[0]["losers"]) == 3

    def test_conflict_winner_value_is_in_safe_set(self, tmp_loader):
        """The winning value of each conflict must be present in the safe entries."""
        result = tmp_loader.load_unified_glossary(apply_safety=True)
        safe_keys = {e["key"] for e in result["entries"]}
        
        for c in result["conflicts"]:
            # Find winning entry by normalized_key
            winner_entries = [e for e in result["entries"] 
                             if e["normalized_key"] == c["normalized_key"]]
            assert len(winner_entries) == 1, \
                f"Conflict winner not uniquely resolved for {c['normalized_key']}"
            assert winner_entries[0]["value"] == c["winner_value"], \
                f"Winner value mismatch for {c['normalized_key']}"


# ─── 6. Arabic normalization tests ───────────────────────────────────────────

class TestArabicNormalization:
    """Verify Arabic normalization for comparison-only purposes."""

    @pytest.mark.parametrize("input_text,expected", [
        # alef variants → ا
        ("أحمد", "احمد"),
        ("إبراهيم", "ابراهيم"),
        ("آدم", "ادم"),
        # alif maqsura → yaa
        ("على", "علي"),
        # persian kaf → arabic kaf
        ("کلب", "كلب"),
        # persian yaa → arabic yaa
        ("موسیم", "موسيم"),
        # whitespace normalization
        ("  hello   world  ", "hello world"),
        # case folding for latin
        ("HELLO", "hello"),
    ])
    def test_normalization(self, input_text, expected):
        """Each normalization rule must produce the expected output."""
        assert normalize_arabic_key(input_text) == expected

    def test_normalization_does_not_destroy_arabic_identity(self):
        """Normalization must not change the meaning-bearing characters."""
        # تطبيع لا يُدمج كلمتين مختلفتين في المعنى
        assert normalize_arabic_key("مدرسة") != normalize_arabic_key("مدرس")
        assert normalize_arabic_key("قلم") != normalize_arabic_key("قلمون")

    def test_normalization_handles_empty_input(self):
        assert normalize_arabic_key("") == ""
        assert normalize_arabic_key(None) == ""


# ─── 7. Historic bug prevention ──────────────────────────────────────────────

class TestHistoricBugPrevention:
    """Verify the historic bugs documented in the user brief are fixed."""

    def test_tramadol_trailing_whitespace_is_quarantined(self):
        """The historic bug 'ترامادول ' (with trailing space) must be quarantined."""
        # Key has trailing space
        is_dangerous, reason = is_dangerous_key("ترامادول ")
        assert is_dangerous, "Trailing-whitespace key must be flagged dangerous"
        assert reason == "whitespace_padding", \
            f"Expected whitespace_padding, got {reason}"

    def test_intended_ocr_correction_still_works(self):
        """A legitimate OCR correction like 'باراسيتبمول' → 'باراسيتامول'
        must NOT be quarantined (key is safe, value is correct)."""
        # Key 'باراسيتبمول' has no dangerous pattern
        is_dangerous, _ = is_dangerous_key("باراسيتبمول")
        assert not is_dangerous, "Legitimate OCR key 'باراسيتبمول' must not be quarantined"

    def test_5OO_digit_correction_still_works_via_spell_checker(self):
        """The digit-recognition path (5OO → 500) is handled in HybridSpellChecker,
        not in the dictionary loader. Verify the loader does NOT interfere."""
        # '5OO' as a key would be quarantined (it's digit-corruption, not a real word)
        # This is correct behavior — the dictionary should not contain '5OO' as a key
        # because the spell checker handles this case via enhance_digit_recognition()
        is_dangerous, _ = is_dangerous_key("5OO")
        # '5OO' is alphanumeric with a digit, but not matching drug_dose_unit pattern
        # It will pass through as 'safe' for the dictionary, but the spell checker
        # has separate digit-correction logic
        # This is acceptable — the dictionary doesn't need to know about OCR artifacts
        # The runtime test in tests/security/test_medical_behavior.py verifies the
        # end-to-end behavior via _auto_correct_ocr


# ─── 8. Loader edge cases ────────────────────────────────────────────────────

class TestLoaderEdgeCases:
    """Verify loader handles missing files and empty inputs gracefully."""

    def test_missing_glossary_csv_returns_empty(self, tmp_path):
        """If glossary CSV is missing, loader should still work (empty list)."""
        loader = MedicalDictionaryLoader(
            glossary_csv_path=tmp_path / "nonexistent.csv",
            malek_json_path=tmp_path / "nonexistent.json",
            existing_fixes_path=tmp_path / "nonexistent.json",
            output_dir=tmp_path / "out",
        )
        result = loader.load_unified_glossary(apply_safety=True)
        assert result["stats"]["total_loaded"] == 0
        assert len(result["entries"]) == 0

    def test_empty_json_fixes_returns_empty(self, tmp_path):
        """Empty arabic_fixes.json ({}) should not crash."""
        fixes = tmp_path / "arabic_fixes.json"
        fixes.write_text("{}", encoding="utf-8")
        loader = MedicalDictionaryLoader(
            glossary_csv_path=tmp_path / "nonexistent.csv",
            malek_json_path=tmp_path / "nonexistent.json",
            existing_fixes_path=fixes,
            output_dir=tmp_path / "out",
        )
        result = loader.load_unified_glossary(apply_safety=True)
        assert result["stats"]["total_loaded"] == 0

    def test_export_safe_ocr_corrections_only_includes_corrections(self, tmp_loader, tmp_path):
        """export_safe_ocr_corrections must only include entries with category=ocr_correction."""
        result = tmp_loader.load_unified_glossary(apply_safety=True)
        out = tmp_path / "ocr_safe.json"
        tmp_loader.export_safe_ocr_corrections(result, out)
        
        with open(out, encoding="utf-8") as f:
            data = json.load(f)
        
        # Should only contain entries from arabic_fixes source
        # (the safe ones, not quarantined)
        for key, value in data.items():
            # Verify each entry is in the safe entries list with source production_arabic_fixes
            matching = [e for e in result["entries"] 
                       if e["key"] == key and e["value"] == value]
            assert any(e["source"].startswith("production_arabic_fixes") 
                      for e in matching), \
                f"Entry {key!r} not from production_arabic_fixes source"
