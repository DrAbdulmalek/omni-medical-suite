# PII_AUDIT.md — Personal Information Audit

> **Generated:** 2026-08-26
> **Repository:** `DrAbdulmalek/omni-medical-suite` @ commit (post-fix)
> **Branch:** `feat/integrate-malek-medical-dictionaries` (PR #92)

## Executive Summary

**No personal PII from `malek_data` enters the production runtime dictionaries.**

The user's personal email (`abdulmalek.husseini@gmail.com`) appears ONLY in:
- `malek_data/New Folder/66e1ddea77492b20-Personal TM (abdulmalek.husseini@gmail.com).tmx` (filename only, 0 entries extracted)
- `malek_data/New Folder/*.docx` files (10 personal Q&A notes, NOT parsed by the loader)

Neither of these is integrated into `omni-medical-suite`. The TMX file yields 0 en↔ar pairs (verified during extraction). The `.docx` files are not parsed by any production code.

## Audit Methodology

For each dictionary file, the audit checks:
1. **Personal email providers**: `@gmail.com`, `@outlook.com`, `@hotmail.com`, `@yahoo.com` (definitive personal PII)
2. **Personal name fragments**: `abdulmalek.husseini`, `abdulmalek husseini`, `abdulmalek.husseini@gmail.com`
3. **Institutional emails**: any email pattern (informational — not PII if it appears in a translated sentence like "contact us at info@hospital.edu")
4. **Phone-like patterns**: numbers with `+` prefix and 10+ digits (potential PII, but Syrian pharmaceutical company switchboards in translated sentences are not PII)

## Per-File Audit Results

| File | Entries | Personal PII | Personal Email Providers | Institutional Emails | Phone-like |
|------|---------|--------------|------------------------|----------------------|------------|
| `data/arabic_fixes.json` | 180 | 0 | 0 | 0 | 0 |
| `data/dictionaries/ocr_corrections_safe.json` | 168 | 0 | 0 | 0 | 0 |
| `data/medical_dictionary.json` | 23 | 0 | 0 | 0 | 0 |
| `data/ortho_lexicon.json` | 6 | 0 | 0 | 0 | 0 |
| `data/translation_rules.json` | 0 | 0 | 0 | 0 | 0 |
| `data/dictionaries/malek_data_terms.json` | 86,523 | 0 | 0 | 1 (`psponse@jhmi.edu`) | 0 |
| `data/dictionaries/medical_glossary_merged.json` | 158,301 | 0 | 0 | 1 (same as above) | 1 (`+963 33 8673941`) |
| `data/dictionaries/quarantined_entries.json` | 1,596 | 0 | 0 | 0 | 0 |

## Key Findings

### 1. Production-loaded files: 100% PII-free

The 5 files actually loaded by production Python code (per `DICTIONARY_INVENTORY.md`):
- `data/arabic_fixes.json` ✅
- `data/dictionaries/ocr_corrections_safe.json` ✅
- `data/medical_dictionary.json` ✅
- `data/ortho_lexicon.json` ✅
- `data/translation_rules.json` ✅

All 5 files contain **0 personal PII**, **0 personal email providers**, and **0 institutional emails**.

### 2. The single institutional email in malek_data

`psponse@jhmi.edu` appears in one entry of `malek_data_terms.json`:

```
en: "Please feel free to send us an e-mail at psponse@jhmi.edu."
ar: "رجاء لا تتردد في إرسال بريد إلكتروني إلينا على psponse@jhmi.edu."
```

This is a translated sentence from a Johns Hopkins Medical Institutions educational document. It is NOT personal PII — it is institutional contact information that appears in a parallel corpus. The email is `psponse@jhmi.edu` (likely "response@jhmi.edu" with a typo), which is a public institutional contact.

### 3. The phone-like number

`+963 33 8673941` appears in one entry from `arabic_medical_glossary:comprehensive_glossary`:

```
key: "Tel.: +963 33 8673941 Fax: +963 33 8673943"
value: "هاتف: +٩٦٣ ٣٣ ٨٦٧٣٩٤١ فاكس: +٩٦٣ ٣٣ ٨٦٧٣٩٤٣"
```

This is a Syrian pharmaceutical company's switchboard number in a parallel corpus sentence. It is NOT personal PII — it is publicly-listed corporate contact information.

### 4. Quarantined entries: 1,596 entries filtered

The firewall quarantined 1,596 entries (down from 1,700 in v1 after the firewall was tightened in this commit to also catch critical drug names). None of these reach `ocr_corrections_safe.json`.

## PII Patterns NOT Found

The audit explicitly searched for and did NOT find:
- `abdulmalek.husseini` (user's name) — 0 hits in any file
- `abdulmalek.husseini@gmail.com` (user's email) — 0 hits in any file
- `abdulmalek` (name fragment) — 0 hits in any file
- `husseini` (name fragment) — 0 hits in any file
- Any `@gmail.com`, `@outlook.com`, `@hotmail.com`, `@yahoo.com` pattern — 0 hits in any file

## Files NOT Audited (intentionally excluded)

- `malek_data/New Folder/*.docx` — 10 personal Q&A notes about TMX-building. These are NOT parsed by the loader and contain author email (PII). They are excluded by design.
- `malek_data/New Folder/66e1ddea77492b20-Personal TM (abdulmalek.husseini@gmail.com).tmx` — filename contains personal email but the file itself yields 0 en↔ar pairs (verified during extraction).
- `apps/handwriting-demo/` and other non-medical-OCR apps — separate codebases, out of scope for this PR.

## Conclusion

The malek_data integration is **PII-safe**. The user's personal information does not enter the production runtime. The medical safety firewall (in `packages/medical/medical_dictionary_loader.py`) and the layered loading design (in `packages/core/spell_checker.py`) together guarantee that:

1. The 5 production-loaded dictionary files contain 0 personal PII.
2. The 158,301-entry merged glossary (research artifact, git-ignored, NOT loaded at runtime) contains 0 personal PII.
3. The 86,523-entry malek_data extraction contains 1 institutional email in a translated sentence (acceptable — not PII).
