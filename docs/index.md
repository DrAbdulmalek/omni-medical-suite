# OmniMedical Suite Documentation

Welcome to the OmniMedical Suite documentation hub. This is the central reference for the entire medical document intelligence ecosystem.

## Quick Start

### For Users
Choose the right tool for your needs:

| Need | Repository | Link |
|------|-----------|------|
| Complete document processing | [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) | [README](../README.md) |
| OCR correction engine | [medical-ocr-postprocessor](https://github.com/DrAbdulmalek/medical-ocr-postprocessor) <!-- ARCHIVED: archived, merged into omni-medical-suite --> | [Install Guide](https://github.com/DrAbdulmalek/medical-ocr-postprocessor <!-- ARCHIVED: archived, merged into omni-medical-suite -->#installation) |
| Production handwriting OCR | [medical-handwriting-ocr](https://github.com/DrAbdulmalek/medical-handwriting-ocr) <!-- ARCHIVED: archived, merged into omni-medical-suite --> | [Docker Profiles](https://github.com/DrAbdulmalek/medical-handwriting-ocr/blob/main/DOCKER_PROFILES <!-- ARCHIVED: archived, merged into omni-medical-suite -->.md) |
| Collect training data | [medical-ocr-trainer](https://github.com/DrAbdulmalek/medical-ocr-trainer) <!-- ARCHIVED: archived, merged into omni-medical-suite --> | [README](https://github.com/DrAbdulmalek/medical-ocr-trainer) <!-- ARCHIVED: archived, merged into omni-medical-suite --> |

### For Developers
- [Architecture Overview](./ADR/001-platform-architecture.md) — Monorepo structure
- [ADR Index](./ADR/) — Architecture Decision Records
- [API Reference](../README.md#api-endpoints) — REST API documentation
- [Docker Deployment](./ADR/003-docker-profiles.md) — Multi-profile setup
- [CI/CD Pipeline](./ADR/004-ci-cd-unified.md) — GitHub Actions

## Architecture

See [PORTFOLIO.md](../PORTFOLIO.md) for the complete ecosystem architecture diagram.

## Architecture Decision Records (ADR)

| ADR | Title | Status |
|-----|-------|--------|
| [001](./ADR/001-platform-architecture.md) | Turborepo Monorepo | Accepted |
| [002](./ADR/002-postprocessor-as-library.md) | Postprocessor as Library | Accepted |
| [003](./ADR/003-docker-profiles.md) | Multi-Profile Docker | Accepted |
| [004](./ADR/004-ci-cd-unified.md) | Unified CI/CD | Accepted |
| [005](./ADR/005-repo-portfolio-strategy.md) | Repository Portfolio Strategy | Accepted |

## Changelog

See [CHANGELOG.md](../CHANGELOG.md) for the full history of changes.
