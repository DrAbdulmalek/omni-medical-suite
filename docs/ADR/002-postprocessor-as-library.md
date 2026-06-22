# ADR-002: Medical OCR Postprocessor as Installable Library

## Status
Accepted

## Context
The medical-ocr-postprocessor contains the core correction logic used across multiple repositories. Previously, this logic was duplicated or referenced as external code. We need a single source of truth for OCR post-processing that all projects can consume.

## Decision
Convert medical-ocr-postprocessor into a standard Python package with:
- `pyproject.toml` for PEP 621 compliant build configuration
- Stable public API: `correct_text()`, `mask_phi()`, `review_candidates()`, `batch_process()`
- Published as `medical-ocr-postprocessor` on PyPI (or installed from git)
- Optional dependency groups: `dev`, `monitoring`, `production`

## Consequences

### Positive
- Single source of truth for OCR correction logic
- Semantic versioning enables safe dependency management
- Easy to install: `pip install medical-ocr-postprocessor`
- Other repos can depend on it via `pip install git+https://github.com/DrAbdulmalek/medical-ocr-postprocessor.git`

### Negative
- Breaking changes to the postprocessor affect all consuming projects
- Requires maintaining backward compatibility or using deprecation warnings
- Additional maintenance burden for publishing

### Migration
All projects using OCR correction should replace inline logic with:
```python
from postprocessor import correct_text, mask_phi
result = correct_text("raw ocr text")
masked = mask_phi(result)
```
