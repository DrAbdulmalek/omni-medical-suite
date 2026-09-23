# Xberg Integration Report — `packages/omni_extraction`

> Branch: `feat/xberg-olmocr-integration` (from `main` @ `39640a6dbba7`)
> Status: **PUSHED — PR opened in the same operation as this push** (see the
> repo's pull-request list for the live PR number; this file deliberately
> avoids hard-coding a number that could drift).
> Rebuild lineage: original implementation (`b069072..fb616cc`) was LOST in
> environment reset #10 before push; this branch is a clean-room rebuild
> performed from worklog records and live-probed engine surfaces.

## 1. Scope and isolation

`packages/omni_extraction` wraps the pinned xberg document-extraction engine
without ever adding it to the suite's main dependency set. The engine is
installed only inside a dedicated virtual environment via the package's
`requirements.txt` (`xberg==1.2.6`). This mirrors the isolation discipline
applied to OLMoCR (R19) and keeps the suite runtime untouched: nothing
outside this package imports it, and removal of the directory restores the
previous behaviour bit-for-bit.

Two execution paths are provided. The **library path** performs an
in-process `ExtractInput` → `extract` → `ExtractedDocument` conversion. The
**CLI path** calls the `xberg-cli` binary and records the binary's SHA-256
for integrity citation, per the XB-02 binary-integrity ruling. Both paths
return the same `ExtractionResult` shape with a mandatory
`ProvenanceRecord`.

## 2. Pins and license posture (PyPI-verified 2026-09-23)

| Item | Value | Note |
|---|---|---|
| `xberg` | `==1.2.6` | MIT; upstream HEAD `588401cec14e`; PyPI also lists 1.2.7 but the record pins 1.2.6 |
| Bundled `libheif` | 1.23.0 | **LGPL** — ships inside the Python wheel (nuance OQ-11) |
| Bundled `libonnxruntime` | present | redistributable; recorded for completeness |
| Network posture | core offline; ML download defaults `allow_network=true` | mirrored explicitly by the wrapper |

The LGPL bundling nuance deserves emphasis: installing the wheel distributes
LGPL-covered libraries inside a MIT-licensed engine artifact. This is a
license-compliance consideration, not a blocker, and it was already recorded
in the XB-02 forensic audit. Any redistribution of the wheel must respect
LGPL terms (dynamic-linking provisions).

## 3. Truth level — SMOKE_TESTED (wrapper-level, real engine)

Truth levels are **never merged** (IMPORTABLE / CONTRACT_TESTED /
SMOKE_TESTED / REAL_MODEL_EXECUTED are distinct claims). The evidence below
supports the first three levels for this package; nothing here claims model-
level OCR execution.

- **IMPORTABLE**: package imports cleanly in the main runtime with the
  engine ABSENT; engine import proven inside the isolated venv only.
- **CONTRACT_TESTED**: `tests/test_omni_extraction.py` — 15 tests, local
  run evidence: `33 passed in 1.76s` across the three new test files
  (Python 3.12.14, pytest 9.0.2, CPU-only, no network).
- **SMOKE_TESTED**: wrapper-level offline run against the real engine
  (`scripts/smoke_omni_extraction.py`, synthetic no-PHI input,
  `HF_HUB_OFFLINE=1`):
  - engine reported version `1.2.6`; `extraction_method=native`
  - text matched the synthetic source; `table_count==1`; quality `1.0`
  - provenance complete: `input_sha256` recorded, `duration_ms=4.7`,
    `offline_env=true`, `allow_network=false`
  - result: **9/9 checks passed**
- **REAL_MODEL_EXECUTED**: NOT EXECUTED for ML-backed extraction paths
  (no GPU model runs in this environment; the native path exercised above
  is engine-internal parsing, not an ML model).

## 4. Fail-closed semantics

Engine absence raises `ExtractionError` — never a silent empty result. This
is deliberate: a silent empty result would be indistinguishable from a
genuinely empty document, which is unacceptable in a medical pipeline. The
contract tests prove loudness on both paths (library import failure and CLI
binary absence), and that offline posture never leaks `HF_HUB_OFFLINE`
mutations into the caller's environment.

## 5. Fallback semantics (the five rules)

1. **Disabled + unavailable → explicit failure.** A caller who requests an
   engine that is not available gets a loud error, not a silent skip.
2. **Enabled chain → fallback + provenance.** When a caller opts into a
   fallback chain, each attempt is recorded (`attempts` trail on
   `OCRResult`) and the winner is identified (`fallback_used`,
   `provenance.winning_engine`).
3. **Loose `except` → review FAIL.** Broad exception swallowing that hides
   engine identity or converts crashes into empty results fails review;
   every caught exception must be attributed to a named engine in the trail.
4. **First-engine win → `fallback_used=False`.** Fallback Used is reserved
   for cases where a non-first engine produced the winning result.
5. **Total failure → trail kept, `fallback_used=False`.** When every engine
   fails, the result records the full attempt trail and a null winner;
   claiming "fallback used" would be false advertising.

## 6. Rollback

Delete `packages/omni_extraction/` and the isolated venv. Nothing else in
the suite references the package. `git revert 9641230 cb4da5c` (or delete
the branch) restores the pre-integration tree.
