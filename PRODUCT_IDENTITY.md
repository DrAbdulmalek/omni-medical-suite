# Product Identity & Scope Definition

## Overview

This document establishes the **non-negotiable product identities** for repositories under `DrAbdulmalek` to prevent scope creep and maintain clear boundaries between projects.

---

## Repository Identities

### 1. intelli-file-manager

| Attribute | Definition |
|-----------|------------|
| **Primary Purpose** | Local-first AI file manager for **personal desktop use** |
| **Target Users** | Individual users managing local documents |
| **Core Features** | File organization, search, tagging, OCR, RAG-based chat with files |
| **Platform** | Desktop (PWA + optional APK) |
| **Data Scope** | Local files only (no cloud sync by default) |
| **Language Support** | Arabic RTL + English |
| **AI Models** | Local (Ollama) - Mistral, Moondream, Whisper |

**❌ EXPLICITLY EXCLUDED:**
- Medical-specific features (DICOM parsing, medical NER, HL7/FHIR)
- Multi-device sync infrastructure
- Patient data management
- Clinical workflows
- Any feature requiring cloud processing

**⚠️ Violation Remediation:**
- DICOM parser must be removed from intelli-file-manager
- SyncManager must be removed from intelli-file-manager
- Medical NER components must be removed from intelli-file-manager

---

### 2. omni-medical-suite

| Attribute | Definition |
|-----------|------------|
| **Primary Purpose** | Arabic medical OCR/NLP platform |
| **Target Users** | Medical professionals, healthcare institutions |
| **Core Features** | Medical document OCR, Arabic medical NER, glossary API, field extraction |
| **Platform** | Backend services + APIs |
| **Data Scope** | Medical documents, reports, X-rays, DICOM |
| **Language Support** | Arabic RTL (primary), English |
| **Integration Points** | Scanner fixers, OCR engines, field extractors, glossary APIs |

**✅ EXPLICITLY INCLUDED:**
- DICOM parsing and processing
- Medical NER (Named Entity Recognition)
- Arabic medical terminology handling
- HL7/FHIR support (if needed)
- Medical document-specific OCR optimization

**❌ EXPLICITLY EXCLUDED:**
- General file management features
- Non-medical document processing
- Consumer-facing mobile apps (should be separate repos)

---

### 3. repo-sync-toolkit

| Attribute | Definition |
|-----------|------------|
| **Primary Purpose** | Secure repository synchronization utilities |
| **Target Users** | Developers, CI/CD pipelines |
| **Core Features** | Git operations, branch management, sync validation |
| **Security Level** | HIGH - requires hardening |

**⚠️ ACTION REQUIRED:**
- Security audit and hardening
- Remove any exposed credentials
- Implement proper access controls

---

## Integration Rules

### intelli-file-manager + omni-medical-suite Integration

**ALLOWED:**
- intelli-file-manager may **consume** omni-medical-suite as a dependency
- intelli-file-manager may call omni-medical-suite APIs for OCR/NLP on medical files
- Shared utilities (Arabic RTL, OCR base classes) may be in a common package

**FORBIDDEN:**
- intelli-file-manager may NOT contain medical-specific code
- omni-medical-suite may NOT contain file management code
- Direct code copying between repos
- Circular dependencies

---

## Scope Enforcement Checklist

- [ ] Remove DICOM parser from intelli-file-manager
- [ ] Remove SyncManager from intelli-file-manager
- [ ] Remove medical NER from intelli-file-manager
- [ ] Verify no medical-specific imports in intelli-file-manager
- [ ] Create shared utilities package if needed
- [ ] Document integration boundaries in both repos

---

## Decision Log

| Date | Decision | Rationale | Owner |
|------|----------|-----------|-------|
| 2026-07-22 | Separate product identities | Prevent scope creep, maintain focus | DrAbdulmalek |
| 2026-07-22 | Remove medical features from intelli-file-manager | Violation of product identity | Mistral (Vibe) |

---

## Approval

**Status:** APPROVED
**Approver:** DrAbdulmalek
**Review Date:** 2026-07-22
**Effective Date:** 2026-07-22