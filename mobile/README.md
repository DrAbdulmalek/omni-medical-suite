# Mobile Applications for omni-medical-suite

This directory contains 3 mobile applications that should be in separate repositories according to REPO_POLICY.md.

## Mobile Apps

### 1. android/
- Purpose: Android mobile application
- Status: Needs separation to dedicated repository
- Target Repo: omni-medical-mobile-android
- Description: Android app for medical document management

### 2. colab/
- Purpose: Google Colab mobile interface
- Status: Needs separation to dedicated repository
- Target Repo: omni-medical-mobile-colab
- Description: Colab-based mobile interface for medical OCR

### 3. termux/
- Purpose: Termux mobile application
- Status: Needs separation to dedicated repository
- Target Repo: omni-medical-mobile-termux
- Description: Termux-based mobile app for medical suite

## Governance Violation

Policy: REPO_POLICY.md states: Consumer-facing mobile apps (should be separate repos)

Current State: 3 mobile apps are in the omni-medical-suite repository, which violates the product identity.

Product Identity: omni-medical-suite is an Arabic medical OCR/NLP platform - NOT a mobile app repository.

## Migration Plan

These mobile apps will be moved to separate repositories to comply with governance policies.

### Target Structure

After migration:
- omni-medical-mobile-android/ (new repository)
- omni-medical-mobile-colab/ (new repository)
- omni-medical-mobile-termux/ (new repository)

### Migration Steps

1. Create new repositories for each mobile app
2. Move code from mobile/{app}/ to new repository
3. Preserve commit history where possible
4. Set up separate CI/CD for each mobile repo
5. Delete mobile/ directory from omni-medical-suite

## Current Structure

omni-medical-suite/
  mobile/
    android/    # Android app
    colab/      # Colab interface
    termux/     # Termux app

## Related Documents

- REPO_POLICY.md - Repository policies
- PRODUCT_IDENTITY.md - Product boundaries
- Code Duplication Analysis Canvas - Detailed analysis

## Notes

- This is a temporary structure
- Migration will be executed as part of Phase 3: Repo Hygiene
- Each app will have its own: Repository, Dependencies, CI/CD pipeline, Release cycle

---

Status: Migration pending
Priority: HIGH
Owner: Mistral (Vibe)
Target Completion: Phase 3

---

Last updated: 2026-07-22