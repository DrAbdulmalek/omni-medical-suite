# Product Identity & Scope Definition

> **Repository**: omni-medical-suite
> **Identity**: Arabic medical OCR/NLP platform
> **Status**: Binding — no scope changes without explicit user approval

## What this project IS

omni-medical-suite is an **Arabic-first medical document intelligence platform**. Its
core capabilities are:

- OCR of scanned Arabic medical documents (prescriptions, lab reports, radiology notes)
- Handwriting recognition for Arabic medical handwriting
- Spell correction and vocabulary expansion for medical Arabic
- Named Entity Recognition (NER) for medical entities (drugs, dosages, conditions)
- Pre-OCR image normalization (`scanner_fixer` package)
- Training data collection and model fine-tuning loops
- Hugging Face Space demo deployment

The platform is **medical-domain-specific**. It is not a general-purpose file manager,
not an enterprise EDMS, and not a personal document organizer.

## What this project is NOT

- **Not a general file manager.** File operations are scoped to medical document
  workflows only. For general file management, use `intelli-file-manager` (a separate
  project under a separate repo) — but that integration is **optional and out of
  scope for this repo's core**.
- **Not a desktop-first product.** The primary deployments are: Docker, HF Space,
  Android APK. The Linux desktop AppImage is a thin wrapper around the OCR pipeline.
- **Not a multi-tenant SaaS.** No tenant isolation, no billing, no SSO. Single-deployment
  assumed.
- **Not a real-time collaboration platform.** No multi-user sync, no live cursors.

## Allowed integrations (optional, external)

- `intelli-file-manager` may be referenced in docs as a sibling project, but no
  cross-repo imports, no shared CI, no shared release pipelines.
- `scanner_fixer` is published as its own PyPI-installable package; it can be imported
  by other projects, but the inverse (omni-medical-suite importing from
  `intelli-file-manager`) is **forbidden**.

## Forbidden scope additions

- DICOM workflow as a first-class feature (DICOM tags are extracted only as OCR targets)
- HL7/FHIR server implementations (out of scope — wrap an external FHIR server instead)
- General-purpose file inventory / smart-tagging (belongs in intelli-file-manager)
- Real-time multi-user sync (no hospital clinical workflow assumptions)

## Architecture invariants

1. All OCR/NLP code lives under `packages/` and `apps/`
2. The `packages/desktop/` is a thin PyInstaller wrapper — no business logic
3. The `apps/handwriting-demo/` is a Next.js + FastAPI demo stack — not the production app
4. No code may import from `intelli-file-manager`'s `src/` tree

## Scope decisions log

| Date | Decision | Reason |
|------|----------|--------|
| 2026-07-24 | IntelliFile-app archived (legacy) | Pre-restructure duplicate |
| 2026-07-24 | backup.sh removed intelli-file-manager from sibling backup | Boundary violation — each repo backs up itself |
| 2026-07-24 | .env.test is now .gitignored | Contains test creds even if marked "test-only" |
