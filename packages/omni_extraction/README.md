# packages/omni_extraction — isolated Xberg extraction wrapper

Isolated, fail-closed, provenant wrapper around the pinned **xberg**
document-extraction engine (PyO3 library + `xberg-cli` binary).

## Governance summary

| Rule | Implementation |
|---|---|
| Engine isolation | `xberg` never enters the suite's main dependency set; install into a dedicated venv via `requirements.txt` |
| Fail-closed | Missing engine → loud `ExtractionError`, never a silent empty result |
| Mandatory provenance | Every `ExtractionResult` carries a `ProvenanceRecord` (tool, version, path, binary SHA-256, network posture, input hash, duration) |
| Binary integrity | CLI path computes and records the binary's SHA-256 (XB-02 ruling) |
| No PHI in evidence | Evidence/smoke runs use synthetic files only |
| Truth levels | IMPORTABLE → CONTRACT_TESTED → SMOKE_TESTED are distinct and never merged (see the integration report) |

## Pins (PyPI-verified 2026-09-23)

- `xberg==1.2.6` (MIT) — upstream HEAD `588401cec14e`
- Wheel bundles `libheif 1.23.0` (**LGPL**) + `libonnxruntime` — the LGPL
  ships inside the Python artifact (license nuance OQ-11, XB-02 audit)

## Network posture

The xberg *core* extraction path performs no network I/O. Its *ML* model
download defaults to `allow_network=true` upstream. This wrapper:

- defaults to `XbergExtractor(allow_network=True)` (mirrors upstream), and
- offers `XbergExtractor(allow_network=False)` for a strict offline
  posture (`HF_HUB_OFFLINE=1` enforced per run).

## Two execution paths

1. **Library** — `XbergExtractor(engine_path="library")`: in-process
   `ExtractInput` → `extract` → `ExtractedDocument`
   (`content` / `chunks` / `djot` / `entities` / `confidence` /
   `metadata`), defensively mapped onto `ExtractionResult`.
2. **CLI** — `XbergExtractor(engine_path="cli")`: subprocess call to
   `xberg-cli` with mandatory SHA-256 binary verification.

## Usage

```python
from packages.omni_extraction import XbergExtractor, ExtractionError

ex = XbergExtractor()
if not ex.is_available():
    raise ExtractionError(ex.availability_error())

result = ex.extract_file("document.pdf")
print(result.success, result.confidence, result.table_count)
print(result.provenance.to_dict())
```

## Rollback

Delete the package directory and (optionally) the isolated venv. Nothing
outside this package depends on it; the suite runtime is untouched.
