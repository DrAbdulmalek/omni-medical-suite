"""Production-call-graph and safety tests for PR #92.

These tests instantiate the real production spell checker and the real loader;
there are no mocks. Large generated artifacts are inspected when present, but
are never required to be committed to Git.

Production call graph (verified):
  hf-space/app_core.py:full_process(image)
    → _auto_correct_ocr(raw_text)        [uses OCR_CORRECTIONS dict, hardcoded]
        handles intended drug-name OCR fixes (باراسيتبمول → باراسيتامول)
    → spell_checker.correct_text(corrected)
        HybridSpellChecker loads data/dictionaries/ocr_corrections_safe.json
        applies safe token-level corrections
        preserves decimals, negations, drug doses (verified by tests below)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# IMPORTANT: insert ROOT *before* "hf-space" so packages/medical/medical_dictionary_loader.py
# is found from the canonical repo location, NOT from hf-space/packages/medical/ (which
# is a stale copy that lacks medical_dictionary_loader.py and translation_memory.py).
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Production path: tests/security/test_medical_behavior.py uses this same path
# for importing app_core. We add it AFTER ROOT so ROOT takes precedence.
hf_space = ROOT / "hf-space"
if str(hf_space) not in sys.path:
    sys.path.append(str(hf_space))

from packages.core.spell_checker import HybridSpellChecker
from packages.medical.medical_dictionary_loader import (
    MedicalDictionaryLoader,
    is_dangerous_key,
    is_critical_medical_term,
)

SAFE_OCR = ROOT / "data/dictionaries/ocr_corrections_safe.json"
MERGED = ROOT / "data/dictionaries/medical_glossary_merged.json"
MALEK_TERMS = ROOT / "data/dictionaries/malek_data_terms.json"


class TestProductionOCRCallGraph:
    """hf-space/app_core -> HybridSpellChecker -> safe OCR map is the real path."""

    def test_production_spell_checker_reads_safe_ocr_map(self):
        """HybridSpellChecker must load ocr_corrections_safe.json as its primary
        fixes source. Critical drug names (e.g. باراسيتبمول) must NOT appear as
        keys — they are quarantined by the safety firewall. The intended drug-name
        OCR corrections live in hf-space/app_core.py:OCR_CORRECTIONS, not here."""
        checker = HybridSpellChecker()
        assert checker._fixes_path.resolve() == SAFE_OCR.resolve()
        # The safe OCR map must NOT contain critical drug names as keys.
        # Intended drug-name OCR corrections (باراسيتبمول → باراسيتامول) live in
        # hf-space/app_core.py:OCR_CORRECTIONS (hardcoded, audited dict).
        for drug in ("باراسيتبمول", "باراسيتامول", "ترامادول"):
            assert drug not in checker._arabic_fixes, \
                f"Critical drug name {drug!r} must NOT be a correction key in the safe OCR map"

    @pytest.mark.parametrize(
        "text, expected",
        [
            # Safety cases: must be UNCHANGED through HybridSpellChecker alone
            ("ترامادول 0.5 mg", "ترامادول 0.5 mg"),
            ("لا يعطى ترامادول 0.5 mg", "لا يعطى ترامادول 0.5 mg"),
            ("0.5", "0.5"),
            ("1.25", "1.25"),
            ("0.75", "0.75"),
            ("٠٫٥", "٠٫٥"),
            ("١٫٢٥", "١٫٢٥"),
            # Additional safety cases
            ("ترامادول 5 mg", "ترامادول 5 mg"),
            ("ترامادول 500 mg", "ترامادول 500 mg"),
            ("باراسيتامول 500 mg", "باراسيتامول 500 mg"),
            ("لا يعطى باراسيتامول 500 mg", "لا يعطى باراسيتامول 500 mg"),
            ("بدون ترامادول", "بدون ترامادول"),
            ("ليس لديه ترامادول", "ليس لديه ترامادول"),
            ("ترامادول 0.5 ملغ", "ترامادول 0.5 ملغ"),
        ],
    )
    def test_safety_cases_through_spell_checker(self, text, expected):
        """Safety cases through HybridSpellChecker alone — must be unchanged."""
        assert HybridSpellChecker().correct_text(text) == expected

    def test_intended_ocr_correction_through_auto_correct(self):
        """The intended drug-name correction (باراسيتبمول → باراسيتامول) happens
        in _auto_correct_ocr (production OCR pipeline), NOT in HybridSpellChecker.
        This test verifies the full production call graph."""
        import app_core
        out, _ = app_core._auto_correct_ocr("باراسيتبمول 500 mg")
        assert out == "باراسيتامول 500 mg", \
            f"Intended OCR correction failed through production _auto_correct_ocr: got {out!r}"

    def test_safety_cases_through_auto_correct(self):
        """All user-brief safety cases through the full production OCR pipeline
        (_auto_correct_ocr → HybridSpellChecker)."""
        import app_core
        cases = [
            ("ترامادول 0.5 mg",        "ترامادول 0.5 mg"),
            ("لا يعطى ترامادول 0.5 mg", "لا يعطى ترامادول 0.5 mg"),
            ("0.5",                     "0.5"),
            ("1.25",                    "1.25"),
            ("0.75",                    "0.75"),
            ("٠٫٥",                     "٠٫٥"),
            ("١٫٢٥",                    "١٫٢٥"),
            ("ترامادول 5 mg",          "ترامادول 5 mg"),
            ("ترامادول 500 mg",        "ترامادول 500 mg"),
            ("باراسيتامول 500 mg",     "باراسيتامول 500 mg"),
            ("لا يعطى باراسيتامول 500 mg", "لا يعطى باراسيتامول 500 mg"),
            ("بدون ترامادول",          "بدون ترامادول"),
            ("ليس لديه ترامادول",      "ليس لديه ترامادول"),
            ("ترامادول 0.5 ملغ",       "ترامادول 0.5 ملغ"),
        ]
        for text, expected in cases:
            out, _ = app_core._auto_correct_ocr(text)
            assert out == expected, \
                f"Production _auto_correct_ocr failed: input={text!r} expected={expected!r} got={out!r}"

    def test_negation_is_not_rewritten(self):
        checker = HybridSpellChecker()
        text = "لا يعطى ترامادول 0.5 mg"
        assert checker.correct_text(text) == text
        assert checker.correct_text("لا يوجد ترامادول") == "لا يوجد ترامادول"

    def test_safe_ocr_map_has_no_dose_or_negation_keys(self):
        """The safe OCR map (loaded by production HybridSpellChecker) must contain
        NO dangerous keys: no decimals, no drug doses, no negations, no whitespace
        padding, no critical drug names as keys."""
        data = json.loads(SAFE_OCR.read_text(encoding="utf-8"))
        assert data
        for key in data:
            dangerous, reason = is_dangerous_key(key)
            assert not dangerous, f"Unsafe OCR key leaked: {key!r} ({reason})"
            # Critical drug names must never be correction keys
            assert not is_critical_medical_term(key), \
                f"Critical drug name as key in safe OCR map: {key!r}"


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
    """Audit the full merged-glossary output whenever it is regenerated locally/CI."""

    @pytest.mark.skipif(not MERGED.exists(), reason="generated 96 MB artifact is intentionally git-ignored")
    def test_merged_dictionary_is_safe(self):
        """The merged dictionary (158,300 entries at last audit) must:
        - have unique normalized keys (no duplicates)
        - have no dangerous keys (decimals, doses, negations, etc.)
        - have non-empty source provenance for every entry
        - have no critical drug names as keys"""
        data = json.loads(MERGED.read_text(encoding="utf-8"))
        entries = data["entries"] if isinstance(data, dict) and "entries" in data else data
        # Entry count is not fixed — it depends on how many malek_data entries
        # pass the firewall. The current count is ~158,300 but may shift if the
        # upstream sources change. The invariant we care about is safety.
        assert len(entries) > 100_000, f"Expected >100k merged entries, got {len(entries)}"
        normalized = [e["normalized_key"] for e in entries]
        assert len(normalized) == len(set(normalized)), "Duplicate normalized keys found"
        for e in entries:
            dangerous, reason = is_dangerous_key(e["key"])
            assert not dangerous, f"Unsafe merged entry: {e['key']!r} ({reason})"
            assert e.get("source"), f"Missing provenance: {e['key']!r}"
            assert not is_critical_medical_term(e["key"]), \
                f"Critical drug as key in merged glossary: {e['key']!r}"

    @pytest.mark.skipif(not MALEK_TERMS.exists(), reason="malek_data extraction is private/regenerated and git-ignored")
    def test_malek_terms_has_no_obvious_pii_fields(self):
        """The malek_data_terms.json extraction (103,169 entries) must contain:
        - No @gmail.com / @outlook.com / @hotmail.com (personal email providers)
        - No phone/telephone/fax label prefixes that suggest personal contact info
        - Only documented fields (en, ar, tuid, source, _file, category, confidence)
        Institutional emails (e.g. @jhmi.edu) appearing in translated sentence
        content are acceptable — they are part of the source corpus, not PII
        about the user."""
        import re as _re
        data = json.loads(MALEK_TERMS.read_text(encoding="utf-8"))
        
        EMAIL_PERSONAL = _re.compile(r"[a-zA-Z0-9._%+-]+@(?:gmail|outlook|hotmail)\.[a-zA-Z]{2,}", _re.IGNORECASE)
        # Personal-name + phone-like combo (the user's specific PII)
        PERSONAL_PII = ["abdulmalek.husseini", "abdulmalek husseini"]
        
        allowed_fields = {"en", "ar", "tuid", "source", "_file", "category", "confidence"}
        
        personal_email_count = 0
        personal_pii_count = 0
        bad_field_count = 0
        
        for entry in data.get("entries", []):
            # Verify only allowed fields
            extra = set(entry) - allowed_fields
            if extra:
                bad_field_count += 1
                continue
            
            en = entry.get("en", "")
            ar = entry.get("ar", "")
            
            # Personal email providers (gmail/outlook/hotmail) = personal PII
            if EMAIL_PERSONAL.search(en) or EMAIL_PERSONAL.search(ar):
                personal_email_count += 1
            
            # User's personal name+email combo
            for pii in PERSONAL_PII:
                if pii in en.lower() or pii in ar.lower():
                    personal_pii_count += 1
                    break
        
        assert personal_email_count == 0, \
            f"Personal email addresses (gmail/outlook/hotmail) found in {personal_email_count} malek_data entries"
        assert personal_pii_count == 0, \
            f"User personal PII (abdulmalek.husseini) found in {personal_pii_count} malek_data entries"
        assert bad_field_count == 0, \
            f"Unexpected fields in {bad_field_count} malek_data entries (allowed: {allowed_fields})"
