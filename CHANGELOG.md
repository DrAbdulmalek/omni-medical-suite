# Changelog

All notable changes to OmniMedical Suite will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2026-07-07

### Fixed
- **Alembic migrations**: Fixed `migrations/env.py` to import Base from `app.db.models.auth` instead of non-existent `app.core.database` and `app.models.document`
- **Migration completeness**: Replaced documents-only migration with comprehensive migration covering all 13 tables (RBAC, documents, jobs)
- **Database URL resolution**: Fixed `DATABASE_URL` environment variable conflict — env.py now reads `alembic.ini` directly and validates URL format before using env vars
- **app/main.py**: Removed references to non-existent `async_scoped_session`, `AsyncSessionLocal`, and `health_check` symbols; made package routers optional with graceful fallback
- **Missing routers**: Created stub routers for pipeline, ocr, jobs, datasets, models, and admin endpoints
- **app/db/models/__init__.py**: Populated empty file with proper re-exports of all RBAC models
- **Condition Parser**: Fixed `ConditionParser()` instantiation — removed invalid `fail_closed` keyword argument
- **8 syntax errors**: Fixed unterminated f-strings, invalid syntax, and unexpected indents across desktop/ and packages/ directories
- **Pydantic compatibility**: Updated all 6 config files (app, security, database, ocr, ml, storage) with v1/v2 import fallback pattern

### Added
- **Complete RBAC migration**: 13 database tables created by Alembic — users, roles, permissions, role_permissions, user_role_assignments, user_permission_assignments, audit_logs, jobs, user_sessions, refresh_tokens, documents, corrections, processing_tasks
- **Router stubs**: 6 new API router modules (pipeline, ocr, jobs, datasets, models, admin) with placeholder endpoints

### Security
- **Safe Condition Parser**: Verified fail-closed behavior — `exec()`, `eval()`, `import`, `__import__` and all dangerous AST nodes are blocked
- **Pydantic v2 readiness**: All config classes support both pydantic v1 and v2 (via `pydantic.v1` compat layer)

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