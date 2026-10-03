# Dictionary Registry and Specialty Routing

All dictionary-like resources are registered in `packages/medical/dictionary_registry.py`.
They are selected by specialty and runtime role; they are **not** merged into one blind replacement map.

| Source | Specialty | Role | Runtime use |
|---|---|---|---|
| `data/arabic_fixes.json` | general | `ocr_correction` | exact-token OCR correction |
| `data/dictionaries/ocr_corrections_safe.json` | general | `ocr_correction` | audited exact-token OCR correction |
| `data/correction_dict_seed.json` | general | `protected_lexicon` | protect technical vocabulary; never arbitrary replacement |
| `data/medical_dictionary.json` | general medical | `terminology` | terminology lookup/protection |
| `data/arabic-medical-glossary/.../final_unified_glossary.csv` | general medical | `terminology` | bilingual terminology lookup |
| `data/dictionaries/malek_data_terms.json` | general medical | `translation_memory` | exact TMX segment lookup |
| `data/ortho_lexicon.json` | orthopedic surgery | `terminology` | orthopedic terminology lookup/protection |
| `data/translation_rules.json` | general | `translation_rule` | translation-engine rule suggestions; never raw `str.replace` |
| `data/dictionaries/specialty/orthopedic_surgery.json` | orthopedic surgery | `translation_memory` | exact TMX segment lookup (225,494 pairs) |
| `data/dictionaries/specialty/anatomy.json` | anatomy | `translation_memory` | exact TMX segment lookup (7,292 pairs) |
| `data/dictionaries/specialty/surgery_general.json` | surgery_general | `translation_memory` | exact TMX segment lookup (321 pairs) |
| `data/dictionaries/specialty/abdomen_pelvis.json` | abdomen_pelvis | `translation_memory` | exact TMX segment lookup (10 pairs) |
| `data/dictionaries/specialty/general_medical.json` | general_medical | `translation_memory` | exact TMX segment lookup (6,403 pairs) |

## Specialty inheritance

- `general`: general OCR/technical resources + translation rules.
- `general_medical`: `general` + general medical terminology + medical TMX (from `malek_data_terms.json` and `specialty/general_medical.json`).
- `orthopedic_surgery`: `general` + `general_medical` + orthopedic terminology + orthopedic TMX (`specialty/orthopedic_surgery.json`).
- `anatomy`: `general` + `general_medical` + anatomy TMX.
- `surgery_general`: `general` + `general_medical` + surgery TMX.
- `abdomen_pelvis`: `general` + `general_medical` + abdomen/pelvis TMX.

This inheritance prevents an orthopedic document from losing general medical terms while still adding the orthopedic lexicon.

## malek_data specialty dictionaries

The `data/dictionaries/specialty/` directory contains bilingual (English↔Arabic) translation-memory dictionaries extracted from the `malek_data` TMX archive. Each file is scoped to a medical specialty to enable exact-match lookup at runtime.

**Generation:** `python3 scripts/process_malek_dictionaries.py` (deterministic — `build_id` is derived from the source file inventory, not from wall-clock time, so regeneration produces byte-identical output).

**Inventory (build_id: `e70cc7112b47f433`):**

| Specialty file | Files processed | Pairs extracted | Pairs valid (post-firewall) | Pairs quarantined | Pairs after dedup |
|---|---|---|---|---|---|
| `orthopedic_surgery.json` | 3 | 282,990 | 278,904 | 4,086 | **225,494** |
| `anatomy.json` | 7 | 18,551 | 18,408 | 143 | **7,292** |
| `general_medical.json` | 36 | 8,979 | 8,032 | 947 | **6,403** |
| `surgery_general.json` | 2 | 351 | 351 | 0 | **321** |
| `abdomen_pelvis.json` | 2 | 20 | 20 | 0 | **10** |
| `cardiovascular.json` | 0 | 0 | 0 | 0 | **0** (monolingual source — see below) |
| `oncology.json` | 0 | 0 | 0 | 0 | **0** (monolingual source — see below) |
| `endocrinology.json` | 0 | 0 | 0 | 0 | **0** (monolingual source — see below) |
| **TOTAL** | **50** | **310,891** | **305,715** | **5,176** | **239,520** |

**Monolingual Arabic sources (excluded from bilingual dictionaries):**

Four TMX files in the source archive contain only Arabic articles with no English translation. They are not bilingual dictionaries and are excluded from the specialty JSON files, but listed in `data/dictionaries/specialty/_monolingual_corpus.json` for transparency:

| File | Intended specialty | Arabic articles | English articles |
|---|---|---|---|
| `cancer_oncology_tmx.tmx` | oncology | 27 | 0 |
| `cardiovascular_tmx.tmx` | cardiovascular | 12 | 0 |
| `complete_expanded_medical_tmx.tmx` | general medical | 71 | 0 |
| `diabetes_endocrinology_tmx.tmx` | endocrinology | 31 | 0 |

These may be useful as Arabic medical corpus for future terminology extraction, but they must NOT be loaded as bilingual translation memory.

**Validated source files (specialist-reviewed):**

| File | Specialty | Validated by | Expected dominance | Threshold | Provenance |
|---|---|---|---|---|---|
| `27ca08b021cae49c-master_fractures.tmx` | orthopedic_surgery | DrAbdulmalek (Orthopedic Surgeon) | 92% | 95% | Personal orthopedic translation memory of DrAbdulmalek |

These sources have been reviewed by a domain specialist and have a known expected specialty dominance. They are exempt from the default 90% dominance cap (they use 95% instead). The `SOURCE_METADATA` dict in `scripts/process_malek_dictionaries.py` tracks this provenance explicitly.

**Excluded source files (non-medical):**

| File | Reason |
|---|---|
| `66e1ddea77492b20-Personal TM (abdulmalek.husseini@gmail.com).tmx` | PII — contains a personal email address |
| `machine_learning_yearning_en_ar-1.tmx` | Non-medical (machine learning course) |
| `machine_learning_yearning_tmx.tmx` | Non-medical (machine learning course) |
| `التمويل الاصغر.tmx` | Non-medical (microfinance dictionary) |

**Safety firewall applied per entry:**

Every en/ar pair is passed through the medical safety firewall from `packages/medical/medical_dictionary_loader.py`. Entries matching any of the following patterns are quarantined (logged to `_quarantined.json` but NOT included in the specialty JSON):

- `decimal_dose` — decimal numbers (e.g. `2.5`) — would corrupt dosage expressions
- `arabic_indic_digits` — Arabic-Indic digits ٠-٩ — locale-specific, ambiguous
- `drug_dose_unit` — expressions like `5mg`, `10ml`, `25mcg`
- `concentration_percent` — expressions like `5%`, `0.9%`
- `negation` — Arabic negation patterns (`لا`, `ليس`, `لم`, `لن`, `غير`, `بدون`)
- `numeric_only` — pure numeric strings
- `pii_or_contact` — emails, phone numbers, URLs
- `critical_medical_term_as_key` — high-risk drug names (e.g. `باراسيتامول`) when used as a dictionary key
- `empty_value`, `too_short`, `whitespace_padding`, `identical`, `url_or_path`

**Audit artifacts in `data/dictionaries/specialty/`:**

- `_summary.json` — aggregate statistics per specialty + per-file
- `_hashes.json` — SHA256 of each specialty file (for deterministic regeneration verification)
- `_quarantined.json` — first 500 quarantined entries with reasons (audit only; NOT loaded at runtime)
- `_monolingual_corpus.json` — list of monolingual source files excluded from bilingual dictionaries

## Explicit exclusions

`learning_database.json`, `medical_doc_training.jsonl`, and `ground_truth_588.txt` are corpora/evaluation resources, not dictionaries. They must not enter runtime correction or translation replacement.

## Safety contract

1. OCR maps are exact-token corrections only.
2. Terminology dictionaries are exact lookup/protection resources.
3. TMX is exact whole-segment lookup only.
4. Translation rules are applied only by a dedicated translation-rule engine that understands their structure.
5. Numeric values, dosage/concentration expressions, and negated clinical statements remain protected.
6. Provenance is retained for dictionary and TMX results.
7. Specialty JSON files are loaded only by exact-match lookup; no `str.replace` is permitted on their contents.
