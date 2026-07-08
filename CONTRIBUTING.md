# Contributing to Omni Medical Suite

Thank you for your interest in contributing! This guide covers the monorepo structure, development workflow, and coding standards.

## Table of Contents

- [Quick Start](#quick-start)
- [Monorepo Structure](#monorepo-structure)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Commit Convention](#commit-convention)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)

## Quick Start

1. **Fork** the repository
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/omni-medical-suite.git
   cd omni-medical-suite
   ```
3. **Install** dependencies:
   ```bash
   python -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```
4. **Create a branch**:
   ```bash
   git checkout -b feat/your-feature
   ```
5. **Make changes**, test, commit, push, open PR.

## Monorepo Structure

This is a monorepo with 31 packages and 5 applications. Changes should be scoped to the relevant package or app.

```
omni-medical-suite/
├── src/              # Core library (OCR engine, NER, LLM, Layout)
├── packages/         # Reusable packages — modify the specific package
├── apps/             # Standalone apps — modify the specific app
├── app/              # Main Gradio HITL application
├── config/           # Shared configuration files
├── tests/            # Monorepo-level tests
└── docs/             # Documentation
```

**Rule**: If you modify code in `packages/nlp/`, only that package is affected. Keep changes scoped.

## Development Setup

### Prerequisites

- Python 3.10+
- Docker + Docker Compose (optional)
- Git

### Install

```bash
# Core dependencies
pip install -r requirements.txt

# Optional: OCR engines
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu

# Dev tools
pip install -r requirements-dev.txt

# Or install everything at once
pip install -e ".[all,dev]"
```

### Environment Variables

```bash
cp .env.example .env
# Edit .env with your settings
```

### Run Locally

```bash
# Gradio HITL UI
python app/gradio_full_hitl.py

# Or via Makefile
make dev
```

### Docker

```bash
# Full stack
docker-compose up -d

# Lite (OCR only)
docker-compose -f docker-compose.lite.yml up -d

# Rebuild after changes
docker-compose build gradio && docker-compose up -d gradio
```

## Code Style

We use **ruff** for linting and formatting (replaces black + flake8 + isort).

```bash
# Check all source code
ruff check src/ packages/ app/ tests/

# Auto-fix
ruff format src/ packages/ app/ tests/
ruff check --fix src/ packages/ app/ tests/
```

### Style Rules

- **Line length**: 100 characters
- **Quotes**: Double quotes
- **Imports**: stdlib → third-party → local (auto-sorted by ruff)
- **Docstrings**: Google style for public functions
- **Type hints**: Required for function signatures
- **Arabic comments**: Allowed alongside English

### Critical Version Constraints

| Package | Constraint | Reason |
|---------|-----------|--------|
| `huggingface_hub` | `<1.0.0` | HfFolder removed in 1.0 |
| `pydantic` | `<2.11.0` | JSON schema boolean crash |
| `gradio` | `>=4.44.0,<5.0.0` | API stability |
| `numpy` | `<2.0.0` | OpenCV compatibility |

## Testing

### Run Tests

```bash
# All tests (excluding slow/load tests)
pytest tests/ -q --ignore=tests/loadtest --ignore=tests/dictionaries

# With coverage
pytest tests/ --cov=src --cov=packages --cov-report=html

# Specific package
pytest tests/test_spell_checker.py -v

# Integration tests only
pytest tests/ -m integration -v

# Run with markers
pytest tests/ -m "not slow and not gpu" -q
```

### Available Markers

| Marker | Description |
|--------|-------------|
| `slow` | Tests that take > 10s |
| `benchmark` | Performance benchmarks |
| `integration` | Integration tests (need DB/Redis) |
| `ocr` | Tests requiring OCR engines |
| `nlp` | Tests requiring NLP models |
| `gpu` | Tests requiring GPU |

### Write Tests

```python
# tests/test_example.py
import pytest
from packages.nlp.spell_checker import HybridSpellChecker

class TestSpellChecker:
    def test_protects_medical_terms(self):
        """Medical terms should not be 'corrected'."""
        checker = HybridSpellChecker()
        result = checker.correct("Metformin 500mg")
        assert "Metformin" in result

    def test_handles_empty_input(self):
        checker = HybridSpellChecker()
        assert checker.correct("") == ""
```

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>
```

### Types

| Type | Description | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(ocr): add Surya engine support` |
| `fix` | Bug fix | `fix(nlp): handle empty Arabic text` |
| `docs` | Documentation | `docs: update architecture diagrams` |
| `refactor` | Code refactoring | `refactor(core): extract DB helpers` |
| `perf` | Performance | `perf(ensemble): parallelize OCR engines` |
| `test` | Tests | `test(nlp): add spell checker edge cases` |
| `chore` | Build/CI/deps | `chore(deps): update paddleocr to 2.8` |
| `ci` | CI/CD | `ci: add security scanning step` |

### Scopes

Use the package or app directory name: `ocr`, `nlp`, `vision`, `medical`, `core`, `scanner_fixer`, `training`, `gradio`, `api`, `docker`, `ci`.

## Pull Request Process

1. **Before PR**: Run `ruff check`, `pytest tests/ -q`, update docs if needed
2. **PR title**: Use conventional commit format
3. **PR body**: Describe what, why, and how to test
4. **CI**: All checks must pass (lint, type-check, tests, build)
5. **Review**: At least 1 approval required
6. **After merge**: Delete your branch

## Release Process

1. Update `pyproject.toml` version
2. Update `CHANGELOG.md`
3. Create and push tag:
   ```bash
   git tag -a v1.2.0 -m "Release v1.2.0"
   git push origin v1.2.0
   ```
4. CI triggers Docker build + HF Space deploy + GitHub Release

## Questions?

- [Open an issue](https://github.com/DrAbdulmalek/omni-medical-suite/issues)
- [Discussions](https://github.com/DrAbdulmalek/omni-medical-suite/discussions)