# Component Migration Map

This document provides a detailed mapping of components in OmniFile_Processor 
to their new locations in the ecosystem architecture.

## Core Modules

| Source Path | Destination | Status |
|------------|-------------|--------|
| `modules/nlp/spell_corrector.py` | `medical-ocr-postprocessor` | 🔄 Migrating |
| `modules/nlp/correction_dict.json` | `medical-ocr-postprocessor/data/` | 🔄 Migrating |
| `modules/nlp/protected_words.py` | `medical-ocr-postprocessor` (PHI) | 🔄 Migrating |
| `modules/nlp/arabic_nlp_utils.py` | `medical-ocr-postprocessor` (Arabic support) | 🔄 Migrating |
| `modules/nlp/language_detector.py` | `medical-ocr-postprocessor` | 🔄 Migrating |
| `modules/ai/gemini_refiner.py` | `omni-medical-suite/ai/` | ⏳ Planned |
| `modules/ai/pattern_matcher.py` | `omni-medical-suite/ai/` | ⏳ Planned |
| `modules/export/markdown_exporter.py` | `omni-medical-suite/export/` | ⏳ Planned |
| `modules/export/layout_preserving.py` | `omni-medical-suite/export/` | ⏳ Planned |
| `modules/evaluation/metrics.py` | `medical-ocr-trainer/evaluation/` | ✅ Completed |

## Training & Data

| Source Path | Destination | Status |
|------------|-------------|--------|
| `training/scripts/train_trocr_lora.py` | `handwriting-ocr-model/training/` | 🔄 Migrating |
| `training/scripts/evaluate_checkpoint.py` | `medical-ocr-trainer/evaluation/` | ✅ Completed |
| `training/models/lora_htr_trainer.py` | `handwriting-ocr-model/training/` | 🔄 Migrating |
| `training/cloud/*.py` | `medical-ocr-trainer/cloud/` | ⏳ Planned |

## Backend & API

| Source Path | Destination | Status |
|------------|-------------|--------|
| `backend/main.py` | `omni-medical-suite/backend/` | 🔄 Migrating |
| `backend/api/training.py` | `omni-medical-suite/backend/api/` | ⏳ Planned |
| `backend/celery_worker.py` | `omni-medical-suite/backend/` | ⏳ Planned |

## Frontend

| Source Path | Destination | Status |
|------------|-------------|--------|
| `frontend/` | `omni-medical-suite/frontend/` | 🔄 Migrating |
| `gui_app.py` | `omni-medical-suite/` | ⏳ Planned |
| `mobile_review/` | `omni-medical-suite/mobile/` | ⏳ Planned |

## Deployment

| Source Path | Destination | Status |
|------------|-------------|--------|
| `k8s/` | `omni-medical-suite/k8s/` | 🔄 Migrating |
| `deployment/` | `omni-medical-suite/deployment/` | 🔄 Migrating |
| `docker-compose.override.yml` | `omni-medical-suite/` | ⏳ Planned |

## Legacy & Archive

| Source Path | Action | Status |
|------------|--------|--------|
| `legacy/` | Keep as historical reference | ✅ Archived |
| `archive/` | Keep as historical reference | ✅ Archived |
| `_dev_references/` | Keep as development reference | ✅ Preserved |
