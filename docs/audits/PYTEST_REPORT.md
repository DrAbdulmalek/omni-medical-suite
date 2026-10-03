# Pytest Report — omni-medical-suite

**Generated:** 2025-01-XX (Task 1d)
**Python:** 3.12.13 | **pytest:** 9.0.2

---

## Summary

| Status   | Count |
|----------|-------|
| **PASSED**  | **305** |
| **FAILED**  | **97**  |
| **SKIPPED** | **45**  |
| **ERRORS**  | **11**  |
| Collected (excl. errors) | 444 |

> **Previous report (CLEANUP_LOG.md)** said "270 passed, 19 failed, 39 skipped, 4 errors".
> The current numbers are significantly different: **305 passed** (up from 270), **97 failed** (up from 19), **45 skipped** (up from 39), **11 errors** (up from 4).
> The large increase in failures (97 vs 19) is primarily driven by missing optional dependencies (`torch`, `transformers`, `interactive_learning`) and ruff auto-fix regressions in core modules.

---

## Test Configuration

- **Config file:** `pytest.ini` (pyproject.toml config is ignored per pytest warning)
- **testpaths:** `tests`
- **addopts:** `-v --tb=short --strict-markers -p no:warnings`
- **asyncio_mode:** `auto`
- **pythonpath:** `. src packages`

---

## All 11 Errors (Collection + Runtime)

### Collection Errors (7) — Test files that cannot be imported at all

| # | Test File | Root Cause |
|---|-----------|------------|
| 1 | `tests/test_advanced_pipeline.py` | `ModuleNotFoundError: No module named 'torch'` |
| 2 | `tests/test_arabic_rtl.py` | `ModuleNotFoundError: No module named 'torch'` |
| 3 | `tests/test_build_training_data.py` | `ModuleNotFoundError: No module named 'tools.build_training_data'` |
| 4 | `tests/test_integration.py` | `ModuleNotFoundError: No module named 'packages.omni_ocr'` |
| 5 | `tests/test_mobile_review_server.py` | `ModuleNotFoundError: No module named 'mobile_review'` |
| 6 | `tests/test_ocr_engine.py` | `ModuleNotFoundError: No module named 'torch'` |
| 7 | `tests/test_preprocessor.py` | `ModuleNotFoundError: No module named 'torch'` |

### Runtime Errors (4) — Fixtures/methods missing at test time

| # | Test | Root Cause |
|---|------|------------|
| 8 | `tests/test_api_performance.py::TestAPIPerformance::test_ocr_latency` | Fixture `'benchmark'` not found (pytest-benchmark not installed) |
| 9 | `tests/test_sensitive_scanner.py::TestSensitiveDataScanner::test_scan_multiple_entities` | Fixture `'sensitive_text'` not found (missing fixture definition) |
| 10 | `tests/test_summarizer.py::TestTextSummarizer::test_summarize_returns_dict` | Fixture `'sample_text_en'` not found |
| 11 | `tests/test_summarizer.py::TestTextSummarizer::test_summarize_detects_language` | Fixture `'sample_text_ar'` not found |

---

## All 97 Failures by Category

### 1. Missing `torch` dependency (49 failures)

All fail with `ModuleNotFoundError: No module named 'torch'` at `packages/vision/batch_ocr.py:11`.

| Test File | Count | Classes |
|-----------|-------|---------|
| `tests/test_integration_full.py` | 40 | `TestHTRPipelineIntegration` (5), `TestErrorRecovery` (3), `TestDataIntegrity` (2 — 1 `interactive_learning`, 1 `torch`) |
| `tests/test_pipeline.py` | 15 | `TestTextReconstructor` (10), `TestImagePreprocessor` (5) |
| `tests/test_e2e.py` | 5 | `TestE2EHTRPipeline` |

### 2. Missing `interactive_learning` module (38 failures)

All fail with `ModuleNotFoundError: No module named 'interactive_learning'`.

| Test File | Count | Classes |
|-----------|-------|---------|
| `tests/test_integration_full.py` | 37 | `TestSecurityModule` (15), `TestMonitoringModule` (16), `TestVersioningModule` (6) |
| `tests/test_pipeline.py` | 0 | (included in torch count above via `modules`) |

### 3. Missing `modules` module (2 failures)

| Test | Root Cause |
|------|------------|
| `tests/test_pipeline.py::TestPipelineOptions::test_default_engine_config` | `ModuleNotFoundError: No module named 'modules'` |
| `tests/test_pipeline.py::TestPipelineOptions::test_custom_engine_config` | `ModuleNotFoundError: No module named 'modules'` |

### 4. Missing `transformers` module (1 failure)

| Test | Root Cause |
|------|------------|
| `tests/test_htr.py::TestFineTunedTrOCR::test_recognize` | `ModuleNotFoundError: No module named 'transformers'` |

### 5. Ruff auto-fix regression: `callable` type hint (10 failures)

All fail with `TypeError: unsupported operand type(s) for |: 'builtin_function_or_method' and 'NoneType'` at `packages/nlp/summarizer.py:390`.

**Root cause:** Ruff auto-fixed `Optional[Callable[..., ...]]` → `callable | None`, but `callable` is the **builtin function** (not `collections.abc.Callable`). The `|` union operator does not work on builtin function objects.

| Test File | Count |
|-----------|-------|
| `tests/test_summarizer.py` | 10 |

### 6. Ruff auto-fix regression: Missing `Path` import (7 failures)

All fail with `NameError: name 'Path' is not defined` at `tests/test_spell_checker.py:11`.

**Root cause:** The test uses `Path()` but doesn't have `from pathlib import Path`. Ruff may have removed a wildcard import or the import was never present.

| Test File | Count |
|-----------|-------|
| `tests/test_spell_checker.py` | 7 |

### 7. Test signature mismatch: `return_info` kwarg (1 failure)

| Test | Root Cause |
|------|------------|
| `tests/test_htr.py::TestProjectionProfileSegmenter::test_segment_with_info` | `TypeError: mock_segment() got an unexpected keyword argument 'return_info'` — the mock function doesn't accept the `return_info` kwarg that the production code passes |

### 8. Dictionary/TMX domain logic failures (3 failures)

See **Detailed TMX Analysis** below.

| Test | Root Cause |
|------|------------|
| `tests/dictionaries/test_dictionary_system.py::TestTMXMedicalExtractor::test_detect_medical_category_fracture` | Pattern matching bug: `CT` in radiology pattern matches substring "ct" in "fra**ct**ure" |
| `tests/dictionaries/test_dictionary_system.py::TestTMXMedicalExtractor::test_detect_medical_category_generic` | Pattern matching bug: `test` in lab_values pattern matches common word "test" |
| `tests/dictionaries/test_dictionary_system.py::TestDictionaryManager::test_export_to_json` | sqlite3.Row iteration bug: `{k: row[k] for k in row}` iterates values not keys |

---

## Detailed TMX Processor Analysis

### Failure 1: `test_detect_medical_category_fracture`

**File:** `tests/dictionaries/test_dictionary_system.py:204-206`
**Code under test:** `packages/medical/tmx_processor.py:527-540` (`TMXMedicalExtractor._detect_medical_category`)

**What the test expects:**
```python
category = self.extractor._detect_medical_category("fracture of the femur")
self.assertEqual(category, "fractures")  # expects "fractures"
```

**What actually happens:**
```
Actual:   'radiology'
Expected: 'fractures'
```

**Root cause — Over-broad regex patterns without word boundaries:**

The `_detect_medical_category` method scores each medical category by counting regex matches in the input text. The patterns are defined in `MEDICAL_PATTERNS` (tmx_processor.py:152-181):

| Category | Pattern that matches | Score contribution |
|----------|---------------------|-------------------|
| anatomy | `femur` (English pattern) | +1 |
| fractures | `fracture` (English pattern) | +1 |
| **radiology** | `CT` (English pattern, IGNORECASE) matches substring "ct" in "fra**ct**ure" | +2 |
| **radiology** | `CT` (Arabic pattern, IGNORECASE) also matches "ct" in "fra**ct**ure" | — |

The radiology pattern `r"(X-ray|radiograph|MRI|CT|ultrasound|scan|imaging|...)"` contains `CT` without word boundaries (`\b`). With `re.IGNORECASE`, the bare pattern `CT` matches any occurrence of the letters "ct" in the text, including the substring in "fra**ct**ure".

Since radiology scores 2 (matches in both `ar` and `en` sub-patterns) while anatomy and fractures each score 1, the `max(scores, key=scores.get)` call returns `"radiology"`.

**Fix needed:** Add `\b` word boundaries to the radiology pattern: `r"(\bX-ray\b|\bradiograph\b|\bMRI\b|\bCT\b|...)"` or use `(?<!\w)` / `(?!\w)` lookarounds. The same issue likely affects other patterns (e.g., `scan` matching "ab**scan**", `test` in lab_values).

---

### Failure 2: `test_detect_medical_category_generic`

**File:** `tests/dictionaries/test_dictionary_system.py:216-218`

**What the test expects:**
```python
category = self.extractor._detect_medical_category("hello world test")
self.assertEqual(category, "general_medical")  # expects default fallback
```

**What actually happens:**
```
Actual:   'lab_values'
Expected: 'general_medical'
```

**Root cause — Same class of bug: over-broad pattern without word boundaries:**

The `lab_values` English pattern (line 175) is:
```python
r"(lab|test|hemoglobin|platelet|WBC|RBC|glucose|ESR|CRP|calcium|phosphorus|uric.acid|creatinine)"
```

The bare word `test` matches the common English word "test" in the input "hello world **test**". This gives `lab_values` a score of 1, making it the only category with a non-zero score, so `max()` returns `"lab_values"` instead of falling through to the default `"general_medical"`.

**Fix needed:** Add `\b` word boundaries to the lab_values pattern and all other patterns. E.g., `r"(\blab\b|\btest\b|\bhemoglobin\b|...)"`. Alternatively, a minimum score threshold could be used before assigning a category instead of the default.

---

### Failure 3: `test_export_to_json`

**File:** `tests/dictionaries/test_dictionary_system.py:303-316`
**Code under test:** `packages/medical/dictionary_manager.py:921-959` (`MedicalDictionaryManager.export_to_json`)

**What the test expects:**
```python
self.manager.import_dictionary(json_path)       # import 1 entry
result = self.manager.export_to_json(output_path)
self.assertTrue(result)                          # expects True (successful export)
self.assertTrue(os.path.exists(output_path))     # expects file to exist
```

**What actually happens:**
```
AssertionError: False is not true
Logged: ERROR packages.medical.dictionary_manager:dictionary_manager.py:956 فشل التصدير: No item with that key
```

**Root cause — Incorrect sqlite3.Row iteration:**

The problematic code is at line 947:
```python
data["entries"] = [
    {k: row[k] for k in row} for row in terms
]
```

`terms` is a list of `sqlite3.Row` objects (because `conn.row_factory = sqlite3.Row` at line 135).

The critical misunderstanding: **iterating over a `sqlite3.Row` yields its column VALUES, not column names.** So:
- `for k in row` yields values like `'اختبار'`, `'test'`, etc.
- `row[k]` then tries `row['اختبار']` — using the value as a key lookup
- Since `'اختبار'` is not a column name, `sqlite3.Row.__getitem__` falls through to integer conversion
- The integer conversion of `'اختبار'` fails, raising `IndexError: No item with that key`

The exception is caught by the broad `except Exception as e:` at line 955, which logs it and returns `False`.

**Verified with debug script:**
```python
>>> row = conn.execute('SELECT a, b FROM t').fetchone()
>>> for k in row:
...     print(f'  k={k!r}')     # prints values: 'x', 'y' — NOT 'a', 'b'
>>> dict(row)                    # works correctly: {'a': 'x', 'b': 'y'}
```

**Fix needed:** Replace `{k: row[k] for k in row}` with `dict(row)` (simplest and most correct), or use `{k: row[k] for k in row.keys()}`.

---

## Failure Breakdown by Root Cause

| Root Cause Category | Count | Fixable without new deps? |
|---------------------|-------|---------------------------|
| Missing `torch` (GPU/vision) | 49 | Yes — add `@pytest.mark.skipif(not HAS_TORCH)` |
| Missing `interactive_learning` | 38 | Yes — add skip markers or mock the module |
| Ruff auto-fix: `callable` type hint | 10 | Yes — change `callable` to `Callable` with import |
| Ruff auto-fix / missing import: `Path` | 7 | Yes — add `from pathlib import Path` |
| Missing `modules` package | 2 | Yes — fix import path or mock |
| Missing `transformers` | 1 | Yes — add skip marker |
| TMX pattern matching (no word boundaries) | 2 | Yes — add `\b` to regex patterns |
| sqlite3.Row iteration bug | 1 | Yes — use `dict(row)` |
| Test signature mismatch (`return_info`) | 1 | Yes — fix mock signature |
| Missing `packages.omni_ocr` module | 0 (error) | Yes — fix module structure or skip |
| Missing `mobile_review` module | 0 (error) | Yes — fix module structure or skip |
| Missing `tools.build_training_data` | 0 (error) | Yes — fix module structure or skip |
| Missing `benchmark` fixture | 0 (error) | Yes — install pytest-benchmark or skip |
| Missing test fixtures | 0 (error) | Yes — add fixture definitions |
| **Total** | **97 + 11 = 108** | |

---

## Recommendations

### Priority 1 — Code fixes (3 issues, resolve 13 test failures)
1. **tmx_processor.py:** Add `\b` word boundaries to all `MEDICAL_PATTERNS` regex patterns to prevent substring false matches
2. **dictionary_manager.py:947:** Change `{k: row[k] for k in row}` to `dict(row)`
3. **summarizer.py:390:** Change `callable` to `collections.abc.Callable` (with proper import)

### Priority 2 — Test fixes (2 issues, resolve 7 test failures)
4. **test_spell_checker.py:** Add `from pathlib import Path` import
5. **test_htr.py:** Update mock signature to accept `return_info` keyword argument

### Priority 3 — Skip markers for missing dependencies (resolve 91 failures/errors)
6. Add `@pytest.mark.skipif(not HAS_TORCH, reason="torch not installed")` to all torch-dependent tests
7. Add similar skip markers for `transformers`, `interactive_learning`, `modules`
8. Add conftest fixtures for `benchmark`, `sensitive_text`, `sample_text_en`, `sample_text_ar`
9. Fix module paths for `packages.omni_ocr`, `mobile_review`, `tools.build_training_data` or add skip markers