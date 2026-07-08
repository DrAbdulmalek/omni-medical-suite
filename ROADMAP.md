# Roadmap

## Completed

### v1.0 — Monorepo Consolidation (2026-07-07)
- [x] Merged 6 repositories into monorepo via `git subtree --squash`
- [x] Deleted 35 redundant repos, archived 7 bundles
- [x] Updated READMEs on all 7 archived Core repos
- [x] Created CLEANUP_LOG.md with full audit trail
- [x] Final inventory: 15 repos (8 active + 7 archived)

### v1.1 — Documentation & CI (2026-07-08)
- [x] Professional README with pipeline diagram and tech stack
- [x] docs/ARCHITECTURE.md with system diagrams, API endpoints, DB schema
- [x] CONTRIBUTING.md updated for monorepo (ruff, markers, scopes)
- [x] CI workflow with lint, type-check, security-scan, Docker build
- [x] pytest.ini configured for monorepo (pythonpath, markers)
- [x] docker-compose.yml with Gradio service (port 7860)
- [x] HF Space `omni-medical-ocr` deployed

### v1.2 — Quality & Desktop (2026-07-08)
- [x] Testing infrastructure: tests/unit/ (5 modules), tests/integration/, tests/utils/
- [x] ruff.toml replacing .flake8 + black + isort
- [x] mypy.ini with per-package overrides
- [x] GitHub Actions CI: 7 jobs (lint, typecheck, test-unit matrix, integration, docker, security, gate)
- [x] .pre-commit-config.yaml updated (ruff v0.8.6, bandit 1.8.0, detect-secrets v1.5.0)
- [x] 14 unit tests passing, 24 skipped (missing heavy deps), ruff clean
- [x] PyQt6 Desktop App with OCREnsemble + Jais LLM integration
- [x] Gradio HITL: prominent "Proofread with Jais" section + before/after comparison
- [x] add_prescription.py CLI tool (add/list/search/export prescriptions)
- [x] README.md updated with Desktop App section

## In Progress

### v1.3 — Multi-Page PDF & Tables
- [ ] Multi-page PDF batch processing with progress tracking
- [ ] Table detection and extraction (Camelot / custom)
- [ ] PDF structure parsing (headers, footers, page numbers)
- [ ] Export tables to Excel with formatting
- [ ] GitHub Actions deploy-to-hf.yml workflow

## Planned

### v1.4 — Training Pipeline
- [ ] Weekly automatic retraining script
- [ ] Training metrics dashboard (loss, CER, WER trends)
- [ ] A/B model comparison before deployment
- [ ] Ground truth validation pipeline

### v1.5 — Desktop Enhancements
- [ ] System tray with quick-scan shortcut
- [ ] Local file watcher for automatic processing
- [ ] Offline mode with local models only
- [ ] Batch OCR from folder

### v2.0 — Production Ready
- [ ] RBAC with JWT auth (admin, reviewer, viewer roles)
- [ ] Audit logging for all operations
- [ ] Rate limiting and API quotas
- [ ] Multi-tenant support
- [ ] Real-time collaboration (WebSocket)
- [ ] Kubernetes Helm chart
- [ ] Monitoring alerts (Grafana + PagerDuty)

## Long Term

### v2.x — Advanced Features
- [ ] FHIR-compliant medical data export
- [ ] Voice-to-text for dictation support
- [ ] Mobile app (React Native)
- [ ] On-premise appliance (Docker image + Ansible playbook)
- [ ] Model marketplace (community fine-tuned models)

## Milestones

| Version | Date | Focus |
|---------|------|-------|
| v1.0 | 2026-07-07 | Monorepo consolidation |
| v1.1 | 2026-07-08 | Documentation & CI |
| v1.2 | 2026-07-08 | Quality, testing, desktop app |
| v1.3 | 2026-07-15 | PDF + tables |
| v1.4 | 2026-08-01 | Training pipeline |
| v1.5 | 2026-08-15 | Desktop enhancements |
| v2.0 | 2026-09-01 | Production ready |