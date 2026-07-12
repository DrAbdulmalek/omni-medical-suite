# Test Coverage Report

**Date:** 2026-07-12
**Tool:** pytest 9.0.2 + pytest-cov 7.0.0
**Python:** 3.12.13

## Results

| Package | Tests | Passed | Failed | Errors | Skipped | Coverage | Notes |
|---------|------:|-------:|-------:|-------:|--------:|--------:|-------|
| packages/handwriting | 138 | 53 | 19 | — | 0 | 14% | 4 test files skipped due to import error; 66 tests not collected |
| packages/file_processor | 183 | 111 | 61 | 10 | 1 | 17% | 1 test file skipped due to import error |
| packages/omnifile | 42 | 13 | 29 | — | 0 | 15% | 1 test file skipped due to import error |
| packages/nlp | 0 | — | — | — | — | 0% | No tests found |
| packages/vision | 0 | — | — | — | — | 0% | No tests found |

## Collection Errors

Three packages (`handwriting`, `file_processor`, `omnifile`) have test files that fail to collect due to a shared root cause:

```
ModuleNotFoundError: No module named 'packages.core.progress_tracker'
```

This import is triggered when test files import `modules.vision.layout_analyzer`, which chains through to `packages.core.__init__` (line 86). The missing `progress_tracker` module blocks collection of all tests in the affected files.

**Affected test files (skipped via `--ignore` to obtain partial results):**

| Package | Skipped Test File |
|---------|-------------------|
| handwriting | `test_advanced_pipeline.py`, `test_arabic_rtl.py`, `test_ocr_engine.py`, `test_preprocessor.py` |
| file_processor | `test_ocr_engine.py` |
| omnifile | `test_ocr_engine.py` |

## Failure Patterns

- **Integration tests** across all three tested packages fail heavily (import-time dependencies on missing modules, missing config classes, etc.).
- **Unit tests** (e.g., `test_fusion.py`, `test_layout_preserving.py`, `test_markdown_exporter.py` in handwriting; `test_protected_vocab.py`, `test_audit_logger.py` in file_processor) tend to pass.
- `file_processor` has 10 test errors in `test_api_performance.py` and `test_ocr.py` (likely missing test fixtures/dependencies).
- `file_processor` spell checker tests (6 failures) likely need the `progress_tracker` module or related NLP dependencies.

## Notes

- Coverage is a baseline measurement for future improvement tracking.
- Tests requiring GPU or external services may be skipped.
- The `packages/nlp` and `packages/vision` directories contain source code (3,106 and 5,035 statements respectively) but have **no test files** — test coverage is a priority gap.
- The missing `packages.core.progress_tracker` module is the single largest blocker; restoring or stubbing it would unblock ~100+ tests across three packages.
