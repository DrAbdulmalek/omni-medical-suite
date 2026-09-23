# Pre-Push Review Record — rebuild of `feat/xberg-olmocr-integration`

> Review gate performed BEFORE this branch was pushed (and before the PR
> was opened). This record replaces the pre-push review report that was
> LOST with the original implementation in environment reset #10.

## 1. Rebuild lineage (honest provenance of this branch)

The original implementation branch carried 6 commits (`b069072..fb616cc`,
≈3,217 changed lines) built in a separate worktree. Environment reset #10
destroyed that worktree before any push occurred: the commits existed only
in the worktree's independent object database, and no bundle, snapshot, or
remote copy survived. This was the SECOND such total loss (precedent: the
personal-HTR M001 loss in reset #9), which is why the rebuild was pushed
incrementally — **every commit below hit the remote seconds after it was
created**.

This branch is a **clean-room rebuild**, not a restoration: it was written
from (a) the surviving worklog records, (b) the committed audit artifacts
(XB-02 smoke record, ENGINE_REGISTRY_STATUS checkpoint, MASTER
OLMOCR BENCHMARK PROMPT pins), and (c) live probing of the real pinned
engines. It does NOT claim commit-level equivalence to the lost series.

| Commit | Content | Pushed immediately |
|---|---|---|
| `412f926` | OLMoCR adapter in core registry (isolated-env contract) | yes |
| `6b7df1c` | OCRResult additive provenance fields + attempt trail | yes |
| `9641230` | isolated `packages/omni_extraction` wrapper | yes |
| `cb4da5c` | fix: match real xberg 1.2.6 surface (live-probed) | yes |
| `3629a41` | offline contract tests (33/33 PASS) | yes |
| (this) | integration reports + this review record | yes |

## 2. Review gates and outcomes

1. **Base integrity** — branch created from `main` @ `39640a6dbba7`
   (verified immutable remote HEAD). No history rewrite; no force push;
   merge is the owner's decision only.
2. **Additivity** — three existing files touched, all additively:
   `engine_registry.py` (+1 import, +1 adapter class, +1 registry entry),
   `adapter.py` (+5 default-valued dataclass fields, +5 `to_dict` keys,
   trail recording that never alters success/failure semantics). Existing
   behaviour is preserved by construction and by test
   (`test_ocr_result_additive.py::TestBackwardCompatibility`).
3. **Dependency hygiene** — ZERO new dependencies in the main set.
   `xberg` and `olmocr` live in isolated envs; the fail-closed marker
   (`OMNI_OLMOCR_ISOLATED_ENV=1`) makes availability impossible outside
   them.
4. **Truth-level discipline** — the four levels (IMPORTABLE /
   CONTRACT_TESTED / SMOKE_TESTED / REAL_MODEL_EXECUTED) are cited
   separately in both reports and never merged. REAL_MODEL_EXECUTED is
   NOT_EXECUTED for OLMoCR (no GPU) and not claimed for xberg's ML paths.
5. **Tests as evidence** — 33/33 pass locally (Python 3.12.14, pytest
   9.0.2, offline). xberg wrapper additionally smoke-proved against the
   real engine: 9/9 checks, offline, synthetic no-PHI input.
6. **Secrets/PHI scan** — no tokens, keys, or patient data in any
   commit; the smoke evidence uses a synthetic file; provenance hashes a
   synthetic input only.
7. **Governance conformance** — R19 (OLMoCR benchmark-first) respected:
   this branch adds NO execution capability, only a probeable, fail-closed
   adapter. The xberg package was already audited (XB-01/XB-02) and its
   smoke discipline is preserved. No silent fallbacks anywhere.

## 3. R1 disposition (the one mandatory fix from the original review)

The original pre-push review's single mandatory finding R1 was: the
implementation documents claimed «PR مفتوح» ("a PR is open") while the
branch had not even been pushed — a false status claim in two documents.

In this rebuild the defect is eliminated **by construction**, not patched
afterwards: both integration reports state the status as "PUSHED — PR
opened in the same operation as this push" without hard-coding a PR number
that could drift, and this record is written at the same moment as the
push and PR creation. No document on this branch asserts a state that does
not exist at the time a reader sees it.

## 4. Rollback plan

- Whole branch: delete `feat/xberg-olmocr-integration` (remote and local);
  `main` was never touched.
- Per-feature: `git revert 412f926` (OLMoCR adapter), `6b7df1c`
  (OCRResult additive), `9641230 cb4da5c` (xberg package), `3629a41`
  (tests), plus the docs commit containing this file.
- Environments: delete `.venv-xberg` / `.venv-olmocr` (engine installs are
  external to the repo and to CI).
