# Changelog

All notable changes to the OmniMedical Suite project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

OmniMedical Suite is a merged monorepo combining **medical-doc-processor** (v3.2) and **OmniFile_Processor** (v5.0) into a unified Turborepo-based medical document intelligence platform.

---

## [Unreleased]

---

## [1.1.0] - 2026-05-26

### Added
- `SECURITY.md` — comprehensive security guide covering HIPAA, GDPR, and GPG best practices
- `Makefile` — 18 build, test, and deploy targets for streamlined development workflows
- CI/CD pipeline (`.github/workflows/ci.yml`) — automated lint, test, build, and security-audit stages
- Docker build & push workflow (`.github/workflows/docker.yml`) — GitHub Container Registry (GHCR) integration
- `apps/collector/` — Handwriting data collection application built with PyQt5
- Fixed all Python import paths (`modules.` → `packages.`) across 70+ files for correct monorepo resolution

### Fixed
- Import path resolution for `services/api/main.py` and all OmniFile packages
- Corrected module references introduced during the OmniFile_Processor merge

---

## [1.0.0] - 2026-05-26

### Added
- Initial merge of **medical-doc-processor** (v3.2) and **OmniFile_Processor** (v5.0) into a unified monorepo
- Turborepo monorepo structure: `apps/web`, `packages/*`, `services/api`, `infrastructure/`
- Next.js 16 web application with NextAuth.js v4, role-based access control (RBAC), and dark mode
- **UnifiedOCR adapter** (`packages/omni-ocr/`) — 6-engine fallback chain for robust OCR
- **MedicalNLPPipeline** (`packages/nlp/`) — 4-stage NLP processing (tokenize → correct → reconstruct → classify)
- **UnifiedLearning** (`packages/learning/`) — KNN + Active Learning + Pattern DB for continuous improvement
- 15 Python packages: `vision`, `nlp`, `security`, `medical`, `ai`, `evaluation`, `export`, `segmentation`, `config`, `audit`, `omni-core`, `training`, `interactive-learning`, `omni-ocr`, `desktop`
- FastAPI backend (`services/api/`) with 42+ REST endpoints
- AES-256-GCM encryption with PBKDF2 key derivation (480,000 iterations)
- Prisma ORM with 10 unified models (`User`, `ProcessedImage`, `OCRResult`, etc.)
- Docker setup: `Dockerfile.web`, `Dockerfile.api`, `docker-compose.yml` (6 services)
- Kubernetes deployment configs: namespace, api, celery, redis, storage, HPA, nginx
- Prometheus + Grafana monitoring stack with medical OCR dashboard
- 35+ Python tests and TypeScript tests
- Full Arabic/RTL language support across all components (OCR, NLP, UI)
- Comprehensive `README.md` (41 KB) with architecture documentation

[Unreleased]: https://github.com/your-org/omni-medical-suite/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/your-org/omni-medical-suite/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/your-org/omni-medical-suite/releases/tag/v1.0.0
