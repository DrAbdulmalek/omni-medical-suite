# PARTIAL_DUPLICATES_DECISION_QUEUE.md
# Generated: 2026-07-11 10:06:18
# Method: git log + diff --stat for each of 124 groups from DUPLICATE_VERIFICATION_REPORT.md

## Summary
- Total groups: 124
- Auto-deletable (one pair identical, rest are copies): 124
- Needs human decision: 0

## Auto-deletable (124 groups — نسخ مطابقة ضمن مجموعات مختلفة جزئياً)

### `active_learning.py` (5 files, 4 unique versions)
- **Primary (keep):** `./packages/ai/active_learning.py` — 20368 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/active_learning.py` — 32187 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/handwriting/modules/ai/active_learning.py`~~ — 32187 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/mobile_review/split/12-active-learning/active_learning.py` — 20999 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/active_learning.py` — 20394 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/active_learning.py`: `1052 changed lines`
  - primary vs `./packages/file_processor/legacy/mobile_review/split/12-active-learning/active_learning.py`: `196 changed lines`
  - primary vs `./packages/file_processor/modules/ai/active_learning.py`: `31 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/legacy/mobile_review/split/12-active-learning/active_learning.py`); verify it includes all content

### `ai_corrector.py` (6 files, 2 unique versions)
- **Primary (keep):** `./packages/nlp/ai_corrector.py` — 13005 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/ai_corrector.py` — 13039 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/ai_corrector.py`~~ — 13039 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/nlp/ai_corrector.py`~~ — 13039 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/ai_corrector.py`~~ — 13039 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/ai_corrector.py`~~ — 13039 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/nlp/ai_corrector.py`: `34 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/handwriting/modules/nlp/ai_corrector.py`); verify it includes all content

### `api_server.py` (6 files, 4 unique versions)
- **Primary (keep):** `./packages/core/api_server.py` — 14638 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/doc-processor/packages/core/api_server.py`~~ — 14638 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/doc_processor/packages/core/api_server.py`~~ — 14638 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./apps/ocr-pipeline/api_server.py` — 11423 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/core/api_server.py` — 14805 bytes — 2026-07-07 18:45:30 +0000
- **Keep (non-primary cluster):** `./legacy/api_server.py` — 2852 bytes — 2026-06-22 12:26:04 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/ocr-pipeline/api_server.py`: `603 changed lines`
  - primary vs `./hf-space/packages/core/api_server.py`: `39 changed lines`
  - primary vs `./legacy/api_server.py`: `406 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/core/api_server.py`); verify it includes all content

### `app.py` (23 files, 22 unique versions)
- **Primary (keep):** `./packages/ai/gateway/api/app.py` — 6122 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/app.py` — 57893 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/app.py`~~ — 57893 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/api/app.py` — 6123 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./apps/ocr-demo/app.py` — 33449 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./tools/medical-ocr-trainer-hf/app.py` — 43209 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/app.py` — 27256 bytes — 2026-07-08 21:55:23 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/translation_corrector/app.py` — 41453 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./tools/ops/telegram_forwarder/app.py` — 27677 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/backend/app.py` — 31331 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/app.py` — 6095 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./tools/telegram-channel-copier/app.py` — 9688 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/app.py` — 57891 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/lgs-only-NovelGenerator/src/app.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./app/config/app.py` — 2576 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/backend/app.py` — 42105 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/hf-deploy/app.py` — 284 bytes — 2026-07-06 18:50:49 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/financial-services/claude-for-msft-365-install/examples/python-bootstrap/app.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/meiguanxiHXX-historyReviewAgent/historical_review/web/app.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./apps/ocr-pipeline/desktop/app.py` — 1768 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/trainer-ui/app.py` — 47451 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/trainer-ui/hf-variant/app.py` — 54692 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/ocr-pipeline/app.py` — 28009 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/app.py`: `1440 changed lines`
  - primary vs `./packages/file_processor/modules/ai/gateway/api/app.py`: `identical`
  - primary vs `./apps/ocr-demo/app.py`: `872 changed lines`
  - primary vs `./tools/medical-ocr-trainer-hf/app.py`: `1039 changed lines`
  - primary vs `./hf-space/app.py`: `696 changed lines`
  - primary vs `./packages/file_processor/legacy/translation_corrector/app.py`: `1089 changed lines`
  - primary vs `./tools/ops/telegram_forwarder/app.py`: `629 changed lines`
  - primary vs `./tools/HandwrittenOCR/backend/app.py`: `883 changed lines`
  - primary vs `./apps/handwriting-demo/app.py`: `252 changed lines`
  - primary vs `./tools/telegram-channel-copier/app.py`: `371 changed lines`
  - primary vs `./packages/file_processor/app.py`: `1440 changed lines`
  - primary vs `./app/config/app.py`: `218 changed lines`
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/backend/app.py`: `1123 changed lines`
  - primary vs `./apps/handwriting-demo/hf-deploy/app.py`: `160 changed lines`
  - primary vs `./apps/ocr-pipeline/desktop/app.py`: `196 changed lines`
  - primary vs `./apps/trainer-ui/app.py`: `1112 changed lines`
  - primary vs `./apps/trainer-ui/hf-variant/app.py`: `1268 changed lines`
  - primary vs `./apps/ocr-pipeline/app.py`: `690 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/modules/ai/gateway/api/app.py`); verify it includes all content

### `arabic_htr.py` (3 files, 2 unique versions)
- **Primary (keep):** `./packages/vision/htr/arabic_htr.py` — 16091 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/vision/htr/arabic_htr.py` — 16100 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./packages/file_processor/modules/vision/htr/arabic_htr.py`~~ — 16100 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/vision/htr/arabic_htr.py`: `24 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/modules/vision/htr/arabic_htr.py`); verify it includes all content

### `arabic_nlp_utils.py` (8 files, 4 unique versions)
- **Primary (keep):** `./packages/nlp/arabic_nlp_utils.py` — 2315 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/arabic_nlp_utils.py` — 2315 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/arabic_nlp_utils.py`~~ — 2315 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/arabic_nlp_utils.py`~~ — 2315 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/arabic_nlp_utils.py`~~ — 2315 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/mobile_review/split/05-review-systems/arabic_nlp_utils.py` — 1558 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tools/arabic_nlp_utils.py`~~ — 1558 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/arabic_nlp_utils.py` — 2340 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/arabic_nlp_utils.py`: `2 changed lines`
  - primary vs `./packages/file_processor/legacy/mobile_review/split/05-review-systems/arabic_nlp_utils.py`: `47 changed lines`
  - primary vs `./hf-space/packages/nlp/arabic_nlp_utils.py`: `3 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/nlp/arabic_nlp_utils.py`); verify it includes all content

### `arabic_rtl.py` (6 files, 2 unique versions)
- **Primary (keep):** `./packages/nlp/arabic_rtl.py` — 25928 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/arabic_rtl.py`~~ — 25928 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/modules/nlp/arabic_rtl.py`~~ — 25928 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/handwriting/modules/nlp/arabic_rtl.py`~~ — 25928 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/modules/nlp/arabic_rtl.py`~~ — 25928 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/arabic_rtl.py` — 25966 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/nlp/arabic_rtl.py`: `2 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/nlp/arabic_rtl.py`); verify it includes all content

### `archive_handler.py` (4 files, 2 unique versions)
- **Primary (keep):** `./packages/security/archive_handler.py` — 30463 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/archive_handler.py` — 30708 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/security/archive_handler.py`~~ — 30708 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/security/archive_handler.py`~~ — 30708 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/archive_handler.py`: `36 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/archive_handler.py`); verify it includes all content

### `audit_logger.py` (5 files, 3 unique versions)
- **Primary (keep):** `./packages/audit/audit_logger.py` — 7343 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/audit_logger.py` — 12070 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/security/audit_logger.py`~~ — 12070 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/security/audit_logger.py`~~ — 12070 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/modules/audit/audit_logger.py` — 7397 bytes — 2026-07-06 18:52:25 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/audit_logger.py`: `406 changed lines`
  - primary vs `./packages/file_processor/modules/audit/audit_logger.py`: `19 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/modules/security/audit_logger.py`); verify it includes all content

### `backup_manager.py` (4 files, 2 unique versions)
- **Primary (keep):** `./packages/security/backup_manager.py` — 33381 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/backup_manager.py` — 33458 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/security/backup_manager.py`~~ — 33458 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/security/backup_manager.py`~~ — 33458 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/backup_manager.py`: `13 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/handwriting/modules/security/backup_manager.py`); verify it includes all content

### `base.py` (8 files, 7 unique versions)
- **Primary (keep):** `./packages/ai/gateway/providers/base.py` — 4440 bytes — 2026-05-26 01:20:07 +0000
  - ~~`./packages/file_processor/modules/ai/gateway/providers/base.py`~~ — 4440 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/backend/agents/base.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/YYHDBL-HelloCodeAgentCli/tools/base.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/doc_processor/skills/ppt/ooxml/scripts/validation/base.py` — 39848 bytes — 2026-07-06 18:50:50 +0000
- **Keep (non-primary cluster):** `./packages/doc_processor/skills/xlsx/templates/base.py` — 21964 bytes — 2026-07-06 18:50:50 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Shawnxyxy-HealthRecordAgent/backend/agents/base.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/agents/base.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
  **Diffs between unique versions:**
  - primary vs `./packages/doc_processor/skills/ppt/ooxml/scripts/validation/base.py`: `909 changed lines`
  - primary vs `./packages/doc_processor/skills/xlsx/templates/base.py`: `617 changed lines`
  **Recommendation:** keep newest/largest — newer and larger variant exists; compare content

### `batch_ocr.py` (3 files, 2 unique versions)
- **Primary (keep):** `./packages/vision/batch_ocr.py` — 14379 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/vision/batch_ocr.py` — 14427 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./packages/file_processor/modules/vision/batch_ocr.py`~~ — 14427 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/vision/batch_ocr.py`: `17 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/modules/vision/batch_ocr.py`); verify it includes all content

### `classifier.py` (7 files, 4 unique versions)
- **Primary (keep):** `./packages/core/classifier.py` — 25478 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/core/classifier.py` — 25486 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/core/classifier.py`~~ — 25486 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/core/classifier.py`~~ — 25486 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/core/classifier.py`~~ — 25486 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/classifier.py` — 25487 bytes — 2026-07-07 18:45:30 +0000
- **Keep (non-primary cluster):** `./packages/data-prep/classifier.py` — 11646 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/core/classifier.py`: `40 changed lines`
  - primary vs `./hf-space/packages/core/classifier.py`: `38 changed lines`
  - primary vs `./packages/data-prep/classifier.py`: `720 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/omnifile/modules/core/classifier.py`); verify it includes all content

### `cli.py` (6 files, 5 unique versions)
- **Primary (keep):** `./packages/ocr_postprocess/src/medical_ocr_postprocessor/cli.py` — 13163 bytes — 2026-07-06 18:50:49 +0000
  - ~~`./hf-space/packages/ocr_postprocess/src/medical_ocr_postprocessor/cli.py`~~ — 13163 bytes — 2026-07-07 18:45:30 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/meiguanxiHXX-historyReviewAgent/historical_review/web/cli.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./hf-space/packages/scanner_fixer/src/scanner_fixer/cli.py` — 4543 bytes — 2026-07-07 18:45:30 +0000
- **Keep (non-primary cluster):** `./packages/scanner_fixer/src/scanner_fixer/cli.py` — 4543 bytes — 2026-07-06 18:50:48 +0000
- **Keep (non-primary cluster):** `./packages/gt_core/tools/ocr-groundtruth/src/ocr_groundtruth/cli.py` — 3886 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/scanner_fixer/src/scanner_fixer/cli.py`: `405 changed lines`
  - primary vs `./packages/scanner_fixer/src/scanner_fixer/cli.py`: `405 changed lines`
  - primary vs `./packages/gt_core/tools/ocr-groundtruth/src/ocr_groundtruth/cli.py`: `372 changed lines`
  **Recommendation:** keep newest — newer variant exists (e.g. `./hf-space/packages/scanner_fixer/src/scanner_fixer/cli.py`); verify it's a superset

### `client.py` (16 files, 15 unique versions)
- **Primary (keep):** `./packages/ai/gateway/providers/llamacpp/client.py` — 501 bytes — 2026-05-26 01:20:07 +0000
  - ~~`./packages/file_processor/modules/ai/gateway/providers/llamacpp/client.py`~~ — 501 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/providers/lmstudio/client.py` — 501 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/ai/gateway/providers/deepseek/client.py` — 1649 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/ai/gateway/providers/ollama/client.py` — 1363 bytes — 2026-05-26 01:20:07 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/providers/ollama/client.py` — 1363 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/ai/gateway/providers/wafer/client.py` — 1362 bytes — 2026-05-26 01:20:07 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/providers/kimi/client.py` — 882 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/ai/gateway/providers/nvidia_nim/client.py` — 2762 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/providers/deepseek/client.py` — 1650 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/providers/open_router/client.py` — 4429 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/ai/gateway/providers/kimi/client.py` — 881 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/providers/wafer/client.py` — 1362 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/ai/gateway/providers/lmstudio/client.py` — 501 bytes — 2026-05-26 01:20:07 +0000
- **Keep (non-primary cluster):** `./packages/ai/gateway/providers/open_router/client.py` — 4428 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/providers/nvidia_nim/client.py` — 2763 bytes — 2026-07-06 18:52:25 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/file_processor/modules/ai/gateway/providers/lmstudio/client.py`: `12 changed lines`
  - primary vs `./packages/ai/gateway/providers/deepseek/client.py`: `39 changed lines`
  - primary vs `./packages/ai/gateway/providers/ollama/client.py`: `31 changed lines`
  - primary vs `./packages/file_processor/modules/ai/gateway/providers/ollama/client.py`: `31 changed lines`
  - primary vs `./packages/ai/gateway/providers/wafer/client.py`: `31 changed lines`
  - primary vs `./packages/file_processor/modules/ai/gateway/providers/kimi/client.py`: `25 changed lines`
  - primary vs `./packages/ai/gateway/providers/nvidia_nim/client.py`: `71 changed lines`
  - primary vs `./packages/file_processor/modules/ai/gateway/providers/deepseek/client.py`: `39 changed lines`
  - primary vs `./packages/file_processor/modules/ai/gateway/providers/open_router/client.py`: `108 changed lines`
  - primary vs `./packages/ai/gateway/providers/kimi/client.py`: `25 changed lines`
  - primary vs `./packages/file_processor/modules/ai/gateway/providers/wafer/client.py`: `31 changed lines`
  - primary vs `./packages/ai/gateway/providers/lmstudio/client.py`: `12 changed lines`
  - primary vs `./packages/ai/gateway/providers/open_router/client.py`: `108 changed lines`
  - primary vs `./packages/file_processor/modules/ai/gateway/providers/nvidia_nim/client.py`: `71 changed lines`
  **Recommendation:** keep newest/largest — newer and larger variant exists; compare content

### `code_protector.py` (4 files, 2 unique versions)
- **Primary (keep):** `./packages/security/code_protector.py` — 22296 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/security/code_protector.py` — 22394 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/security/code_protector.py`~~ — 22394 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/security/code_protector.py`~~ — 22394 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/security/code_protector.py`: `10 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/modules/security/code_protector.py`); verify it includes all content

### `config.py` (32 files, 30 unique versions)
- **Primary (keep):** `./packages/handwriting/config.py` — 11046 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/config.py`~~ — 11046 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/config.py`~~ — 11046 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/xujikai-SentenceExpandAgent/backend/src/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/YYHDBL-HelloCodeAgentCli/core/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./tools/ai_fuel/core/config.py` — 12281 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./labs/omniparse_study/omniparse/web/config.py` — 1471 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/melxy1997-ColumnWriter/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/config.py` — 12470 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/core/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/haoye2-UnivesalAgent/src/agents/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/mobile_review/split/10-backend-api/config.py` — 777 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter13/helloagents-trip-planner/backend/app/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Shawnxyxy-HealthRecordAgent/backend/core/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/usernamedadad-AutoFlow/backend/app/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/rss_digest/src/rss_digest/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/meiguanxiHXX-historyReviewAgent/historical_review/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/omniparse/omniparse/web/config.py` — 1470 bytes — 2026-07-06 18:52:26 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/JJason-DeepCastAgent/backend/src/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter14/helloagents-deepresearch/backend/src/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/backend/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/deep_research/src/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter15/Helloagents-AI-Town/backend/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/tino-chen-HelloClaw/src/api/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/config.py` — 10798 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/ai-fuel/core/config.py` — 12281 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/939147533-DatabaseAgent/src/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/afei-GuessWhoAmI/backend/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/config.py` — 15815 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/financial-services/claude-for-msft-365-install/examples/python-bootstrap/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/healer-666-Academic-Data-Agent/src/data_analysis_agent/config.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./apps/handwriting-demo/hf-deploy/app/config.py` — 199 bytes — 2026-07-06 18:50:49 +0000
  **Diffs between unique versions:**
  - primary vs `./tools/ai_fuel/core/config.py`: `456 changed lines`
  - primary vs `./labs/omniparse_study/omniparse/web/config.py`: `268 changed lines`
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/config.py`: `433 changed lines`
  - primary vs `./packages/file_processor/legacy/mobile_review/split/10-backend-api/config.py`: `264 changed lines`
  - primary vs `./packages/omniparse/omniparse/web/config.py`: `268 changed lines`
  - primary vs `./tools/HandwrittenOCR/config.py`: `407 changed lines`
  - primary vs `./packages/ai-fuel/core/config.py`: `456 changed lines`
  - primary vs `./packages/file_processor/config.py`: `104 changed lines`
  - primary vs `./apps/handwriting-demo/hf-deploy/app/config.py`: `246 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./tools/ai_fuel/core/config.py`); verify it includes all content

### `conftest.py` (7 files, 5 unique versions)
- **Primary (keep):** `./tests/conftest.py` — 7018 bytes — 2026-07-08 14:54:13 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/conftest.py` — 2890 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/handwriting/tests/conftest.py`~~ — 2890 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/conftest.py`~~ — 2890 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/desktop/conftest.py` — 197 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/tests/conftest.py` — 3137 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/tests/conftest.py` — 1098 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/conftest.py`: `214 changed lines`
  - primary vs `./packages/desktop/conftest.py`: `167 changed lines`
  - primary vs `./apps/handwriting-demo/tests/conftest.py`: `238 changed lines`
  - primary vs `./packages/file_processor/tests/conftest.py`: `180 changed lines`
  **Recommendation:** keep newest — newer variant exists (e.g. `./packages/desktop/conftest.py`); verify it's a superset

### `constants.py` (4 files, 3 unique versions)
- **Primary (keep):** `./packages/ai/gateway/api/web_tools/constants.py` — 602 bytes — 2026-05-26 01:20:07 +0000
  - ~~`./packages/file_processor/modules/ai/gateway/api/web_tools/constants.py`~~ — 602 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/config/constants.py` — 443 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/ai/gateway/config/constants.py` — 443 bytes — 2026-05-26 01:20:07 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/file_processor/modules/ai/gateway/config/constants.py`: `20 changed lines`
  - primary vs `./packages/ai/gateway/config/constants.py`: `20 changed lines`
  **Recommendation:** keep newest — newer variant exists (e.g. `./packages/file_processor/modules/ai/gateway/config/constants.py`); verify it's a superset

### `core.py` (3 files, 2 unique versions)
- **Primary (keep):** `./packages/ocr_postprocess/src/medical_ocr_postprocessor/core.py` — 22570 bytes — 2026-07-06 18:50:49 +0000
  - ~~`./hf-space/packages/ocr_postprocess/src/medical_ocr_postprocessor/core.py`~~ — 22570 bytes — 2026-07-07 18:45:30 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/doc_processor/skills/ui-ux-pro-max/scripts/core.py` — 10227 bytes — 2026-07-06 18:50:50 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/doc_processor/skills/ui-ux-pro-max/scripts/core.py`: `735 changed lines`
  **Recommendation:** keep newest — newer variant exists (e.g. `./hf-space/packages/ocr_postprocess/src/medical_ocr_postprocessor/core.py`); verify it's a superset

### `correction.py` (7 files, 5 unique versions)
- **Primary (keep):** `./packages/benchmark_core/benchmarks/postprocessor/correction.py` — 10598 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/src/correction.py` — 30840 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/src/correction.py`~~ — 30840 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/src/correction.py`~~ — 30840 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/correction.py` — 6170 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/src/correction.py` — 20071 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/src/correction.py` — 14018 bytes — 2026-07-06 18:52:25 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/src/correction.py`: `898 changed lines`
  - primary vs `./tools/HandwrittenOCR/src/correction.py`: `397 changed lines`
  - primary vs `./packages/file_processor/src/correction.py`: `665 changed lines`
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/src/correction.py`: `541 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/src/correction.py`); verify it includes all content

### `data_augmentation.py` (5 files, 3 unique versions)
- **Primary (keep):** `./packages/vision/data_augmentation.py` — 30388 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/data_augmentation.py` — 30424 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/data_augmentation.py`~~ — 30424 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/data_augmentation.py`~~ — 30424 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/data_augmentation.py` — 30533 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/data_augmentation.py`: `18 changed lines`
  - primary vs `./hf-space/packages/vision/data_augmentation.py`: `25 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/modules/vision/data_augmentation.py`); verify it includes all content

### `database.py` (14 files, 11 unique versions)
- **Primary (keep):** `./packages/handwriting/src/database.py` — 507 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/src/database.py`~~ — 507 bytes — 2026-07-06 18:52:26 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/src/database.py`~~ — 507 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/src/database.py`~~ — 507 bytes — 2026-07-07 12:21:24 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/src/database.py` — 10647 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/database.py` — 50954 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./app/config/database.py` — 1712 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/hf-deploy/app/database.py` — 7865 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/database.py` — 50958 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/database.py` — 50958 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/database.py` — 10610 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/core/database.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/mobile_review/split/10-backend-api/database.py` — 697 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/omnifile/database.py` — 50958 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/src/database.py`: `250 changed lines`
  - primary vs `./packages/file_processor/database.py`: `1090 changed lines`
  - primary vs `./app/config/database.py`: `57 changed lines`
  - primary vs `./apps/handwriting-demo/hf-deploy/app/database.py`: `206 changed lines`
  - primary vs `./packages/handwriting/database.py`: `1090 changed lines`
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/database.py`: `1090 changed lines`
  - primary vs `./tools/HandwrittenOCR/src/database.py`: `249 changed lines`
  - primary vs `./packages/file_processor/legacy/mobile_review/split/10-backend-api/database.py`: `29 changed lines`
  - primary vs `./packages/omnifile/database.py`: `1090 changed lines`
  **Recommendation:** keep newest/largest — newer and larger variant exists; compare content

### `database_manager.py` (6 files, 4 unique versions)
- **Primary (keep):** `./packages/core/database_manager.py` — 15519 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/core/database_manager.py` — 15600 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/core/database_manager.py`~~ — 15600 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/core/database_manager.py`~~ — 15600 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/database_manager.py` — 15691 bytes — 2026-07-07 18:45:30 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/core/database_manager.py` — 15689 bytes — 2026-07-06 18:52:25 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/core/database_manager.py`: `229 changed lines`
  - primary vs `./hf-space/packages/core/database_manager.py`: `51 changed lines`
  - primary vs `./packages/file_processor/modules/core/database_manager.py`: `53 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/handwriting/modules/core/database_manager.py`); verify it includes all content

### `dataset_generator.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/core/dataset_generator.py` — 14793 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/dataset_generator.py` — 14834 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/core/dataset_generator.py`~~ — 14834 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/core/dataset_generator.py`~~ — 14834 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/core/dataset_generator.py`~~ — 14834 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/dataset_generator.py` — 14860 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/dataset_generator.py`: `28 changed lines`
  - primary vs `./hf-space/packages/core/dataset_generator.py`: `27 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/omnifile/modules/core/dataset_generator.py`); verify it includes all content

### `db_manager.py` (4 files, 3 unique versions)
- **Primary (keep):** `./packages/core/db_manager.py` — 12731 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/doc-processor/packages/core/db_manager.py` — 12286 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/doc_processor/packages/core/db_manager.py`~~ — 12286 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/db_manager.py` — 12829 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/doc-processor/packages/core/db_manager.py`: `18 changed lines`
  - primary vs `./hf-space/packages/core/db_manager.py`: `29 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/core/db_manager.py`); verify it includes all content

### `document_schemas.py` (4 files, 2 unique versions)
- **Primary (keep):** `./packages/core/document_schemas.py` — 3089 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/doc-processor/packages/core/document_schemas.py`~~ — 3089 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/doc_processor/packages/core/document_schemas.py`~~ — 3089 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/document_schemas.py` — 3207 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/core/document_schemas.py`: `69 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/core/document_schemas.py`); verify it includes all content

### `encryption.py` (8 files, 6 unique versions)
- **Primary (keep):** `./packages/core/encryption.py` — 7360 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/doc-processor/packages/core/encryption.py`~~ — 7360 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/doc_processor/packages/core/encryption.py`~~ — 7360 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/handwriting/modules/security/encryption.py` — 8247 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/encryption.py` — 8247 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/security/encryption.py` — 8768 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/security/encryption.py` — 8728 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/core/encryption.py` — 7387 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/security/encryption.py`: `315 changed lines`
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/encryption.py`: `315 changed lines`
  - primary vs `./packages/file_processor/modules/security/encryption.py`: `323 changed lines`
  - primary vs `./packages/security/encryption.py`: `320 changed lines`
  - primary vs `./hf-space/packages/core/encryption.py`: `27 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/handwriting/modules/security/encryption.py`); verify it includes all content

### `engine.py` (4 files, 3 unique versions)
- **Primary (keep):** `./packages/ai-fuel/engine.py` — 35125 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./tools/ai_fuel/engine.py`~~ — 35125 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./tools/ai_fuel/dedup/engine.py` — 9477 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/ai-fuel/dedup/engine.py` — 9477 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./tools/ai_fuel/dedup/engine.py`: `945 changed lines`
  - primary vs `./packages/ai-fuel/dedup/engine.py`: `945 changed lines`
  **Recommendation:** keep packages/ version — primary is in canonical packages/ location

### `entity_extractor.py` (6 files, 2 unique versions)
- **Primary (keep):** `./packages/nlp/entity_extractor.py` — 22578 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/entity_extractor.py` — 22609 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/entity_extractor.py`~~ — 22609 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/nlp/entity_extractor.py`~~ — 22609 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/entity_extractor.py`~~ — 22609 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/entity_extractor.py`~~ — 22609 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/nlp/entity_extractor.py`: `3 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/omnifile/modules/nlp/entity_extractor.py`); verify it includes all content

### `exceptions.py` (6 files, 5 unique versions)
- **Primary (keep):** `./packages/ai/gateway/providers/exceptions.py` — 3103 bytes — 2026-05-26 01:20:07 +0000
  - ~~`./packages/file_processor/modules/ai/gateway/providers/exceptions.py`~~ — 3103 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/core/exceptions.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Shawnxyxy-HealthRecordAgent/backend/core/exceptions.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Yixiang-Wu-LearningAgent/utils/exceptions.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/YYHDBL-HelloCodeAgentCli/core/exceptions.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
  **Diffs between unique versions:**
  **Recommendation:** keep newest — newer variant exists (e.g. `./packages/file_processor/modules/ai/gateway/providers/exceptions.py`); verify it's a superset

### `export.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/handwriting/src/export.py` — 11130 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/src/export.py`~~ — 11130 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/src/export.py`~~ — 11130 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/src/export.py`~~ — 11130 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/export.py` — 8756 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/src/export.py` — 8734 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./tools/HandwrittenOCR/src/export.py`: `71 changed lines`
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/src/export.py`: `60 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `exporter.py` (7 files, 4 unique versions)
- **Primary (keep):** `./packages/export/exporter.py` — 22215 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/export/exporter.py` — 22261 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/export/exporter.py`~~ — 22261 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/export/exporter.py`~~ — 22261 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/export/exporter.py`~~ — 22261 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/melxy1997-ColumnWriter/exporter.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/mobile_review/split/11-export-modules/exporter.py` — 4761 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/export/exporter.py`: `15 changed lines`
  - primary vs `./packages/file_processor/legacy/mobile_review/split/11-export-modules/exporter.py`: `647 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/omnifile/modules/export/exporter.py`); verify it includes all content

### `feedback.py` (7 files, 4 unique versions)
- **Primary (keep):** `./packages/nlp/feedback.py` — 18377 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/feedback.py` — 18419 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/feedback.py`~~ — 18419 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/feedback.py`~~ — 18419 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/feedback.py`~~ — 18419 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./app/core/monitoring/feedback.py` — 3652 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/feedback.py` — 18436 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/feedback.py`: `31 changed lines`
  - primary vs `./app/core/monitoring/feedback.py`: `457 changed lines`
  - primary vs `./hf-space/packages/nlp/feedback.py`: `32 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/omnifile/modules/nlp/feedback.py`); verify it includes all content

### `file_fingerprint.py` (6 files, 4 unique versions)
- **Primary (keep):** `./packages/core/file_fingerprint.py` — 15882 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/file_fingerprint.py` — 15569 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/handwriting/modules/core/file_fingerprint.py`~~ — 15569 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/core/file_fingerprint.py`~~ — 15569 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/modules/core/file_fingerprint.py` — 15855 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/core/file_fingerprint.py` — 15906 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/file_fingerprint.py`: `213 changed lines`
  - primary vs `./packages/file_processor/modules/core/file_fingerprint.py`: `22 changed lines`
  - primary vs `./hf-space/packages/core/file_fingerprint.py`: `16 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/core/file_fingerprint.py`); verify it includes all content

### `file_organizer.py` (4 files, 2 unique versions)
- **Primary (keep):** `./packages/security/file_organizer.py` — 19869 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/file_organizer.py` — 19876 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/security/file_organizer.py`~~ — 19876 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/security/file_organizer.py`~~ — 19876 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/file_organizer.py`: `8 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/file_organizer.py`); verify it includes all content

### `file_scanner.py` (4 files, 2 unique versions)
- **Primary (keep):** `./packages/security/file_scanner.py` — 25805 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/security/file_scanner.py` — 25842 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/security/file_scanner.py`~~ — 25842 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/security/file_scanner.py`~~ — 25842 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/security/file_scanner.py`: `7 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/handwriting/modules/security/file_scanner.py`); verify it includes all content

### `finetuning.py` (14 files, 9 unique versions)
- **Primary (keep):** `./packages/ai/finetuning.py` — 12997 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/finetuning.py` — 17802 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/finetuning.py`~~ — 17802 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/finetuning.py`~~ — 17802 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/src/finetuning.py` — 4812 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/handwriting/src/finetuning.py`~~ — 4812 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/src/finetuning.py`~~ — 4812 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/mobile_review/split/12-active-learning/finetuning.py` — 13065 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/ai/finetuning.py`~~ — 13065 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/finetuning.py` — 17955 bytes — 2026-07-07 18:45:30 +0000
- **Keep (non-primary cluster):** `./packages/vision/finetuning.py` — 17749 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/src/finetuning.py` — 4163 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/src/finetuning.py` — 5020 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/finetuning.py` — 4164 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/finetuning.py`: `684 changed lines`
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/src/finetuning.py`: `440 changed lines`
  - primary vs `./packages/file_processor/legacy/mobile_review/split/12-active-learning/finetuning.py`: `52 changed lines`
  - primary vs `./hf-space/packages/vision/finetuning.py`: `686 changed lines`
  - primary vs `./packages/vision/finetuning.py`: `682 changed lines`
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/src/finetuning.py`: `429 changed lines`
  - primary vs `./packages/file_processor/src/finetuning.py`: `440 changed lines`
  - primary vs `./tools/HandwrittenOCR/src/finetuning.py`: `429 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/modules/vision/finetuning.py`); verify it includes all content

### `gemini_refiner.py` (5 files, 2 unique versions)
- **Primary (keep):** `./packages/ai/gemini_refiner.py` — 8592 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/gemini_refiner.py` — 8629 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/ai/gemini_refiner.py`~~ — 8629 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/ai/gemini_refiner.py`~~ — 8629 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/ai/gemini_refiner.py`~~ — 8629 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/gemini_refiner.py`: `7 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/handwriting/modules/ai/gemini_refiner.py`); verify it includes all content

### `gradio_ui.py` (5 files, 3 unique versions)
- **Primary (keep):** `./packages/handwriting/src/gradio_ui.py` — 0 bytes — 2026-07-10 18:00:29 +0000 (DELETED)
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/src/gradio_ui.py`~~ — 0 bytes — 2026-07-10 18:00:29 +0000 (DELETED) → identical to primary, safe to delete
  - ~~`./packages/omnifile/src/gradio_ui.py`~~ — 0 bytes — 2026-07-10 18:00:29 +0000 (DELETED) → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./app/gradio_ui.py` — 4122 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/src/gradio_ui.py` — 0 bytes — 2026-07-10 18:00:29 +0000 (DELETED)
  **Recommendation:** Primary is deleted — consider `./app/gradio_ui.py` as replacement

### `handwriting_db.py` (6 files, 4 unique versions)
- **Primary (keep):** `./packages/core/handwriting_db.py` — 11572 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/core/handwriting_db.py` — 11736 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/core/handwriting_db.py`~~ — 11736 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/core/handwriting_db.py`~~ — 11736 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/modules/core/handwriting_db.py` — 11270 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/core/handwriting_db.py` — 11634 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/core/handwriting_db.py`: `97 changed lines`
  - primary vs `./packages/file_processor/modules/core/handwriting_db.py`: `22 changed lines`
  - primary vs `./hf-space/packages/core/handwriting_db.py`: `10 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/handwriting/modules/core/handwriting_db.py`); verify it includes all content

### `hf_app.py` (5 files, 4 unique versions)
- **Primary (keep):** `./packages/handwriting/hf_app.py` — 0 bytes — 2026-07-10 18:00:29 +0000 (DELETED)
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/hf_app.py`~~ — 0 bytes — 2026-07-10 18:00:29 +0000 (DELETED) → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/hf_app.py` — 0 bytes — 2026-07-10 18:00:29 +0000 (DELETED)
- **Keep (non-primary cluster):** `./app/hf_app.py` — 78815 bytes — 2026-07-10 18:00:29 +0000
- **Keep (non-primary cluster):** `./packages/omnifile/hf_app.py` — 0 bytes — 2026-07-10 18:00:29 +0000 (DELETED)
  **Recommendation:** Primary is deleted — consider `./app/hf_app.py` as replacement

### `htr_config.py` (3 files, 2 unique versions)
- **Primary (keep):** `./packages/file_processor/modules/config/htr_config.py` — 1365 bytes — 2026-07-06 18:52:25 +0000
  - ~~`./hf-space/packages/config/htr_config.py`~~ — 1365 bytes — 2026-07-07 18:45:30 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/config/htr_config.py` — 1307 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/config/htr_config.py`: `6 changed lines`
  **Recommendation:** keep newest — newer variant exists (e.g. `./hf-space/packages/config/htr_config.py`); verify it's a superset

### `image_preprocessor.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/vision/image_preprocessor.py` — 20889 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/vision/image_preprocessor.py` — 20900 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/image_preprocessor.py`~~ — 20900 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/vision/image_preprocessor.py`~~ — 20900 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/image_preprocessor.py`~~ — 20900 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./apps/ocr-pipeline/src/preprocessing/image_preprocessor.py` — 18213 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/vision/image_preprocessor.py`: `6 changed lines`
  - primary vs `./apps/ocr-pipeline/src/preprocessing/image_preprocessor.py`: `890 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/image_preprocessor.py`); verify it includes all content

### `image_processor.py` (4 files, 2 unique versions)
- **Primary (keep):** `./packages/core/image_processor.py` — 16509 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/doc-processor/packages/core/image_processor.py`~~ — 16509 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/doc_processor/packages/core/image_processor.py`~~ — 16509 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/image_processor.py` — 16537 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/core/image_processor.py`: `14 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/core/image_processor.py`); verify it includes all content

### `language_corrector.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/nlp/language_corrector.py` — 11794 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/language_corrector.py` — 11817 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/language_corrector.py`~~ — 11817 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/language_corrector.py`~~ — 11817 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/language_corrector.py`~~ — 11817 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/language_corrector.py` — 11825 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/language_corrector.py`: `18 changed lines`
  - primary vs `./hf-space/packages/nlp/language_corrector.py`: `16 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/omnifile/modules/nlp/language_corrector.py`); verify it includes all content

### `language_detector.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/nlp/language_detector.py` — 11330 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/language_detector.py` — 11346 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/language_detector.py`~~ — 11346 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/language_detector.py`~~ — 11346 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/language_detector.py`~~ — 11346 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/language_detector.py` — 11436 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/language_detector.py`: `9 changed lines`
  - primary vs `./hf-space/packages/nlp/language_detector.py`: `10 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/modules/nlp/language_detector.py`); verify it includes all content

### `layout_analyzer.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/vision/layout_analyzer.py` — 11647 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/layout_analyzer.py` — 11646 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/layout_analyzer.py`~~ — 11646 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/layout_analyzer.py`~~ — 11646 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/layout_analyzer.py`~~ — 11646 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/layout_analyzer.py` — 11675 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/layout_analyzer.py`: `2 changed lines`
  - primary vs `./hf-space/packages/vision/layout_analyzer.py`: `1 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/vision/layout_analyzer.py`); verify it includes all content

### `layout_preserving.py` (5 files, 3 unique versions)
- **Primary (keep):** `./packages/handwriting/modules/export/layout_preserving.py` — 9107 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/export/layout_preserving.py`~~ — 9107 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/modules/export/layout_preserving.py`~~ — 9107 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/mobile_review/split/03-layout-preserving-export/layout_preserving.py` — 4056 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/export/layout_preserving.py` — 9430 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/file_processor/legacy/mobile_review/split/03-layout-preserving-export/layout_preserving.py`: `228 changed lines`
  - primary vs `./packages/file_processor/modules/export/layout_preserving.py`: `6 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/modules/export/layout_preserving.py`); verify it includes all content

### `logger.py` (10 files, 7 unique versions)
- **Primary (keep):** `./packages/handwriting/src/logger.py` — 17501 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/src/logger.py`~~ — 17501 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/src/logger.py`~~ — 17501 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/src/logger.py`~~ — 17501 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Yixiang-Wu-LearningAgent/utils/logger.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/src/logger.py` — 1176 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter15/Helloagents-AI-Town/backend/logger.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/doc_processor/download/medical-image-ai-suite/src/utils/logger.py` — 3030 bytes — 2026-07-06 18:50:50 +0000
- **Keep (non-primary cluster):** `./apps/ocr-pipeline/src/utils/logger.py` — 7237 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/logger.py` — 1177 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/src/logger.py`: `401 changed lines`
  - primary vs `./packages/doc_processor/download/medical-image-ai-suite/src/utils/logger.py`: `428 changed lines`
  - primary vs `./apps/ocr-pipeline/src/utils/logger.py`: `542 changed lines`
  - primary vs `./tools/HandwrittenOCR/src/logger.py`: `401 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `main.py` (40 files, 37 unique versions)
- **Primary (keep):** `./packages/handwriting/src/main.py` — 8220 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/src/main.py`~~ — 8220 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/src/main.py`~~ — 8220 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/src/main.py`~~ — 8220 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/main.py` — 4047 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/tino-chen-HelloClaw/src/cli/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Shawnxyxy-HealthRecordAgent/backend/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/src/main.py` — 7870 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/deep_research/src/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter13/helloagents-trip-planner/backend/app/api/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/mobile_review/split/10-backend-api/main.py` — 13136 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Yixiang-Wu-LearningAgent/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/usernamedadad-AutoFlow/backend/app/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/haoye2-UnivesalAgent/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Shawnxyxy-HealthRecordAgent/backend/api/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/lll0807-CodeTutorAgent/programmer/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/main.py` — 4047 bytes — 2026-07-06 18:52:26 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/api/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter9/project/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/melxy1997-ColumnWriter/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/main.py` — 5336 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/939147533-DatabaseAgent/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/handwriting/main.py` — 4047 bytes — 2026-07-07 12:21:28 +0000
- **Keep (non-primary cluster):** `./packages/omnifile/main.py` — 4047 bytes — 2026-07-07 12:21:24 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/xujikai-SentenceExpandAgent/backend/src/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/tino-chen-HelloClaw/src/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/backend/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/afei-GuessWhoAmI/backend/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter14/helloagents-deepresearch/backend/src/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./app/main.py` — 5380 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/lgs-only-NovelGenerator/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/angelen-SoftwareDevHelper/src/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/pamdla-MindEchoAgent/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/alexrunner-DataAnalysisAgent/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/rss_digest/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/zjzhou-SREOnCallAgent/src/api/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/JJason-DeepCastAgent/backend/src/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter15/Helloagents-AI-Town/backend/main.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
  **Diffs between unique versions:**
  - primary vs `./packages/file_processor/main.py`: `271 changed lines`
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/src/main.py`: `11 changed lines`
  - primary vs `./packages/file_processor/legacy/mobile_review/split/10-backend-api/main.py`: `482 changed lines`
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/main.py`: `271 changed lines`
  - primary vs `./tools/HandwrittenOCR/src/main.py`: `67 changed lines`
  - primary vs `./packages/handwriting/main.py`: `271 changed lines`
  - primary vs `./packages/omnifile/main.py`: `271 changed lines`
  - primary vs `./app/main.py`: `291 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/legacy/mobile_review/split/10-backend-api/main.py`); verify it includes all content

### `markdown_exporter.py` (5 files, 2 unique versions)
- **Primary (keep):** `./packages/export/markdown_exporter.py` — 4537 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/export/markdown_exporter.py` — 4568 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/export/markdown_exporter.py`~~ — 4568 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/export/markdown_exporter.py`~~ — 4568 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/export/markdown_exporter.py`~~ — 4568 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/export/markdown_exporter.py`: `3 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/modules/export/markdown_exporter.py`); verify it includes all content

### `medical_doc_gui_final.py` (3 files, 2 unique versions)
- **Primary (keep):** `./packages/doc_processor/desktop/medical_doc_gui_final.py` — 35993 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/doc-processor/desktop/medical_doc_gui_final.py`~~ — 35993 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/desktop/medical_doc_gui_final.py` — 139948 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/desktop/medical_doc_gui_final.py`: `3221 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/desktop/medical_doc_gui_final.py`); verify it includes all content

### `metrics.py` (21 files, 14 unique versions)
- **Primary (keep):** `./packages/evaluation/metrics.py` — 10047 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/src/metrics.py` — 3019 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/src/metrics.py`~~ — 3019 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/legacy/ocr_unified_v2/src/metrics.py`~~ — 3019 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/src/metrics.py`~~ — 3019 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/src/metrics.py`~~ — 3019 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/handwriting/modules/evaluation/metrics.py` — 8743 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/evaluation/metrics.py`~~ — 8743 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/evaluation/metrics.py`~~ — 8743 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/ai-fuel/core/metrics.py` — 6952 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./tools/ai_fuel/core/metrics.py`~~ — 6952 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/metrics.py` — 3019 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/evaluation/metrics.py` — 10088 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/training/utils/metrics.py` — 1450 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./app/core/monitoring/metrics.py` — 6247 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/doc_processor/download/medical-image-ai-suite/src/utils/metrics.py` — 8450 bytes — 2026-07-06 18:50:50 +0000
- **Keep (non-primary cluster):** `./packages/training-framework/utils/metrics.py` — 1484 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./src/evaluation/metrics.py` — 3117 bytes — 2026-07-08 23:18:50 +0000
- **Keep (non-primary cluster):** `./apps/trainer-ui/evaluation/metrics.py` — 8723 bytes — 2026-07-06 18:52:26 +0000
- **Keep (non-primary cluster):** `./packages/benchmark_core/src/benchmarks/metrics.py` — 9473 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/benchmark_core/benchmarks/core/metrics.py` — 17312 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/src/metrics.py`: `292 changed lines`
  - primary vs `./packages/handwriting/modules/evaluation/metrics.py`: `32 changed lines`
  - primary vs `./packages/ai-fuel/core/metrics.py`: `388 changed lines`
  - primary vs `./tools/HandwrittenOCR/src/metrics.py`: `292 changed lines`
  - primary vs `./packages/file_processor/modules/evaluation/metrics.py`: `7 changed lines`
  - primary vs `./packages/file_processor/training/utils/metrics.py`: `258 changed lines`
  - primary vs `./app/core/monitoring/metrics.py`: `366 changed lines`
  - primary vs `./packages/doc_processor/download/medical-image-ai-suite/src/utils/metrics.py`: `415 changed lines`
  - primary vs `./packages/training-framework/utils/metrics.py`: `257 changed lines`
  - primary vs `./src/evaluation/metrics.py`: `296 changed lines`
  - primary vs `./apps/trainer-ui/evaluation/metrics.py`: `423 changed lines`
  - primary vs `./packages/benchmark_core/src/benchmarks/metrics.py`: `402 changed lines`
  - primary vs `./packages/benchmark_core/benchmarks/core/metrics.py`: `648 changed lines`
  **Recommendation:** keep newest/largest — newer and larger variant exists; compare content

### `migration.py` (9 files, 7 unique versions)
- **Primary (keep):** `./packages/core/migration/migration.py` — 20383 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/src/migration.py` — 26156 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/handwriting/src/migration.py`~~ — 26156 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/src/migration.py`~~ — 26156 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/migration/migration.py` — 20447 bytes — 2026-07-07 18:45:30 +0000
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/migration.py` — 20295 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/src/migration.py` — 20268 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/core/migration/migration.py` — 20356 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/src/migration.py` — 26455 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/src/migration.py`: `140 changed lines`
  - primary vs `./hf-space/packages/core/migration/migration.py`: `27 changed lines`
  - primary vs `./tools/HandwrittenOCR/src/migration.py`: `2 changed lines`
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/src/migration.py`: `21 changed lines`
  - primary vs `./packages/file_processor/modules/core/migration/migration.py`: `19 changed lines`
  - primary vs `./packages/file_processor/src/migration.py`: `150 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/omnifile/src/migration.py`); verify it includes all content

### `mixed_language.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/nlp/mixed_language.py` — 7360 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/nlp/mixed_language.py` — 7211 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/mixed_language.py`~~ — 7211 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/mixed_language.py`~~ — 7211 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/mixed_language.py` — 7394 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./packages/file_processor/modules/nlp/mixed_language.py`~~ — 7394 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/nlp/mixed_language.py`: `10 changed lines`
  - primary vs `./hf-space/packages/nlp/mixed_language.py`: `7 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/nlp/mixed_language.py`); verify it includes all content

### `mixed_text.py` (6 files, 2 unique versions)
- **Primary (keep):** `./packages/nlp/mixed_text.py` — 6733 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/mixed_text.py`~~ — 6733 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/modules/nlp/mixed_text.py`~~ — 6733 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/handwriting/modules/nlp/mixed_text.py`~~ — 6733 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/modules/nlp/mixed_text.py`~~ — 6733 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/mixed_text.py` — 6786 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/nlp/mixed_text.py`: `3 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/nlp/mixed_text.py`); verify it includes all content

### `normalize.py` (6 files, 2 unique versions)
- **Primary (keep):** `./packages/vision/normalize.py` — 7750 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/vision/normalize.py` — 7782 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/normalize.py`~~ — 7782 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/vision/normalize.py`~~ — 7782 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/normalize.py`~~ — 7782 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/normalize.py`~~ — 7782 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/vision/normalize.py`: `10 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/normalize.py`); verify it includes all content

### `ocr_engine.py` (7 files, 4 unique versions)
- **Primary (keep):** `./packages/vision/ocr_engine.py` — 53856 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/ocr_engine.py` — 53939 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/ocr_engine.py`~~ — 53939 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/ocr_engine.py`~~ — 53939 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/ocr_engine.py`~~ — 53939 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/ocr_engine.py` — 54022 bytes — 2026-07-07 18:45:30 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/hf-deploy/app/ocr_engine.py` — 12821 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/ocr_engine.py`: `65 changed lines`
  - primary vs `./hf-space/packages/vision/ocr_engine.py`: `58 changed lines`
  - primary vs `./apps/handwriting-demo/hf-deploy/app/ocr_engine.py`: `1522 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/handwriting/modules/vision/ocr_engine.py`); verify it includes all content

### `orchestrator.py` (4 files, 3 unique versions)
- **Primary (keep):** `./packages/ai-fuel/classifier/orchestrator.py` — 18957 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./tools/ai_fuel/classifier/orchestrator.py`~~ — 18957 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/xujikai-SentenceExpandAgent/backend/src/agents/orchestrator.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/melxy1997-ColumnWriter/orchestrator.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
  **Diffs between unique versions:**
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `parquet_exporter.py` (3 files, 2 unique versions)
- **Primary (keep):** `./packages/ai-fuel/export/parquet_exporter.py` — 6732 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./tools/ai_fuel/export/parquet_exporter.py`~~ — 6732 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./apps/trainer-ui/exports/parquet_exporter.py` — 6500 bytes — 2026-07-06 18:52:26 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/trainer-ui/exports/parquet_exporter.py`: `301 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `pattern_db.py` (6 files, 4 unique versions)
- **Primary (keep):** `./packages/learning/pattern_db.py` — 8729 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/pattern_db.py` — 18039 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/handwriting/modules/ai/pattern_db.py`~~ — 18039 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/ai/pattern_db.py`~~ — 18039 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/modules/learning/pattern_db.py` — 8751 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/pattern_db.py` — 17258 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/pattern_db.py`: `621 changed lines`
  - primary vs `./packages/file_processor/modules/learning/pattern_db.py`: `15 changed lines`
  - primary vs `./packages/file_processor/modules/ai/pattern_db.py`: `575 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/pattern_db.py`); verify it includes all content

### `pattern_matcher.py` (5 files, 2 unique versions)
- **Primary (keep):** `./packages/ai/pattern_matcher.py` — 14417 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/ai/pattern_matcher.py` — 14449 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/pattern_matcher.py`~~ — 14449 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/ai/pattern_matcher.py`~~ — 14449 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/ai/pattern_matcher.py`~~ — 14449 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/ai/pattern_matcher.py`: `22 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/pattern_matcher.py`); verify it includes all content

### `pdf_processor.py` (12 files, 5 unique versions)
- **Primary (keep):** `./packages/vision/pdf_processor.py` — 18438 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/vision/pdf_processor.py` — 18481 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/pdf_processor.py`~~ — 18481 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/vision/pdf_processor.py`~~ — 18481 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/pdf_processor.py`~~ — 18481 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/pdf_processor.py`~~ — 18481 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/src/pdf_processor.py` — 20419 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/src/pdf_processor.py`~~ — 20419 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/src/pdf_processor.py`~~ — 20419 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/src/pdf_processor.py`~~ — 20419 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/src/pdf_processor.py` — 18713 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/pdf_processor.py` — 13075 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/vision/pdf_processor.py`: `29 changed lines`
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/src/pdf_processor.py`: `804 changed lines`
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/src/pdf_processor.py`: `770 changed lines`
  - primary vs `./tools/HandwrittenOCR/src/pdf_processor.py`: `659 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/legacy/ocr_unified_v2/src/pdf_processor.py`); verify it includes all content

### `pdf_to_training_data.py` (5 files, 3 unique versions)
- **Primary (keep):** `./packages/vision/pdf_to_training_data.py` — 32417 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/pdf_to_training_data.py` — 32516 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/pdf_to_training_data.py`~~ — 32516 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/pdf_to_training_data.py`~~ — 32516 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/pdf_to_training_data.py` — 32562 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/pdf_to_training_data.py`: `75 changed lines`
  - primary vs `./hf-space/packages/vision/pdf_to_training_data.py`: `79 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/vision/pdf_to_training_data.py`); verify it includes all content

### `pipeline.py` (16 files, 14 unique versions)
- **Primary (keep):** `./packages/nlp/pipeline.py` — 41449 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/scanner_fixer/src/scanner_fixer/pipeline.py` — 6877 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./packages/scanner_fixer/src/scanner_fixer/pipeline.py`~~ — 6877 bytes — 2026-07-06 18:50:48 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/ai-fuel/export/pipeline.py` — 13757 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./tools/ai_fuel/export/pipeline.py`~~ — 13757 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/usernamedadad-AutoFlow/backend/app/agents/mermaid/pipeline.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/zjzhou-SREOnCallAgent/src/agents/pipeline.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./omni_medical_suite/pipeline.py` — 5178 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/audit/pipeline.py` — 15715 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/audit/pipeline.py` — 15769 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./app/routers/pipeline.py` — 400 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/pipeline.py` — 41491 bytes — 2026-07-07 18:45:30 +0000
- **Keep (non-primary cluster):** `./packages/doc_processor/download/medical-image-ai-suite/services/ocr/data_collection/pipeline.py` — 44611 bytes — 2026-07-06 18:50:50 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/rss_digest/src/rss_digest/pipeline.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/training_hub/src/promotion/pipeline.py` — 19952 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/ocr-pipeline/src/core/pipeline.py` — 33937 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/scanner_fixer/src/scanner_fixer/pipeline.py`: `1084 changed lines`
  - primary vs `./packages/ai-fuel/export/pipeline.py`: `1192 changed lines`
  - primary vs `./omni_medical_suite/pipeline.py`: `1030 changed lines`
  - primary vs `./packages/audit/pipeline.py`: `1202 changed lines`
  - primary vs `./packages/file_processor/modules/audit/pipeline.py`: `1204 changed lines`
  - primary vs `./app/routers/pipeline.py`: `953 changed lines`
  - primary vs `./hf-space/packages/nlp/pipeline.py`: `70 changed lines`
  - primary vs `./packages/doc_processor/download/medical-image-ai-suite/services/ocr/data_collection/pipeline.py`: `1941 changed lines`
  - primary vs `./packages/training_hub/src/promotion/pipeline.py`: `1398 changed lines`
  - primary vs `./apps/ocr-pipeline/src/core/pipeline.py`: `1695 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/nlp/pipeline.py`); verify it includes all content

### `preprocessing.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/handwriting/src/preprocessing.py` — 11298 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/src/preprocessing.py`~~ — 11298 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/src/preprocessing.py`~~ — 11298 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/src/preprocessing.py`~~ — 11298 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/preprocessing.py` — 4967 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/src/preprocessing.py` — 9931 bytes — 2026-07-06 18:52:25 +0000
  **Diffs between unique versions:**
  - primary vs `./tools/HandwrittenOCR/src/preprocessing.py`: `230 changed lines`
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/src/preprocessing.py`: `246 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `process.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/handwriting/process.py` — 11539 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/process.py`~~ — 11539 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/process.py`~~ — 11539 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/process.py`~~ — 11539 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/omniparse/omniparse/image/process.py` — 8208 bytes — 2026-07-06 18:52:26 +0000
- **Keep (non-primary cluster):** `./labs/omniparse_study/omniparse/image/process.py` — 6366 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/omniparse/omniparse/image/process.py`: `447 changed lines`
  - primary vs `./labs/omniparse_study/omniparse/image/process.py`: `406 changed lines`
  **Recommendation:** keep packages/ version — primary is in canonical packages/ location

### `prompts.py` (8 files, 7 unique versions)
- **Primary (keep):** `./packages/omniparse/omniparse/web/prompts.py` — 8052 bytes — 2026-07-06 18:52:26 +0000
  - ~~`./labs/omniparse_study/omniparse/web/prompts.py`~~ — 8052 bytes — 2026-07-06 18:52:26 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter14/helloagents-deepresearch/backend/src/prompts.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/JJason-DeepCastAgent/backend/src/prompts.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/melxy1997-ColumnWriter/prompts.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/deep_research/src/prompts.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/xujikai-SentenceExpandAgent/backend/src/agents/prompts.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/healer-666-Academic-Data-Agent/src/data_analysis_agent/prompts.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
  **Diffs between unique versions:**
  **Recommendation:** keep newest — newer variant exists (e.g. `./labs/omniparse_study/omniparse/web/prompts.py`); verify it's a superset

### `protected_vocab.py` (3 files, 2 unique versions)
- **Primary (keep):** `./packages/core/protected_vocab.py` — 7515 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/core/protected_vocab.py` — 7506 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./packages/file_processor/modules/core/protected_vocab.py`~~ — 7506 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/core/protected_vocab.py`: `2 changed lines`
  **Recommendation:** keep packages/ version — primary is in canonical packages/ location

### `protected_words.py` (5 files, 3 unique versions)
- **Primary (keep):** `./packages/nlp/protected_words.py` — 24903 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/protected_words.py` — 25009 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/protected_words.py`~~ — 25009 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/protected_words.py`~~ — 25009 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/protected_words.py` — 25055 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/protected_words.py`: `20 changed lines`
  - primary vs `./hf-space/packages/nlp/protected_words.py`: `22 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/modules/nlp/protected_words.py`); verify it includes all content

### `rate_limit.py` (4 files, 3 unique versions)
- **Primary (keep):** `./packages/ai/gateway/core/rate_limit.py` — 1754 bytes — 2026-05-26 01:20:07 +0000
  - ~~`./packages/file_processor/modules/ai/gateway/core/rate_limit.py`~~ — 1754 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/ai/gateway/providers/rate_limit.py` — 9291 bytes — 2026-05-26 01:20:07 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/providers/rate_limit.py` — 9291 bytes — 2026-07-06 18:52:25 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/ai/gateway/providers/rate_limit.py`: `256 changed lines`
  - primary vs `./packages/file_processor/modules/ai/gateway/providers/rate_limit.py`: `256 changed lines`
  **Recommendation:** keep newest/largest — newer and larger variant exists; compare content

### `recognition.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/handwriting/src/recognition.py` — 17759 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/src/recognition.py`~~ — 17759 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/src/recognition.py`~~ — 17759 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/src/recognition.py`~~ — 17759 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/src/recognition.py` — 10265 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/recognition.py` — 9340 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/src/recognition.py`: `204 changed lines`
  - primary vs `./tools/HandwrittenOCR/src/recognition.py`: `313 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `reconstruction.py` (12 files, 6 unique versions)
- **Primary (keep):** `./packages/nlp/reconstruction.py` — 8613 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/src/reconstruction.py` — 698 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/src/reconstruction.py`~~ — 698 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/src/reconstruction.py`~~ — 698 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/src/reconstruction.py`~~ — 698 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/reconstruction.py` — 8603 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/reconstruction.py`~~ — 8603 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/reconstruction.py`~~ — 8603 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/reconstruction.py`~~ — 8603 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/reconstruction.py` — 7022 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/src/reconstruction.py` — 7013 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/reconstruction.py` — 8606 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/src/reconstruction.py`: `194 changed lines`
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/reconstruction.py`: `8 changed lines`
  - primary vs `./tools/HandwrittenOCR/src/reconstruction.py`: `145 changed lines`
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/src/reconstruction.py`: `147 changed lines`
  - primary vs `./hf-space/packages/nlp/reconstruction.py`: `14 changed lines`
  **Recommendation:** keep packages/ version — primary is in canonical packages/ location

### `registry.py` (4 files, 3 unique versions)
- **Primary (keep):** `./packages/ai/gateway/providers/registry.py` — 17491 bytes — 2026-05-26 01:20:07 +0000
  - ~~`./packages/file_processor/modules/ai/gateway/providers/registry.py`~~ — 17491 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/YYHDBL-HelloCodeAgentCli/tools/registry.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/backend/agents/registry.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
  **Diffs between unique versions:**
  **Recommendation:** keep newest — newer variant exists (e.g. `./packages/file_processor/modules/ai/gateway/providers/registry.py`); verify it's a superset

### `request.py` (10 files, 9 unique versions)
- **Primary (keep):** `./packages/ai/gateway/api/web_tools/request.py` — 3352 bytes — 2026-05-26 01:20:07 +0000
  - ~~`./packages/file_processor/modules/ai/gateway/api/web_tools/request.py`~~ — 3352 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/providers/deepseek/request.py` — 16596 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/providers/nvidia_nim/request.py` — 9239 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/providers/kimi/request.py` — 1071 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/ai/gateway/providers/open_router/request.py` — 1304 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/ai/gateway/providers/open_router/request.py` — 1304 bytes — 2026-05-26 01:20:07 +0000
- **Keep (non-primary cluster):** `./packages/ai/gateway/providers/kimi/request.py` — 1071 bytes — 2026-05-26 01:20:07 +0000
- **Keep (non-primary cluster):** `./packages/ai/gateway/providers/deepseek/request.py` — 16596 bytes — 2026-05-26 01:20:07 +0000
- **Keep (non-primary cluster):** `./packages/ai/gateway/providers/nvidia_nim/request.py` — 9239 bytes — 2026-05-26 01:20:07 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/file_processor/modules/ai/gateway/providers/deepseek/request.py`: `454 changed lines`
  - primary vs `./packages/file_processor/modules/ai/gateway/providers/nvidia_nim/request.py`: `279 changed lines`
  - primary vs `./packages/file_processor/modules/ai/gateway/providers/kimi/request.py`: `91 changed lines`
  - primary vs `./packages/file_processor/modules/ai/gateway/providers/open_router/request.py`: `96 changed lines`
  - primary vs `./packages/ai/gateway/providers/open_router/request.py`: `96 changed lines`
  - primary vs `./packages/ai/gateway/providers/kimi/request.py`: `91 changed lines`
  - primary vs `./packages/ai/gateway/providers/deepseek/request.py`: `454 changed lines`
  - primary vs `./packages/ai/gateway/providers/nvidia_nim/request.py`: `279 changed lines`
  **Recommendation:** keep newest/largest — newer and larger variant exists; compare content

### `result_fusion.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/vision/result_fusion.py` — 17064 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/result_fusion.py` — 17118 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/result_fusion.py`~~ — 17118 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/result_fusion.py`~~ — 17118 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/result_fusion.py`~~ — 17118 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/result_fusion.py` — 17137 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/result_fusion.py`: `23 changed lines`
  - primary vs `./hf-space/packages/vision/result_fusion.py`: `24 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/handwriting/modules/vision/result_fusion.py`); verify it includes all content

### `review_ui.py` (6 files, 2 unique versions)
- **Primary (keep):** `./packages/handwriting/src/review_ui.py` — 14900 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/src/review_ui.py`~~ — 14900 bytes — 2026-07-06 18:52:26 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/legacy/ocr_unified_v2/src/review_ui.py`~~ — 14900 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/src/review_ui.py`~~ — 14900 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/src/review_ui.py`~~ — 14900 bytes — 2026-07-07 12:21:24 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/review_ui.py` — 14910 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./tools/HandwrittenOCR/src/review_ui.py`: `12 changed lines`
  **Recommendation:** keep newest/largest — newer and larger variant exists; compare content

### `schemas.py` (5 files, 4 unique versions)
- **Primary (keep):** `./packages/file_processor/legacy/mobile_review/split/10-backend-api/schemas.py` — 2449 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/ai-fuel/core/schemas.py` — 11317 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./tools/ai_fuel/core/schemas.py`~~ — 11317 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/usernamedadad-AutoFlow/backend/app/models/schemas.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter13/helloagents-trip-planner/backend/app/models/schemas.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
  **Diffs between unique versions:**
  - primary vs `./packages/ai-fuel/core/schemas.py`: `282 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/ai-fuel/core/schemas.py`); verify it includes all content

### `search_engine.py` (6 files, 4 unique versions)
- **Primary (keep):** `./packages/core/search_engine.py` — 22663 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/search_engine.py` — 21541 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/handwriting/modules/core/search_engine.py`~~ — 21541 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/core/search_engine.py`~~ — 21541 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/search_engine.py` — 22976 bytes — 2026-07-07 18:45:30 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/core/search_engine.py` — 21836 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/search_engine.py`: `274 changed lines`
  - primary vs `./hf-space/packages/core/search_engine.py`: `62 changed lines`
  - primary vs `./packages/file_processor/modules/core/search_engine.py`: `85 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/core/search_engine.py`); verify it includes all content

### `secure_file_handler.py` (4 files, 2 unique versions)
- **Primary (keep):** `./packages/security/secure_file_handler.py` — 5497 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/secure_file_handler.py` — 5531 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/security/secure_file_handler.py`~~ — 5531 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/security/secure_file_handler.py`~~ — 5531 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/secure_file_handler.py`: `5 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/modules/security/secure_file_handler.py`); verify it includes all content

### `sensitive_data_scanner.py` (4 files, 3 unique versions)
- **Primary (keep):** `./packages/security/sensitive_data_scanner.py` — 12901 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/sensitive_data_scanner.py` — 12703 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/handwriting/modules/security/sensitive_data_scanner.py`~~ — 12703 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/modules/security/sensitive_data_scanner.py` — 12907 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/sensitive_data_scanner.py`: `10 changed lines`
  - primary vs `./packages/file_processor/modules/security/sensitive_data_scanner.py`: `7 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/modules/security/sensitive_data_scanner.py`); verify it includes all content

### `server.py` (10 files, 9 unique versions)
- **Primary (keep):** `./packages/ai/gateway/server.py` — 933 bytes — 2026-05-26 01:20:07 +0000
  - ~~`./packages/file_processor/modules/ai/gateway/server.py`~~ — 933 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter10/weather-mcp-server/server.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/handwriting/mobile_review/server.py` — 2556 bytes — 2026-07-07 12:21:28 +0000
- **Keep (non-primary cluster):** `./packages/omniparse/server.py` — 2785 bytes — 2026-07-06 18:52:26 +0000
- **Keep (non-primary cluster):** `./labs/omniparse_study/server.py` — 0 bytes — 2026-07-10 18:00:29 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/mobile_review/server.py` — 5236 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/mobile_review/server.py` — 2556 bytes — 2026-07-06 18:52:26 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/mobile_review/split/02-mobile-review/server.py` — 1766 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/omnifile/mobile_review/server.py` — 2556 bytes — 2026-07-07 12:21:24 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/mobile_review/server.py`: `80 changed lines`
  - primary vs `./packages/omniparse/server.py`: `96 changed lines`
  - primary vs `./packages/file_processor/mobile_review/server.py`: `126 changed lines`
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/mobile_review/server.py`: `80 changed lines`
  - primary vs `./packages/file_processor/legacy/mobile_review/split/02-mobile-review/server.py`: `62 changed lines`
  - primary vs `./packages/omnifile/mobile_review/server.py`: `80 changed lines`
  **Recommendation:** keep newest/largest — newer and larger variant exists; compare content

### `settings.py` (3 files, 2 unique versions)
- **Primary (keep):** `./packages/ai/gateway/config/settings.py` — 20718 bytes — 2026-05-26 01:20:07 +0000
  - ~~`./packages/file_processor/modules/ai/gateway/config/settings.py`~~ — 20718 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./apps/ocr-pipeline/config/settings.py` — 8355 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/ocr-pipeline/config/settings.py`: `643 changed lines`
  **Recommendation:** keep newest — newer variant exists (e.g. `./apps/ocr-pipeline/config/settings.py`); verify it's a superset

### `setup.py` (5 files, 4 unique versions)
- **Primary (keep):** `./packages/bilingual/setup.py` — 963 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/ai-fuel/setup.py` — 38 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./tools/ai_fuel/setup.py`~~ — 38 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./apps/ocr-pipeline/setup.py` — 4831 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/setup.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
  **Diffs between unique versions:**
  - primary vs `./packages/ai-fuel/setup.py`: `37 changed lines`
  - primary vs `./apps/ocr-pipeline/setup.py`: `160 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/ocr-pipeline/setup.py`); verify it includes all content

### `smart_migrator.py` (5 files, 3 unique versions)
- **Primary (keep):** `./packages/core/smart_migrator.py` — 13724 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/smart_migrator.py` — 14301 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/core/smart_migrator.py`~~ — 14301 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/core/smart_migrator.py`~~ — 14301 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/smart_migrator.py` — 14365 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/smart_migrator.py`: `60 changed lines`
  - primary vs `./hf-space/packages/core/smart_migrator.py`: `61 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/core/smart_migrator.py`); verify it includes all content

### `spell_corrector.py` (5 files, 2 unique versions)
- **Primary (keep):** `./packages/nlp/spell_corrector.py` — 26439 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/spell_corrector.py` — 26536 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/spell_corrector.py`~~ — 26536 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/nlp/spell_corrector.py`~~ — 26536 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/spell_corrector.py`~~ — 26536 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/nlp/spell_corrector.py`: `21 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/spell_corrector.py`); verify it includes all content

### `structure.py` (6 files, 2 unique versions)
- **Primary (keep):** `./packages/core/structure.py` — 10284 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/core/structure.py` — 10323 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/core/structure.py`~~ — 10323 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/core/structure.py`~~ — 10323 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/core/structure.py`~~ — 10323 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/core/structure.py`~~ — 10323 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/core/structure.py`: `13 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/handwriting/modules/core/structure.py`); verify it includes all content

### `study_guide.py` (10 files, 5 unique versions)
- **Primary (keep):** `./packages/nlp/study_guide.py` — 36633 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/src/study_guide.py` — 33068 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/src/study_guide.py`~~ — 33068 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/src/study_guide.py`~~ — 33068 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/src/study_guide.py`~~ — 33068 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/study_guide.py` — 36646 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/study_guide.py`~~ — 36646 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/study_guide.py`~~ — 36646 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/study_guide.py` — 36669 bytes — 2026-07-07 18:45:30 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/src/study_guide.py` — 33644 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/src/study_guide.py`: `1482 changed lines`
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/study_guide.py`: `4 changed lines`
  - primary vs `./hf-space/packages/nlp/study_guide.py`: `8 changed lines`
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/src/study_guide.py`: `1493 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/handwriting/modules/nlp/study_guide.py`); verify it includes all content

### `summarizer.py` (9 files, 5 unique versions)
- **Primary (keep):** `./packages/nlp/summarizer.py` — 15652 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/summarizer.py` — 15701 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/summarizer.py`~~ — 15701 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/nlp/summarizer.py`~~ — 15701 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/summarizer.py`~~ — 15701 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/summarizer.py`~~ — 15701 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/JJason-DeepCastAgent/backend/src/services/summarizer.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter14/helloagents-deepresearch/backend/src/services/summarizer.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/deep_research/src/services/summarizer.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/nlp/summarizer.py`: `15 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/summarizer.py`); verify it includes all content

### `surya_ocr.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/vision/surya_ocr.py` — 6160 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/vision/surya_ocr.py` — 6191 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/surya_ocr.py`~~ — 6191 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/vision/surya_ocr.py`~~ — 6191 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/surya_ocr.py`~~ — 6191 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/surya_ocr.py` — 6192 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/vision/surya_ocr.py`: `9 changed lines`
  - primary vs `./hf-space/packages/vision/surya_ocr.py`: `7 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/surya_ocr.py`); verify it includes all content

### `sync.py` (8 files, 7 unique versions)
- **Primary (keep):** `./packages/security/sync/sync.py` — 15980 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./tools/HandwrittenOCR/src/sync.py`~~ — 15980 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/src/sync.py` — 16057 bytes — 2026-07-06 18:52:26 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/src/sync.py` — 16057 bytes — 2026-07-07 12:21:28 +0000
- **Keep (non-primary cluster):** `./packages/omnifile/src/sync.py` — 16057 bytes — 2026-07-07 12:21:24 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/ocr_unified_v2/src/sync.py` — 16057 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/security/sync/sync.py` — 16057 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/src/sync.py` — 16057 bytes — 2026-07-06 18:52:25 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/src/sync.py`: `25 changed lines`
  - primary vs `./packages/handwriting/src/sync.py`: `25 changed lines`
  - primary vs `./packages/omnifile/src/sync.py`: `25 changed lines`
  - primary vs `./packages/file_processor/legacy/ocr_unified_v2/src/sync.py`: `25 changed lines`
  - primary vs `./packages/file_processor/modules/security/sync/sync.py`: `25 changed lines`
  - primary vs `./packages/file_processor/src/sync.py`: `25 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/src/sync.py`); verify it includes all content

### `sync_backend.py` (3 files, 2 unique versions)
- **Primary (keep):** `./packages/security/sync/sync_backend.py` — 9640 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/mobile_review/split/02-mobile-review/sync_backend.py` — 9685 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/security/sync/sync_backend.py`~~ — 9685 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/file_processor/legacy/mobile_review/split/02-mobile-review/sync_backend.py`: `29 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/legacy/mobile_review/split/02-mobile-review/sync_backend.py`); verify it includes all content

### `table_detection.py` (6 files, 2 unique versions)
- **Primary (keep):** `./packages/vision/table_detection.py` — 5957 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/vision/table_detection.py` — 5974 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/table_detection.py`~~ — 5974 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/vision/table_detection.py`~~ — 5974 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/table_detection.py`~~ — 5974 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/table_detection.py`~~ — 5974 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/vision/table_detection.py`: `7 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/vision/table_detection.py`); verify it includes all content

### `table_extractor.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/vision/table_extractor.py` — 11463 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/vision/table_extractor.py` — 11499 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/table_extractor.py`~~ — 11499 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/vision/table_extractor.py`~~ — 11499 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/table_extractor.py`~~ — 11499 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/table_extractor.py` — 11500 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/vision/table_extractor.py`: `9 changed lines`
  - primary vs `./hf-space/packages/vision/table_extractor.py`: `7 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/modules/vision/table_extractor.py`); verify it includes all content

### `tasks.py` (5 files, 2 unique versions)
- **Primary (keep):** `./packages/handwriting/tasks.py` — 6024 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tasks.py`~~ — 6024 bytes — 2026-07-06 18:52:26 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/tasks.py`~~ — 6024 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/tasks.py`~~ — 6024 bytes — 2026-07-07 12:21:24 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/api/routes/tasks.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
  **Diffs between unique versions:**
  **Recommendation:** keep packages/ version — primary is in canonical packages/ location

### `test_advanced_pipeline.py` (5 files, 2 unique versions)
- **Primary (keep):** `./tests/test_advanced_pipeline.py` — 8900 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/tests/test_advanced_pipeline.py` — 8894 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tests/test_advanced_pipeline.py`~~ — 8894 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/tests/test_advanced_pipeline.py`~~ — 8894 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_advanced_pipeline.py`~~ — 8894 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/tests/test_advanced_pipeline.py`: `14 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_arabic_nlp_utils.py` (5 files, 2 unique versions)
- **Primary (keep):** `./tests/test_arabic_nlp_utils.py` — 6008 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_arabic_nlp_utils.py` — 6007 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_arabic_nlp_utils.py`~~ — 6007 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_arabic_nlp_utils.py`~~ — 6007 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_arabic_nlp_utils.py`~~ — 6007 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_arabic_nlp_utils.py`: `4 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_arabic_rtl.py` (5 files, 2 unique versions)
- **Primary (keep):** `./tests/test_arabic_rtl.py` — 15120 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/tests/test_arabic_rtl.py` — 15120 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tests/test_arabic_rtl.py`~~ — 15120 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/tests/test_arabic_rtl.py`~~ — 15120 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_arabic_rtl.py`~~ — 15120 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/tests/test_arabic_rtl.py`: `2 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_core.py` (12 files, 10 unique versions)
- **Primary (keep):** `./packages/core/test_core.py` — 12001 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/doc-processor/packages/core/test_core.py`~~ — 12001 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/doc_processor/packages/core/test_core.py`~~ — 12001 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/test_core.py` — 12033 bytes — 2026-07-07 18:45:30 +0000
- **Keep (non-primary cluster):** `./packages/ocr_postprocess/tests/test_core.py` — 8525 bytes — 2026-07-06 18:50:49 +0000
- **Keep (non-primary cluster):** `./tests/unit/test_core.py` — 3889 bytes — 2026-07-08 14:54:13 +0000
- **Keep (non-primary cluster):** `./packages/doc_processor/test_core.py` — 10525 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/desktop/test_core.py` — 25761 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/ocr_postprocess/tests/test_core.py` — 8525 bytes — 2026-07-07 18:45:30 +0000
- **Keep (non-primary cluster):** `./packages/doc-processor/desktop/test_core.py` — 3067 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/doc-processor/test_core.py` — 10525 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/doc_processor/desktop/test_core.py` — 3067 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/core/test_core.py`: `16 changed lines`
  - primary vs `./packages/ocr_postprocess/tests/test_core.py`: `456 changed lines`
  - primary vs `./tests/unit/test_core.py`: `332 changed lines`
  - primary vs `./packages/doc_processor/test_core.py`: `443 changed lines`
  - primary vs `./packages/desktop/test_core.py`: `772 changed lines`
  - primary vs `./hf-space/packages/ocr_postprocess/tests/test_core.py`: `456 changed lines`
  - primary vs `./packages/doc-processor/desktop/test_core.py`: `306 changed lines`
  - primary vs `./packages/doc-processor/test_core.py`: `443 changed lines`
  - primary vs `./packages/doc_processor/desktop/test_core.py`: `306 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/core/test_core.py`); verify it includes all content

### `test_fusion.py` (5 files, 2 unique versions)
- **Primary (keep):** `./tests/test_fusion.py` — 14834 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/tests/test_fusion.py` — 14868 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tests/test_fusion.py`~~ — 14868 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/tests/test_fusion.py`~~ — 14868 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_fusion.py`~~ — 14868 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/tests/test_fusion.py`: `7 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/tests/test_fusion.py`); verify it includes all content

### `test_gemini_modules.py` (5 files, 2 unique versions)
- **Primary (keep):** `./tests/test_gemini_modules.py` — 18957 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_gemini_modules.py` — 18946 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_gemini_modules.py`~~ — 18946 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_gemini_modules.py`~~ — 18946 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_gemini_modules.py`~~ — 18946 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_gemini_modules.py`: `46 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_integration.py` (6 files, 4 unique versions)
- **Primary (keep):** `./tests/test_integration.py` — 6982 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_integration.py` — 19800 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/handwriting/tests/test_integration.py`~~ — 19800 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_integration.py`~~ — 19800 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./apps/handwriting-demo/tests/test_integration.py` — 25714 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/tests/test_integration.py` — 6814 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_integration.py`: `565 changed lines`
  - primary vs `./apps/handwriting-demo/tests/test_integration.py`: `621 changed lines`
  - primary vs `./packages/file_processor/tests/test_integration.py`: `304 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/omnifile/tests/test_integration.py`); verify it includes all content

### `test_layout_preserving.py` (5 files, 2 unique versions)
- **Primary (keep):** `./tests/test_layout_preserving.py` — 1726 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/tests/test_layout_preserving.py` — 1723 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tests/test_layout_preserving.py`~~ — 1723 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/tests/test_layout_preserving.py`~~ — 1723 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_layout_preserving.py`~~ — 1723 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/tests/test_layout_preserving.py`: `2 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_markdown_exporter.py` (5 files, 2 unique versions)
- **Primary (keep):** `./tests/test_markdown_exporter.py` — 1930 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/tests/test_markdown_exporter.py` — 1915 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tests/test_markdown_exporter.py`~~ — 1915 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/tests/test_markdown_exporter.py`~~ — 1915 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_markdown_exporter.py`~~ — 1915 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/tests/test_markdown_exporter.py`: `7 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_metrics.py` (7 files, 4 unique versions)
- **Primary (keep):** `./tests/test_metrics.py` — 13491 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_metrics.py` — 13480 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_metrics.py`~~ — 13480 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_metrics.py`~~ — 13480 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_metrics.py`~~ — 13480 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./apps/trainer-ui/tests/test_metrics.py` — 8561 bytes — 2026-07-06 18:52:26 +0000
- **Keep (non-primary cluster):** `./packages/benchmark_core/tests/test_metrics.py` — 6960 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_metrics.py`: `20 changed lines`
  - primary vs `./apps/trainer-ui/tests/test_metrics.py`: `509 changed lines`
  - primary vs `./packages/benchmark_core/tests/test_metrics.py`: `469 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_ocr_engine.py` (6 files, 4 unique versions)
- **Primary (keep):** `./tests/test_ocr_engine.py` — 5251 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/tests/test_ocr_engine.py` — 5141 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tests/test_ocr_engine.py`~~ — 5141 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_ocr_engine.py`~~ — 5141 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/tests/test_ocr_engine.py` — 5249 bytes — 2026-07-06 18:52:25 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/tests/test_ocr_engine.py` — 4625 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/tests/test_ocr_engine.py`: `7 changed lines`
  - primary vs `./packages/file_processor/tests/test_ocr_engine.py`: `4 changed lines`
  - primary vs `./apps/handwriting-demo/tests/test_ocr_engine.py`: `232 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_pattern_matcher.py` (5 files, 2 unique versions)
- **Primary (keep):** `./tests/test_pattern_matcher.py` — 4448 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_pattern_matcher.py` — 4447 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_pattern_matcher.py`~~ — 4447 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_pattern_matcher.py`~~ — 4447 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_pattern_matcher.py`~~ — 4447 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_pattern_matcher.py`: `identical`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_performance.py` (5 files, 2 unique versions)
- **Primary (keep):** `./tests/test_performance.py` — 3703 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_performance.py` — 3810 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_performance.py`~~ — 3810 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_performance.py`~~ — 3810 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_performance.py`~~ — 3810 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_performance.py`: `24 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/omnifile/tests/test_performance.py`); verify it includes all content

### `test_pipeline.py` (7 files, 4 unique versions)
- **Primary (keep):** `./tests/integration/test_pipeline.py` — 4775 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_pipeline.py` — 7944 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_pipeline.py`~~ — 7944 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_pipeline.py`~~ — 7944 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_pipeline.py`~~ — 7944 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./tests/test_pipeline.py` — 7961 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/ocr-pipeline/tests/test_pipeline.py` — 31408 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_pipeline.py`: `261 changed lines`
  - primary vs `./tests/test_pipeline.py`: `261 changed lines`
  - primary vs `./apps/ocr-pipeline/tests/test_pipeline.py`: `695 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/file_processor/tests/test_pipeline.py`); verify it includes all content

### `test_preprocessor.py` (5 files, 2 unique versions)
- **Primary (keep):** `./tests/test_preprocessor.py` — 7981 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/tests/test_preprocessor.py` — 7979 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tests/test_preprocessor.py`~~ — 7979 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/tests/test_preprocessor.py`~~ — 7979 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_preprocessor.py`~~ — 7979 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/tests/test_preprocessor.py`: `2 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_processing.py` (3 files, 2 unique versions)
- **Primary (keep):** `./packages/doc_processor/desktop/test_processing.py` — 13309 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/doc-processor/desktop/test_processing.py`~~ — 13309 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/desktop/test_processing.py` — 13314 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/desktop/test_processing.py`: `14 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/desktop/test_processing.py`); verify it includes all content

### `test_sensitive_scanner.py` (5 files, 2 unique versions)
- **Primary (keep):** `./tests/test_sensitive_scanner.py` — 5905 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_sensitive_scanner.py` — 5890 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_sensitive_scanner.py`~~ — 5890 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_sensitive_scanner.py`~~ — 5890 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_sensitive_scanner.py`~~ — 5890 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_sensitive_scanner.py`: `30 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_spell_corrector.py` (5 files, 2 unique versions)
- **Primary (keep):** `./tests/test_spell_corrector.py` — 5095 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_spell_corrector.py` — 5082 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_spell_corrector.py`~~ — 5082 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_spell_corrector.py`~~ — 5082 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_spell_corrector.py`~~ — 5082 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_spell_corrector.py`: `26 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_summarizer.py` (5 files, 2 unique versions)
- **Primary (keep):** `./tests/test_summarizer.py` — 3943 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_summarizer.py` — 3931 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_summarizer.py`~~ — 3931 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_summarizer.py`~~ — 3931 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_summarizer.py`~~ — 3931 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_summarizer.py`: `24 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `text_classifier.py` (6 files, 2 unique versions)
- **Primary (keep):** `./packages/nlp/text_classifier.py` — 15772 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/text_classifier.py` — 15789 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/text_classifier.py`~~ — 15789 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/nlp/text_classifier.py`~~ — 15789 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/text_classifier.py`~~ — 15789 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/text_classifier.py`~~ — 15789 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/nlp/text_classifier.py`: `7 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/handwriting/modules/nlp/text_classifier.py`); verify it includes all content

### `text_reconstructor.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/vision/text_reconstructor.py` — 22397 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/text_reconstructor.py` — 22456 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/text_reconstructor.py`~~ — 22456 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/text_reconstructor.py`~~ — 22456 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/text_reconstructor.py`~~ — 22456 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/text_reconstructor.py` — 22494 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/text_reconstructor.py`: `5 changed lines`
  - primary vs `./hf-space/packages/vision/text_reconstructor.py`: `7 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/text_reconstructor.py`); verify it includes all content

### `tools.py` (4 files, 3 unique versions)
- **Primary (keep):** `./packages/ai/gateway/core/anthropic/tools.py` — 7966 bytes — 2026-05-26 01:20:07 +0000
  - ~~`./packages/file_processor/modules/ai/gateway/core/anthropic/tools.py`~~ — 7966 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/939147533-DatabaseAgent/src/tools.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter4/tools.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
  **Diffs between unique versions:**
  **Recommendation:** keep newest — newer variant exists (e.g. `./packages/file_processor/modules/ai/gateway/core/anthropic/tools.py`); verify it's a superset

### `translation_corrector.py` (5 files, 3 unique versions)
- **Primary (keep):** `./packages/nlp/translation_corrector.py` — 20594 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/translation_corrector.py` — 20673 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/translation_corrector.py`~~ — 20673 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/translation_corrector.py`~~ — 20673 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/translation_corrector.py` — 20698 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/translation_corrector.py`: `24 changed lines`
  - primary vs `./hf-space/packages/nlp/translation_corrector.py`: `25 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/nlp/translation_corrector.py`); verify it includes all content

### `translator.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/nlp/translator.py` — 24992 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/translator.py` — 25033 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/translator.py`~~ — 25033 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/translator.py`~~ — 25033 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/translator.py`~~ — 25033 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/translator.py` — 25082 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/translator.py`: `11 changed lines`
  - primary vs `./hf-space/packages/nlp/translator.py`: `12 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/nlp/translator.py`); verify it includes all content

### `user_manager.py` (5 files, 3 unique versions)
- **Primary (keep):** `./packages/core/user_manager.py` — 3828 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/mobile_review/split/05-review-systems/user_manager.py` — 3143 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tools/user_manager.py`~~ — 3143 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/user_manager.py` — 3859 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./packages/file_processor/modules/core/user_manager.py`~~ — 3859 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/file_processor/legacy/mobile_review/split/05-review-systems/user_manager.py`: `138 changed lines`
  - primary vs `./hf-space/packages/core/user_manager.py`: `3 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./hf-space/packages/core/user_manager.py`); verify it includes all content

### `utils.py` (21 files, 20 unique versions)
- **Primary (keep):** `./packages/ai/gateway/core/anthropic/utils.py` — 253 bytes — 2026-05-26 01:20:07 +0000
  - ~~`./packages/file_processor/modules/ai/gateway/core/anthropic/utils.py`~~ — 253 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/omniparse/omniparse/web/utils.py` — 21873 bytes — 2026-07-06 18:52:26 +0000
- **Keep (non-primary cluster):** `./packages/doc_processor/skills/skill-creator/scripts/utils.py` — 1661 bytes — 2026-07-06 18:50:50 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/melxy1997-ColumnWriter/utils.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./tools/ai_fuel/core/utils.py` — 13466 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./labs/omniparse_study/omniparse/utils.py` — 1045 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter14/helloagents-deepresearch/backend/src/utils.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/omniparse/omniparse/image/utils.py` — 2946 bytes — 2026-07-06 18:52:26 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/JJason-DeepCastAgent/backend/src/utils.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/doc_processor/skills/quiz-mastery/src/quiz_mastery/utils.py` — 137 bytes — 2026-07-06 18:50:50 +0000
- **Keep (non-primary cluster):** `./labs/omniparse_study/omniparse/web/utils.py` — 21869 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./labs/omniparse_study/python-sdk/omniparse_client/utils.py` — 7770 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/omniparse/omniparse/utils.py` — 1042 bytes — 2026-07-06 18:52:26 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/code/chapter9/codebase/utils.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./packages/omniparse/python-sdk/omniparse_client/utils.py` — 7804 bytes — 2026-07-06 18:52:26 +0000
- **Keep (non-primary cluster):** `./labs/omniparse_study/omniparse/image/utils.py` — 2972 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/deep_research/src/utils.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
- **Keep (non-primary cluster):** `./labs/omniparse_study/omniparse/media/utils.py` — 1714 bytes — 2026-07-06 18:52:26 +0000
- **Keep (non-primary cluster):** `./packages/ai-fuel/core/utils.py` — 13466 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/omniparse/omniparse/media/utils.py` — 1714 bytes — 2026-07-06 18:52:26 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/omniparse/omniparse/web/utils.py`: `525 changed lines`
  - primary vs `./packages/doc_processor/skills/skill-creator/scripts/utils.py`: `44 changed lines`
  - primary vs `./tools/ai_fuel/core/utils.py`: `342 changed lines`
  - primary vs `./labs/omniparse_study/omniparse/utils.py`: `34 changed lines`
  - primary vs `./packages/omniparse/omniparse/image/utils.py`: `105 changed lines`
  - primary vs `./packages/doc_processor/skills/quiz-mastery/src/quiz_mastery/utils.py`: `10 changed lines`
  - primary vs `./labs/omniparse_study/omniparse/web/utils.py`: `527 changed lines`
  - primary vs `./labs/omniparse_study/python-sdk/omniparse_client/utils.py`: `189 changed lines`
  - primary vs `./packages/omniparse/omniparse/utils.py`: `34 changed lines`
  - primary vs `./packages/omniparse/python-sdk/omniparse_client/utils.py`: `191 changed lines`
  - primary vs `./labs/omniparse_study/omniparse/image/utils.py`: `105 changed lines`
  - primary vs `./labs/omniparse_study/omniparse/media/utils.py`: `53 changed lines`
  - primary vs `./packages/ai-fuel/core/utils.py`: `342 changed lines`
  - primary vs `./packages/omniparse/omniparse/media/utils.py`: `53 changed lines`
  **Recommendation:** keep newest/largest — newer and larger variant exists; compare content

### `video_ocr.py` (5 files, 3 unique versions)
- **Primary (keep):** `./packages/vision/video_ocr.py` — 22872 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/video_ocr.py` — 22884 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/video_ocr.py`~~ — 22884 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/video_ocr.py`~~ — 22884 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/video_ocr.py` — 22892 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/video_ocr.py`: `25 changed lines`
  - primary vs `./hf-space/packages/vision/video_ocr.py`: `23 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./packages/handwriting/modules/vision/video_ocr.py`); verify it includes all content

### `watchdog_service.py` (6 files, 3 unique versions)
- **Primary (keep):** `./packages/core/watchdog_service.py` — 15605 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/watchdog_service.py` — 15674 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/core/watchdog_service.py`~~ — 15674 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/core/watchdog_service.py`~~ — 15674 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/core/watchdog_service.py`~~ — 15674 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/watchdog_service.py` — 15764 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/watchdog_service.py`: `35 changed lines`
  - primary vs `./hf-space/packages/core/watchdog_service.py`: `35 changed lines`
  **Recommendation:** keep largest — larger variant exists (e.g. `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/watchdog_service.py`); verify it includes all content

## Needs Human Decision — Grouped by package

*No groups in this category — all 124 partial-duplicate groups contain at least one pair of identical files.*

However, within the auto-deletable groups above, many still have **differing variants** that need human decision. See the diff stats in each group for details.
