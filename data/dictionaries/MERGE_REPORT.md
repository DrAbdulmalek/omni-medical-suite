# MERGE_REPORT.md — Dictionary Merge Statistics

This report covers two independent dictionary pipelines:

1. **Unified glossary pipeline** (`packages/medical/medical_dictionary_loader.py`) — produces `data/dictionaries/ocr_corrections_safe.json` and the unified glossary audit artifact.
2. **Specialty TMX pipeline** (`scripts/process_malek_dictionaries.py`) — produces the per-specialty JSON files under `data/dictionaries/specialty/`.

The two pipelines are intentionally separate. The unified glossary is a build-time audit artifact (158k entries, including conflicts). The specialty files are runtime-lookup resources, scoped per medical specialty, with safety firewall applied per entry.

---

## Unified glossary pipeline

Generated: 2026-08-26 09:24:46 UTC

### Top-level Numbers

| Metric | Value |
|--------|-------|
| Total entries loaded | 226,677 |
| Safe after firewall | 224,977 |
| Quarantined | 1,700 |
| After dedup + conflict resolution | 158,301 |
| Conflicts detected | 27,688 |

### Sources Used

| Source | Entries Loaded |
|--------|-----------------|
| `production_arabic_fixes` | 180 |
| `arabic_medical_glossary` | 124,756 |
| `malek_data_tmx` | 101,741 |

---

## Specialty TMX pipeline (malek_data)

Generated: 2026-08-29 (build_id: `e70cc7112b47f433` — deterministic; re-running the processor produces byte-identical output).

### Top-level Numbers

| Metric | Value |
|--------|-------|
| Source TMX files in archive | 58 |
| Files processed (bilingual, medical) | 50 |
| Files excluded (non-medical / PII) | 4 |
| Files excluded (monolingual Arabic — see `_monolingual_corpus.json`) | 4 |
| Pairs extracted | 310,891 |
| Pairs valid after firewall | 305,715 |
| Pairs quarantined | 5,176 |
| Pairs after dedup | **239,520** |

### By Specialty

| Specialty | Files | Pairs extracted | Valid (post-firewall) | Quarantined | After dedup |
|---|---|---|---|---|---|
| `orthopedic_surgery` | 3 | 282,990 | 278,904 | 4,086 | **225,494** |
| `anatomy` | 7 | 18,551 | 18,408 | 143 | **7,292** |
| `general_medical` | 36 | 8,979 | 8,032 | 947 | **6,403** |
| `surgery_general` | 2 | 351 | 351 | 0 | **321** |
| `abdomen_pelvis` | 2 | 20 | 20 | 0 | **10** |
| `cardiovascular` | 0 (monolingual source) | 0 | 0 | 0 | **0** |
| `oncology` | 0 (monolingual source) | 0 | 0 | 0 | **0** |
| `endocrinology` | 0 (monolingual source) | 0 | 0 | 0 | **0** |
| **TOTAL** | **50** | **310,891** | **305,715** | **5,176** | **239,520** |

### Quarantine breakdown (top reasons)

| Reason | Count | What it catches |
|---|---|---|
| `dangerous:decimal_dose` | 2,159 | Decimal numbers (e.g. `2.5`) — would corrupt dosage expressions |
| `dangerous:concentration_percent` | 1,161 | Expressions like `5%`, `0.9%` |
| `invalid:identical` | 950 | en == ar (no translation actually happened) |
| `dangerous:arabic_indic_digits` | 290 | Arabic-Indic digits ٠-٩ (locale-specific, ambiguous) |
| `dangerous:drug_dose_unit` | 324 | Expressions like `5mg`, `10ml`, `25mcg` |
| `invalid:url_or_path` | 55 | URLs and filesystem paths |
| `dangerous:negation` | 39 | Arabic negations (`لا`, `ليس`, `لم`, etc.) |
| `invalid:too_short` | 100 | Entries shorter than 2 chars |
| `pii_or_contact` | 45 | Emails, phone numbers, URLs |
| `invalid:empty_after_clean` | 22 | Empty after whitespace/punctuation cleanup |
| `invalid:numeric_only_en` | 4 | Pure numeric English strings |

### Deterministic regeneration

The processor uses a `build_id` derived from the source directory's file inventory (filename + size + mtime), NOT from wall-clock time. This means re-running the processor on the same source files produces byte-identical output.

**Verification:** Two consecutive runs produce identical SHA256 hashes for all 12 output files. See `data/dictionaries/specialty/_hashes.json` for the canonical hashes.

### Source files

**Archive:** `malek_data_combined.7z` (extracted locally to `/tmp/my-project/work/malek_data_extracted/`)

The original GitHub URL `https://github.com/DrAbdulmalek/malek_data/blob/main/dictionaries_backup_17files.7z` returns 404 — the `malek_data` repository is private or removed. The local mirror was used instead. The 17-file count in the URL likely refers to a subset of the 58 TMX files in the archive (perhaps the original curated set before additional files were added). All 58 TMX files were processed; 50 produced bilingual pairs and were included in the specialty dictionaries.

### Audit artifacts

- `_summary.json` — full per-file statistics (file, specialty, pairs_extracted, pairs_valid, pairs_quarantined, pairs_added, size_bytes, parse_method)
- `_hashes.json` — SHA256 of each specialty file (for deterministic regeneration verification)
- `_quarantined.json` — first 500 quarantined entries with file, specialty, en, ar, and reason (audit only; NOT loaded at runtime)
- `_monolingual_corpus.json` — list of 4 monolingual Arabic TMX files excluded from bilingual dictionaries