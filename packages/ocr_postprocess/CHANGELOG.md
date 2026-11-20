# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2026-06-06

### Added
- **PostProcessor** class with Arabic/English medical text correction
- Arabic text normalization (alef, yaa, tatweel, diacritics)
- Built-in medical dictionary with 80+ terms (EN + AR)
- Three correction strategies: normalization → dictionary lookup → fuzzy match
- Batch correction with per-word confidence scores
- Arabic text validation (OCR artifact detection)
- Medical term coverage validation
- Custom dictionary loading from file
- Session statistics tracking
- **BatchProcessor** for concurrent processing (ThreadPoolExecutor/ProcessPoolExecutor)
- Configurable workers, auto-accept thresholds, flagged output directory
- Queue draining support for continuous processing
- **CLI**: `medical-ocr-postprocess correct|batch|validate`
- **Tests**: 37 unit tests with full coverage
- PyPI-ready packaging with optional extras: [dev], [monitoring], [production]
- GitHub Actions CI/CD (lint, test, benchmark, package, release)

### Dependencies
- Core: Pillow, numpy, python-Levenshtein, rapidfuzz
- Dev: pytest, black, ruff
- Monitoring: prometheus-client
- Production: celery, redis
