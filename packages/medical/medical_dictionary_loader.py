#!/usr/bin/env python3
"""Role-aware medical dictionary loader with a deterministic safety firewall.

Runtime contracts are intentionally separate:
- OCR corrections: exact-token corrections only.
- Medical glossary: terminology/translation lookup, never arbitrary replacement.
- TMX: translation-memory exact lookup/suggestions, never arbitrary replacement.
The large merged dictionary remains a reproducible build/audit artifact.
"""
from __future__ import annotations
import csv
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GLOSSARY_CSV = PROJECT_ROOT / "data/arabic-medical-glossary/glossaries/final_unified_glossary.csv"
DEFAULT_MALEK_JSON = PROJECT_ROOT / "data/dictionaries/malek_data_terms.json"
DEFAULT_EXISTING_FIXES = PROJECT_ROOT / "data/arabic_fixes.json"
DEFAULT_SAFE_OCR = PROJECT_ROOT / "data/dictionaries/ocr_corrections_safe.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data/dictionaries"

ARABIC_NEGATION_PATTERNS = [r"^\s*لا\b", r"^\s*ليس\b", r"^\s*لم\b", r"^\s*لن\b", r"^\s*غير\b", r"^\s*بدون\b", r"\bلا\s+يعطى\b", r"\bلا\s+يوجد\b", r"\bليس\s+لديه\b"]
DECIMAL_PATTERN = re.compile(r"(?:\d+[.,]\d+|[٠-٩]+[٫٬،][٠-٩]+)")
DRUG_DOSE_PATTERN = re.compile(r"\b(?:\d+(?:\.\d+)?|[٠-٩]+(?:[٫٬،][٠-٩]+)?)\s*(?:mg|ml|g|mcg|µg|ug|IU|units?|قطرات?|مل|جم|مجم|ملغ|مغ)\b", re.IGNORECASE)
CONCENTRATION_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*%")
ARABIC_INDIC_DIGITS = re.compile(r"[\u0660-\u0669\u06F0-\u06F9]")
CRITICAL_MEDICAL_TERMS = {"ترامادول", "باراسيتامول", "باراسيتبمول", "ايبوبروفين", "ايبوروفين", "اموكسيسيلين", "اموكسيستلين", "اموكسيسلين", "ديكلوفيناك", "نابروكسين", "كوديين", "سالبوتامول", "لوراتادين", "سيتيريزين", "رانيتيدين", "فاموتيدين", "ميترونيدازول", "ميتروندازول", "اوجمنتين", "اوجمينتين", "اوميبرازول", "ازيثرومايسين", "ازيثروميسين", "سيفترياكسون", "دوكسيسيكلين", "سيبروفلوكساسين", "لوفلوكساسين", "ميفيناميك", "بنادول", "ادفيل", "كاتافلام", "فولتارين", "مونتيلوكاست", "سودوافيدرين", "انالجين"}

@dataclass
class DictionaryEntry:
    key: str
    value: str
    normalized_key: str
    source: str
    category: str = "general"
    confidence: str = "medium"
    section: str = ""
    conflicts: List[Dict[str, str]] = field(default_factory=list)
    safety_flag: str = "safe"
    def to_dict(self) -> Dict[str, Any]:
        return {"key": self.key, "value": self.value, "normalized_key": self.normalized_key, "source": self.source, "category": self.category, "confidence": self.confidence, "section": self.section, "conflicts": self.conflicts, "safety_flag": self.safety_flag}

def normalize_arabic_key(text: str) -> str:
    if not text: return ""
    s = text.strip()
    s = re.sub(r"[\u064B-\u0652\u0670]", "", s)
    s = re.sub(r"[\u0622\u0623\u0625]", "ا", s)
    s = s.replace("ى", "ي").replace("ک", "ك").replace("ی", "ي").replace("ہ", "ه").replace("ة", "ه")
    return re.sub(r"\s+", " ", s).lower()

def is_dangerous_key(key: str) -> Tuple[bool, str]:
    if not key or not key.strip(): return True, "empty_key"
    stripped = key.strip()
    if DECIMAL_PATTERN.search(stripped): return True, "decimal_dose"
    if ARABIC_INDIC_DIGITS.search(stripped): return True, "arabic_indic_digits"
    if DRUG_DOSE_PATTERN.search(stripped): return True, "drug_dose_unit"
    if CONCENTRATION_PATTERN.search(stripped): return True, "concentration_percent"
    for pattern in ARABIC_NEGATION_PATTERNS:
        if re.search(pattern, stripped): return True, f"negation:{pattern}"
    if stripped.replace(".", "").replace(",", "").isdigit(): return True, "numeric_only"
    if len(stripped) < 2: return True, "too_short"
    if key != stripped: return True, "whitespace_padding"
    return False, ""

def is_critical_medical_term(text: str) -> bool:
    return bool(text and text.strip().lower() in CRITICAL_MEDICAL_TERMS)

class MedicalDictionaryLoader:
    SOURCE_PRIORITY = ["production_arabic_fixes", "arabic_medical_glossary", "malek_data_tmx", "ocr_corrections_hf_space"]
    def __init__(self, glossary_csv_path: Optional[Path] = None, malek_json_path: Optional[Path] = None, existing_fixes_path: Optional[Path] = None, output_dir: Optional[Path] = None):
        self.glossary_csv_path = Path(glossary_csv_path or DEFAULT_GLOSSARY_CSV)
        self.malek_json_path = Path(malek_json_path or DEFAULT_MALEK_JSON)
        self.existing_fixes_path = Path(existing_fixes_path or DEFAULT_EXISTING_FIXES)
        self.output_dir = Path(output_dir or DEFAULT_OUTPUT_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_arabic_medical_glossary(self) -> List[DictionaryEntry]:
        if not self.glossary_csv_path.exists(): return []
        entries = []
        with self.glossary_csv_path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                en, ar = (row.get("en") or "").strip(), (row.get("ar") or "").strip()
                if not en or not ar: continue
                entries.append(DictionaryEntry(en, ar, normalize_arabic_key(en), f"arabic_medical_glossary:{(row.get('source') or '').strip()}", f"glossary_{(row.get('type') or 'term').strip()}", (row.get('confidence') or 'medium').strip().lower(), (row.get('section') or '').strip()))
        return entries

    def load_malek_data_terms(self) -> List[DictionaryEntry]:
        if not self.malek_json_path.exists(): return []
        with self.malek_json_path.open(encoding="utf-8") as f: data = json.load(f)
        entries = []
        for item in data.get("entries", []):
            en, ar = (item.get("en") or "").strip(), (item.get("ar") or "").strip()
            if not en or not ar or "التمويل الاصغر.tmx" in item.get("_file", ""): continue
            src = item.get("source", "") or "unknown"
            entries.append(DictionaryEntry(en, ar, normalize_arabic_key(en), f"malek_data:{src.split(':')[0][:60]}", "translation_memory", "medium"))
        return entries

    def load_existing_arabic_fixes(self) -> List[DictionaryEntry]:
        if not self.existing_fixes_path.exists(): return []
        with self.existing_fixes_path.open(encoding="utf-8") as f: data = json.load(f)
        return [DictionaryEntry(k, v, normalize_arabic_key(k), "production_arabic_fixes", "ocr_correction", "high") for k, v in sorted(data.items())]

    def _source_priority(self, entry: DictionaryEntry) -> int:
        prefix = entry.source.split(":", 1)[0]
        try: return self.SOURCE_PRIORITY.index(prefix)
        except ValueError: return len(self.SOURCE_PRIORITY)

    def detect_and_resolve_conflicts(self, entries: List[DictionaryEntry]):
        groups: Dict[str, List[DictionaryEntry]] = {}
        for e in entries: groups.setdefault(e.normalized_key, []).append(e)
        resolved, conflicts = [], []
        for nkey in sorted(groups):
            group = sorted(groups[nkey], key=lambda e: (self._source_priority(e), e.key, e.value, e.source))
            winner, losers = group[0], group[1:]
            if losers:
                winner.conflicts = [{"source": e.source, "value": e.value, "decision": "duplicate_same_value" if e.value == winner.value else f"lost_to:{winner.source}"} for e in losers]
                if any(e.value != winner.value for e in losers): conflicts.append({"normalized_key": nkey, "winner_source": winner.source, "winner_value": winner.value, "losers": winner.conflicts})
            resolved.append(winner)
        return resolved, conflicts

    def apply_medical_safety_firewall(self, entries: List[DictionaryEntry]):
        safe, quarantined = [], []
        for entry in entries:
            dangerous, reason = is_dangerous_key(entry.key)
            if dangerous:
                entry.safety_flag = f"quarantined:{reason}"; quarantined.append(entry); continue
            if not entry.value.strip():
                entry.safety_flag = "quarantined:empty_value"; quarantined.append(entry); continue
            # Critical medical terms (drug names) must NEVER be used as correction keys,
            # even from the production arabic_fixes source. Allowing a drug name as a
            # correction key risks corrupting prescriptions if the value field is ever
            # changed. The intended drug-name OCR corrections (باراسيتبمول → باراسيتامول)
            # are handled separately in hf-space/app_core.py:OCR_CORRECTIONS dict,
            # NOT through this dictionary.
            if is_critical_medical_term(entry.key):
                entry.safety_flag = "quarantined:critical_medical_term_as_key"; quarantined.append(entry); continue
            safe.append(entry)
        return safe, quarantined

    def load_unified_glossary(self, apply_safety: bool = True) -> Dict[str, Any]:
        all_entries, sources = [], []
        for loader, name, path in [(self.load_existing_arabic_fixes, "production_arabic_fixes", self.existing_fixes_path), (self.load_arabic_medical_glossary, "arabic_medical_glossary", self.glossary_csv_path), (self.load_malek_data_terms, "malek_data_tmx", self.malek_json_path)]:
            loaded = loader(); all_entries.extend(loaded)
            if loaded: sources.append({"name": name, "path": str(path), "entries_loaded": len(loaded)})
        safe, quarantined = self.apply_medical_safety_firewall(all_entries) if apply_safety else (all_entries, [])
        resolved, conflicts = self.detect_and_resolve_conflicts(safe)
        stats = {"total_loaded": len(all_entries), "safe_after_firewall": len(safe), "quarantined": len(quarantined), "after_dedup_and_conflict_resolution": len(resolved), "conflicts_detected": len(conflicts), "by_source": {}, "by_category": {}, "by_confidence": {}}
        for e in resolved:
            p = e.source.split(":", 1)[0]; stats["by_source"][p] = stats["by_source"].get(p, 0) + 1; stats["by_category"][e.category] = stats["by_category"].get(e.category, 0) + 1; stats["by_confidence"][e.confidence] = stats["by_confidence"].get(e.confidence, 0) + 1
        return {"entries": [e.to_dict() for e in resolved], "conflicts": conflicts, "quarantined": [e.to_dict() for e in quarantined], "stats": stats, "sources": sources}

    def load_safe_ocr_corrections(self, path: Optional[Path] = None) -> Dict[str, str]:
        p = Path(path or DEFAULT_SAFE_OCR)
        if not p.exists(): return {}
        with p.open(encoding="utf-8") as f: data = json.load(f)
        return {str(k): str(v) for k, v in data.items()}

    def export_to_json(self, data: Dict[str, Any], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)

    def export_safe_ocr_corrections(self, data: Dict[str, Any], path: Path) -> None:
        corrections = {e["key"]: e["value"] for e in data["entries"] if e.get("category") == "ocr_correction" and e.get("source") == "production_arabic_fixes"}
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f: json.dump(dict(sorted(corrections.items())), f, ensure_ascii=False, indent=2)

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print(json.dumps(MedicalDictionaryLoader().load_unified_glossary()["stats"], ensure_ascii=False, indent=2, sort_keys=True))

if __name__ == "__main__": main()
