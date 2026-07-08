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

## In Progress

### v1.2 — Quality & Testing
- [ ] Fix all existing test failures in monorepo context
- [ ] Add pre-commit hooks (ruff + pytest)
- [ ] Achieve 80%+ test coverage on `src/` and `packages/core/`
- [ ] Add integration tests for API endpoints
- [ ] Add GitHub Actions deploy-to-hf.yml workflow

## Planned

### v1.3 — Multi-Page PDF & Tables
- [ ] Multi-page PDF batch processing with progress tracking
- [ ] Table detection and extraction (Camelot / custom)
- [ ] PDF structure parsing (headers, footers, page numbers)
- [ ] Export tables to Excel with formatting

### v1.4 — Desktop Application
- [ ] PyQt6 desktop app integrated into `desktop/`
- [ ] System tray with quick-scan shortcut
- [ ] Local file watcher for automatic processing
- [ ] Offline mode with local models only

### v1.5 — Training Pipeline
- [ ] Weekly automatic retraining script
- [ ] Training metrics dashboard (loss, CER, WER trends)
- [ ] A/B model comparison before deployment
- [ ] Ground truth validation pipeline

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

| Version | Target Date | Focus |
|---------|------------|-------|
| v1.0 | 2026-07-07 | Monorepo consolidation |
| v1.1 | 2026-07-08 | Documentation & CI |
| v1.2 | 2026-07-15 | Quality & testing |
| v1.3 | 2026-07-22 | PDF + tables |
| v1.4 | 2026-08-01 | Desktop app |
| v1.5 | 2026-08-15 | Training pipeline |
| v2.0 | 2026-09-01 | Production ready |