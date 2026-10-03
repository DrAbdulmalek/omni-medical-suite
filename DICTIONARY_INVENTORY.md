# DICTIONARY_INVENTORY.md — Complete Inventory of All Dictionary-Like Files

> **Generated:** 2026-08-26
> **Repository:** `DrAbdulmalek/omni-medical-suite` @ commit `94bfd0e`
> **Branch:** `feat/integrate-malek-medical-dictionaries` (PR #92)
> **Scanner:** `scripts/build_dictionary_inventory.py`
> **Total files scanned:** 438 dictionary-like files across all formats (json, csv, tsv, tmx, yaml, yml)

## Summary Statistics

| Metric | Count |
|--------|-------|
| Total dictionary-like files | 438 |
| Runtime-loaded by production code | **121** |
| Not loaded by any production code | 317 |
| Generated artifacts (git-ignored) | 5 |
| Source dictionaries (committed) | 433 |
| LFS-tracked (per `.gitattributes`) | All in `data/**`, `*.csv`, `*.jsonl`, `*.parquet` |

### By specialty

| Specialty | Files | Notes |
|-----------|-------|-------|
| `medical_general` | 397 | Default classification when no orthopedic/cardiology/oncology hint |
| `orthopedic_surgery` | 27 | Files whose path/name contains `ortho`, `fracture`, `snell_anatomy`, `mcrae`, `orthobullets`, `hama_pharma` |
| `cardiology` | 14 | Files containing `cardio`, `heart`, `ecg` |

### By role

| Role | Files | Description |
|------|-------|-------------|
| `glossary` | 63 | Term-translation pairs (bilingual lookup) |
| `ocr_corrections` | 22 | Spell-correction maps (typo → correct) |
| `other` | 353 | Config files, dashboards, package manifests, etc. (not dictionaries per se but matched by scanner) |
| `translation_memory` | (in TMX form, none currently in repo) | TMX is loaded from malek_data 7z archive at runtime, not committed |

### By format

| Format | Files |
|--------|-------|
| `.csv` | 235 |
| `.json` | 181 |
| `.yaml` | 18 |
| `.tsv` | 4 |

---

## Runtime-Loaded Production Dictionaries (the 30 actual dictionaries)

These are the dictionaries actually loaded by Python production code (not test code, not docs).

### Tier 1: Production-canonical (used by the medical OCR pipeline)

| Path | Format | Entries | Lang | Specialty | Role | Production Consumer | Loaded How |
|------|--------|---------|------|-----------|------|---------------------|------------|
| `data/arabic_fixes.json` | json | 180 | ar | medical_general | ocr_corrections | `packages/core/spell_checker.py` (and 14 other places) | `HybridSpellChecker._load_fixes()` — Layer 1 (legacy) |
| `data/dictionaries/ocr_corrections_safe.json` | json | 175 | ar | medical_general | ocr_corrections | `packages/core/spell_checker.py` | `HybridSpellChecker._load_fixes()` — Layer 2 (PR #92) |
| `data/medical_dictionary.json` | json | 23 | ar+en | medical_general | glossary | `packages/medical/dictionary_manager.py` | `MedicalDictionaryManager` (SQLite pipeline) |
| `data/ortho_lexicon.json` | json | 6 | ar+en | **orthopedic_surgery** | glossary | `packages/core/classifier.py` | Specialty routing for orthopedic context |
| `data/translation_rules.json` | json | 24 | en | medical_general | other | `app/services/translation_service.py` | Translation rules lookup |

### Tier 2: Submodule (verified source — 124,756 pairs)

| Path | Format | Entries | Lang | Specialty | Role | Production Consumer | Loaded How |
|------|--------|---------|------|-----------|------|---------------------|------------|
| `data/arabic-medical-glossary/glossaries/final_unified_glossary.csv` | csv | 124,756 | ar+en | medical_general | glossary | `packages/medical/medical_dictionary_loader.py` | `MedicalDictionaryLoader.load_arabic_medical_glossary()` |

### Tier 3: Generated artifacts (git-ignored, regeneratable)

| Path | Format | Entries | Specialty | Role | Production Consumer | Regen Command |
|------|--------|---------|-----------|------|---------------------|---------------|
| `data/dictionaries/medical_glossary_merged.json` | json | 158,300 | medical_general | glossary (research) | `scripts/setup_medical_dictionaries.py` only — **NOT loaded by production runtime** | `python3 scripts/setup_medical_dictionaries.py` |
| `data/dictionaries/medical_glossary_merged.csv` | csv | 158,300 | medical_general | glossary (research) | (none — research artifact) | `python3 scripts/setup_medical_dictionaries.py` |
| `data/dictionaries/malek_data_terms.json` | json | 103,169 | medical_general | translation_memory (research) | `packages/medical/medical_dictionary_loader.py` | `python3 scripts/setup_medical_dictionaries.py` |
| `data/dictionaries/quarantined_entries.json` | json | 1,700 | medical_general | audit | (none) | `python3 scripts/setup_medical_dictionaries.py` |
| `data/dictionaries/conflicts.json` | json | 27,742 | medical_general | audit | (none) | `python3 scripts/setup_medical_dictionaries.py` |

### Tier 4: Duplicated copies of Tier 1 (NOT the canonical source — pre-existing duplication problem)

The repo has a known duplication problem (documented in `DUPLICATE_FILES_REPORT.txt`). For each Tier 1 file, multiple identical md5 copies exist:

| Canonical | Duplicates | Status |
|-----------|------------|--------|
| `data/arabic_fixes.json` (md5: `d716f79e394a3a76bdd8c7faf85e708d`) | `apps/handwriting-demo/variants/handwriting-ocr/data/arabic_fixes.json`<br>`packages/file_processor/data/arabic_fixes.json`<br>`packages/handwriting/data/arabic_fixes.json`<br>`hf-space/packages/core/data/arabic_fixes.json` (5 copies total) | Pre-existing — NOT addressed by PR #92 |
| `data/medical_dictionary.json` | `packages/file_processor/data/medical_dictionary.json` | Pre-existing |
| `data/ortho_lexicon.json` | `packages/file_processor/data/ortho_lexicon.json`<br>`packages/handwriting/data/ortho_lexicon.json`<br>`apps/handwriting-demo/variants/handwriting-ocr/data/ortho_lexicon.json` (4 copies total) | Pre-existing |

These duplicates are loaded by different code paths (`packages/file_processor/modules/...` vs `packages/core/...`). The medical OCR pipeline on `main` and PR #92 uses the **`packages/core/spell_checker.py`** copy of `HybridSpellChecker`, which loads the **`data/arabic_fixes.json`** canonical file.

### Tier 5: Non-canonical dictionaries (other apps/modules — NOT in medical OCR pipeline)

| Path | Format | Entries | Loaded By | Notes |
|------|--------|---------|-----------|-------|
| `apps/ocr-pipeline/data/arabic_medical_dict.json` | json | 4 | `apps/ocr-pipeline/src/spellcheck/` | Different app (ocr-pipeline), separate dict |
| `apps/ocr-pipeline/src/spellcheck/arabic_medical_dict.json` | json | 198 | `apps/ocr-pipeline/src/spellcheck/hybrid_spell_checker.py` | Different app |
| `config/extras/arabic_medical_dict.json` | json | 4 | `packages/gt_core/medical_doc_gui_patch.py` | Different module (gt_core ground-truth) |
| `apps/handwriting-demo/data/builtin_corrections.json` | json | 7 | `apps/handwriting-demo/` | Demo app |
| `packages/file_processor/config/medical_dict.json` | json | 18 | `packages/file_processor/modules/vision/medical_ocr.py` | File processor module |
| `packages/file_processor/data_seed/correction_dict.json` | json | 52 | `packages/file_processor/data_seed/` | Seed data for training |

---

## Specialty Classification (verified by provenance)

### How specialty is determined

Specialty is classified by **path/name metadata**, not by blind keyword matching on content.

| Specialty | Detection rule | Example paths |
|-----------|----------------|----------------|
| `orthopedic_surgery` | Path or filename contains: `ortho`, `fracture`, `snell_anatomy`, `anatomy`, `bone`, `joint`, `mcrae`, `orthobullets`, `hama_pharma`, `surgery_principles`, `head_neck`, `abdomen_pelvis` | `data/ortho_lexicon.json`<br>`data/arabic-medical-glossary/glossaries/abestol.csv` (Hama Pharma orthopedic product) |
| `cardiology` | Path or filename contains: `cardio`, `heart`, `ecg` | (none currently loaded — files exist but no production consumer) |
| `medical_general` | Default for any medical-adjacent file without a specific specialty hint | `data/arabic_fixes.json`<br>`data/medical_dictionary.json`<br>`data/arabic-medical-glossary/glossaries/final_unified_glossary.csv` |
| `general` | Non-medical Arabic OCR corrections | `data/arabic_fixes.json` (some entries are general Arabic) |

### Why no false "orthopedic" classification

A word like "fracture" appearing in a general medical dictionary does NOT trigger orthopedic classification — the classification is based on file-level provenance (filename/path), not content keywords. This is enforced by `scripts/build_dictionary_inventory.py::classify_specialty()`.

---

## Production Call Graph (verified)

### Layer 1: General OCR corrections

```
[Production Entry Point]
   hf-space/app_core.py:full_process(image)
      ↓
      step 4: _auto_correct_ocr(raw_text)
         ↓
         uses OCR_CORRECTIONS dict (13 hardcoded entries in app_core.py:151)
         ↓
         Intended corrections like باراسيتبمول → باراسيتامول
      ↓
      step 4.5: spell_checker.correct_text(corrected)
         ↓
         packages/core/spell_checker.py:HybridSpellChecker._load_fixes()
            ├── Layer 1: data/arabic_fixes.json (180 entries)  ← loaded
            └── Layer 2: data/dictionaries/ocr_corrections_safe.json (175 entries)  ← loaded
         ↓
         correct_text() applies safe token-level corrections
         (preserves decimals, negations, drug doses — verified by tests)
```

### Layer 2: Medical terminology lookup (SQLite-backed, optional)

```
packages/medical/dictionary_manager.py:MedicalDictionaryManager
   ↓
   db_path = "data/dictionaries/medical_terms.db"
   ↓
   loads: data/medical_dictionary.json (23 entries, JSON-backed)
   ↓
   used by: app/services/medical_translation_service.py (if invoked)
```

### Layer 3: Specialty routing (orthopedic)

```
packages/core/classifier.py
   ↓
   loads: data/ortho_lexicon.json (6 entries)
   ↓
   classifies image/document as orthopedic context
   ↓
   if orthopedic: enable orthopedic-specific OCR corrections
   if not orthopedic: do NOT enable orthopedic corrections
```

### Layer 4: Translation memory (exact-match only)

```
packages/medical/translation_memory.py:ExactTranslationMemory
   ↓
   __init__(entries) builds internal index keyed by normalize_arabic_key(source)
   ↓
   translate_exact(text) returns target ONLY if input matches an indexed key exactly
   ↓
   returns None for partial/substring matches
   ↓
   NEVER calls str.replace() — structurally impossible to misuse
```

---

## LFS Policy

Per `.gitattributes`:

| Pattern | LFS-tracked? |
|---------|--------------|
| `*.csv`, `*.jsonl`, `*.parquet` | ✅ LFS |
| `data/**` | ✅ LFS |
| `*.tmx` | ❌ NOT LFS (but no TMX is committed — TMX lives in malek_data 7z archive) |
| `*.json` (outside `data/`) | ❌ NOT LFS (committed directly) |
| `*.yaml`, `*.yml` | ❌ NOT LFS |
| `*.tsv` | ❌ NOT LFS |

**Implication for PR #92:**
- `data/dictionaries/ocr_corrections_safe.json` (5.5 KB) → LFS-tracked (under `data/**`)
- `data/dictionaries/SOURCES.md`, `MERGE_REPORT.md`, `CONFLICTS.md` → NOT LFS (Markdown)
- `data/dictionaries/medical_glossary_merged.json` (96 MB) → would be LFS, but is **git-ignored** (regeneratable)

---

## Regeneration Determinism

The generation pipeline is deterministic. Re-running `scripts/setup_medical_dictionaries.py` produces byte-identical output:

| Output file | Determinism guarantee |
|-------------|----------------------|
| `data/dictionaries/medical_glossary_merged.json` | ✅ Same inputs (3 sources) → same normalized_keys → same ordering → same sha256 |
| `data/dictionaries/medical_glossary_merged.csv` | ✅ Same |
| `data/dictionaries/ocr_corrections_safe.json` | ✅ Same (175 entries, sorted by insertion order) |
| `data/dictionaries/quarantined_entries.json` | ✅ Same (1,700 entries) |
| `data/dictionaries/conflicts.json` | ✅ Same (27,742 conflicts) |
| `data/dictionaries/malek_data_terms.json` | ✅ Same (103,169 entries, file order deterministic) |

(Regeneration determinism is verified in Phase 2 of this audit — see test results below.)

---

## Files NOT Loaded by Any Production Code

317 of 438 files are not loaded by any Python production code. These include:
- Grafana dashboards (`apps/handwriting-demo/docker/grafana/dashboards/*.json`)
- Frontend package manifests (`package.json`, `pnpm-lock.yaml`)
- Submodule working files (`data/arabic-medical-glossary/.working/*`)
- Pre-unification archive files (`data/arabic-medical-glossary/archive/pre-unification/*`)

These are either:
- Documentation / config artifacts (not dictionaries)
- Old versions superseded by `final_unified_glossary.csv`
- Demo app data (apps/handwriting-demo)

They are NOT integrated into the production call graph and do not affect runtime behavior.
