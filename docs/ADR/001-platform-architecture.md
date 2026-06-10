# ADR-001: Platform Architecture — Monorepo with Turborepo

## Status
Accepted

## Context
The OmniMedical Suite project evolved from merging two separate repositories (medical-doc-processor v3.2 and OmniFile_Processor v5.0) into a unified platform. We needed a structure that allows shared code, independent deployment of services, and clear separation of concerns.

## Decision
We adopted a Turborepo monorepo structure with the following organization:

```
omni-medical-suite/
├── apps/
│   ├── web/          # Next.js 16 frontend
│   └── mobile/       # React Native (future)
├── packages/
│   ├── ai/           # AI Gateway & provider integrations
│   ├── vision/       # Image processing utilities
│   ├── nlp/          # NLP pipeline components
│   ├── omni-core/    # Shared types, utils, constants
│   ├── omni-ocr/     # Multi-engine OCR orchestration
│   ├── learning/     # Continuous learning pipeline
│   ├── security/     # Encryption, PII detection, auth
│   ├── export/       # Multi-format export (DOCX, PDF, etc.)
│   ├── training-framework/    # Model training utilities
│   ├── interactive-learning/ # Human-in-the-loop components
│   ├── audit/        # Audit logging
│   ├── segmentation/ # Document segmentation
│   ├── medical/      # Medical-specific logic & dictionaries
│   └── evaluation/   # Benchmark & evaluation tools
├── services/
│   └── api/          # FastAPI backend
└── infrastructure/
    ├── docker/        # Docker Compose files
    ├── k8s/           # Kubernetes manifests
    └── terraform/     # AWS infrastructure
```

## Consequences

### Positive
- Shared code across frontend and backend
- Independent deployment of services
- Clear ownership boundaries per package
- Turborepo caching speeds up builds

### Negative
- Monorepo tooling has learning curve
- Large initial clone size
- Requires Turborepo configuration knowledge

### Risks
- Package dependency cycles must be actively prevented
- Breaking changes in shared packages affect multiple consumers
