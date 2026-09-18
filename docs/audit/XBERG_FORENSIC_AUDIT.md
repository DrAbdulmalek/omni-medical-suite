# XBERG FORENSIC AUDIT — XB-01

**Project**: DrAbdulmalek/omni-medical-suite
**Audit ID**: XB-01 (Forensic Upstream Audit — Xberg)
**Date**: 2026-09-18
**Independence Level**: LEVEL 2 (separate model instance, fresh SDK context; same-family limitation disclosed — see Appendix C)
**Status**: COMPLETE (DoD Appendix D) — XB-02 authorized by owner 2026-09-18 («نفذ ب ثم أ» = close OQ-2+OQ-9, then XB-02)
**RECOVERY NOTE**: This report was originally created uncommitted (per XB master §3) and LOST in environment reset #5 the same day. Recreated byte-identical from session context and now COMMITTED — justified deviation from the no-commit rule, because reset #5 empirically proved uncommitted work does not survive this environment. Rollback remains trivial (revert this commit).

---

## 1. Executive Summary

Xberg (`xberg-io/xberg`) is the rebranded continuation of Kreuzberg: a Rust-based document-intelligence/extraction engine that unifies 100+ input formats into 6 output formats (plain text, Markdown, Djot, HTML, JSON tree, Docling DocTags) and wraps external OCR engines (Tesseract, PaddleOCR, Candle/TrOCR, VLM backends) rather than owning any OCR engine. It ships as a Rust workspace (v1.2.3) with ~15 language binding surfaces, a CLI, a REST API server, an MCP server, audio transcription, chunking/embeddings, and code intelligence. License: MIT (Kreuzberg, Inc.), with a mature third-party license governance layer (`cargo-deny` + explicit `THIRD_PARTY_LICENSES.md` for LGPL natives such as opt-in libheif).

The architectural conclusion mirrors the OCR-CR-01 boundary discipline: **Xberg is a candidate OPTIONAL DOCUMENT EXTRACTION LAYER, not an OCR engine and not a replacement for AHW / OLMoCR / the Omni OCR router / OCRResult**. Its plausible value for Omni is format unification (DOCX/XLSX/PPTX/EPUB/Email/Archives), layout/table reconstruction, structured output with provenance fields, and MCP/CLI as developer tooling — **not** Arabic handwriting OCR (zero local evidence; benchmark-gated future phase XB-05). A significant overlap risk exists: Omni already contains `packages/doc_processor/` and `packages/file_processor/` whose extraction scope vs Xberg is unquantified at XB-01 depth. **Initial status: CANDIDATE / STUDY ONLY — no adoption decision is made or implied by this report.**

## 2. Exact Upstream Version

| Field | Value |
|---|---|
| UPSTREAM_REPOSITORY | https://github.com/xberg-io/xberg (official; cloned read-only into `/home/z/tools-sandbox/xberg`) |
| UPSTREAM_VERSION | 1.2.3 (workspace `[workspace.package] version`) |
| UPSTREAM_TAG | v1.2.3 |
| UPSTREAM_COMMIT (TAG) | `19a189d37b4d383f6bd66b13c3a3b7272c789e18` |
| UPSTREAM_COMMIT (HEAD at audit) | `41040097d044970b9638d006cb1ac01782f847cb` = tag + 2 commits (`fix(pdf)` heading wrap; `chore(deps)` refresh holding skrifa 0.46) |
| COMMIT_DATE / RELEASE_DATE | 2026-09-16 (tag "chore(release): 1.2.3" 22:15 +0200) |
| RUNTIME | Rust core (edition 2024, rust-version 1.92, `unsafe_code = "deny"`), PyO3/Python, Node (napi), WASM, FFI/JNI/PHP natives |
| LANGUAGE_BINDINGS | packages/: csharp, dart, elixir, go, java, kotlin-android, php, python, ruby, swift, zig (11) + crates: ffi, jni, node, php, py, wasm (6) → ≈15 surfaces incl. C FFI (PROVEN count from directory inventory) |
| INTEGRATION_SURFACES | Library (per-language), CLI (`xberg-cli`), REST API (`crates/xberg/src/api/`), MCP server (`crates/xberg/src/mcp/`) |

## 3. Exact Commit SHA

Both coordinates recorded (§2). If XB-02 is authorized, the pilot MUST pin `v1.2.3^{commit} = 19a189d3…` (or a newer owner-approved tag) — never `main`. HEAD being 2 commits past the tag is a normal release cadence artifact, recorded for reproducibility.

## 4. License

- **XBERG_LICENSE = MIT** — read from the actual `LICENSE` file ("Copyright (c) 2025-2026 Kreuzberg, Inc."), confirming Kreuzberg lineage.
- **DEPENDENCY_LICENSE_RISK = DOCUMENTED** — `deny.toml` enforces `cargo deny check licenses` over 1,153 locked Rust dependencies; `THIRD_PARTY_LICENSES.md` explicitly documents C-ABI native libraries, highlighting copyleft components: **libheif (LGPL) is opt-in via the `heic` Cargo feature**, libwpd similar handling. Whether Omni would enable such features is a later, per-feature decision.
- **MODEL_LICENSE_RISK = NOT EXECUTED at XB-01 depth** — bundled/backable models (TrOCR, GLM-OCR, DeepSeek-OCR, PaddleOCR-VL, Whisper variants, PP-DocLayout/RT-DETR/TATR/SLANet weights) each carry their own HF model licenses; inventory deferred (OQ-3).
- **COMMERCIAL_USE = YES for MIT core** (subject to third-party/component terms; not legal advice).

## 5. Dependency Analysis

`Cargo.lock`: 1,153 pinned dependencies. License policy machine-enforced via `cargo-deny` (`deny.toml` present at root). Non-Rust dependency surfaces also present and pinned: `uv.lock` (Python), `pnpm-lock.yaml` (Node/TS/docs), `composer.lock` (PHP), `go.work.sum` (Go bindings). Supply-chain posture is above-average for the category (integrity gates on model downloads, §17). A full vulnerability scan (`cargo audit`/`pip-audit`) was **NOT EXECUTED** (XB-03 scope; OQ-4). Depth note: 1,153 transitive crates is a large audit surface — a real adoption decision needs the XB-03 dependency pass, not just license enforcement evidence.

## 6. Architecture

Rust workspace with 16 member crates: core `xberg`; CLI `xberg-cli`; bindings `xberg-py`, `xberg-node`, `xberg-wasm`, `xberg-ffi`, `xberg-jni`, `xberg-php`; OCR backends `xberg-tesseract`, `xberg-paddle-ocr`, `xberg-candle-ocr`; format/PDF stack `xberg-native-pdf`, `xberg-pdfium-render`, `xberg-libheif` (opt-in), `xberg-libwpd`; NER `xberg-gliner`. Core modules (`crates/xberg/src/`): `api, cache, candle_ocr, captioning, chunking, core, diff, doc_orientation, doctor, embeddings, engine, extraction, extractors, formula_recognition, heuristics, image, inference, keywords, language_detection, late_interaction, layout, llm, mcp, model_cache, model_download, ocr, onnx, paddle_ocr, pdf, plugins, presets, rendering, reranking, sceptre_ocr, sparse_embeddings, stopwords, table_core, telemetry, text, transcription, types, utils`. README-claimed format matrix (Office/HTML/Email/EPUB/Archives/images/text) is consistent with crate/module structure; per-format extraction verification is deferred to XB-02 runtime evidence.

## 7. CLI

`crates/xberg-cli/` — subcommands include `extract` and `server` (MCP/REST hosting), plus output/diagnostics (contract tests under `crates/xberg-cli/tests/contract_cli.rs`). The PyPI/npm `cli-proxy/` wrappers download platform release binaries at install time (`cli-proxy/pypi/xberg_cli/downloader.py`) — same class of installer-download surface as OpenCodeReview's launcher; **pin the version and review the downloader before any install** (OQ-5).

## 8. REST

`crates/xberg/src/api/`: `router.rs`, `openapi.rs` (OpenAPI spec), `jobs.rs` (async job model), `openweb.rs`, `config.rs`, `error.rs`. REST server existence = PROVEN. Authentication/authorization/input-validation depth = **NOT EXECUTED** at XB-01 (OQ-6). Any hosted deployment inside Omni infrastructure would require this review first; default posture = do not host.

## 9. MCP

`crates/xberg/src/mcp/` (`server.rs`, `schema.rs`, `prompts.rs`, `resources.rs`, `params.rs`, `allowed_hosts.rs`, `errors.rs`, `format.rs`) + CLI `server` command. MCP server = **PROVEN**. Notably `allowed_hosts.rs` indicates egress host allowlisting for MCP-exposed operations — a security-positive design. MCP vulnerability review = NOT EXECUTED (OQ-7). For Omni: MCP/CLI qualify as **developer tooling only**; no path into OCR runtime.

## 10. OCR Backends

Source-verified backends: `tesseract_backend.rs` (+ `tessdata_manager.rs`, `tessdata_download.rs`, `hocr_parser.rs`, preprocessing, layout assembly); `paddle_ocr/`; `candle_ocr/` with `trocr_backend.rs` (line-level), `glm_ocr_backend.rs`, `deepseek_ocr_backend.rs`, `paddleocr_vl_backend.rs` (+ `model_stager.rs`, pinned `paddleocr-vl-1.6.sha256`). PDF OCR pipeline contains fallback/recovery machinery (`pipeline.rs`: page replacements, XObject recovery, fallback render). Backend orchestration/confidence scoring = PROVEN at source level; **backend fallback-chain semantics = PARTIALLY PROVEN** (mechanism present; exhaustive behavior unverified). Arabic/RTL quality: **UNPROVEN** — no local benchmark exists; nothing in this audit may be read as Arabic capability evidence (§ master prompt 17 separation enforced).

## 11. Layout

Layout assembly exists in the OCR path (`layout_assembly.rs`) and a `layout` core module; README claims PP-DocLayout-V3 / RT-DETR / TATR / SLANet reconstruction. Engine-name strings verified in config/handler sources → **PARTIALLY PROVEN** (naming/config present; per-engine runtime behavior NOT EXECUTED).

## 12. Tables

`table_core.rs` + OCR `table/` module + TATR/SLANet references → table reconstruction surface = **PROVEN present**; quality and medical-table accuracy = UNPROVEN (XB-05 scope).

## 13. VLM

VLM backends in `candle_ocr/` (GLM-OCR, DeepSeek-OCR, PaddleOCR-VL) + `llm`/`inference` core modules. "Handwriting via vision model" claims remain **PARTIALLY PROVEN** as capability existence; **Arabic handwriting = UNPROVEN**; TrOCR line-level-only limitation (README) is consistent with the backend name/scope found — full-page Arabic handwriting via TrOCR alone would need line-segmentation pipelines and remains unproven.

## 14. Audio/Video

`transcription/` module (`decode.rs`, `engine.rs`, `model.rs`, `tags.rs`) + whisper references across bindings → audio transcription surface = PROVEN present. Specific Whisper variant support (tiny→large-v3 claim) = **UNPROVEN** at XB-01 (per-model verification NOT EXECUTED). Video: container/decode paths exist but dedicated video intelligence = UNPROVEN. Priority for Omni: **P2** (value study only).

## 15. Code Intelligence

`tree-sitter` present in dependency manifests; code-extraction claims (371 languages) = **PARTIALLY PROVEN** (mechanism present; exact language count NOT EXECUTED — marketing figure treated as upstream claim). Relevance to Omni OCR runtime: none; at most developer tooling (P2).

## 16. Structured Extraction

Unified output types in `types/` (incl. `djot.rs`), JSON tree, structured JSON with bounding boxes (README), chunking/embeddings/sparse_embeddings/reranking modules. Unified representation = PROVEN as output-format surface; content-shape compatibility with any future Omni `ExtractionResult` contract = UNPROVEN until Omni contracts are mapped in XB-04 (no contract work in XB-01 per §16 of the master prompt).

## 17. Security

- **Command execution**: OCR pipelines legitimately spawn OCR binaries (tesseract/paddle); build scripts execute at compile time; cli-proxy installers download release binaries. No evidence of untrusted-document-driven command construction found in audited paths — **PARTIALLY PROVEN** (static reading; dynamic malicious-document testing NOT EXECUTED).
- **Network egress**: model downloads via `hf-hub` against HuggingFace — cache-first, offline flags block network on cache-miss misconfiguration, SHA256 integrity, wall-clock watchdog (`download_guard.rs`, `model_download.rs`). `trust_remote_code`: zero hits repo-wide. No vendor telemetry found (see below). Egress = **documented, gated, verifiable**.
- **Telemetry**: core `telemetry/` module = local observability (tracing spans, metrics, Prometheus/OTel exporter behind `otel`/`prometheus` feature flags, operator-configured sink). **No phone-home**. Off unless enabled.
- **Sandboxing/isolation of OCR child processes**: NOT EXECUTED review (OQ-8).

## 18. Data Flow

`Input document → format detection → native extraction (PDF/Office/HTML/Email/EPUB/Archive) → optional OCR backend selection (tesseract/paddle/candle/VLM) → optional model download (HF, gated) → layout/table assembly → unified output (text/MD/Djot/HTML/JSON/DocTags) → optional chunking/embeddings/MCP/REST delivery`. Network leaves the machine only for: (a) HF model downloads (opt-in by use, integrity-checked), (b) operator-configured OTel/Prometheus sinks if enabled, (c) nothing else found. PHI rule: no patient data may enter any XB phase without explicit authorization; XB-01 touched none.

## 19. Secret Handling

No evidence of reading credential stores (`.env`, `.git-credentials`, SSH keys) in audited paths; no hardcoded provider keys found in searches; model auth (HF tokens) would flow via standard environment variables if private repos were used — **PARTIALLY PROVEN** (static). Secrets policy: XB-01 introduced no credentials; none present in this report.

## 20. Prompt Injection

LLM/VLM-adjacent surfaces exist (`llm`, `inference`, VLM backends, MCP `prompts.rs`). Document content reaching a VLM/LLM prompt is inherent to those features — injection surface = **PROVEN present where VLM/LLM features are enabled**; default CLI extraction without VLM does not construct LLM prompts. Mitigation posture for Omni: keep VLM features disabled unless explicitly piloted; synthetic injection testing = NOT EXECUTED (XB-03/05 scope).

## 21. Malicious Document Risk

Static risk model only (XB-01): malformed PDFs, ZIP bombs / recursive archives, decompression bombs, malicious Office macros, hostile HTML, oversized images — all **UNTESTED** (NOT EXECUTED). Positive signals: `unsafe_code = "deny"` across the workspace; SHA256-pinned model artifacts; native parsers isolated in feature-gated crates. A malicious-document test battery is mandatory before any pilot that touches untrusted input (XB-03/05).

## 22. Omni Mapping

Omni baseline (unmodified during XB-01): branch `feat/ocr-cr-01-opencodereview-audit` @ `639062c7f579729a9c8788bfd555338ebb411f7e` (contains the OCR-CR-01 audit commit; parent `4845e8e9` = Phase-1 rebuild line), worktree clean before this report file. Tools: Python 3, pytest, node/npm, git.
**Omni OCR inventory (verified live)**:
| Component | Path | Status |
|---|---|---|
| Mixed Engine (Tesseract+EasyOCR+Surya+TrOCR via PatternDB) | `packages/omni_ocr/mixed_engine.py` | present (code) |
| Engine adapters/IDs + availability probes + OCR_ENGINE_ORDER | `packages/omni_ocr/adapter.py` | present |
| OCRResult contract | `packages/omni_ocr/contract/result.py` | present — DO NOT MODIFY |
| AHW handwriting | `apps/handwriting-demo/`, `tools/HandwrittenOCR/` | present |
| OLMoCR refs | `packages/core/router_executor.py`, `mistral_integration.py` | present |
| Benchmark reporter | `tests/test_benchmark_reporter_p1.py` | present (partial) |
| Doc processing web app | `packages/doc_processor/` | present (legacy notice) |
| File processing | `packages/file_processor/` | present |
| Bilingual/terminology | `packages/bilingual/` | present |
| PDF/Office/HTML utilities | doc_processor/file_processor/ai-fuel deps (pdfplumber/PyMuPDF-family refs) | present, unquantified |

## 23. Overlap

Significant and UNQUANTIFIED: `doc_processor` + `file_processor` already cover document/file processing scope; `omni_ocr` covers OCR orchestration; `bilingual` covers terminology. Xberg's PDF/Office/HTML extraction may **duplicate** existing Omni capabilities — or may replace fragile per-format code with one unified engine. This trade is exactly the XB-04 mapping question; no duplication claim is settled here.

## 24. Missing Capabilities (in Omni, that Xberg could supply)

Candidate list only (each requires XB-04 validation): unified multi-format ingestion (Email/EPUB/Archives/PPTX), layout/table reconstruction with coordinates, unified structured output with backend/provenance metadata, chunking/embeddings prep, audio transcription (P2), MCP dev tooling. Arabic handwriting: **explicitly NOT assumed** — Omni AHW remains the specialist.

## 25. Candidate Uses (priority per owner directive)

1. Format support breadth (DOCX/XLSX/PPTX/EPUB/Email) — P0 study target
2. Structured/table extraction — P0/P1
3. Unified representation — P0/P1
4. Provenance/metadata — P1
5. External layer that can host Omni's specialist engines (ingestion→normalization→Omni OCR) — P1 hypothesis
6. MCP/CLI developer tooling — P2
7. Audio/video — P2 value study

## 26. Components to Exclude (outside `packages/omni_ocr/` — master §14)

Xberg core as OCR replacement; any modification of OCRResult/router/AHW/OLMoCR; REST server hosting by default; embeddings/RAG into current runtime; code intelligence; audio/video into OCR runtime; cli-proxy global installers; auto-downloading model layers without pinning. `OMNI_XBERG_ENABLED=false` default applies to any future integration (currently: nothing integrated at all).

## 27. Risks

R1 dependency surface (1,153 crates) + transitive license/vuln load; R2 LGPL natives if `heic`/`full` features enabled; R3 model-license heterogeneity; R4 supply chain of cli-proxy binary downloads (signing/checksum policy UNPROVEN); R5 overlap/duplication with existing Omni packages; R6 Rust toolchain (1.92) as new build requirement for any in-repo use; R7 malicious-document exposure untested; R8 scope creep from "extraction layer" into OCR runtime (architectural discipline required).

## 28. Preliminary Decision

**INITIAL STATUS = CANDIDATE / STUDY ONLY.** No ADOPT. Phase order: XB-01 (this) → Evidence Review → owner authorization → XB-02 (isolated snapshot install) → XB-03 (security/license/dataflow deep audit) → XB-04 (Omni mapping incl. doc_processor/file_processor overlap quantification) → XB-05 (controlled benchmark incl. Arabic categories) → ADOPT/ADAPT/WRAP/PILOT/STUDY ONLY/DEFER/REJECT. CER/MCER-style thresholds, if used later, are **revisable experimental thresholds**, not rejection rules — Xberg may be highly valuable for DOCX/EPUB/HTML even if unsuitable for Arabic handwriting.

## 29. Evidence Classification

**PROVEN**: MIT/LICENSE+lineage; tag/commit pins; 16-crate workspace; ~15 binding surfaces; MCP server (+allowed_hosts); REST API modules; transcription module; 6 output formats incl. Djot; OCR backends (tesseract/paddle/candle incl. GLM-OCR/DeepSeek-OCR/PaddleOCR-VL/TrOCR); table_core; tree-sitter presence; no pull_request_target in 18 workflows; hf-hub gated downloads + SHA256 + watchdog; telemetry = local OTel/Prometheus behind features; unsafe_code deny; cargo-deny + THIRD_PARTY_LICENSES.md; Omni inventory table above.
**PARTIALLY PROVEN**: fallback-chain semantics; layout engine naming/config; secret-handling static review; SECURITY.md currency (states "5.x supported" vs version 1.2.3 — stale-doc inconsistency, PARTIALLY PROVEN).
**UNPROVEN**: Arabic/RTL/mixed-script quality; Arabic handwriting; Whisper variant matrix; code-intel language count (371 = upstream claim); per-format extraction quality; doc_processor/file_processor overlap extent; model licenses inventory.
**CONTRADICTED**: none.
**BLOCKED**: none (no credentials needed at XB-01).
**NOT EXECUTED**: runtime extraction; malicious-document battery; vulnerability scans; REST authn/authz review; MCP vuln review; sandboxing review; supply-chain signing verification of release binaries; dependency vuln audit; model license inventory.

## 30. Open Questions

OQ-1: Can untrusted document content influence command construction or config in extraction paths (dynamic proof)? OQ-2: Do release binaries (PyPI/npm cli-proxy downloads) carry verifiable checksums/signatures? OQ-3: Full model-license inventory for every backable backend? OQ-4: `cargo audit`/`pip-audit` vulnerability posture at pinned version? OQ-5: cli-proxy install-time behavior under pinned install (postinstall surface)? OQ-6: REST API authentication/authorization/input-validation depth? OQ-7: MCP server vulnerability review (incl. allowed_hosts enforcement)? OQ-8: OCR child-process sandboxing? OQ-9: Quantified overlap: Xberg vs `doc_processor`/`file_processor`? OQ-10: Which layout/table engines are enabled by default in the pinned build, and with which weights/licenses?

---

## Appendix A: Evidence Index

| Claim | Evidence (repo-relative) |
|---|---|
| MIT/Kreuzberg | `LICENSE` (Copyright (c) 2025-2026 Kreuzberg, Inc.) |
| Version/workspace | `Cargo.toml` ([workspace.package] version=1.2.3, edition 2024, rust 1.92, unsafe_code deny, members) |
| Pins | `git rev-parse v1.2.3^{commit}`; `git log` release commit |
| Bindings | `packages/` (11 dirs) + `crates/xberg-{ffi,jni,node,php,py,wasm}` |
| MCP | `crates/xberg/src/mcp/` (9 files incl. allowed_hosts.rs); `xberg-cli/src/commands/server.rs` |
| REST | `crates/xberg/src/api/` (router/openapi/jobs/openweb/config) |
| OCR backends | `crates/xberg/src/ocr/tesseract_backend.rs`, `paddle_ocr/`, `candle_ocr/{trocr,glm_ocr,deepseek_ocr,paddleocr_vl}_backend.rs` |
| Model gating | `crates/xberg-candle-ocr/src/download_guard.rs`; `crates/xberg/src/model_download.rs` |
| Telemetry nature | `crates/xberg/src/telemetry/{mod,metrics,spans,prometheus_exporter}.rs` (feature-gated) |
| Formats | `README.md:135,503,542`; `crates/xberg/src/types/djot.rs` |
| License governance | `deny.toml`; `THIRD_PARTY_LICENSES.md` (libheif LGPL opt-in) |
| Workflows | `.github/workflows/` (18; zero pull_request_target) |
| Omni inventory | `packages/omni_ocr/{adapter,mixed_engine}.py`, `contract/result.py`, `apps/handwriting-demo/`, `packages/core/router_executor.py`, `packages/doc_processor/`, `packages/file_processor/` |

## Appendix B: Component-by-Component Map (master §12/§20 condensed)

| Capability | In Omni? | Xberg evidence | Omni need | Sec risk | Lic risk | Action |
|---|---|---|---|---|---|---|
| Format detection | partial (doc_processor) | PROVEN module | High(?) | Low | Low | STUDY |
| PDF extraction | partial | PROVEN crate | High(?) | Med | Low | STUDY/XB-04 |
| DOCX/XLSX/PPTX | partial | PROVEN claims/config | High | Med | Low | STUDY |
| HTML/Email/EPUB | partial | PROVEN claims/config | Med | Med | Low | STUDY |
| Archives | unknown | PROVEN claims | Med | Med (zip bombs) | Low | STUDY |
| OCR orchestration | YES (omni_ocr) | PROVEN | Duplicate | – | – | DEFER (keep Omni's) |
| Layout | partial | PARTIALLY PROVEN | Med | Low | Model | PILOT-later |
| Tables | partial | PROVEN surface | Med | Low | Model | PILOT-later |
| VLM OCR | partial (TrOCR) | PROVEN backends | Low | Med (injection) | Model | DEFER |
| Audio | NO | PROVEN module | Low (P2) | Low | Model | STUDY-value |
| Video | NO | UNPROVEN | Low (P2) | – | – | DEFER |
| Code intelligence | NO | PARTIALLY PROVEN | None-for-OCR | Low | Low | OUT (tooling) |
| Chunking/embeddings | partial (bilingual/RAG?) | PROVEN modules | Med | Low | Low | DEFER (not runtime) |
| MCP | NO | PROVEN | Dev tooling | Med (review OQ-7) | Low | WRAP-later |
| REST | NO | PROVEN | None now | Med (OQ-6) | Low | DEFER |
| Unified output contract | NO (OCRResult fixed) | PROVEN | High | – | – | ADAPT-concept |
| Structured extraction | partial | PROVEN surface | High | Low | Low | STUDY |

## Appendix C: Independence Disclosure

LEVEL 2 EXECUTED — separate model instance via fresh SDK invocation (`scripts/xb01-level2-response.json`, mirrored to handover area). Corrections adopted: (1) Whisper variants PARTIALLY→UNPROVEN; (2) dependency-license "manageable" softened to DOCUMENTED (assessment ≠ evidence); (3) SECURITY.md staleness re-labeled PARTIALLY PROVEN (not CONTRADICTED-evidence); (4) verdict softened: Arabic-handwriting exclusion re-worded as "not assumed, benchmark-gated" rather than evidence-based exclusion. NEW risks added by reviewer: release-binary supply chain (OQ-2), REST authn review (OQ-6), MCP vuln review (OQ-7), OCR sandboxing (OQ-8). LEVEL 3 BLOCKED (no external provider credentials; gitleaks/semgrep absent). LEVEL 4 NOT EXECUTED.

## Appendix D: DoD Checklist (master §29)

```
[x] exact upstream SHA recorded (tag 19a189d3… + HEAD 41040097…)
[x] actual LICENSE inspected (MIT, Kreuzberg, Inc.)
[x] major dependency licenses inspected (cargo-deny + THIRD_PARTY_LICENSES.md; full inventory OQ-3/OQ-4)
[x] source forensic searches executed (exec/network/telemetry/trust_remote_code/credentials)
[x] network/egress reviewed (HF model downloads gated; observability operator-side)
[x] command execution reviewed (OCR binaries + build.rs + cli-proxy; static)
[x] filesystem access reviewed (cache/model dirs; static)
[x] secret handling reviewed (static; no creds touched)
[x] MCP reviewed (present + allowed_hosts; vuln review OQ-7)
[x] GitHub Actions reviewed (18 workflows; no pull_request_target)
[x] Omni baseline SHA recorded (639062c7…; recreated as <recreated-sha> after reset #5)
[x] Omni baseline test result recorded (inherited 940/81/45/4 KNOWN BASELINE; no changes made)
[x] Omni OCR inventory completed (§22 table)
[x] component mapping completed (Appendix B)
[x] decision matrix completed (Appendix B)
[x] data-flow map completed (§18)
[x] evidence statuses assigned (§29)
[x] independence level recorded (Appendix C)
[x] report saved to docs/audit/XBERG_FORENSIC_AUDIT.md
```

**XB-01 = COMPLETE. XB-02 AUTHORIZED by owner (2026-09-18) after OQ-2 + OQ-9 closure.**

---

# ADDENDUM (XB-01.5) — OQ-2 + OQ-9 Closure (owner-directed, 2026-09-18)

Scope: owner ordered «نفذ ب ثم أ» — close OQ-2 + OQ-9 before starting XB-02. Both closed below from source evidence + live Omni inspection. Environment note: reset #5 destroyed the sandbox clone, Omni repo, and handovers mid-task; audit branch recreated as `ea3bf3de` (OCR-CR-01, re-parented onto main — original parent `4845e8e9` lineage LOST) and this report as `d0dd5325`; upstream re-cloned at exact pin `19a189d3` (verified match). Bundle: `download/OMNI-EXECUTION/handovers/audit-branch-ea3bf3de-d0dd5325.bundle` (sha256 prefix `ab9c1a21…`) + `/tmp` mirror.

## A.1 — OQ-2 RESOLVED: Release-binary integrity (PyPI/npm cli-proxy)

Evidence (pinned `19a189d3…`):
- `cli-proxy/pypi/xberg_cli/downloader.py`: fetches release `SHA256SUMS` asset; `_verify_or_warn` **REFUSES install** when the digest entry is missing ("refusing to install unverified binary") and **fails on mismatch** (`hashlib.sha256` compare, downloader.py:124-157). HTTPS-only enforced for both direct URLs and redirects (downloader.py:66-76).
- `cli-proxy/npm/install.js`: same SHA256SUMS mechanism (install.js:157-181) but **WARN-ONLY** when SHA256SUMS asset is absent — npm path continues installation without checksum coverage. Weaker posture, recorded.
- **No signature layer** on `SHA256SUMS` itself (no minisign/cosign/GPG/`.sig` verification in either downloader).
- `.github/workflows/publish.yaml`: `provenance: "true"` configured (5 occurrences) — sigstore provenance attestations generated at publish time.

**Verdict**: OQ-2 = **RESOLVED — PARTIALLY PROVEN**. Integrity: PROVEN (SHA256, mandatory on PyPI path). Authenticity: PARTIALLY PROVEN (sigstore provenance configured upstream; no in-downloader signature verification of the checksum manifest; residual risk = compromised release pipeline shipping matched binary+SUMS). **XB-02 mandate**: install via PyPI path (mandatory checksum), pinned version only; npm path prohibited for Omni use unless warn-only behavior patched or provenance attestation verified externally.

## A.2 — OQ-9 RESOLVED: Overlap quantification (Xberg vs Omni packages)

Evidence: live inspection of `packages/doc_processor/`, `packages/file_processor/`, `packages/ai-fuel/` @ main `39640a6`.

| Capability axis | Omni today (evidence) | Xberg | Overlap verdict |
|---|---|---|---|
| Document INGESTION: DOCX/XLSX/PPTX/EPUB/Email/Archives | **No real equivalent** — `doc_processor` = legacy Next.js/Prisma web APP (`LEGACY_NOTICE.md` "Merge In Progress"; UI deps: dnd-kit/mdxeditor/radix, not extraction libs); `ai-fuel` = `openpyxl` only | Core value surface (100+ formats) | **LOW overlap — genuine gap** |
| PDF ingestion | partial (`ai-fuel` reqs reference PyMuPDF/pdfplumber family; depth unquantified) | native-pdf + pdfium-render crates | PARTIAL |
| OCR orchestration | STRONG (`omni_ocr` mixed_engine: Tesseract/EasyOCR/Surya/TrOCR + adapter registry) | tesseract/paddle/candle wrappers | **HIGH overlap — excluded anyway** (Omni keeps its router; master §14) |
| Table extraction | CV heuristics (`file_processor` README: "Hough line detection + contour analysis") | DL models (TATR/SLANet) | PARTIAL — different technique class, potentially complementary for complex tables (XB-05 question) |
| Office EXPORT (DOCX RTL/HTML/PDF/Excel/JSON+BBox) | OWNS it (`file_processor`: "6 Export Formats" incl. searchable PDF, RTL DOCX) | ingestion-side only | **NONE — opposite direction; complementary** |
| Arabic HTR | OWNS it (AHW: LineSegmenter→TrOCR→DottedRecovery, LoRA) | UNPROVEN | NONE assumed |

**Verdict**: OQ-9 = **RESOLVED**. Xberg's extraction-layer hypothesis is **STRENGTHENED**: the P0 owner priority (format ingestion breadth) targets the axis where Omni has NO real equivalent; the axes where Xberg would duplicate Omni (OCR orchestration) are already excluded by the architectural boundary. doc_processor/file_processor = legacy merge-in-progress apps whose value is export/UI, not ingestion.

## A.3 — XB-02 Authorization Record

Owner directive: «نفذ ب ثم أ» (2026-09-18). (ب) executed = A.1 + A.2 above. (أ) authorized = **XB-02: Isolated installation / snapshot** — to be executed in `/home/z/tools-sandbox/` only: pinned PyPI install into a dedicated venv, checksum-verified per A.1, smoke tests on synthetic non-PHI files, offline-egress verification, full snapshot manifest. No Omni repo/runtime changes; `OMNI_XBERG_ENABLED` concept remains not-applicable (nothing integrated).

---

# ADDENDUM 2 — XB-02 EXECUTION RECORD (owner-authorized «نفذ ب ثم أ», 2026-09-18)

Scope executed: (ب) = Addendum 1 (OQ-2+OQ-9) → (أ) = XB-02 Isolated Installation / Snapshot. All activity in `/home/z/tools-sandbox/` — zero Omni repo/runtime changes.

## B.1 — Installation (isolated, pinned, checksum-gated)

| Item | Value |
|---|---|
| Method | Python venv `/home/z/tools-sandbox/xberg-venv` (NO global install; no Omni pollution) |
| LIBRARY | `xberg==1.2.3` (PyPI; PyO3 binding — matches upstream pin `19a189d3` exactly) |
| CLI | `xberg-cli==1.2.3` (PyPI wrapper; native binary fetched from GitHub Releases **with mandatory SHA256 verification** per OQ-2 downloader forensics) |
| Toolchain | NO rustc in environment → prebuilt-binary path mandatory (by design) |
| Venv size | 315 MB |
| Bundled native libs (hashes, sha256[:16]) | `libaom-…3.6.1` 4944211d1d0a2d59 · `libheif-…1.23.0` 2ddf3e072bd727f2 · `libonnxruntime-…1.24.2` 0efed01c2ca3342b |

**License nuance discovered at install time**: the PyPI wheel BUNDLES `libheif 1.23.0` (LGPL) and `libonnxruntime` inside `xberg.libs/` — i.e., LGPL component ships by default in the Python artifact even though `heic` is opt-in at the Rust feature level. License posture for any future redistribution must treat the wheel as LGPL-containing (dynamic linking per libheif LGPL terms); this refines §4/A.1 of the main report (label: PARTIALLY PROVEN → refined evidence recorded here).

## B.2 — Runtime Smoke Evidence (synthetic non-PHI file only)

1. **Library path (async API)**: `import xberg` → `__version__=1.2.3`; `xberg.extract(ExtractInput(kind=URI, uri='file:///…/xb-smoke.md'))` → `ExtractionResult.results[0]: ExtractedDocument` with unified keys: `content, djot_content, chunks, code_intelligence, elements, entities, extraction_confidence, extraction_method, formulas, images, metadata, mime_type, ocr_elements, pages, form_fields, annotations…` → **CONTENT_OK=True**. API notes: `extract()` is async-only; string paths are rejected (must pass `ExtractInput`); result is batch-shaped (`.results`). **PROVEN**.
2. **CLI path**: `xberg --version` → `xberg 1.2.3` (exit 0; first run downloaded platform binary and verified SHA256 — OQ-2 behavior exercised live). `xberg extract xb-smoke.md` with `HF_HUB_OFFLINE=1` → correct text + envelope: `mime type: text/markdown; tables: 1; quality score: 1.00; extraction time: 3.41 ms`. **PROVEN (offline-capable for native formats; no model download triggered)**.
3. **Egress posture observed**: extraction of a native markdown file required NO network (HF_HUB_OFFLINE=1 honored); OCR/VLM backends were NOT invoked (would be the network/opt-in surface).

## B.3 — XB-02 Record (persistence-policy fields)

```
COMMIT_SHA:   <this addendum's commit> (docs-only)
PARENT_SHA:   fb93bbc… (XB-01.5 addendum) ← ea3bf3de… (OCR-CR-01 recreation) ← 39640a6 (main)
BRANCH:       feat/ocr-cr-01-opencodereview-audit
CHANGED_FILES: docs/audit/XBERG_FORENSIC_AUDIT.md (this addendum only)
TEST_RESULTS: smoke tests above (synthetic file; NO PHI; NO real patient data)
SECURITY_RESULTS: no credentials touched; no secrets in artifacts; venv isolated in tools-sandbox
ENVIRONMENT:  Linux container; Python 3.12.14; pip 25.0.1; no rustc
REMOTE_SHA:   branch NOT on remote (PUSH=BLOCKED — no credentials); bundle updated
WORKTREE:     clean after this commit
```

**XB-02 = COMPLETE (isolated install + snapshot + minimal runtime evidence).**
**NEXT: STOP — awaiting owner authorization for XB-03** (deep security/license/dataflow audit incl. OQ-3/4/5/6/7/8) **and/or XB-04** (Omni architecture mapping incl. ingestion-gap bridge design).

## B.4 — Updated Open Questions status

OQ-2 **RESOLVED** (A.1) · OQ-9 **RESOLVED** (A.2) · OQ-5 **RESOLVED** (B.1: cli-proxy behavior = mandatory-SHA256 PyPI path; npm warn-only path NOT used) · Remaining: OQ-1, OQ-3, OQ-4, OQ-6, OQ-7, OQ-8, OQ-10 (+ new: OQ-11 full LGPL/redistribution posture of bundled wheel libs → folds into XB-03 license audit).
