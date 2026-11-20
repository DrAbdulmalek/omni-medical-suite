# Dependency Strategy

## Decision: pyproject.toml Extras

All Python dependencies are now declared in the root `pyproject.toml` under
`[project.optional-dependencies]`.  This replaces the fragmented
`requirements-*.txt` files scattered across sub-packages with a single
source of truth.

### Why extras instead of requirements files?

| Aspect | requirements\*.txt | pyproject.toml extras |
|---|---|---|
| Install command | `pip install -r file.txt` | `pip install -e ".[group]"` |
| Composable? | Manual `-r` chaining | Native: `.[core,ocr,nlp]` |
| Version resolution | Per-file only | Cross-group, single lock |
| `pip freeze` / `pip show` | Shows file origin | Shows project + extras |
| PEP 621 compliant | No | Yes |
| IDE / tooling support | Limited | Full (pip, poetry, uv, ruff) |

---

## Installation Commands

```bash
# Bare install — minimal runtime (API server + basic CV + env)
pip install -e .

# Basic file processing + UI (Streamlit, Gradio, export, PDF)
pip install -e ".[core]"

# Add OCR engines (EasyOCR, PaddleOCR, Surya)
pip install -e ".[core,ocr]"

# Add NLP & translation (transformers, Arabic NLP, spell check)
pip install -e ".[core,nlp]"

# Add LLM/AI providers (OpenAI, Gemini, Mistral, token routing)
pip install -e ".[core,ai]"

# HuggingFace Spaces deployment (CPU-only, Gradio 6+)
pip install -e ".[hf]"

# Model training (higher-pin transformers, LoRA, experiment tracking)
pip install -e ".[core,training]"

# Development (testing + linting + type checking)
pip install -e ".[dev]"

# Full production install (core + ocr + nlp + ai + security + deployment + export)
pip install -e ".[full]"

# Custom combination
pip install -e ".[core,ocr,nlp,ai]"
```

---

## Extras Groups Reference

| Group | Size | Description |
|---|---|---|
| `core` | 21 deps | Web frameworks, data processing, file export, PDF, logging |
| `ocr` | 9 deps | OCR engines (EasyOCR, PaddleOCR, Surya), CV libs, ONNX |
| `nlp` | 17 deps | Transformers, Arabic NLP, translation, embeddings |
| `ai` | 8 deps | LLM providers, token routing, FHIR |
| `hf` | 14 deps | HuggingFace Spaces optimized (CPU-only, self-contained) |
| `training` | 19 deps | LoRA, quantization, experiment tracking, data augmentation |
| `dev` | 12 deps | pytest, ruff, mypy, bandit, pre-commit |
| `security` | 5 deps | Presidio PII, rate limiting, secrets detection |
| `deployment` | 5 deps | Gunicorn, Celery, Redis, Prometheus, ngrok |
| `export` | 4 deps | Excel, DOCX, PDF, HTML export |
| `full` | meta | Combines core + ocr + nlp + ai + security + deployment + export |
| `all` | 35 deps | Legacy flat list (backward compat, prefer `full`) |

### Base `dependencies` (always installed)

These 10 packages are installed with any `pip install -e .`:

`fastapi`, `uvicorn[standard]`, `numpy`, `opencv-python-headless`, `Pillow`,
`pytesseract`, `python-dotenv`, `cryptography`, `scikit-learn`, `rapidfuzz`

---

## Old requirements*.txt Files → New Extras Mapping

### Root-level (KEEP for Dockerfile compatibility)

| Old File | Status | New Equivalent |
|---|---|---|
| `requirements.txt` | **KEEP** — referenced by `Dockerfile.dev`, `Dockerfile.review` | `.[full]` |
| `requirements-dev.txt` | **KEEP** — referenced by `Dockerfile.dev`, `Dockerfile` | `.[dev]` |

### packages/file_processor/ (PRIMARY source)

| Old File | Status | New Equivalent |
|---|---|---|
| `requirements.txt` | CAN REMOVE | `.[full]` |
| `requirements-base.txt` | CAN REMOVE | `.[core]` + base deps |
| `requirements-core.txt` | CAN REMOVE | `.[core]` |
| `requirements-ocr.txt` | CAN REMOVE | `.[ocr]` |
| `requirements-ocr-basic.txt` | CAN REMOVE | `.[ocr]` (subset) |
| `requirements-ocr-advanced.txt` | CAN REMOVE | `.[ocr,nlp]` |
| `requirements-nlp.txt` | CAN REMOVE | `.[nlp]` |
| `requirements-nlp-arabic.txt` | CAN REMOVE | `.[nlp]` (subset) |
| `requirements-hf.txt` | **KEEP** — referenced by `Dockerfile` | `.[hf]` |
| `requirements-training.txt` | **KEEP** — referenced by `Dockerfile.training` | `.[core,training]` |
| `requirements-dev.txt` | CAN REMOVE | `.[dev]` |
| `requirements-full.txt` | CAN REMOVE | `.[full]` |
| `requirements-gateway.txt` | CAN REMOVE | `.[core,ai]` |
| `requirements-ai-gateway.txt` | CAN REMOVE | `.[ai]` |
| `requirements-deployment.txt` | CAN REMOVE | `.[deployment,security]` |
| `requirements-colab.txt` | CAN REMOVE | `.[core,ocr,nlp]` |

### packages/omnifile/ (mirror of file_processor)

| Old File | Status | New Equivalent |
|---|---|---|
| `requirements.txt` | CAN REMOVE | `.[full]` |
| `requirements-core.txt` | CAN REMOVE | `.[core]` |
| `requirements-ocr.txt` | CAN REMOVE | `.[ocr]` |
| `requirements-nlp.txt` | CAN REMOVE | `.[nlp]` |
| `requirements-hf.txt` | **KEEP** — referenced by `Dockerfile` | `.[hf]` |
| `requirements-dev.txt` | CAN REMOVE | `.[dev]` |
| `requirements-full.txt` | CAN REMOVE | `.[full]` |
| `requirements-colab.txt` | CAN REMOVE | `.[core,ocr,nlp]` |

### packages/handwriting/ (mirror of omnifile)

| Old File | Status | New Equivalent |
|---|---|---|
| `requirements.txt` | CAN REMOVE | `.[full]` |
| `requirements-core.txt` | CAN REMOVE | `.[core]` |
| `requirements-ocr.txt` | CAN REMOVE | `.[ocr]` |
| `requirements-nlp.txt` | CAN REMOVE | `.[nlp]` |
| `requirements-hf.txt` | **KEEP** — referenced by `Dockerfile` | `.[hf]` |
| `requirements-dev.txt` | CAN REMOVE | `.[dev]` |
| `requirements-full.txt` | CAN REMOVE | `.[full]` |
| `requirements-colab.txt` | CAN REMOVE | `.[core,ocr,nlp]` |

### apps/handwriting-demo/variants/handwriting-ocr/ (mirror)

| Old File | Status | New Equivalent |
|---|---|---|
| `requirements.txt` | CAN REMOVE | `.[full]` |
| `requirements-core.txt` | CAN REMOVE | `.[core]` |
| `requirements-ocr.txt` | CAN REMOVE | `.[ocr]` |
| `requirements-nlp.txt` | CAN REMOVE | `.[nlp]` |
| `requirements-hf.txt` | **KEEP** — referenced by `Dockerfile` | `.[hf]` |
| `requirements-dev.txt` | CAN REMOVE | `.[dev]` |
| `requirements-full.txt` | CAN REMOVE | `.[full]` |
| `requirements-colab.txt` | CAN REMOVE | `.[core,ocr,nlp]` |

### Other app/tool packages (KEEP — independent deployables)

| Old File | Status | Reason |
|---|---|---|
| `apps/ocr-demo/requirements.txt` | **KEEP** | Own Dockerfile |
| `apps/ocr-pipeline/requirements.txt` | **KEEP** | Own Dockerfile |
| `apps/collector/requirements.txt` | **KEEP** | Independent tool |
| `apps/trainer-ui/requirements.txt` | **KEEP** | Own Dockerfile |
| `apps/trainer-ui/hf-variant/requirements.txt` | **KEEP** | Own Dockerfile |
| `apps/handwriting-demo/requirements.txt` | **KEEP** | Own Dockerfile |
| `apps/handwriting-demo/hf-deploy/requirements.txt` | **KEEP** | Own Dockerfile |
| `apps/handwriting-demo/training/requirements.training.txt` | **KEEP** | Own Dockerfile |
| `tools/ai_fuel/requirements.txt` | **KEEP** | Own Dockerfile |
| `tools/telegram-channel-copier/requirements.txt` | **KEEP** | Independent tool |
| `tools/ops/telegram_forwarder/requirements.txt` | **KEEP** | Own Dockerfile |
| `tools/medical-ocr-trainer-hf/requirements.txt` | **KEEP** | Own Dockerfile |
| `tools/HandwrittenOCR/requirements.txt` | **KEEP** | Sub-project |
| `tools/HandwrittenOCR/backend/requirements-api.txt` | **KEEP** | Sub-project |
| `packages/ai-fuel/requirements.txt` | **KEEP** | Independent package |
| `packages/bilingual/requirements.txt` | **KEEP** | Independent package |
| `packages/desktop/requirements.txt` | **KEEP** | Qt desktop app |
| `packages/gt_core/requirements_ground_truth.txt` | **KEEP** | Ground truth system |
| `packages/core/requirements.txt` | **KEEP** | Core package |
| `packages/doc-processor/requirements.txt` | **KEEP** | Own Dockerfile |
| `packages/doc-processor/desktop/requirements.txt` | **KEEP** | Desktop variant |
| `packages/doc-processor/packages/core/requirements.txt` | **KEEP** | Sub-package |
| `packages/doc_processor/requirements.txt` | **KEEP** | Own Dockerfile |
| `packages/doc_processor/desktop/requirements.txt` | **KEEP** | Desktop variant |
| `packages/doc_processor/packages/core/requirements.txt` | **KEEP** | Sub-package |
| `hf-space/requirements.txt` | **KEEP** | Own Dockerfile |
| `hf-space/packages/core/requirements.txt` | **KEEP** | HF deployment |
| `packages/file_processor/archive/requirements/*` | **KEEP** | Historical archive |

---

## Migration Plan for "CAN REMOVE" Files

1. **Phase 1 (now):** pyproject.toml is the source of truth; old files remain.
2. **Phase 2:** Update all Dockerfiles to use `pip install -e ".[group]"` instead of `pip install -r requirements-*.txt`.
3. **Phase 3:** Remove the "CAN REMOVE" files once no Dockerfile or CI references them.

---

## Unique Dependencies Added During Consolidation

The following packages were found only in scattered sub-package requirements and
are now available via the appropriate extras group:

| Package | Group | Previously in |
|---|---|---|
| `mistralai` | `ai` | `packages/core/requirements.txt` |
| `fhir.resources` | `ai` | `packages/core/requirements.txt` |
| `tiktoken` | `ai` | `packages/ai-fuel/requirements.txt`, `requirements-gateway.txt` |
| `loguru` | `ai` | `requirements-gateway.txt` |
| `markdown-it-py` | `ai` | `requirements-gateway.txt` |
| `sentence-transformers` | `nlp` | `packages/ai-fuel/requirements.txt`, `packages/bilingual/requirements.txt` |
| `faiss-cpu` | `nlp` | `packages/ai-fuel/requirements.txt` |
| `striprtf` | `core` | `packages/gt_core/requirements_ground_truth.txt` |
| `imagehash` | `ocr` | `packages/desktop/requirements.txt` |
| `bitsandbytes` | `training` | `requirements-training.txt` |
| `trl` | `training` | `requirements-training.txt` |
| `wandb` | `training` | `requirements-training.txt` |
| `albumentations` | `training` | `requirements-training.txt` |
| `lmdb` | `training` | `requirements-training.txt` |
| `optimum` | `training` | `requirements-training.txt` |
| `factory-boy` | `dev` | `requirements-dev.txt` (root) |
| `faker` | `dev` | `requirements-dev.txt` (root) |
| `weasyprint` | `export` | `requirements.txt` (omnifile) |