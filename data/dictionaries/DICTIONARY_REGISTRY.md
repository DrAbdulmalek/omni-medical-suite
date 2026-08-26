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

## Specialty inheritance

- `general`: general OCR/technical resources + translation rules.
- `general_medical`: `general` + general medical terminology + medical TMX.
- `orthopedic_surgery`: `general` + `general_medical` + orthopedic terminology.

This inheritance prevents an orthopedic document from losing general medical terms while still adding the orthopedic lexicon.

## Explicit exclusions

`learning_database.json`, `medical_doc_training.jsonl`, and `ground_truth_588.txt` are corpora/evaluation resources, not dictionaries. They must not enter runtime correction or translation replacement.

## Safety contract

1. OCR maps are exact-token corrections only.
2. Terminology dictionaries are exact lookup/protection resources.
3. TMX is exact whole-segment lookup only.
4. Translation rules are applied only by a dedicated translation-rule engine that understands their structure.
5. Numeric values, dosage/concentration expressions, and negated clinical statements remain protected.
6. Provenance is retained for dictionary and TMX results.
