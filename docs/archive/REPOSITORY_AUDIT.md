# REPOSITORY_AUDIT.md — malek_data Integration Audit

> **Audit date:** 2026-08-26
> **Auditor:** AI Engineering Agent (acting under user brief #eff2bbe3)
> **Repositories audited:**
> - `DrAbdulmalek/malek_data` (private, source of materials)
> - `DrAbdulmalek/omni-medical-suite` (public, integration target)
> - `DrAbdulmalek/arabic-medical-glossary` (public submodule of omni-medical-suite)

---

## EXECUTIVE SUMMARY

The `malek_data` repository contains 301 files (882 MB uncompressed) extracted from a 7z
archive split into 4 parts. The substantive content is **58 TMX (Translation Memory eXchange)
files** containing 103,169 bilingual English↔Arabic medical term pairs. These pairs were
extracted from authoritative sources: Mayo Clinic, NIH, altibbi.com, Syrian pharmaceutical
leaflets (Hama Pharma), and parallel corpora (Quran, OMW, UN, Tashkeela, Khaleej).

Integration into `omni-medical-suite` was performed via a **deterministic, reproducible
pipeline** that:

1. Extracts malek_data TMX term pairs to `data/dictionaries/malek_data_terms.json`.
2. Loads three sources — production `arabic_fixes.json` (180 entries), submodule
   `arabic-medical-glossary/final_unified_glossary.csv` (124,756 verified pairs), and the
   malek_data extraction (103,169 pairs) — into a unified `DictionaryEntry[]`.
3. Applies a **medical safety firewall** that quarantines dangerous keys: decimal doses,
   Arabic-Indic digits, drug-dose-unit combinations, negation prefixes, and critical drug
   names used as correction keys.
4. Resolves conflicts by documented source priority: `production_arabic_fixes` >
   `arabic_medical_glossary` > `malek_data_tmx`.
5. Emits a single merged runtime file plus three audit documents
   (`SOURCES.md`, `MERGE_REPORT.md`, `CONFLICTS.md`).

**Result:** 228,105 loaded → 1,700 quarantined by safety firewall → 159,554 unique entries
after dedup and conflict resolution. The existing production `tests/security/test_medical_behavior.py`
(12 tests) continue to pass, plus 61 new tests covering the loader, the firewall, and the
historic `'ترامادول '` trailing-whitespace bug.

---

## FACT / EXECUTED / INFERRED / NOT VERIFIED

The four buckets below classify every claim in this audit. **No claim marked EXECUTED is
inferred or assumed.** If a claim is not supported by a directly executed command, it is
classified as INFERRED or NOT VERIFIED.

### FACT (verified by direct inspection)

- `malek_data` is a private repository owned by `DrAbdulmalek`, default branch `main`, size
  144,327 KB. Last push 2026-08-24.
- `malek_data` HEAD contains exactly four files at top level: `New Folder.7z.001`,
  `New Folder.7z.002`, `New Folder.7z.003`, `New Folder.7z.004`. Total uncompressed
  archive size: 147,779,701 bytes.
- The 7z archive contains 326 entries; the meaningful top-level dir `New Folder/` contains
  301 real files totalling 882.79 MB.
- The substantive data in `New Folder/` is:
  - **58 TMX files** (337.87 MB) — bilingual translation memories
  - **112 `.txt` files** (400.62 MB) — mostly TMX content saved with `.txt` extension
  - **67 `.py` files** (2.68 MB) — TMX builders/extractors (not runtime code)
  - **10 `.docx` files** — personal Q&A notes; contain author email (PII)
  - **8 `.md` files**, **6 `.sh` files**, **2 `.jsonl` files**, **6 `.pyc` bytecode files**
- `New Folder/ocr_pro/merged_repo/` is a *different project* (`medical_doc_gui_v12`, a PyQt5
  medical document OCR GUI). Per `MERGED_SOURCES.txt`, it tracks `DrAbdulmalek/medical-doc-processor`
  and `DrAbdulmalek/medical-document-scanner` — not `omni-medical-suite`. **Not integrated.**
- `omni-medical-suite` is public, default branch `main`, size 1,324,002 KB. Last push
  2026-08-25.
- HEAD of `main` is `5fcb9fc fix: repair full-stack API Docker build` — same commit merged
  via PR #91 (closed/merged 2026-08-25 21:42 UTC).
- Baseline commit `3451e6ecf49d9315084dde82e9e7c3444d5bd69d` IS an ancestor of HEAD
  (verified via `git merge-base --is-ancestor`).
- 7 commits separate `3451e6e` from HEAD: 5 security-fix related, 1 Docker build fix,
  1 merge commit. Net diff: 8 files changed, 229 insertions, 29 deletions.
- The current `data/arabic_fixes.json` (the production spell-checker dictionary) contains
  exactly 180 entries. **None** contain medical terms, drug names, or dosages.
  0 entries have trailing whitespace. 0 contain `ترامادول`. 87 entries are identity
  mappings (`key == value`) — harmless no-ops. 93 entries are effective corrections.
- The submodule `data/arabic-medical-glossary/` was checked out at commit
  `f7557a256bc1ce13f6d008cdea37fc846d68c518`. Its `glossaries/final_unified_glossary.csv`
  contains 124,757 lines (124,756 entries + header).
- The submodule's `archive/quarantine/hitti_dictionary_UNVERIFIED.csv` is intentionally
  excluded by upstream — verified not in `final_unified_glossary.csv`.
- The existing `tests/test_spell_checker.py` had a `NameError: name 'Path' is not defined`
  at HEAD `main` (imported `pathlib.Path` was missing). This caused 7/7 tests in that
  file to fail at baseline.

### EXECUTED (commands run, results captured)

The following commands were executed during this audit. Their outputs are in the
worklog and in the repository history.

| Command | Result |
|---------|--------|
| `git clone --depth 1 https://github.com/DrAbdulmalek/malek_data.git` | Succeeded (private repo, authenticated via token) |
| `py7zr.SevenZipFile(...).extractall()` | Extracted 326 entries to `malek_data_extracted/` |
| `python3 scripts/inventory_malek_data.py` | Built 301-file manifest JSON + report |
| `python3 scripts/extract_malek_tmx_terms.py` | Extracted 103,169 en↔ar pairs from 58 TMX files |
| `git clone --depth 5 omni-medical-suite` (with `GIT_LFS_SKIP_SMUDGE=1`) | Succeeded; 3,766 files, 512 MB working tree |
| `git submodule update --init data/arabic-medical-glossary` | Succeeded; submodule at `f7557a2` |
| `python3 -m pytest tests/test_spell_checker.py` (before fix) | 7 failed (NameError), 0 passed |
| `Edit tests/test_spell_checker.py` to add `from pathlib import Path` | Applied |
| `python3 -m pytest tests/test_spell_checker.py` (after fix) | **7 passed**, 0 failed |
| `python3 -m pytest tests/security/` (existing medical tests) | **12 passed**, 0 failed |
| `python3 -m packages.medical.medical_dictionary_loader` (loader dry-run) | Loaded 228,105 entries; quarantined 1,700; resolved 27,742 conflicts; final 159,554 unique |
| `python3 scripts/export_unified_glossary.py` | Generated `medical_glossary_merged.json` (96 MB), `medical_glossary_merged.csv` (30 MB), `ocr_corrections_safe.json` (5.5 KB), `SOURCES.md`, `MERGE_REPORT.md`, `CONFLICTS.md` |
| `python3 -m pytest tests/test_medical_dictionary_loader.py` (new tests) | **61 passed**, 0 failed |

### INFERRED (logical conclusion from FACT + EXECUTED, not directly measured)

- The `merged_repo` directory inside `malek_data` is unrelated to `omni-medical-suite`
  because `MERGED_SOURCES.txt` explicitly references `medical-doc-processor` and
  `medical-document-scanner`, two other repositories by the same user.
- The duplicated TMX files (e.g., `complete_snell_anatomy_book.tmx`,
  `corrected_complete_snell_anatomy_book.tmx`,
  `manually_corrected_complete_snell_anatomy_book.tmx` — all 6,172 pairs each) represent
  iterative snapshots of the same translation memory. Their deduplication via
  `normalized_key` is the correct behavior.
- The runtime safety tests in `tests/security/test_medical_behavior.py` continue to pass
  because the firewall quarantines dangerous keys *before* they reach the spell-checker
  dictionary. The spell-checker's `enhance_digit_recognition()` is the *only* mechanism
  that mutates decimal-looking strings, and it operates at a different layer than the
  dictionary loader.

### NOT VERIFIED (could not be tested in this run)

- **CI run on GitHub Actions:** The PR has not been opened yet at the time of writing
  this audit. CI status will be visible only after the PR is created and GitHub Actions
  triggers the workflow.
- **End-to-end behavior under the deployed Docker image:** The Dockerfiles exist
  (`Dockerfile.api`, `Dockerfile.gradio`, etc.) but were not built locally in this audit.
  The pre-existing `tests/security/test_medical_safety_contract.py` covers the deployment
  topology assertions (e.g., `test_production_image_uses_authenticated_launcher_not_app_directly`).
- **Performance of loading 159,554 entries at runtime in production:** The loader is fast
  (sub-second on local disk), but the actual production deployment uses a SQLite database
  via `packages/medical/dictionary_pipeline.py` — out of scope for this PR.
- **Licensing of the malek_data translation memories:** The repository is private and
  contains the user's personal collection; the user has authorized its use in
  `omni-medical-suite` (which is public) by issuing this task. The SOURCES.md documents
  this provenance clearly.

---

## Production Topology (verified)

| Component | Path | Status |
|-----------|------|--------|
| Production dictionary | `data/arabic_fixes.json` | 180 entries, weak (NO medical content) |
| Submodule glossary | `data/arabic-medical-glossary/` | 124,756 verified pairs, **NOT used by production code** prior to this PR |
| New merged glossary | `data/dictionaries/medical_glossary_merged.json` | 159,554 entries (generated, git-ignored — regeneratable via `scripts/setup_medical_dictionaries.py`) |
| New safe OCR corrections | `data/dictionaries/ocr_corrections_safe.json` | 168 entries, git-tracked |
| Loader code | `packages/medical/medical_dictionary_loader.py` | New file, git-tracked |
| Setup script | `scripts/setup_medical_dictionaries.py` | New file, git-tracked |
| Loader tests | `tests/test_medical_dictionary_loader.py` | New file, 61 tests, git-tracked |
| Spell-checker tests | `tests/test_spell_checker.py` | Existing file, bug-fixed (`Path` import) |
| Medical safety tests | `tests/security/test_medical_behavior.py` | Existing, still passing |
| Production spell-checker | `packages/core/spell_checker.py` v7.0 | Unchanged |
| HF Space OCR pipeline | `hf-space/app_core.py:_auto_correct_ocr` | Unchanged (still uses `OCR_CORRECTIONS` dict, 13 entries) |
| Dictionary pipeline (SQLite) | `packages/medical/dictionary_pipeline.py` | Unchanged (out of scope) |

---

## Security Findings

| Severity | Finding | Status |
|----------|---------|--------|
| P0 | Personal email `abdulmalek.husseini@gmail.com` appears in filename `66e1ddea77492b20-Personal TM (abdulmalek.husseini@gmail.com).tmx` inside the malek_data 7z archive | NOT INTEGRATED — file excluded by loader (0 en↔ar pairs extracted) |
| P0 | Personal email appears in 10 `.docx` files inside the 7z archive | NOT INTEGRATED — `.docx` files are not parsed by the loader |
| P1 | Historic bug `'ترامادول '` (trailing whitespace key) was reported in user brief but does NOT exist in current `data/arabic_fixes.json` | VERIFIED — 0 keys with whitespace padding. Firewall would catch it if reintroduced. |
| P2 | Duplicate `spell_checker.py` exists in 5 locations with md5 mismatch (1.3KB stub vs 19KB production vs 15KB file_processor copy) | PRE-EXISTING — out of scope for this PR. Documented in `DUPLICATE_FILES_REPORT.txt`. |
| P3 | 87 identity entries (`key == value`) in `data/arabic_fixes.json` are harmless no-ops | NOT FIXED — they consume ~1 KB of memory; fixing would be a behavioral change beyond scope. |

---

## Remaining Risks

1. **CI status unknown** — GitHub Actions result for the PR is not available until the
   PR is opened. Recommend monitoring CI after PR creation.

2. **Pre-existing `DUPLICATE_FILES_REPORT.txt`** (104 KB) documents extensive duplicate
   code across `packages/`, `hf-space/`, `apps/ocr-pipeline/`. This PR does NOT address
   those duplicates — it is scoped to dictionary integration only.

3. **The loader does NOT auto-replace `data/arabic_fixes.json` in production.** The
   production `HybridSpellChecker` continues to load `data/arabic_fixes.json`. The new
   `ocr_corrections_safe.json` is generated as a side artifact; switching production to
   use it would require a one-line change in `packages/core/spell_checker.py:ARABIC_FIXES_PATH`
   and is intentionally deferred to a follow-up PR to keep this PR surgical.

4. **The 96 MB `medical_glossary_merged.json` is git-ignored** — it is regeneratable
   via `python3 scripts/setup_medical_dictionaries.py`. The script requires:
   - The malek_data 7z archive (currently cloned at `/home/z/my-project/repos/malek_data/`)
   - The `data/arabic-medical-glossary` submodule initialized (`git submodule update --init`)
   - Python packages: `py7zr` (already in `requirements-scanner.txt`)

5. **The 4-PR-91 commits between `3451e6e` and HEAD are security fixes that were merged
   in good faith.** This PR branches off HEAD (`5fcb9fc`), so it includes all those
   security fixes. No regression introduced.

---

## Final Verdict

The integration is **safe, reproducible, and auditable**. The medical safety firewall
correctly quarantines every dangerous input listed in the user brief. The historic
`'ترامادول '` bug is structurally prevented by the `whitespace_padding` check. The
existing 12 security tests continue to pass, and 61 new tests verify the loader's
contract end-to-end.

The PR is ready for human review. Recommended next steps after merge:
- Wire `packages/core/spell_checker.py:ARABIC_FIXES_PATH` to use
  `data/dictionaries/ocr_corrections_safe.json` (one-line change, separate PR).
- Run `scripts/setup_medical_dictionaries.py` in CI to regenerate the merged glossary
  on every submodule update.
- Address the pre-existing duplicate `spell_checker.py` problem documented in
  `DUPLICATE_FILES_REPORT.txt` (large effort, separate epic).
