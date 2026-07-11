# LEGACY_REVIEW_FINAL.md
# Generated: 2026-07-11
# Method: MD5 comparison + path analysis

## Summary

| Metric | Count |
|--------|-------|
| Original LEGACY REVIEW count | 200 |
| Auto-deleted (MD5 match to canonical) | 19 |
| **Remaining — needs human review** | **181** |
|   In `legacy/` subdirectory | 19 |
|   In merged-remnant pkg (not legacy/) | 162 |

## Why these can't be auto-deleted

**Import analysis is unreliable for generic filenames.**
Files named `app.py`, `config.py`, `main.py` etc. are imported via relative
imports (`from .app import router`) which makes it impossible to distinguish
which specific `app.py` is being referenced without full AST analysis.
Therefore, only MD5-identical copies were auto-deleted (100% mechanical certainty).
The remaining files need human review to determine if they're safe to delete.

---

## Files in `legacy/` subdirectories (likely safe to delete)

These are inside `legacy/` paths within merged-remnant packages.
They are very likely safe to delete but need human confirmation.

- `./packages/file_processor/legacy/mobile_review/split/02-mobile-review/server.py` — 1766 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/mobile_review/split/02-mobile-review/sync_backend.py` — 9685 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/mobile_review/split/10-backend-api/config.py` — 777 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/mobile_review/split/10-backend-api/database.py` — 697 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/mobile_review/split/10-backend-api/main.py` — 13136 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/mobile_review/split/10-backend-api/schemas.py` — 2449 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/mobile_review/split/12-active-learning/active_learning.py` — 20999 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/mobile_review/split/12-active-learning/finetuning.py` — 13065 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/ocr_unified_v2/backend/app.py` — 42105 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/ocr_unified_v2/config.py` — 12470 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/ocr_unified_v2/src/correction.py` — 14018 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/ocr_unified_v2/src/database.py` — 10647 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/ocr_unified_v2/src/finetuning.py` — 4163 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/ocr_unified_v2/src/logger.py` — 1176 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/ocr_unified_v2/src/main.py` — 7870 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/ocr_unified_v2/src/metrics.py` — 3019 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/ocr_unified_v2/src/migration.py` — 20268 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/ocr_unified_v2/src/sync.py` — 16057 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/legacy/translation_corrector/app.py` — 41453 bytes — in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation

---

## Files in merged-remnant packages (not in legacy/)

These are in merged-remnant packages but NOT inside `legacy/`.
They may have been intentionally kept during the subtree merge.

- `./apps/handwriting-demo/variants/handwriting-ocr/app.py` — 57893 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/config.py` — 11046 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/database.py` — 50958 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/main.py` — 4047 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/mobile_review/server.py` — 2556 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/active_learning.py` — 32187 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/pattern_db.py` — 18039 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/database_manager.py` — 15600 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/file_fingerprint.py` — 15569 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/handwriting_db.py` — 11736 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/search_engine.py` — 21541 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/evaluation/metrics.py` — 8743 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/encryption.py` — 8247 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/sensitive_data_scanner.py` — 12703 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/finetuning.py` — 17802 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/correction.py` — 30840 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/database.py` — 507 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/finetuning.py` — 4812 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/logger.py` — 17501 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/main.py` — 8220 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/metrics.py` — 3019 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/migration.py` — 26156 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/sync.py` — 16057 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/tests/conftest.py` — 2890 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_integration.py` — 19800 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_ocr_engine.py` — 5141 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/app.py` — 27256 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/config/htr_config.py` — 1365 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/api_server.py` — 14805 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/database_manager.py` — 15691 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/db_manager.py` — 12829 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/encryption.py` — 7387 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/file_fingerprint.py` — 15906 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/handwriting_db.py` — 11634 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/migration/migration.py` — 20447 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/protected_vocab.py` — 7506 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/search_engine.py` — 22976 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/test_core.py` — 12033 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/nlp/pipeline.py` — 41491 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/ocr_postprocess/tests/test_core.py` — 8525 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/scanner_fixer/src/scanner_fixer/cli.py` — 4543 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/scanner_fixer/src/scanner_fixer/pipeline.py` — 6877 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/vision/batch_ocr.py` — 14427 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/vision/finetuning.py` — 17955 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/vision/htr/arabic_htr.py` — 16100 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./legacy/api_server.py` — 2852 bytes — in legacy/ root directory — needs human review
- `./packages/doc-processor/desktop/medical_doc_gui_final.py` — 35993 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc-processor/desktop/test_core.py` — 3067 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc-processor/desktop/test_processing.py` — 13309 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc-processor/packages/core/db_manager.py` — 12286 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc-processor/test_core.py` — 10525 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/desktop/medical_doc_gui_final.py` — 35993 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/desktop/test_core.py` — 3067 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/desktop/test_processing.py` — 13309 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/download/medical-image-ai-suite/services/ocr/data_collection/pipeline.py` — 44611 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/download/medical-image-ai-suite/src/utils/logger.py` — 3030 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/download/medical-image-ai-suite/src/utils/metrics.py` — 8450 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/packages/core/db_manager.py` — 12286 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/skills/ppt/ooxml/scripts/validation/base.py` — 39848 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/skills/quiz-mastery/src/quiz_mastery/utils.py` — 137 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/skills/skill-creator/scripts/utils.py` — 1661 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/skills/ui-ux-pro-max/scripts/core.py` — 10227 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/skills/xlsx/templates/base.py` — 21964 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/test_core.py` — 10525 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/app.py` — 57891 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/config.py` — 15815 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/database.py` — 50954 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/main.py` — 4047 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/mobile_review/server.py` — 5236 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/active_learning.py` — 20394 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/finetuning.py` — 13065 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/api/app.py` — 6123 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/config/constants.py` — 443 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/deepseek/client.py` — 1650 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/deepseek/request.py` — 16596 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/kimi/client.py` — 882 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/kimi/request.py` — 1071 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/lmstudio/client.py` — 501 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/nvidia_nim/client.py` — 2763 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/nvidia_nim/request.py` — 9239 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/ollama/client.py` — 1363 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/open_router/client.py` — 4429 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/open_router/request.py` — 1304 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/rate_limit.py` — 9291 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/wafer/client.py` — 1362 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/pattern_db.py` — 17258 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/audit/pipeline.py` — 15769 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/config/htr_config.py` — 1365 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/core/database_manager.py` — 15689 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/core/file_fingerprint.py` — 15855 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/core/handwriting_db.py` — 11270 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/core/migration/migration.py` — 20356 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/core/protected_vocab.py` — 7506 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/core/search_engine.py` — 21836 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/evaluation/metrics.py` — 10088 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/learning/pattern_db.py` — 8751 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/security/encryption.py` — 8768 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/security/sensitive_data_scanner.py` — 12907 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/security/sync/sync.py` — 16057 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/security/sync/sync_backend.py` — 9685 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/vision/batch_ocr.py` — 14427 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/vision/finetuning.py` — 17802 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/vision/htr/arabic_htr.py` — 16100 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/src/correction.py` — 20071 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/src/database.py` — 507 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/src/finetuning.py` — 5020 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/src/logger.py` — 17501 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/src/main.py` — 8220 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/src/metrics.py` — 3019 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/src/migration.py` — 26455 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/src/sync.py` — 16057 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/tests/conftest.py` — 1098 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/tests/test_integration.py` — 6814 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/tests/test_ocr_engine.py` — 5249 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/training/utils/metrics.py` — 1450 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/app.py` — 57893 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/config.py` — 11046 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/database.py` — 50958 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/main.py` — 4047 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/mobile_review/server.py` — 2556 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/ai/active_learning.py` — 32187 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/ai/pattern_db.py` — 18039 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/core/database_manager.py` — 15600 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/core/file_fingerprint.py` — 15569 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/core/handwriting_db.py` — 11736 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/core/search_engine.py` — 21541 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/evaluation/metrics.py` — 8743 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/security/encryption.py` — 8247 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/security/sensitive_data_scanner.py` — 12703 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/vision/finetuning.py` — 17802 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/src/correction.py` — 30840 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/src/database.py` — 507 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/src/finetuning.py` — 4812 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/src/logger.py` — 17501 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/src/main.py` — 8220 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/src/metrics.py` — 3019 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/src/migration.py` — 26156 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/src/sync.py` — 16057 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/tests/conftest.py` — 2890 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/tests/test_integration.py` — 19800 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/tests/test_ocr_engine.py` — 5141 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/config.py` — 11046 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/database.py` — 50958 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/main.py` — 4047 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/mobile_review/server.py` — 2556 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/modules/ai/pattern_db.py` — 18039 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/modules/core/database_manager.py` — 15600 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/modules/core/file_fingerprint.py` — 15569 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/modules/core/handwriting_db.py` — 11736 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/modules/core/search_engine.py` — 21541 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/modules/evaluation/metrics.py` — 8743 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/correction.py` — 30840 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/database.py` — 507 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/finetuning.py` — 4812 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/logger.py` — 17501 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/main.py` — 8220 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/metrics.py` — 3019 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/migration.py` — 26156 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/sync.py` — 16057 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/tests/conftest.py` — 2890 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/tests/test_integration.py` — 19800 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/tests/test_ocr_engine.py` — 5141 bytes — in merged-remnant package — may be copy of canonical version, needs content comparison

