# ADR-004: Unified CI/CD Pipeline

## Status
Accepted

## Context
Each repository had inconsistent or absent CI/CD. Some had no tests, no linting, and no automated quality gates. We need a standardized pipeline that ensures code quality across the ecosystem.

## Decision
Create a unified GitHub Actions CI/CD pattern with:
- **Lint**: ruff for Python, npm lint for Node.js
- **Test**: pytest for Python, npm test for Node.js
- **Build**: Docker build validation on main pushes
- **Matrix testing**: Multiple Python versions for core libraries
- **Conditional jobs**: Benchmark runs only on main, Docker builds only on main

Each repository gets its own `.github/workflows/ci.yml` following this pattern.

## Consequences

### Positive
- Every push gets quality-checked automatically
- Breaking changes caught early in PRs
- Consistent quality standards across all repos
- Benchmark tracking for performance regressions

### Negative
- Initial setup effort for repos without tests
- CI failures may block development if not triaged quickly

### Template Repositories
The following repositories now have CI/CD:
- medical-ocr-postprocessor: Lint → Test (3.10/3.11/3.12) → Benchmark
- omni-medical-suite: Lint Python + Lint Frontend → Test → Docker Build
- medical-handwriting-ocr: Lint → Test → Docker Build
- medical-ocr-trainer: Lint → Test → Streamlit Health Check
