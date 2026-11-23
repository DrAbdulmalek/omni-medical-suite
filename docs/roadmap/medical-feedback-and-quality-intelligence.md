# Medical Feedback and Quality Intelligence

**Status:** Proposal only. This document does not authorize clinical use, automatic correction promotion, or model training.

## Goal

Add an auditable feedback layer around the existing medical OCR/document workflows. Reuse `ocr-core` for OCR engines, post-processing, correction data, and benchmark contracts; avoid maintaining parallel implementations.

## Feedback categories

- OCR recognition and layout corrections;
- Arabic/English terminology corrections;
- structured-field extraction corrections;
- duplicate or missing field reports;
- document ingestion and processing failures;
- retrieval or answer-quality feedback, where applicable;
- UI/workflow usability feedback.

## Data separation

Maintain distinct namespaces for:
1. user preferences;
2. document-specific review annotations;
3. reusable, human-approved terminology/correction candidates;
4. engineering defects and telemetry.

Do not treat a document-specific correction as a general medical rule. Do not mix identifiable patient records into engineering feedback.

## Suggested lifecycle

`observed → captured → privacy-screened → reviewed → evaluated → accepted/rejected → versioned`

Each state transition should record actor, time, reason, and evidence. AI suggestions remain untrusted proposals until reviewed.

## Quality dashboard

Display:
- OCR engine and version;
- CER/WER and field-level metrics where ground truth exists;
- review queue and correction status;
- accepted/rejected suggestions;
- regression count;
- provenance of terminology;
- data-quality warnings.

Avoid a single aggregate score that hides language, handwriting, or document-type failures.

## Privacy and clinical safety

- Local-first processing; no cloud fallback.
- Use synthetic or de-identified fixtures in CI.
- Keep raw patient content out of GitHub issues, logs, telemetry, and analytics.
- Do not present generated output as a diagnosis or verified clinical fact.
- Any clinical workflow remains subject to qualified human review.
- Export must follow the repository's existing de-identification and privacy controls.

## Acceptance gates for implementation

- no regression in existing OCR/medical tests;
- negative tests for PHI leakage and unreviewed correction promotion;
- audit trail for every accepted reusable correction;
- provenance and versioning for glossary/correction sources;
- benchmark report split by language and document type;
- explicit rollback to the previous correction set.

## Dependency rule

Prefer `ocr-core` as the single OCR/correction/benchmark source. Before implementation, inspect current package boundaries and open PRs to avoid conflicting changes.
