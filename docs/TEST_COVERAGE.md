# Test Coverage Report

**Date:** 2026-07-12 (updated)
**Tool:** pytest 9.0.2 + pytest-cov 7.0.0
**Python:** 3.12.13

## Results

| Package | Tests | Passed | Failed | Errors | Skipped | Coverage | Notes |
|---------|------:|-------:|-------:|-------:|--------:|--------:|-------|
| packages/handwriting | 158 | 139 | 19 | — | 0 | 22% | **Fixed:** 4 test files unblocked (was 14%, 53 passed) |
| packages/file_processor | 162 | 107 | 54 | 10 | 1 | 16% | 1 test file still has unrelated import error |
| packages/omnifile | 51 | 22 | 29 | — | 0 | 17% | **Fixed:** test_ocr_engine.py unblocked (was 15%, 13 passed) |
| packages/nlp | 0 | — | — | — | — | 0% | No tests found |
| packages/vision | 0 | — | — | — | — | 0% | No tests found |

## Before/After: progress_tracker Fix

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| handwriting: tests collected | 138 (4 files skipped) | 158 | **+20 tests unblocked** |
| handwriting: tests passed | 53 | 139 | **+86 passed** |
| handwriting: coverage | 14% | 22% | **+8pp** |
| file_processor: tests collected | 183 (1 file skipped) | 162 | 1 file still blocked (unrelated) |
| file_processor: tests passed | 111 | 107 | -4 (different skip pattern) |
| omnifile: tests collected | 42 (1 file skipped) | 51 | **+9 tests unblocked** |
| omnifile: tests passed | 13 | 22 | **+9 passed** |
| omnifile: coverage | 15% | 17% | **+2pp** |

## Remaining Collection Error

`file_processor/tests/test_ocr_engine.py` still fails to collect with:
```
ModuleNotFoundError: No module named 'modules'
```
This is a separate issue (test file uses `from modules.vision.ocr_engine import OCREngine` but the package's own pyproject.toml sets rootdir inside the package). Not caused by the progress_tracker gap.

## Failure Patterns

- **Integration tests** across all three tested packages fail heavily (import-time dependencies on missing modules like `modules.vision.normalize`, `modules.vision.table_detection`, missing config classes, etc.).
- **Unit tests** (e.g., `test_fusion.py`, `test_layout_preserving.py`, `test_markdown_exporter.py` in handwriting; `test_protected_vocab.py`, `test_audit_logger.py` in file_processor) tend to pass.
- `file_processor` has 10 test errors in `test_api_performance.py` and `test_ocr.py` (likely missing test fixtures/dependencies).
- `file_processor` spell checker tests (6 failures) likely need NLP dependencies.

## Notes

- Coverage is a baseline measurement for future improvement tracking.
- Tests requiring GPU or external services may be skipped.
- The `packages/nlp` and `packages/vision` directories contain source code (3,106 and 5,035 statements respectively) but have **no test files** — test coverage is a priority gap.
- The `progress_tracker` blocker is **resolved** — 86 additional tests now pass in handwriting, 9 more in omnifile.
