# OLMoCR Integration Report — core registry adapter

> Branch: `feat/xberg-olmocr-integration` (from `main` @ `39640a6dbba7`)
> Status: **PUSHED — PR opened in the same operation as this push** (see the
> repo's pull-request list for the live PR number; this file deliberately
> avoids hard-coding a number that could drift).
> Rebuild lineage: original implementation (`b069072..fb616cc`) was LOST in
> environment reset #10 before push; this branch is a clean-room rebuild
> performed from worklog records and live-verified pins.

## 1. What this integration does — and does not do

This integration wires an **OLMoCR engine adapter** into the runtime-aware
engine registry (`packages/core/engine_registry.py`) as the 8th default
adapter, next to EasyOCR, Tesseract, TrOCR, PaddleOCR, the Qwen handwriting
engine, QARI and Nougat. It does **not**:

- add `olmocr`, `vllm`, `torch>=2.7` or `transformers==4.57.3` to the
  suite's dependency set (these pins live ONLY in the isolated env);
- enable OLMoCR in any default routing chain (the registry reports it, the
  router never selects it implicitly);
- download or load any model weights at import or probe time.

Owner ruling R19 (BENCHMARK-FIRST, isolated env, GPU ≥ 12 GB) remains the
governing frame for anything beyond this adapter: real model execution
belongs to the benchmark phase on GPU hardware, not to this integration.

## 2. The isolated-env contract

OLMoCR runs only inside a dedicated virtual environment that satisfies all
of the following, verified against PyPI metadata on 2026-09-23:

| Constraint | Value |
|---|---|
| `olmocr` | `==0.4.27` (gpu extra) |
| `transformers` | `==4.57.3` (pulled by the gpu extra) |
| `vllm` | `==0.11.2` (gpu extra) |
| `torch` | `>=2.7.0` (gpu extra) |
| Weights | `allenai/olmOCR-2-7B-1025-FP8` (HuggingFace-verified) |
| Hardware | GPU ≥ 12 GB VRAM, CUDA 12.x (R19) |
| Env marker | `OMNI_OLMOCR_ISOLATED_ENV=1` must be exported inside the isolated env |

Availability is **fail-closed at code level**: `_OLMoCRAdapter.is_available()`
returns `True` only when the marker is set AND `import olmocr` succeeds. A
stray `pip install olmocr` in the main environment is therefore insufficient
by contract, not merely by convention.

Historical note recorded honestly: the S11 conflict ("repo pins
`transformers>=5.10,<5.13` vs olmocr `==4.57.3`") was proven against an
earlier pin state. At this base (`main` @ `39640a6`), `pyproject.toml` pins
`transformers>=4.36.0` (uncapped), which would technically admit 4.57.3 —
the isolated env remains mandatory regardless, per R19 (GPU gating, vllm
pins, and benchmark attribution discipline).

## 3. Adapter behaviour

- `name = "OLMoCR"`; `estimated_ram_gb = 12.0`; tasks
  `["printed", "scientific_pdf", "structured"]`.
- `healthcheck()` loads **no weights**: it validates the transformers pin
  (`__version__ == "4.57.3"`), reports CUDA presence/device count when torch
  is importable, and returns a structured failure with the pin contract
  violation spelled out when the pins do not match.
- `discover()` includes the adapter; `health_report()` always shows OLMoCR
  with `available=false` outside the isolated env, and
  `available_engine_names()` can never contain it there.

## 4. Truth level — CONTRACT_TESTED (adapter contract)

- **IMPORTABLE**: adapter module imports cleanly in the main runtime;
  engine itself is NOT importable there (by design).
- **CONTRACT_TESTED**: `tests/test_olmocr_adapter.py` — 10 tests covering
  pin constants, marker-gated availability, no-weights healthcheck,
  pin-violation detection (stubbed modules), and registry integration.
  Local run evidence: `33 passed in 1.76s` across the three new test files
  (Python 3.12.14, pytest 9.0.2, CPU-only, no network).
- **SMOKE_TESTED**: NOT CLAIMED for OLMoCR in this environment.
- **REAL_MODEL_EXECUTED**: **NOT_EXECUTED** — no GPU, no weights, no vllm
  here. Any future claim must come from the isolated GPU benchmark phase
  with its own evidence record.

## 5. Fallback semantics

The five rules documented in `XBERG_INTEGRATION_REPORT.md` §5 apply verbatim
to OLMoCR: disabled+unavailable is a loud failure; opted-in chains record
attempt trails; loose exception swallowing fails review; first-engine wins
do not claim fallback; total failure keeps the trail with a null winner.

## 6. Isolated-env bootstrap (reference)

```bash
python3 -m venv .venv-olmocr
.venv-olmocr/bin/pip install "olmocr[gpu]==0.4.27"
export OMNI_OLMOCR_ISOLATED_ENV=1     # inside this env only
.venv-olmocr/bin/python -c "import olmocr"   # now, and only now, available
```

Nothing in the suite sets the marker automatically; the operator of the
isolated env does. This is the fail-closed hinge of the whole contract.

## 7. Rollback

`git revert 412f926` (or delete the branch) removes the adapter and its
registry entry; no other file is touched by that commit.
