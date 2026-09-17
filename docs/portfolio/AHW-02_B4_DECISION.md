# AHW-02 B4 DECISION — hf-space / packages/core divergence

> Directive: document current state, decide nothing by intuition, execute no migration.
> Scope of this doc: `packages/core/` vs `hf-space/packages/core/`, focus
> `engine_registry.py`, `router_executor.py`, `mistral_integration.py`.
> All evidence gathered live 2026-09-17 on `feat/ahw-02-controlled-handwriting-ocr`
> @ base `39640a6dbba741eaf13e078dad64719e147ea79b`.

## 0. Classification

| Aspect | Label |
|---|---|
| Divergence facts (§1) | **PROVEN** (byte-level `cmp`/`diff`/`ls`) |
| Intentional vs accidental (§2) | **PROVEN** — divergence is 100% attributable to the AHW-02E3 patch applied to the canonical copy only; no unexplained drift found |
| Mirror intent (§3) | **PROVEN** — documented in `.github/workflows/hf-space-drift.yml` ("intentional mirror", "any unexpected drift fails the build") |
| Import shim feasibility (§4) | **PROVEN INFEASIBLE** without packaging change (hf-space is a standalone Docker Space; repo root is not importable at Space runtime) |
| Runtime dependence on hf-space copies (§5) | **PROVEN NONE** in production code (comments/strings/sync-tooling only); one legacy TEST imported hf-space `app_core` (kept working via `append`) |
| sys.path fix semantics (§6) | **PROVEN** — resolution change (intended), suite behavior unchanged (identifier-level proof) |
| Required decision (§8) | **DECISION REQUIRED — URGENT** (drift gate will fail) |

## 1. What differs? (PROVEN, byte-level)

| File | Verdict | Evidence |
|---|---|---|
| `engine_registry.py` | byte-identical | `cmp -s` → identical |
| `engine_router.py` | byte-identical | `cmp -s` → identical |
| `model_registry.py` | byte-identical | `cmp -s` → identical |
| `router_executor.py` | **ABSENT in hf-space** | `ls` → cannot access; it is the ONLY listing difference between the two `core/` trees (`diff <(ls packages/core) <(ls hf-space/packages/core)` → `26d25 < router_executor.py`) |
| `mistral_integration.py` | **diverges by exactly the E3 patch** | `diff` = 19 lines: 13-line opt-in helper block (lines 13–25 canonical) + 3 gate conditions (`if self.api_key and HAS_MISTRAL and _cloud_opt_in_enabled():` vs `if self.api_key and HAS_MISTRAL:` at 3 client `__init__`s). hf-space copy = pre-E3 state. No other drift. |

## 2. Intentional or accidental? (PROVEN)

Every difference is accounted for:
- `router_executor.py` — new AHW-02B file, intentionally created in canonical only.
- `mistral_integration.py` — E3 hardening applied to canonical only (hf-space was NOT
  touched in AHW-02 — mirror sync was out of scope).
- Zero unexplained drift: registry/router/model_registry byte-identical.

So: the divergence is **intentional on the canonical side, and INCOMPLETE on the mirror
side** — the mirror simply has not received the AHW-02 changes.

## 3. Should hf-space be a mirror? (PROVEN intent)

`.github/workflows/hf-space-drift.yml` self-describes: "Protects the **intentional
mirror** between the canonical OCR service and the frozen HF Space application core…
Failure policy: any unexpected drift fails the build." Layer 1 =
`scripts/sync-hf-space.sh --verify` over auto-synced directories; its `SYNC_MAP`
contains `"packages/core:packages/core"` (line 62). Layer 2 compares OCR knobs between
`hf-space/app_core.py` and `app/services/ocr_service.py` (does not involve
`mistral_integration.py`).

⇒ YES: hf-space `packages/core` is *by design* an auto-synced mirror of canonical
`packages/core`.

## 4. Is an import shim possible without circular import? (PROVEN INFEASIBLE as such)

The MIGRATION_PLAN "WRAP (import shim)" pattern (hf-space file imports canonical) is
**not viable here without a packaging change**: `hf-space/README.md` frontmatter declares
an independent HF Space (`sdk: docker`, `app_port: 7860`) with its own
`requirements.txt` / `app.py` / `app_core.py` / `deploy_space.py`. At Space runtime the
repo root is not on `sys.path`; `from packages.core...` inside hf-space resolves to
hf-space's OWN namespace tree (hf-space is self-contained: its `packages/medical/*` and
`src/ocr/rtl_utils.py` import `packages.*` resolved within the Space). A shim would
therefore either (a) fail at Space runtime, or (b) require shipping canonical code into
the Space image (i.e., the existing whole-directory sync — which is what SYNC_MAP
already does). Circular import is NOT the blocker; standalone deployment is.

## 5. Does any code path deliberately depend on the hf-space copy? (PROVEN: none at runtime)

- Production references to "hf-space" (rg over `app/ packages/ src/`):
  `src/api/server.py:178,181` (classifier label string + log text),
  `app/services/ocr_service.py:79` (comment "Kept in lock-step with hf-space/app.py"),
  `pdf_ocr_processor.py:956` (comment), `sync_hf_github.py:32` (deployment tooling path).
  **No imports.**
- Test-side dependence: `tests/security/test_medical_behavior.py` imports
  `app_core`, which exists ONLY at `hf-space/app_core.py`. Pre-AHW-02 it did
  `sys.path.insert(0, hf-space)` (shadowing canonical `packages.core` for all
  later-collected modules — AHW-02 finding N1); AHW-02G changed it to `append`,
  which keeps `app_core` resolution working (proven: standalone run = 5 passed)
  while canonical `packages.core` wins for the `packages` namespace.
- `tests/test_pr92_*` / `test_pr94_*` append hf-space inside functions for their own
  imports — module-level namespace resolution unaffected.

## 6. Did the sys.path fix change only resolution, or behavior? (PROVEN: resolution-only + intended)

- Resolution: for modules collected after `tests/security/` in full-suite runs,
  `packages.core` now resolves to the CANONICAL tree instead of the hf-space shadow.
  This is what un-blocked collection of `test_router_executor.py`,
  `test_handwriting_htr_adapter.py`, `test_olmocr_adapter.py` (the shadow copy has no
  `router_executor.py`) and made E3 tests run against the PATCHED canonical module
  (the shadow is unpatched — tests would have failed against it).
- Behavior: (a) the fixed module's own tests still pass standalone (5 passed) — its
  `app_core` import is unaffected by `insert`→`append`; (b) machine-readable
  identifier-level suite comparison vs clean base shows IDENTICAL failed/error/skipped
  sets (sha256-equal sorted id lists; `ahw02_recon_compare_result.json`) — no test
  changed outcome anywhere. Conclusion: the fix changed import RESOLUTION (intended);
  no observable behavior change beyond the intended new tests passing.

## 7. Impact warning (PROVEN)

Because `packages/core` is in `SYNC_MAP`, the current canonical-only AHW-02 changes
(`mistral_integration.py` E3 patch + new `router_executor.py`) **will make
`hf-space-drift.yml` Layer-1 verification FAIL on the next CI run** (push/PR/scheduled).
This is a GUARANTEED red gate, not a hypothetical.

## 8. Decision required (NOT executed — per directive)

Options:
- **(a) RECOMMENDED — sync the AHW-02 changes into the mirror** (`sync-hf-space.sh`
  direction canonical→hf-space for `packages/core`): copies the E3 gate and
  `router_executor.py` into `hf-space/packages/core/`. Restores drift-gate green;
  also extends "cloud disabled by default" to the Space (PHI-posture improvement).
  Dead code inside the Space (nothing there imports `router_executor`) — harmless.
  Needs its own micro-authorization (mirror write = outside AHW-02 branch scope).
- (b) Allowlist/exception in the drift gate for these two files — weakens a
  documented guard; not recommended.
- (c) True single-source shim — infeasible without packaging changes (§4); the
  existing whole-directory sync IS the shim mechanism.

Decision owner: repository owner. Until decided, the divergence stays as-is and the
drift gate stays expected-red for `packages/core`.
