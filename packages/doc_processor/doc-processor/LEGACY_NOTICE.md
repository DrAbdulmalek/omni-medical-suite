# ⚠️ Legacy Repository — Merge In Progress

> **Status**: 🟡 Legacy / Merging into omni-medical-suite  
> **Successor**: [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite)  
> **Last Updated**: June 2026

## Overview

This repository (`medical-doc-processor`) contains a Next.js-based medical document 
processing application with OCR, batch processing, Mistral AI integration, training 
data management, and a comprehensive React UI. The functionality of this application 
is being consolidated into `omni-medical-suite` as part of the ecosystem restructuring.

## What's Being Migrated

### → `omni-medical-suite` (Platform/Suite Layer)
| Component | Source Path | Destination |
|-----------|-------------|-------------|
| Next.js App | `src/app/` | `omni-medical-suite/src/app/` |
| React Components | `src/components/` | `omni-medical-suite/src/components/` |
| API Routes | `src/app/api/` | `omni-medical-suite/src/app/api/` |
| Core Libraries | `src/lib/` | `omni-medical-suite/src/lib/` |
| Prisma Schema | `prisma/` | `omni-medical-suite/prisma/` |
| Docker Config | `Dockerfile`, `docker-compose.yml` | `omni-medical-suite/` |

### → `medical-ocr-postprocessor` (Core Engine)
| Component | Source Path | Destination |
|-----------|-------------|-------------|
| Word Correction | `src/app/api/word-correction/` | Packaged in postprocessor |
| Training Models | `model/` | `medical-ocr-postprocessor/data/` |

### → `medical-ocr-trainer` (Evaluation)
| Component | Source Path | Destination |
|-----------|-------------|-------------|
| Training API | `src/app/api/training/` | `medical-ocr-trainer/evaluation/` |
| Evaluation API | `src/app/api/ocr/evaluate/` | `medical-ocr-trainer/evaluation/` |

## Migration Timeline

| Phase | Status | Description |
|-------|--------|-------------|
| Phase 1 | ✅ Complete | README/topic/description updates |
| Phase 2 | 🔄 In Progress | Legacy tagging, component identification |
| Phase 3 | ⏳ Planned | Code merge into omni-medical-suite |

## What's Still Active Here

During the merge period, this repository remains functional. Key features:
- Document OCR with multiple engine support
- Batch processing with SSE progress
- Mistral AI integration for classification and extraction
- Training data collection and word correction
- PHI-aware document handling

## How to Migrate

1. **New deployments**: Use `omni-medical-suite` as the primary platform
2. **Existing users**: The migration will preserve all API endpoints
3. **Contributors**: Submit PRs to `omni-medical-suite` for new features

## Contact

For questions, open an issue in [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite).
