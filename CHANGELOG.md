# Changelog

All notable changes to OmniMedical Suite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.0] - 2026-06-03

### Added
- PORTFOLIO.md — unified project architecture map with 4-layer diagram
- Repository Status sections added to all 10 ecosystem repositories
- GitHub Topics added to all repositories for discoverability
- UPSTREAM.md added to omniparse fork repository
- env.example.production — production environment variable template
- scripts/generate-secrets.sh — automated secret generator
- docs/ADR/ — Architecture Decision Records (5 ADRs)
- Docker deployment profiles (lite/standard/gpu-production) for medical-handwriting-ocr
- evaluation/benchmark_runner.py — standardized benchmark tool
- .github/workflows/ci.yml — CI/CD pipelines for 4 repositories
- pyproject.toml — package configuration for medical-ocr-postprocessor
- API contract test suite for medical-ocr-postprocessor

### Changed
- All repository descriptions updated with role and status information
- README unified sections added (Status, Role, Priority, Relation, When to Use)

## [2.0.0] - 2026-05-28

### Added
- Initial merge of medical-doc-processor (v3.2) and OmniFile_Processor (v5.0)
- Multi-Engine OCR Fusion V2 with 6 engines and fallback
- Medical NLP Pipeline (4 stages)
- Qdrant VectorStore integration
- MedicalContextProtector
- AutoPromotionEngine
- CorrectionMemory V2
- BenchmarkSuite
- AES-256-GCM encryption
- NextAuth + RBAC authentication
