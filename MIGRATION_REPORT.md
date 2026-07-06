# Monorepo Migration Report
# Date: 2026-07-07
# Canonical Repo: omni-medical-suite

## Merged Repos (17 total)

### Core Medical/OCR (8 repos → packages/ + apps/)
| Source Repo | Target Path | Status |
|---|---|---|
| scanner-fixer | packages/scanner_fixer/ | Merged |
| medical-ocr-ground-truth | packages/gt_core/ | Merged |
| medical-ocr-benchmarks | packages/benchmark_core/ | Merged |
| medical-ocr-training-hub | packages/training_hub/ | Merged |
| medical-ocr-postprocessor | packages/ocr_postprocess/ | Merged |
| medical-doc-processor | packages/doc_processor/ | Merged |
| omni-medical-ocr-pipeline | apps/ocr-pipeline/ | Merged |
| medical-handwriting-ocr | apps/handwriting-demo/ | Merged |

### Tools/Ops (5 repos → tools/)
| Source Repo | Target Path | Status |
|---|---|---|
| git-sync-system | tools/repo_admin/git-sync/ | Merged |
| telegram-forwarder | tools/ops/telegram_forwarder/ | Merged |
| reset-net | tools/sys/reset_net/ | Merged |
| manjaro-care | tools/sys/manjaro-care/ | Merged |
| ai-fuel-engine | tools/ai_fuel/ | Merged |

### Shared Text/Data (4 repos → packages/ + labs/)
| Source Repo | Target Path | Status |
|---|---|---|
| bilingual-extractor | packages/bilingual/ | Merged |
| OmniFile_Processor | packages/file_processor/ | Merged |
| omniparse | packages/omniparse/ | Merged |
| omniparse-study | labs/omniparse_study/ | Merged |

### Trainer/Demo (3 repos → apps/)
| Source Repo | Target Path | Status |
|---|---|---|
| medical-ocr-trainer | apps/trainer-ui/ | Merged |
| medical-ocr-trainer-hf | apps/trainer-ui/hf-variant/ | Merged |
| medical-ocr-demo | apps/ocr-demo/ | Merged |
| handwriting-ocr | apps/handwriting-demo/variants/ | Merged |

## Method: git subtree add --squash
- Preserves file history in squash commits
- Each source repo becomes a self-contained subdirectory
- Original repos can be archived after verification