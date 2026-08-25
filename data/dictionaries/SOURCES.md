# SOURCES.md — Provenance of Merged Medical Dictionary

Generated: 2026-08-25 23:48:43 UTC

## Overview

This document records the origin, license, version, and contribution of every data source
merged into the unified medical dictionary at `data/dictionaries/medical_glossary_merged.json`.

## Source Priority (highest → lowest)

When two sources disagree on the translation of the same key, the higher-priority source wins.
Lower-priority sources are recorded as `conflicts` in `CONFLICTS.md` for human review.

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | `production_arabic_fixes` | Existing production `data/arabic_fixes.json` (180 entries) |
| 2 | `arabic_medical_glossary` | Submodule `data/arabic-medical-glossary` (124,756 verified pairs) |
| 3 | `malek_data_tmx` | Translation memories extracted from malek_data 7z archive |
| 4 | `ocr_corrections_hf_space` | Hardcoded OCR corrections in `hf-space/app_core.py` |

## Detailed Sources

### `production_arabic_fixes`

- **Path:** `/home/z/my-project/repos/omni-medical-suite/data/arabic_fixes.json`
- **Entries loaded:** 180
- **License:** Project-internal (existing in omni-medical-suite)
- **Provenance:** Direct production data; treated as canonical for existing keys.
- **Original filename:** `arabic_fixes.json`
- **Version:** HybridSpellChecker v7.0 production baseline

### `arabic_medical_glossary`

- **Path:** `/home/z/my-project/repos/omni-medical-suite/data/arabic-medical-glossary/glossaries/final_unified_glossary.csv`
- **Entries loaded:** 124,756
- **License:** See `data/arabic-medical-glossary/README.md`
- **Provenance:** Curated bilingual medical glossary extracted from Syrian pharmaceutical leaflets + parallel corpora (Quran, OMW, UN, Tashkeela, Khaleej). 124,756 verified medical pairs filtered from 386,402 raw pairs.
- **Original filename:** `glossaries/final_unified_glossary.csv`
- **Submodule commit:** `f7557a256bc1ce13f6d008cdea37fc846d68c518`
- **Quarantine note:** `archive/quarantine/hitti_dictionary_UNVERIFIED.csv` is excluded by upstream (not used).

### `malek_data_tmx`

- **Path:** `/home/z/my-project/repos/omni-medical-suite/data/dictionaries/malek_data_terms.json`
- **Entries loaded:** 103,169
- **License:** Source repo: `DrAbdulmalek/malek_data` (private). Personal translation-memory collection.
- **Provenance:** 58 TMX files extracted from 7z archive (`New Folder.7z.001-004`). Extracted via Python `py7zr` library.
- **Original filename:** Multiple TMX files (master_fractures, snell_anatomy, mayo_clinic, etc.)
- **Excluded files:** `التمويل الاصغر.tmx` (1,428 pairs) - non-medical (microfinance).
- **Extraction date:** 2026-08-25
- **Notes:** Multiple duplicate versions of same TMX exist (e.g., 4 copies of snell_anatomy with identical 6,172 pairs). Deduplicated via `normalized_key`.

## Malek_data Archive Inventory

The `malek_data` repository contains a 7z archive (`New Folder.7z.001-004`, ~141 MB) with:

| Category | Count | Size |
|----------|-------|------|
| Translation memory (TMX) | 58 | 337.87 MB |
| Text files (.txt) | 112 | 400.62 MB |
| Python source (.py) | 67 | 2.68 MB |
| Word documents (.docx) | 10 | 0.09 MB |
| Markdown (.md) | 8 | 0.04 MB |
| Shell scripts (.sh) | 6 | 0.01 MB |
| JSONL | 2 | 0.06 MB |
| Python bytecode (.pyc) | 6 | 0.33 MB |
| Unknown / archives | 24 | 75.43 MB |

**Total:** 301 files, 882.79 MB uncompressed.

## Data NOT Merged (intentionally excluded)

The following malek_data contents were NOT merged for safety or relevance reasons:

- **`التمويل الاصغر.tmx`** — microfinance domain, not medical (1,428 pairs excluded).
- **`.docx` files** — personal Q&A notes about TMX-building, contain author email (PII).
- **`medical_doc_gui_v*.py`** — different project (PyQt5 medical document OCR GUI); tracked separately at `DrAbdulmalek/medical-doc-processor`.
- **`*.pyc` bytecode** — generated artifacts, not source.
- **Personal TM** containing `abdulmalek.husseini@gmail.com` — PII, excluded.
- **Archive.7z.* files** — nested archive (already-extracted versions of the same TMX).

## Medical Safety Firewall

Every entry passes through `is_dangerous_key()` before being added to the runtime dictionary.
Quarantined entries are listed in `quarantined_entries.json` with the rejection reason.

Quarantine categories:
- `decimal_dose` — keys containing decimal numbers like `0.5`, `1.25` (drug doses)
- `concentration_percent` — keys containing `5%`, `10%` etc.
- `arabic_indic_digits` — keys containing `٠٫٥`, `١٫٢٥` (Arabic-Indic digits)
- `drug_dose_unit` — keys matching `\d+\s*(mg|ml|g|mcg|...)`
- `numeric_only` — purely numeric keys
- `too_short` — single-character keys
- `whitespace_padding` — keys with leading/trailing whitespace (the historic `'ترامادول '` bug)
- `negation:*` — keys beginning with `لا`, `ليس`, `لم`, `لن`, `غير`, `بدون`
- `critical_medical_term_as_key` — drug names used as correction keys (would corrupt prescriptions)
