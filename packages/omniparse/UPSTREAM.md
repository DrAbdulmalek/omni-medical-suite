# UPSTREAM.md — Upstream Tracking

> This repository is a fork of [adithya-s-k/omniparse](https://github.com/adithya-s-k/omniparse)

## Upstream Information

| Field | Value |
|-------|-------|
| **Original Repository** | https://github.com/adithya-s-k/omniparse |
| **Original Author** | adithya-s-k |
| **Original License** | GPL-3.0 |
| **Last Synced** | 2026-05-30 |

## Changes Made

### Analysis & Study
- Evaluated OmniParse's multi-modal parsing capabilities for medical document extraction
- Benchmarked parsing accuracy on Arabic medical handwriting samples
- Explored integration paths with medical-ocr-postprocessor pipeline

### No Code Modifications
This fork is kept as-is for reference purposes. No modifications were made to the upstream code.

## Why This Fork Exists

The OmniParse project was forked to study its architecture and evaluate whether its parsing capabilities could enhance the medical handwriting OCR pipeline developed in the `medical-handwriting-ocr` and `omni-medical-suite` repositories.

## Migration Path

If any upstream changes need to be incorporated:
1. Add upstream remote: `git remote add upstream https://github.com/adithya-s-k/omniparse.git`
2. Fetch upstream: `git fetch upstream`
3. Merge: `git merge upstream/main`

## Related Repositories

| Repo | Relationship |
|------|-------------|
| [omniparse-study](https://github.com/DrAbdulmalek/omniparse-study) | Study notes and analysis |
| [medical-ocr-postprocessor](https://github.com/DrAbdulmalek/medical-ocr-postprocessorNone) <!-- ARCHIVED: merged into omni-medical-suite/packages/ocr_postprocess/ --> | Target integration point |
| [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) | Main platform |
