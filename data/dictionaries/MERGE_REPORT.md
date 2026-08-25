# MERGE_REPORT.md — Dictionary Merge Statistics

Generated: 2026-08-25 23:48:43 UTC

## Top-level Numbers

| Metric | Value |
|--------|-------|
| Total entries loaded | 228,105 |
| Safe after firewall | 226,405 |
| Quarantined (medical safety) | 1,700 |
| After dedup + conflict resolution | 159,554 |
| Conflicts detected | 27,742 |

## Sources Used

| Source | Entries Loaded | Status |
|--------|-----------------|--------|
| `production_arabic_fixes` | 180 | loaded |
| `arabic_medical_glossary` | 124,756 | loaded |
| `malek_data_tmx` | 103,169 | loaded |

## Distribution by Source (after dedup)

| Source | Count | % |
|--------|-------|---|
| `arabic_medical_glossary` | 84,398 | 52.9% |
| `malek_data` | 74,988 | 47.0% |
| `production_arabic_fixes` | 168 | 0.1% |

## Distribution by Category

| Category | Count |
|----------|-------|
| `glossary_term` | 78,337 |
| `translation_memory` | 74,988 |
| `glossary_phrase` | 5,518 |
| `ocr_correction` | 168 |
| `glossary_dosage` | 166 |
| `glossary_product` | 136 |
| `glossary_sentence` | 134 |
| `glossary_active_ingredient` | 51 |
| `glossary_therapeutic_category` | 30 |
| `glossary_dosage_form` | 13 |
| `glossary_clinical_term` | 7 |
| `glossary_medical_term` | 6 |

## Distribution by Confidence

| Confidence | Count |
|-----------|-------|
| `medium` | 148,412 |
| `high` | 11,003 |
| `very_high` | 139 |

## Quarantine Breakdown

| Reason | Count | Example |
|--------|-------|---------|
| `quarantined:decimal_dose` | 810 | `'**VITOREX (Pizotifen 0.5 mg) (Capsules)**'` |
| `quarantined:concentration_percent` | 436 | `'**Bioavailability: 87%**'` |
| `quarantined:arabic_indic_digits` | 276 | `':  A carton box contains  ٠٣chewable tablets.'` |
| `quarantined:drug_dose_unit` | 107 | `'PRICKSAGE (Agomelatine 25mg) (Film-Coated Tablets)'` |
| `quarantined:too_short` | 44 | `'I'` |
| `quarantined:numeric_only` | 16 | `'1'` |
| `quarantined:negation:^\s*لا\b` | 10 | `'لا'` |
| `quarantined:negation:^\s*لم\b` | 1 | `'لم يظهر فحص القناة الشرجية أي شيء شاذ'` |

## Medical Safety Test Cases (all must pass)

These cases from the user prompt are guaranteed by the firewall:

```
0.5                  → quarantined (decimal_dose)
1.25                 → quarantined (decimal_dose)
2.5                  → quarantined (decimal_dose)
0.75                 → quarantined (decimal_dose)
٠٫٥                  → quarantined (arabic_indic_digits)
١٫٢٥                 → quarantined (arabic_indic_digits)
جرعة 0.75 مل          → quarantined (drug_dose_unit)
ترامادول 0.5 mg       → quarantined (drug_dose_unit)
لا يعطى ترامادول      → quarantined (negation)
لا يوجد سكري          → quarantined (negation)
ليس لديه حساسية        → quarantined (negation)
لا يعطى ترامادول 0.5 mg → quarantined (multiple)
باراسيتبمول 500 mg     → quarantined (drug_dose_unit)
```

> These keys never enter the production dictionary, so the HybridSpellChecker
> cannot silently mutate them. The runtime tests in
> `tests/test_medical_safety_firewall.py` verify this contract end-to-end.
