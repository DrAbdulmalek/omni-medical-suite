# AHW-02 IMPLEMENTATION REPORT — CONTROLLED ARABIC HANDWRITING / OCR CONSOLIDATION

> Scope: `DrAbdulmalek/omni-medical-suite` · branch-local work only.
> Inputs: AHW-01 REBUILD audit (LOST with environment reset #4 — sha256
> `29274608…c49eb49` preserved in session worklog; NOT re-fabricated)
> + owner-supplied portfolio study (PORTFOLIO_FORENSIC_REPORT, OCR_ASSET_INVENTORY,
> DUPLICATION_MAP, TARGET_ARCHITECTURE, MIGRATION_PLAN, EXECUTION_MASTER_PLAN,
> HTR_TRAINING_PLAN, SECURITY_PRIVACY_PLAN).
> Principle: REUSE > ADAPT > WRAP > EXTEND > MERGE > BUILD NEW — no OCR system was rebuilt.
> **Reconstruction disclosure:** environment reset #4 (2026-09-17) erased the local repo
> including the original AHW-02 commits. The implementation was rebuilt VERBATIM from
> session-recorded evidence (exact diffs and full file contents captured in-session);
> original commit SHAs are therefore unrecoverable and current SHAs differ. See §K.

---

## A. Identity

| Item | Value |
|---|---|
| Repository | `DrAbdulmalek/omni-medical-suite` (origin, HTTPS) |
| Base SHA (verified `git rev-parse HEAD` at start) | `39640a6dbba741eaf13e078dad64719e147ea79b` (= verified main HEAD, unchanged on remote throughout) |
| Branch | `feat/ahw-02-controlled-handwriting-ocr` (created at base SHA) |
| Commits on branch | see §K.1 Commit Manifest — authoritative counts/SHAs read from `git rev-list --count 39640a6d..HEAD`; **no push, no merge, no PR, no tag, main untouched** |
| Session dates | 2026-09-17 (UTC) |
| Python / pytest | 3.12.14 / 9.0.2 (identical across all evidence runs) |
| Environment | CPU-only 2 cores / 3.9 GiB; torch, transformers, paddleocr, easyocr, peft, nougat ABSENT; Tesseract 5.5.0 langs = eng, osd (no `ara`) |
| Authorization | `AUTHORIZE AHW-02` (branch + commit). PUSH/MERGE AUTHORIZATION = NOT GRANTED |

## B. Changes

| # | File | Sub-phase | Change | Claim |
|---|---|---|---|---|
| 1 | `packages/core/router_executor.py` (NEW) | B, C, F | `RouterExecutor` execution bridge: `EngineRouter.select()` → executable adapters → `OCRResult`. `ExecutableEngineAdapter` (extends existing `EngineAdapter` ABC). `HandwritingHTRAdapter` (wires existing `packages/vision/htr`). `OLMoCRAdapter` (strictly optional). `build_default_executor()` factory. | PROVEN |
| 2 | `app/advanced_review_app.py` | B | Tab 7 «تنفيذ OCR (يدوي)»: image + language + block_type + profile → `RouterExecutor.execute()`; renders result + full provenance JSON. Optional import (`EXECUTOR_AVAILABLE` guard); app builds and imports OK (smoke-tested live, twice — pre- and post-reset). | PROVEN |
| 3 | `packages/omni_ocr/adapter.py` | D | `OCRResult` extended backward-compatibly: ONE new optional field `provenance: Dict` (default empty), included in `to_dict()`. All existing fields/keys unchanged. | PROVEN |
| 4 | `packages/core/mistral_integration.py` | E3 | All three cloud clients now created ONLY if `MISTRAL_API_KEY` present **AND** `OMNI_ENABLE_CLOUD_OCR` ∈ {1,true,yes} (case-insensitive). Cloud disabled by default; explicit opt-in. | PROVEN |
| 5 | `packages/interactive-learning/learning/online_learner.py` | E1 | `torch.load(..., weights_only=True)`. | PROVEN |
| 6 | `packages/file_processor/interactive_learning/learning/online_learner.py` | E1 | Same fix. | PROVEN |
| 7 | `apps/handwriting-demo/training/continual_trainer.py` | E1 | Same fix (`EWCRegularizer.load`). | PROVEN |
| 8 | `.gitignore` | E2 | Weight/checkpoint patterns: `*.pt *.pth *.bin *.ckpt *.safetensors *.onnx`. | PROVEN |
| 9 | `tests/test_router_executor.py` (NEW) | G | 17 tests: selection→execution, real-router binding, NO SILENT FALLBACK, explicit-failure, provenance contract, factory. | PROVEN |
| 10 | `tests/test_handwriting_htr_adapter.py` (NEW) | G | 11 tests: adapter contract, no download at construction, explicit unavailability, mocked-inference success, LATIN-baseline flag pinned. | PROVEN |
| 11 | `tests/test_olmocr_adapter.py` (NEW) | G | 12 tests: optional dependency, `is_available()=False` without olmocr, NOT in any router profile, explicit failures, mocked success/failure. | PROVEN |
| 12 | `tests/test_ahw02_security_regressions.py` (NEW) | G | 26 tests: E1 AST regression (3 sites + safe reference + package sweep), E2 patterns, canonical-resolution guards (N1), E3 opt-in matrix. | PROVEN |
| 13 | `tests/security/test_medical_behavior.py` (1-line fix) | G | `sys.path.insert(0, hf-space)` → `append` — see B4 doc §6. Full analysis: `docs/portfolio/AHW-02_B4_DECISION.md`. | PROVEN |

Design decision (recorded): AHW-02D dimensions live in the `provenance` payload (one
additive field) instead of 12 new top-level fields; the MASTER-PLAN TASK-005 top-level
field set remains a planned backward-compatible extension (B8).

## C. Architecture (AHW-02A — canonical review, verified live)

### C.1 Dependency graph (target state, now real)

```
app/advanced_review_app.py  (caller — previously recommendation-STRING only)
   └─▶ packages/core/router_executor.py   (NEW — execution bridge)
         ├─▶ packages/core/engine_router.py      EngineRouter.select()   [contract UNCHANGED: (names, reasons)]
         │      └─▶ packages/core/engine_registry.py  EngineAdapter / EngineRegistry  [UNCHANGED]
         ├─▶ ExecutableEngineAdapter.run()
         │      ├─▶ HandwritingHTRAdapter ("TrOCR")
         │      │      └─▶ packages/vision/htr/arabic_htr.py  ArabicHandwrittenHTR  [EXISTING, now reachable]
         │      └─▶ OLMoCRAdapter ("OLMoCR") ─▶ optional `olmocr` package (absent ⇒ explicit skip)
         └─▶ packages/omni_ocr/adapter.py  OCRResult (+ optional provenance)
```

### C.2 Classification of the six reviewed paths (all six verified present, live)

| Path | Entries | Verdict |
|---|---|---|
| `packages/core/` | 35 | **CANONICAL** — registry, router, executor (new), E3-gated cloud integration |
| `hf-space/packages/core/` | 34 | **MIRROR duplicate** — registry/router/model_registry byte-identical (`cmp`); `mistral_integration` diverges by exactly the E3 patch; `router_executor` absent → B4 doc |
| `packages/file_processor/modules/core/` | 20 | **DIVERGENT duplicate** (own engine_router 240 vs 297 lines, TrOCR-only handwriting — AHW-01) |
| `src/ocr/` | 10 | **LEGACY / parallel engine set** — not wired to the canonical router |
| `packages/omni_ocr/` | 3 | **CANONICAL result contract** (`OCRResult`, `UnifiedOCR`) |
| `packages/handwriting/` | 31 | **LEGACY full-stack copy** — not the production path |

### C.3 SOURCE OF TRUTH declaration

| Concern | Source of truth |
|---|---|
| Result contract | `packages/omni_ocr/adapter.py` → `OCRResult` |
| Engine abstraction | `packages/core/engine_registry.py` → `EngineAdapter` / `EngineRegistry` |
| Engine selection | `packages/core/engine_router.py` → `EngineRouter` |
| Selection → execution bridge | `packages/core/router_executor.py` → `RouterExecutor` (NEW, single source) |
| Arabic HTR pipeline | `packages/vision/htr/` (`arabic_htr.py` + segmenters + `dotted_recovery` + `trocr_finetuned`) |
| Cloud OCR integration | `packages/core/mistral_integration.py` (E3-gated canonical copy) |

## D. Router before / after (AHW-02B)

**Before (AHW-01, PROVEN):** `select()` returned names only; the only production caller
formatted a recommendation string; **no engine was ever executed**.

**After (PROVEN — §K.6 chain evidence):**
- `select()` contract preserved exactly — legacy router tests **11 passed** (verbatim
  baseline parity, re-run post-reconstruction).
- `RouterExecutor.execute()` attempts ONLY the router's selected engines in router
  order; skips/failures recorded in `provenance["attempts"]`; `fallback_used=True` only
  for executed-then-rescued chains; otherwise explicit-error `OCRResult`; no engine
  outside the selection is ever conjured; no cloud engine possible (test-pinned).
- NO SILENT FALLBACK is a test-enforced invariant (5 dedicated tests) AND demonstrated
  live through the real router (§K.6).

## E. Arabic HTR inventory (AHW-02C)

| Dimension | Label | Basis |
|---|---|---|
| implemented | **PROVEN** | `ArabicHandwrittenHTR`, `FineTunedTrOCR`, segmenters, `dotted_recovery` exist and import |
| importable | **PROVEN** | `from packages.vision.htr.arabic_htr import HTRResult, LineResult` succeeds in this env |
| tested | **PROVEN (contract level)** | 11 adapter contract tests + mocked `HTRResult → OCRResult` mapping. Pre-existing `tests/test_e2e.py` broken class names remain untouched (B6) |
| wired | **PROVEN** | `HandwritingHTRAdapter` bound to router id "TrOCR" (Qwen→QARI→TrOCR); reachable from caller |
| executable | **PROVEN (path) / BLOCKED (live inference here)** | contract tests + live chain smoke prove execution path; torch/transformers absent (B1) |
| Arabic-capable | **UNPROVEN** | default base model `microsoft/trocr-base-handwritten` is LATIN; flagged in provenance + test-pinned; `model_path` accepts a true Arabic model without code changes; NO accuracy claim anywhere |
| production-proven | **NOT PROVEN** | no benchmark / GT588 run in scope |

## F. Security hardening (AHW-02E)

- **E1:** the three PROVEN-unsafe `torch.load` sites now pass `weights_only=True`;
  AST-based regression tests (per-site + safe-reference + package sweep). Bounded
  reproducible scan (§K.5): **6 hits in 354 scoped files, ALL SAFE** (3 pre-existing
  safe `line_segmenter.py` copies + 3 remediated E1 sites); zero unsafe sites remain
  in scope.
- **E2:** `.gitignore` blocks the six weight extensions; guard test pins them.
- **E3:** cloud disabled by default even with `MISTRAL_API_KEY`; explicit
  `OMNI_ENABLE_CLOUD_OCR` opt-in; test matrix (key-without-opt-in / truthy / junk /
  UnifiedOCR chain / executor-no-cloud). Closes the AHW-01 §M-2 default-egress risk
  on the canonical path (mirror copy = B4 decision pending).

## G. OLMoCR (AHW-02F) — status ladder

| Stage | Status | Evidence |
|---|---|---|
| UPSTREAM AVAILABLE | **YES — PROVEN** | `git ls-remote https://github.com/allenai/olmocr.git` → HEAD `f7cfe4c22098b154c76b6ec950d1c0a464eecf8d` (verified twice: pre- and post-reset) |
| ADAPTER PRESENT | **YES — PROVEN** | `OLMoCRAdapter` in `packages/core/router_executor.py`; `issubclass(…, EngineAdapter)` |
| DEPENDENCY INSTALLED | **NO** | `importlib.util.find_spec("olmocr")` → None (this env) |
| ENTRYPOINT AVAILABLE | **NO (unverifiable without dependency)** | adapter probes `process_document`/`process_pdf`/`pipeline`; upstream API not pinned (B7) |
| MODEL AVAILABLE | **NO** | nothing downloaded; adapter never downloads |
| EXECUTED | **NOT EXECUTED** | no olmocr run occurred — by design OPTIONAL; absence is NOT a central-architecture failure |
| TESTED | **YES (mocked contract tests)** | 12 tests, offline, no network |
| BENCHMARKED | **NO** | out of scope |

`is_available()` = False; healthcheck explicit: "olmocr package not installed
(optional dependency)". OLMoCR remains a strictly OPTIONAL ADAPTER.

## H. Tests — raw numbers (machine-readable; §K.2)

| Run | Result |
|---|---|
| Target tests (AHW-02 files) | **63 passed** in 2.08 s |
| Legacy router tests | **11 passed** in 0.59 s (baseline parity) |
| `pytest --collect-only` BASE (clean worktree @ 39640a6d) | **1004 collected, 5 errors** |
| `pytest --collect-only` BRANCH | **1067 collected, 5 errors** (same 5 modules) |
| Full suite BASE (`-q --continue-on-collection-errors`) | **81 failed, 868 passed, 51 skipped, 9 errors** (9 = 5 collection + 4 runtime) in 18.69 s |
| Full suite BRANCH (identical command/env/plugins) | **81 failed, 931 passed, 51 skipped, 9 errors** in 18.94 s |
| Identifier-level comparison | **FAILURE SET IDENTITY = TRUE** (sha256-equal sorted id lists for failed/error/skipped; 5 collector-error modules identical) |

## I. Blockers & new findings

**Pre-existing:** B1 torch/transformers absent (live inference blocked) · B2 no
Tesseract `ara` · B5 the 5 collection errors + 81 pre-existing failures (NOT repaired
per discipline; identity proven by §K.2) · B6 `tests/test_e2e.py` broken class names
(AHW-01 finding, untouched).

**N1 (PROVEN, FIXED, guarded):** `tests/security/test_medical_behavior.py`
`sys.path.insert(0, hf-space)` shadowed canonical `packages.core` (hf-space copy lacks
`router_executor`; unpatched `mistral_integration` would receive E3 tests). Fix:
`append` + 3 canonical-resolution guard tests. Resolution-only change; suite behavior
unchanged (§K.2 identifier proof). Full analysis: `docs/portfolio/AHW-02_B4_DECISION.md` §6.

**N2 (PROVEN):** AHW-01 "5 collection errors" identity confirmed (jose ×2 =
`test_auth_security` + `test_security_hardening`).

**Open:** B4 hf-space mirror divergence → drift-gate WILL fail next CI run; decision
documented, NOT executed (`docs/portfolio/AHW-02_B4_DECISION.md` §8) · B7 OLMoCR
entrypoint unpinned (§G) · B8 TASK-005 full field list deferred by design.

## J. Claims register (six-state labels)

| Claim | Label |
|---|---|
| Router selection reaches actual adapter execution, contract unchanged | **PROVEN** (tests + 11 legacy tests + live chain smoke) |
| NO SILENT FALLBACK invariant | **PROVEN** (5 tests + live scenario 1) |
| OCRResult extension backward-compatible | **PROVEN** (round-trip test; suite outcome sets identical) |
| Arabic HTR pipeline wired behind EngineAdapter | **PROVEN** |
| Arabic handwriting accuracy / capability | **UNPROVEN** (no benchmark; LATIN default flagged) |
| Live HTR inference in this environment | **BLOCKED** (B1/B2) |
| E1/E2/E3 hardening on canonical path | **PROVEN** |
| OLMoCR strictly optional, absent from profiles | **PROVEN** |
| OLMoCR EXECUTED | **NOT EXECUTED** (dependency absent — optional by design, not an architecture failure) |
| OLMoCR upstream reachable | **PROVEN** (ls-remote, twice) |
| AHW-02 introduces zero test regressions vs base | **PROVEN** (identifier-level identity, §K.2) |
| Full-suite green | **CONTRADICTED as stated** — 81 pre-existing failures remain, pre-dating AHW-02 |
| hf-space mirror dedup (shim) | **BLOCKED** (infeasible without packaging change — B4 §4) |

## K. RECONCILIATION ADDENDUM (post-directive, 2026-09-17)

### K.0 Environment reset #4 — disclosure

Between the implementation session and the reconciliation directive, the container was
reset: `/home/z/my-project/repos/` (with the three original AHW-02 commits
`7319bc9`/`6e89c7b`/`05b56f2`, branch-local, never pushed), `download/ahw02/` mirrors,
in-session evidence files, and the SESSION-20 worklog entry were lost. Remote `main`
remained untouched at `39640a6dbba7…` (verified by `git ls-remote`; no `feat/ahw-02*`
ref exists on the remote). Recovery followed the worklog precedent (SESSION-19 option
B): fresh anonymous clone (read-only) + verbatim reconstruction of every file from
session-recorded diffs/contents. The AHW-01 audit report file is NOT reconstructable
byte-faithfully and was NOT re-fabricated; its verified sha256
(`29274608…c49eb49`) and content summary survive in the session worklog.

### K.1 Commit Manifest (authoritative — read from git, not memory)

Command basis: `git rev-list --count 39640a6dbba741eaf13e078dad64719e147ea79b..HEAD`
and `git log --oneline --decorate 39640a6d..HEAD` at closure time.

| # | Commit | Subject | Files changed |
|---|---|---|---|
| 1 | `26dea72…` (full SHA in closure report/worklog) | `feat(ahw-02): controlled handwriting OCR consolidation (B/C/D/E/F/G)` | 13 files: +`packages/core/router_executor.py`, +4 test files, ~`app/advanced_review_app.py`, `packages/core/mistral_integration.py`, `packages/omni_ocr/adapter.py`, 2×`online_learner.py`, `continual_trainer.py`, `.gitignore`, `tests/security/test_medical_behavior.py` |
| 2 | reconciliation-closure commit | `docs(ahw-02): gate-closure reconciliation (B4 decision doc, addendum K, commit-manifest correction)` | `docs/audit/AHW-02_IMPLEMENTATION_REPORT.md` (this file), `docs/portfolio/AHW-02_B4_DECISION.md` |

The earlier draft of this report stated "2 commits" in §A while the prior session
produced 3 (implementation + report + AHW-01-input inclusion). Resolution per
directive: counted from git itself. Post-reset the branch legitimately contains the
two commits above (the AHW-01 input file is unrecoverable and was not re-fabricated);
the full SHA list is recorded in the chat closure report and `worklog.md`.

### K.2 Machine-readable test reconciliation

Method: `pytest --json-report` (plugin 1.5.0), identical command
`-q --continue-on-collection-errors`, same container/plugins/Python (3.12.14/pytest
9.0.2), BASE = fresh `git worktree` at `39640a6dbba7…`. Artifacts:
`scripts/ahw02_recon_base.json`, `scripts/ahw02_recon_branch.json`,
`scripts/ahw02_recon_compare.py`, `scripts/ahw02_recon_compare_result.json`.

| Metric | Clean Base | AHW-02 | Delta |
|---|---|---|---|
| collected | 1004 | 1067 | **+63** |
| passed | 868 | 931 | **+63** |
| failed | 81 | 81 | **0** |
| skipped | 51 | 51 | **0** |
| collection errors | 5 | 5 | **0** |
| runtime errors (test-level) | 4 | 4 | **0** |

Identifier-level proof (NOT count-similarity):
- failed-set sha256: base `7f24cfbf4d3a95e9…` == branch `7f24cfbf4d3a95e9…`
- error-set sha256: `744d313a6e3ffbde…` == identical
- skipped-set sha256: `d94dd923b5b1cd6c…` == identical
- collector-error modules (identical, both sides): `tests/integration/test_auth_postgres.py`,
  `tests/test_auth_security.py`, `tests/test_build_training_data.py`,
  `tests/test_mobile_review_server.py`, `tests/test_security_hardening.py`
- **BASE FAILURE SET == AHW-02 FAILURE SET → TRUE (by ids + sha256)**
- ⇒ **REGRESSION = ZERO** (explicit)

### K.3 B4 — pointer + classification summary

Full evidence & decision: `docs/portfolio/AHW-02_B4_DECISION.md` (created by this
reconciliation). Headline: divergence = exactly the E3 patch + absent
`router_executor.py` (PROVEN); hf-space is a documented intentional mirror
(drift-CI); import shim infeasible without packaging change (standalone Docker
Space); zero production runtime dependence on hf-space copies; sys.path fix =
resolution-only. **Impact:** `packages/core` is in `SYNC_MAP` → drift gate WILL fail
next CI run. Decision (a) sync E3+executor into mirror — recommended, NOT executed;
requires separate micro-authorization.

### K.4 B7 — OLMoCR ladder

See §G. `OLMOCR EXECUTION = NOT EXECUTED` (dependency absent). Optional-adapter
status unchanged; NOT a central-architecture failure.

### K.5 AHW-02A torch.load evidence (bounded, reproducible)

Script `scripts/ahw02a_torchload_scan.py` (AST-based, 14 explicitly allow-listed
directories, 60 s hard bound — used 14 s; 354 files). Results (JSON:
`scripts/ahw02a_torchload_scan.json`):

| Path:line | weights_only | Safe? | Remediated by AHW-02 |
|---|---|---|---|
| packages/vision/htr/line_segmenter.py:283 | True | SAFE | pre-existing safe |
| hf-space/packages/vision/htr/line_segmenter.py:283 | True | SAFE | pre-existing safe |
| packages/file_processor/modules/vision/htr/line_segmenter.py:283 | True | SAFE | pre-existing safe |
| packages/interactive-learning/learning/online_learner.py:408 | True | SAFE | YES (E1) |
| packages/file_processor/interactive_learning/learning/online_learner.py:412 | True | SAFE | YES (E1) |
| apps/handwriting-demo/training/continual_trainer.py:127 | True | SAFE | YES (E1) |

Zero unsafe `torch.load` sites remain within the declared scope. Six AHW-02A paths:
all present and classified (§C.2).

### K.6 Router integration evidence

- Legacy router tests: `pytest tests/test_engine_router.py tests/test_engine_router_advanced.py -q`
  → **11 passed** (matches AHW-01 baseline verbatim).
- AHW-02 router tests: **17 passed**.
- Live chain smoke (`scripts/ahw02_router_chain_smoke.py`, real router, no stubbing of
  selection): SCENARIO 1 — selection `[Qwen, QARI, TrOCR]`; first engine fails at
  runtime → `QARI` executes → success, `attempts=[failed, executed]`,
  `fallback_used=True` (DECLARED fallback). SCENARIO 2 — default factory in CPU-only
  env → both selected engines skipped with reasons → explicit-failure `OCRResult`,
  `fallback_used=False`, no cloud engine in attempts. Every result is the standard
  `packages.omni_ocr.adapter.OCRResult`; `to_dict()` carries
  `confidence/engine/error/processing_time/provenance/text/word_count/words`; provenance
  carries profile/language/script_kind/normalization/selection/reasons/attempts/
  fallback_used. All assertions passed.

---

## L. Evidence persistence (SESSION-22, owner persistence directive)

The §K.2/§K.5/§K.6 evidence originally existed only as run artifacts and was
lost after SESSION-21. Per `docs/SESSION_ARTIFACTS_POLICY.md` (committed
policy), the evidence was RE-CREATED live 2026-09-17 and is now COMMITTED to
this branch (`59a9813d…`):

| Artifact | Re-creation result |
|---|---|
| `scripts/ahw02_recon_{base,branch}.json` + `ahw02_recon_compare.py` + `_result.json` | same table as §K.2; failed/error/skipped set sha256 **identical to the pre-loss fingerprints** (`7f24cfbf…`/`744d313a…`/`d94dd923…`) ⇒ §K.2 identity independently re-proven |
| `scripts/ahw02a_torchload_scan.{py,json}` | 16 declared scope dirs / 753 files / 6 hits ALL SAFE, same paths+lines as §K.5 |
| `scripts/ahw02_router_chain_smoke.{py,_output.json}` | both §K.6 scenarios ALL ASSERTIONS PASSED (real router names, incl. declared fallback `fallback_used=True`) |
| `scripts/ahw02_targeted_tests_output.txt` | 74 passed (63 AHW-02 + 11 legacy router) |

Mandatory final closure record (directive item 8):
`docs/audit/AHW-02_GATE_CLOSURE_REPORT.md`. All artifact hashes are registered
in the append-only `docs/SESSION_ARTIFACTS_LEDGER.md` and machine-verified by
`scripts/verify_session_artifacts.py`.

---

## GATE

| Sub-phase | Status |
|---|---|
| AHW-02A canonical review + SOURCE OF TRUTH + bounded torch.load evidence | DONE (§C, §K.5) |
| AHW-02B router execution repair | DONE (§D, §K.6) |
| AHW-02C Arabic HTR inventory | DONE with honest labels (§E) |
| AHW-02D result contract | DONE — minimal additive `provenance` (§B/§I-B8) |
| AHW-02E security hardening E1/E2/E3 | DONE (§F, §K.5) |
| AHW-02F OLMoCR optional adapter | DONE (§G, §K.4) |
| AHW-02G test-first discipline | DONE (63 tests; guards; §B) |
| Evidence reconciliation (directive items 1–7) | DONE (§K) |

**FINAL STATUS: AHW-02 GATE = PARTIAL**

Reason (strictest-condition reading): all sub-phases delivered and test-proven;
zero regressions (identifier-level proof); BUT live Arabic HTR inference remains
BLOCKED by the documented environment (B1/B2), OLMoCR entrypoint/model unpinned and
NOT EXECUTED (B7 — optional by design), and the hf-space mirror divergence requires
the recorded B4 decision (drift gate expected-red until decided). BLOCKED/UNPROVEN
items are recorded, not assumed away. No accuracy claim is made anywhere.

**PUSH AUTHORIZATION = NOT GRANTED**
**MERGE AUTHORIZATION = NOT GRANTED**

Work stops here. AHW-03 not started. Main untouched; no PR; no tag.
