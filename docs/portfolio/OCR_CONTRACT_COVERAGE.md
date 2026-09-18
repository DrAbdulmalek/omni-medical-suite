# OCR CONTRACT COVERAGE — TASK 001 (PHASE 1)

EXECUTION ENVIRONMENT: sandbox python3.12 + pytest (no GPU, no OCR engines installed)
BASE: 39640a6dbba741eaf13e078dad64719e147ea79b (main, verified 2026-09-18 via API + clone HEAD)
BRANCH: feat/central-ocr-foundation
EVIDENCE RULES: portfolio_forensics_v2.md §0 (E1–E9)

## Inspected files (PROVEN, fetched at base SHA)
- packages/omni_ocr/adapter.py — `OCRResult` dataclass
- apps/ocr-pipeline/src/engines/base_engine.py — `OCREngine`/`BBox` (alt contract)
- hf-space/packages/vision/htr/arabic_htr.py — `HTRResult`/`LineResult`/`WordResult`

## Field coverage: REQUIRED (plan §11) vs `OCRResult` v1.0 (pre-TASK-005)
| Required field | OCRResult v1.0 | Where today | Gap |
|---|---|---|---|
| text | ✓ | adapter.py | — |
| language | ✗ | — | GAP |
| script | ✗ | — | GAP |
| confidence | ✓ | adapter.py | — |
| boxes | PARTIAL | words[].x/y/w/h (flat rects, no polygon) | PARTIAL |
| lines | ✗ (words only, no line grouping) | — | GAP |
| words | ✓ | adapter.py words[] | — |
| characters | ✗ | — | GAP |
| page | ✗ | — | GAP |
| reading_order | ✗ | — | GAP |
| engine | ✓ | adapter.py | — |
| engine_version | ✗ | — | GAP |
| model | ✗ | — | GAP |
| model_version | ✗ | — | GAP |
| processing_time | ✓ | adapter.py | — |
| provenance | ✗ (engine name only) | — | GAP |
| warnings | ✗ | — | GAP |
| fallback_status | ✗ | — | GAP |

## HTRResult (hf-space/packages/vision/htr/arabic_htr.py) coverage
text ✓ · lines ✓ (LineResult{text,confidence,words[]}) · words ✓ (WordResult{text,confidence}) ·
confidence ✓ · language PARTIAL (implicit "ar" in orchestrator) · boxes/characters/page/
reading_order/engine_version/provenance/fallback_status ✗

## Gap closure plan
TASK 005 (this branch) extends `OCRResult` additively with: blocks, lines, characters,
language, script, page, engine_version, model, model_version, provenance, warnings,
fallback_status + contract_version. HTRResult unification (full parity) = PHASE 2+,
not in this authorization.

## Baseline verification (executed)
- `sha256sum` both engine_registry.py copies → see TASK 002 doc (byte-identical PROVEN).
- `python3 -m pytest packages/core packages/omni_ocr -q` (pre-edit baseline): recorded in
  PHASE1_EXECUTION_LOG.md. packages/omni_ocr had NO tests pre-branch (pytest exit 5 =
  "no tests ran") → contract tests are ADDED in TASK 005.

## LIMITS
- No GPU / OCR engines in this env → no engine execution claims.
- app.core.decision_log not imported at module scope by router (lazy import inside
  select()) → router tests stub it; production path unchanged.
