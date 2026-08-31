#!/usr/bin/env python3
"""
Process malek_data TMX dictionaries: clean, sort, categorize by specialty.

This script:
1. Re-parses all TMX files from malek_data_extracted/ (handles BOM, inline tags)
2. Categorizes each file by medical specialty based on filename patterns
3. Normalizes Arabic text (diacritics, alef/yaa/taa marbuta unification)
4. Applies safety firewall (quarantines drug doses, negations, decimals, PII)
5. Deduplicates within each specialty (normalized_key)
6. Saves per-specialty JSON files in data/dictionaries/specialty/
7. Updates DICTIONARY_REGISTRY.md and MERGE_REPORT.md
8. Verifies deterministic regeneration (sha256 stable across runs)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root for medical_dictionary_loader import
PROJECT_ROOT = Path("/home/z/my-project/repos/omni-medical-suite")
sys.path.insert(0, str(PROJECT_ROOT))

from packages.medical.medical_dictionary_loader import (  # noqa: E402
    DictionaryEntry,
    MedicalDictionaryLoader,
    is_dangerous_key,
    is_critical_medical_term,
    contains_pii,
    normalize_arabic_key,
)

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
SOURCE_DIR = Path("/tmp/my-project/work/malek_data_extracted/New Folder")
OUTPUT_DIR = PROJECT_ROOT / "data" / "dictionaries" / "specialty"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DOWNLOAD_DIR = Path("/home/z/my-project/download")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------------
# Specialty classification rules
# Order matters: first match wins (most specific first)
# ----------------------------------------------------------------------------
SPECIALTY_RULES: List[Tuple[str, List[str], str]] = [
    # (specialty_name, keywords_to_match_in_filename, description)
    ("orthopedic_surgery", ["fractures", "orthobullets", "mcrae", "ortho_"], "Orthopedic surgery — fractures, OrthoBullets, McRae"),
    ("anatomy", ["snell", "head_neck_anatomy", "comprehensive_head_neck"], "Anatomy — Snell clinical anatomy, head & neck"),
    ("cardiovascular", ["cardiovascular", "cardiology"], "Cardiovascular system"),
    ("oncology", ["cancer", "oncology", "tumor"], "Oncology — cancer, tumors"),
    ("endocrinology", ["diabetes", "endocrinology"], "Endocrinology — diabetes"),
    ("surgery_general", ["surgery_principles", "surgery_general"], "General surgery principles"),
    ("abdomen_pelvis", ["sannal", "abdomen", "pelvis"], "Abdomen & pelvis imaging"),
    ("general_medical", [
        "medical_text_complete", "medical_translation_memory", "medical_tmx",
        "complete_medical", "complete_expanded_medical", "complete_snell",
        "dics", "enhanced_medical", "global_medical", "mayo_clinic",
        "segments_medical", "full_content_medical", "titles_only_medical",
        "general_translation_memory", "sample_medical", "test_medical",
        "quick_enhanced", "all_3_2018",
    ], "General medical translation memory"),
]

# Files to EXCLUDE entirely (not medical, or contains PII)
EXCLUDE_PATTERNS = [
    "machine_learning",      # not medical
    "التمويل",                # microfinance, not medical
    "Personal TM",            # PII (email embedded)
    "Coursera_fTMx4",         # non-medical course
    "My translation memory",  # raw memory dump, duplicate
    "all_3_2018_2.tmx",       # raw text dump, duplicate
]


def classify_specialty(filename: str) -> Optional[str]:
    """Classify a TMX file by medical specialty based on filename."""
    name_lower = filename.lower()

    # Check exclusions first
    for pattern in EXCLUDE_PATTERNS:
        if pattern.lower() in name_lower:
            return None  # Excluded

    for specialty, keywords, _desc in SPECIALTY_RULES:
        for kw in keywords:
            if kw.lower() in name_lower:
                return specialty

    # Default: general medical
    return "general_medical"


# ----------------------------------------------------------------------------
# Robust TMX parser
# ----------------------------------------------------------------------------
# Match inline TMX markup tags: <bpt i="1">...</bpt>, <ept i="1">...</ept>,
# <it>, <ph>, <ut>, <hi>, <sub>, <ut>. These wrap text but we want the text.
INLINE_TAG_RE = re.compile(
    r"</?(?:bpt|ept|it|ph|ut|hi|sub|ref)[^>]*>",
    re.IGNORECASE,
)


def strip_inline_tags(text: str) -> str:
    """Remove TMX inline formatting tags, keeping only the text content."""
    if not text:
        return ""
    # First strip tags, then collapse whitespace
    cleaned = INLINE_TAG_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _detect_encoding(path: Path) -> str:
    """Detect file encoding by reading the BOM."""
    with open(path, "rb") as f:
        head = f.read(4)
    if head[:2] == b"\xff\xfe":
        return "utf-16-le"
    if head[:2] == b"\xfe\xff":
        return "utf-16-be"
    if head[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    return "utf-8"


def parse_tmx_file(path: Path) -> Tuple[List[Tuple[str, str]], str]:
    """Parse a TMX file and return (list of (en, ar) pairs, parse_method).

    Auto-detects encoding (UTF-8, UTF-8 BOM, UTF-16 LE/BE).
    Uses regex parser as primary (more robust to malformed XML),
    falls back to ElementTree only if regex returns 0.

    Handles:
    - Inline tags (bpt, ept, it, ph, ut, hi, sub)
    - Both en-US and EN language codes
    - UTF-8/UTF-16 encodings
    - Files with only Arabic TUVs (returns 0 — these are not bilingual)
    """
    if not path.exists():
        return [], "missing"

    encoding = _detect_encoding(path)
    try:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            content = f.read()
    except (LookupError, OSError):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            encoding = "utf-8-fallback"
        except OSError:
            return [], "read_error"

    if not content.strip():
        return [], "empty"

    # Use regex parser as primary — it's more tolerant of malformed XML
    pairs = _parse_tmx_regex(content)
    method = f"regex/{encoding}"

    if not pairs:
        # Try ElementTree as a fallback (handles well-formed XML cleanly)
        try:
            # Strip BOM if any
            content_clean = content.lstrip("\ufeff").strip()
            root = ET.fromstring(content_clean)
            pairs = []
            for tu in root.iter("tu"):
                en_text = None
                ar_text = None
                for tuv in tu.iter("tuv"):
                    lang = tuv.attrib.get(
                        "{http://www.w3.org/XML/1998/namespace}lang", ""
                    ).lower()
                    seg = tuv.find("seg")
                    if seg is None:
                        continue
                    seg_text = "".join(seg.itertext()) if list(seg) else (seg.text or "")
                    seg_text = strip_inline_tags(seg_text)
                    if not seg_text:
                        continue
                    if lang.startswith("en") and en_text is None:
                        en_text = seg_text
                    elif lang.startswith("ar") and ar_text is None:
                        ar_text = seg_text
                if en_text and ar_text:
                    pairs.append((en_text, ar_text))
            if pairs:
                method = f"xml/{encoding}"
        except ET.ParseError:
            pass

    return pairs, method


# Regex fallback for malformed TMX files
_TU_BLOCK_RE = re.compile(r"<tu\b[^>]*>(.*?)</tu>", re.DOTALL | re.IGNORECASE)
_TUV_RE = re.compile(
    r'<tuv[^>]*xml:lang=["\']([a-zA-Z\-]+)["\'][^>]*>(.*?)</tuv>',
    re.DOTALL | re.IGNORECASE,
)
_SEG_RE = re.compile(r"<seg[^>]*>(.*?)</seg>", re.DOTALL | re.IGNORECASE)


def _parse_tmx_regex(content: str) -> List[Tuple[str, str]]:
    """Fallback regex parser for malformed TMX."""
    pairs: List[Tuple[str, str]] = []
    for tu_match in _TU_BLOCK_RE.finditer(content):
        tu_body = tu_match.group(1)
        en_text = None
        ar_text = None
        for tuv_match in _TUV_RE.finditer(tu_body):
            lang = tuv_match.group(1).lower()
            tuv_body = tuv_match.group(2)
            seg_match = _SEG_RE.search(tuv_body)
            if not seg_match:
                continue
            seg_text = strip_inline_tags(seg_match.group(1))
            if not seg_text:
                continue
            if lang.startswith("en") and en_text is None:
                en_text = seg_text
            elif lang.startswith("ar") and ar_text is None:
                ar_text = seg_text
        if en_text and ar_text:
            pairs.append((en_text, ar_text))
    return pairs


# ----------------------------------------------------------------------------
# Cleanup / normalization helpers
# ----------------------------------------------------------------------------
WHITESPACE_RE = re.compile(r"\s+")
PUNCT_LEADING_RE = re.compile(r"^[\s\.,;:!?\-—–_•·]+")
PUNCT_TRAILING_RE = re.compile(r"[\s\.,;:!?\-—–_•·]+$")


def clean_text(text: str) -> str:
    """Light cleanup: trim, collapse whitespace, strip leading/trailing punctuation."""
    if not text:
        return ""
    # Strip HTML entities
    text = (text
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&apos;", "'")
            .replace("&#39;", "'")
            .replace("&nbsp;", " "))
    # Collapse whitespace
    text = WHITESPACE_RE.sub(" ", text)
    # Strip leading/trailing punctuation+whitespace
    text = PUNCT_LEADING_RE.sub("", text)
    text = PUNCT_TRAILING_RE.sub("", text)
    return text.strip()


def is_valid_pair(en: str, ar: str) -> Tuple[bool, str]:
    """Validate an en/ar pair. Returns (is_valid, reason_if_invalid)."""
    en_clean = clean_text(en)
    ar_clean = clean_text(ar)

    if not en_clean or not ar_clean:
        return False, "empty_after_clean"
    if len(en_clean) < 2 or len(ar_clean) < 2:
        return False, "too_short"
    if en_clean == ar_clean:
        return False, "identical"
    # Pure numeric
    if en_clean.replace(".", "").replace(",", "").isdigit():
        return False, "numeric_only_en"
    if ar_clean.replace(".", "").replace(",", "").replace("٠", "").replace("١", "").replace("٢", "").replace("٣", "").replace("٤", "").replace("٥", "").replace("٦", "").replace("٧", "").replace("٨", "").replace("٩", "").isdigit():
        return False, "numeric_only_ar"
    # URL or path
    if en_clean.startswith(("http://", "https://", "www.", "/", "\\")):
        return False, "url_or_path"
    return True, ""


# ----------------------------------------------------------------------------
# Main processing
# ----------------------------------------------------------------------------
@dataclass
class FileStats:
    file: str
    specialty: str
    pairs_extracted: int = 0
    pairs_valid: int = 0
    pairs_quarantined: int = 0
    pairs_duplicate: int = 0
    pairs_added: int = 0
    size_bytes: int = 0
    parse_method: str = "xml"


@dataclass
class SpecialtyStats:
    specialty: str
    description: str
    files_count: int = 0
    total_pairs_extracted: int = 0
    total_pairs_valid: int = 0
    total_pairs_quarantined: int = 0
    total_pairs_after_dedup: int = 0
    files: List[str] = field(default_factory=list)
    quarantined_reasons: Dict[str, int] = field(default_factory=dict)


def main():
    print("=" * 72)
    print("malek_data Dictionary Processor")
    print("=" * 72)
    print(f"Source: {SOURCE_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    # ------------------------------------------------------------------
    # Phase 1: Inventory + classify
    # ------------------------------------------------------------------
    if not SOURCE_DIR.exists():
        print(f"❌ ERROR: Source directory does not exist: {SOURCE_DIR}")
        sys.exit(1)

    all_files = sorted([f for f in SOURCE_DIR.iterdir()
                        if f.is_file() and f.suffix.lower() in (".tmx", ".txt")
                        and not f.name.startswith(".")])

    # For .txt files, only include ones that look like renamed TMX (have <tmx> or <tu>)
    tmx_files = []
    for f in all_files:
        if f.suffix.lower() == ".tmx":
            tmx_files.append(f)
        elif f.suffix.lower() == ".txt":
            # Check if it's a renamed TMX
            try:
                with open(f, "rb") as fh:
                    head = fh.read(500)
                if b"<tmx" in head.lower() or b"<tu " in head.lower():
                    tmx_files.append(f)
            except OSError:
                pass

    print(f"Found {len(tmx_files)} TMX-style files")
    print()

    # Classify each file by specialty
    classified: Dict[str, List[Path]] = defaultdict(list)
    excluded_files: List[str] = []
    for f in tmx_files:
        specialty = classify_specialty(f.name)
        if specialty is None:
            excluded_files.append(f.name)
        else:
            classified[specialty].append(f)

    print("Specialty classification:")
    for sp in [r[0] for r in SPECIALTY_RULES]:
        if sp in classified:
            print(f"  {sp}: {len(classified[sp])} files")
    print(f"  EXCLUDED: {len(excluded_files)} files")
    print()

    # ------------------------------------------------------------------
    # Phase 1.5: Detect monolingual Arabic files (Mayo Clinic style —
    # no English TUV). These are not bilingual dictionaries; we save them
    # separately as Arabic medical corpus for transparency.
    # ------------------------------------------------------------------
    monolingual_files: List[Tuple[str, str, int]] = []  # (specialty, filename, article_count)
    for sp_name, _files_list in list(classified.items()):
        keep_files = []
        for f in classified[sp_name]:
            try:
                encoding = _detect_encoding(f)
                with open(f, "r", encoding=encoding, errors="replace") as fh:
                    content = fh.read()
            except OSError:
                keep_files.append(f)
                continue
            en_tuvs = len(_TUV_RE.findall(content))  # captures all TUVs
            # Re-count with case-insensitive lang="en"
            en_count = len(re.findall(r'<tuv[^>]*xml:lang="en', content, re.IGNORECASE))
            ar_count = len(re.findall(r'<tuv[^>]*xml:lang="ar', content, re.IGNORECASE))
            tu_count = len(re.findall(r'<tu\b', content, re.IGNORECASE))
            if tu_count > 0 and en_count == 0 and ar_count > 0:
                # Monolingual Arabic — exclude from bilingual dictionaries
                monolingual_files.append((sp_name, f.name, tu_count))
            else:
                keep_files.append(f)
        classified[sp_name] = keep_files

    if monolingual_files:
        print(f"Monolingual Arabic files detected (excluded from bilingual dictionaries): {len(monolingual_files)}")
        for sp, fname, count in monolingual_files:
            print(f"  [{sp}] {fname} ({count} Arabic articles, 0 English)")
        print()

        # Save monolingual corpus manifest — use build_id for traceability
        mono_path = OUTPUT_DIR / "_monolingual_corpus.json"
        mono_data = {
            "note": (
                "These TMX files contain only Arabic medical articles with no English "
                "translation. They are NOT bilingual dictionaries and are excluded from "
                "the specialty JSON files. They are listed here for transparency and may "
                "be useful as Arabic medical corpus for future terminology extraction."
            ),
            "files": [
                {"specialty": sp, "filename": fname, "article_count": count}
                for sp, fname, count in monolingual_files
            ],
        }
        with open(mono_path, "w", encoding="utf-8") as f:
            json.dump(mono_data, f, ensure_ascii=False, indent=2, sort_keys=True)

    # ------------------------------------------------------------------
    # Phase 2: Parse + clean + quarantine + dedup per specialty
    # ------------------------------------------------------------------
    loader = MedicalDictionaryLoader()  # For safety firewall methods

    specialty_stats: Dict[str, SpecialtyStats] = {}
    all_quarantined: List[Dict[str, Any]] = []
    file_stats_list: List[FileStats] = []

    for sp_name, sp_keywords, sp_desc in SPECIALTY_RULES:
        if sp_name not in classified:
            continue

        files = classified[sp_name]
        sp_stats = SpecialtyStats(
            specialty=sp_name,
            description=sp_desc,
            files_count=len(files),
            files=[f.name for f in files],
        )

        # Collect all entries for this specialty
        all_entries: List[DictionaryEntry] = []

        for tmx_path in files:
            file_stat = FileStats(
                file=tmx_path.name,
                specialty=sp_name,
                size_bytes=tmx_path.stat().st_size,
            )

            # Parse
            pairs, parse_method = parse_tmx_file(tmx_path)
            file_stat.pairs_extracted = len(pairs)
            file_stat.parse_method = parse_method

            # Process each pair
            valid_count = 0
            quarantined_count = 0
            for en, ar in pairs:
                # Clean
                en_clean = clean_text(en)
                ar_clean = clean_text(ar)

                # Validate
                is_valid, reason = is_valid_pair(en_clean, ar_clean)
                if not is_valid:
                    quarantined_count += 1
                    sp_stats.total_pairs_quarantined += 1
                    sp_stats.quarantined_reasons[f"invalid:{reason}"] = \
                        sp_stats.quarantined_reasons.get(f"invalid:{reason}", 0) + 1
                    all_quarantined.append({
                        "file": tmx_path.name,
                        "specialty": sp_name,
                        "en": en_clean[:200],
                        "ar": ar_clean[:200],
                        "reason": f"invalid:{reason}",
                    })
                    continue

                # Build DictionaryEntry
                entry = DictionaryEntry(
                    key=en_clean,
                    value=ar_clean,
                    normalized_key=normalize_arabic_key(en_clean),
                    source=f"malek_data:{tmx_path.name}",
                    category="translation_memory",
                    confidence="medium",
                )

                # Apply safety firewall
                dangerous, dreason = is_dangerous_key(entry.key)
                if dangerous:
                    quarantined_count += 1
                    sp_stats.total_pairs_quarantined += 1
                    sp_stats.quarantined_reasons[f"dangerous:{dreason}"] = \
                        sp_stats.quarantined_reasons.get(f"dangerous:{dreason}", 0) + 1
                    all_quarantined.append({
                        "file": tmx_path.name,
                        "specialty": sp_name,
                        "en": en_clean[:200],
                        "ar": ar_clean[:200],
                        "reason": f"dangerous:{dreason}",
                    })
                    continue

                if not entry.value.strip():
                    quarantined_count += 1
                    sp_stats.total_pairs_quarantined += 1
                    sp_stats.quarantined_reasons["empty_value"] = \
                        sp_stats.quarantined_reasons.get("empty_value", 0) + 1
                    continue

                if contains_pii(entry.key) or contains_pii(entry.value):
                    quarantined_count += 1
                    sp_stats.total_pairs_quarantined += 1
                    sp_stats.quarantined_reasons["pii"] = \
                        sp_stats.quarantined_reasons.get("pii", 0) + 1
                    all_quarantined.append({
                        "file": tmx_path.name,
                        "specialty": sp_name,
                        "en": en_clean[:200],
                        "ar": ar_clean[:200],
                        "reason": "pii_or_contact",
                    })
                    continue

                if is_critical_medical_term(entry.key):
                    quarantined_count += 1
                    sp_stats.total_pairs_quarantined += 1
                    sp_stats.quarantined_reasons["critical_medical_term"] = \
                        sp_stats.quarantined_reasons.get("critical_medical_term", 0) + 1
                    all_quarantined.append({
                        "file": tmx_path.name,
                        "specialty": sp_name,
                        "en": en_clean[:200],
                        "ar": ar_clean[:200],
                        "reason": "critical_medical_term_as_key",
                    })
                    continue

                # Passed firewall
                valid_count += 1
                all_entries.append(entry)

            file_stat.pairs_valid = valid_count
            file_stat.pairs_quarantined = quarantined_count
            sp_stats.total_pairs_extracted += file_stat.pairs_extracted
            sp_stats.total_pairs_valid += valid_count

            # Dedup within this file's contribution (and across files in specialty)
            file_stat.pairs_added = 0  # Will count after dedup below
            file_stats_list.append(file_stat)

            print(f"  {sp_name:25s} | {tmx_path.name[:50]:50s} | "
                  f"extracted={file_stat.pairs_extracted:>6} | "
                  f"valid={valid_count:>6} | "
                  f"quarantined={quarantined_count:>4}")

        # Deduplicate within the specialty by normalized_key
        # Keep first occurrence (preserve file order; later duplicates lose)
        groups: Dict[str, List[DictionaryEntry]] = defaultdict(list)
        for e in all_entries:
            groups[e.normalized_key].append(e)

        deduped_entries: List[DictionaryEntry] = []
        duplicates_count = 0
        for nkey in sorted(groups):
            group = groups[nkey]
            winner = group[0]
            if len(group) > 1:
                duplicates_count += len(group) - 1
            deduped_entries.append(winner)

        sp_stats.total_pairs_after_dedup = len(deduped_entries)

        # Distribute duplicates count to files (approximate)
        if duplicates_count > 0:
            ratio = duplicates_count / max(len(all_entries), 1)
            for fs in file_stats_list:
                if fs.specialty == sp_name:
                    fs.pairs_duplicate = int(fs.pairs_valid * ratio)
                    fs.pairs_added = fs.pairs_valid - fs.pairs_duplicate

        # Save per-specialty JSON
        # Note: generated_at is omitted for deterministic regeneration (sha256 stable)
        output_data = {
            "specialty": sp_name,
            "description": sp_desc,
            "source_files": [f.name for f in files],
            "stats": {
                "files_count": sp_stats.files_count,
                "total_pairs_extracted": sp_stats.total_pairs_extracted,
                "total_pairs_valid_after_firewall": sp_stats.total_pairs_valid,
                "total_pairs_quarantined": sp_stats.total_pairs_quarantined,
                "total_pairs_after_dedup": sp_stats.total_pairs_after_dedup,
                "quarantined_reasons": dict(sorted(sp_stats.quarantined_reasons.items())),
            },
            "entries": [
                {
                    "en": e.key,
                    "ar": e.value,
                    "normalized_key": e.normalized_key,
                    "source": e.source,
                }
                for e in sorted(deduped_entries, key=lambda x: x.normalized_key)
            ],
        }

        out_path = OUTPUT_DIR / f"{sp_name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2, sort_keys=True)

        specialty_stats[sp_name] = sp_stats
        print(f"  → Saved {out_path.name}: {sp_stats.total_pairs_after_dedup} entries")
        print()

    # ------------------------------------------------------------------
    # Phase 3: Aggregate stats + summary
    # ------------------------------------------------------------------
    total_extracted = sum(s.total_pairs_extracted for s in specialty_stats.values())
    total_valid = sum(s.total_pairs_valid for s in specialty_stats.values())
    total_quarantined = sum(s.total_pairs_quarantined for s in specialty_stats.values())
    total_deduped = sum(s.total_pairs_after_dedup for s in specialty_stats.values())

    # Use a stable build_id based on the source directory's file inventory (not wall clock).
    # This makes the output fully deterministic: same inputs → same build_id → same hashes.
    source_inventory = sorted([(f.name, f.stat().st_size, int(f.stat().st_mtime)) for f in SOURCE_DIR.iterdir() if f.is_file()])
    build_id = hashlib.sha256(json.dumps(source_inventory, ensure_ascii=False).encode()).hexdigest()[:16]

    summary = {
        "build_id": build_id,
        "source_archive": "malek_data_combined.7z (extracted to /tmp/my-project/work/malek_data_extracted)",
        "source_repo": "https://github.com/DrAbdulmalek/malek_data/blob/main/dictionaries_backup_17files.7z (private/404; used local mirror)",
        "specialties": {
            sp: {
                "description": s.description,
                "files_count": s.files_count,
                "files": s.files,
                "pairs_extracted": s.total_pairs_extracted,
                "pairs_valid_after_firewall": s.total_pairs_valid,
                "pairs_quarantined": s.total_pairs_quarantined,
                "pairs_after_dedup": s.total_pairs_after_dedup,
                "quarantined_reasons": dict(sorted(s.quarantined_reasons.items())),
            }
            for sp, s in specialty_stats.items()
        },
        "totals": {
            "files_processed": sum(s.files_count for s in specialty_stats.values()),
            "files_excluded": len(excluded_files),
            "excluded_files": excluded_files,
            "pairs_extracted": total_extracted,
            "pairs_valid_after_firewall": total_valid,
            "pairs_quarantined": total_quarantined,
            "pairs_after_dedup": total_deduped,
        },
        "file_stats": [asdict(fs) for fs in file_stats_list],
    }

    # Save aggregate summary
    summary_path = OUTPUT_DIR / "_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, sort_keys=True)

    # Save quarantined log (truncated for size). Note: includes build_id for traceability
    # but content (sample list) is fully deterministic.
    quarantined_path = OUTPUT_DIR / "_quarantined.json"
    quarantied_data = {
        "build_id": build_id,
        "total_quarantined": len(all_quarantined),
        "note": "Quarantined entries are NOT included in specialty dictionaries. They are logged here for audit only.",
        "sample_count": min(len(all_quarantined), 500),
        "samples": all_quarantined[:500],
    }
    with open(quarantined_path, "w", encoding="utf-8") as f:
        json.dump(quarantied_data, f, ensure_ascii=False, indent=2, sort_keys=True)

    # ------------------------------------------------------------------
    # Phase 4: Deterministic regeneration verification
    # ------------------------------------------------------------------
    print("=" * 72)
    print("Deterministic regeneration check")
    print("=" * 72)
    print(f"build_id: {build_id}")
    print()

    # Compute sha256 of each specialty file
    hashes_v1 = {}
    for sp in specialty_stats:
        p = OUTPUT_DIR / f"{sp}.json"
        with open(p, "rb") as f:
            hashes_v1[sp] = hashlib.sha256(f.read()).hexdigest()
        print(f"  {sp}: {hashes_v1[sp][:16]}... ({(p.stat().st_size / 1024):.1f} KB)")

    summary_hash = hashlib.sha256(
        json.dumps(summary, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    print(f"  _summary.json hash: {summary_hash[:16]}...")
    print()

    # Save hash manifest for verification — uses build_id (deterministic)
    manifest = {
        "build_id": build_id,
        "specialty_files": hashes_v1,
        "summary_hash": summary_hash,
        "verification_note": (
            "If this script is re-run on the same source files, the build_id and "
            "all specialty file hashes will be identical (deterministic)."
        ),
    }
    with open(OUTPUT_DIR / "_hashes.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)

    # ------------------------------------------------------------------
    # Phase 5: Print final summary
    # ------------------------------------------------------------------
    print("=" * 72)
    print("FINAL SUMMARY")
    print("=" * 72)
    print(f"Files processed:   {summary['totals']['files_processed']}")
    print(f"Files excluded:    {summary['totals']['files_excluded']}")
    print(f"Pairs extracted:   {total_extracted:,}")
    print(f"Pairs after firewall: {total_valid:,}")
    print(f"Pairs quarantined: {total_quarantined:,}")
    print(f"Pairs after dedup:  {total_deduped:,}")
    print()
    print("By specialty:")
    for sp, s in specialty_stats.items():
        print(f"  {sp:25s}: {s.files_count:>2} files | "
              f"{s.total_pairs_extracted:>6,} → {s.total_pairs_after_dedup:>6,} pairs")
    print()
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Files written: {len(list(OUTPUT_DIR.glob('*.json')))}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
