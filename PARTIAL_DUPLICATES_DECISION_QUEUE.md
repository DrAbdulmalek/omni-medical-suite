# PARTIAL_DUPLICATES_DECISION_QUEUE.md
# Reclassified: 2026-07-11 (v3 — path-based analysis for Category A)
# Method: Quantitative split — unique-ratio > 60% = Category A (generic), ≤ 60% = Category B (specialized)
# Category A: Path-based classification (import analysis unreliable for generic names)
# Category B: Original diff-stats + date analysis preserved

## Summary

| Metric | Count |
|--------|-------|
| **Total groups** | **124** |
|
| **فئة أ — generic names (>60% unique)** | **52 groups** |
| Total files in فئة أ | 436 |
| DO NOT TOUCH (independent, active path) | 144 |
| LEGACY REVIEW (in merged-remnant/legacy) | 200 |
| CANDIDATE FOR DELETION (in _dev_references/) | 0 |
| Already deleted (0 bytes) | 92 |
|
| **فئة ب — specialized names (≤60% unique)** | **72 groups** |
| Total files in فئة ب | 415 |
| All need content comparison before any deletion | 415 |

---

## فئة أ — أسماء عامة/شائعة (نسبة النسخ الفريدة > 60%)

**المعيار الكمي:** نسبة النسخ الفريدة / عدد الملفات > 60% → ملفات مستقلة
تتشارك اسمًا شائعًا (مثل `app.py`, `config.py`, `main.py`) وليست نسخًا مكررة.

**ملاحظة عن فحص الاستيراد:** فحص `import` غير موثوق للأسماء العامة لأن `from .app import`
يتطابق مع كل `__init__.py` يستورد `app.py` المحلي. لذلك نعتمد على تحليل المسار فقط.

**تصنيفات فئة أ:**
- **DO NOT TOUCH**: الملف في مسار نشط وليس في legacy/_dev_references → مستقل تمامًا
- **LEGACY REVIEW**: الملف في حزمة مدمجة-متبقية (merged-remnant) أو `legacy/` → يحتاج مراجعة بشرية
- **CANDIDATE FOR DELETION**: الملف في `_dev_references/` (مشروع خارجي لا ينتمي للمستودع)
- **Already deleted**: 0 bytes على القرص

### `app.py` (23 files, 22 unique — ratio 95.7%)

- `./packages/ai/gateway/api/app.py` — 6122 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/handwriting/app.py` — 57893 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/app.py` — 57893 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/api/app.py` — 6123 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/ocr-demo/app.py` — 33449 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/medical-ocr-trainer-hf/app.py` — 43209 bytes — **DO NOT TOUCH**: independent module in active path
- `./hf-space/app.py` — 27256 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/legacy/translation_corrector/app.py` — 41453 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./tools/ops/telegram_forwarder/app.py` — 27677 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/HandwrittenOCR/backend/app.py` — 31331 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/handwriting-demo/app.py` — 6095 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/telegram-channel-copier/app.py` — 9688 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/app.py` — 57891 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/lgs-only-NovelGenerator/src/app.py`~~ — 0 bytes — DELETED
- `./app/config/app.py` — 2576 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/legacy/ocr_unified_v2/backend/app.py` — 42105 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./apps/handwriting-demo/hf-deploy/app.py` — 284 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/financial-services/claude-for-msft-365-install/examples/python-bootstrap/app.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/meiguanxiHXX-historyReviewAgent/historical_review/web/app.py`~~ — 0 bytes — DELETED
- `./apps/ocr-pipeline/desktop/app.py` — 1768 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/trainer-ui/app.py` — 47451 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/trainer-ui/hf-variant/app.py` — 54692 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/ocr-pipeline/app.py` — 28009 bytes — **DO NOT TOUCH**: independent module in active path

### `utils.py` (21 files, 20 unique — ratio 95.2%)

- `./packages/ai/gateway/core/anthropic/utils.py` — 253 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/core/anthropic/utils.py` — 253 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omniparse/omniparse/web/utils.py` — 21873 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/doc_processor/skills/skill-creator/scripts/utils.py` — 1661 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/melxy1997-ColumnWriter/utils.py`~~ — 0 bytes — DELETED
- `./tools/ai_fuel/core/utils.py` — 13466 bytes — **DO NOT TOUCH**: independent module in active path
- `./labs/omniparse_study/omniparse/utils.py` — 1045 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter14/helloagents-deepresearch/backend/src/utils.py`~~ — 0 bytes — DELETED
- `./packages/omniparse/omniparse/image/utils.py` — 2946 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/JJason-DeepCastAgent/backend/src/utils.py`~~ — 0 bytes — DELETED
- `./packages/doc_processor/skills/quiz-mastery/src/quiz_mastery/utils.py` — 137 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./labs/omniparse_study/omniparse/web/utils.py` — 21869 bytes — **DO NOT TOUCH**: independent module in active path
- `./labs/omniparse_study/python-sdk/omniparse_client/utils.py` — 7770 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/omniparse/omniparse/utils.py` — 1042 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter9/codebase/utils.py`~~ — 0 bytes — DELETED
- `./packages/omniparse/python-sdk/omniparse_client/utils.py` — 7804 bytes — **DO NOT TOUCH**: independent module in active path
- `./labs/omniparse_study/omniparse/image/utils.py` — 2972 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/deep_research/src/utils.py`~~ — 0 bytes — DELETED
- `./labs/omniparse_study/omniparse/media/utils.py` — 1714 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/ai-fuel/core/utils.py` — 13466 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/omniparse/omniparse/media/utils.py` — 1714 bytes — **DO NOT TOUCH**: independent module in active path

### `client.py` (16 files, 15 unique — ratio 93.8%)

- `./packages/ai/gateway/providers/llamacpp/client.py` — 501 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/providers/llamacpp/client.py` — 501 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/lmstudio/client.py` — 501 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/ai/gateway/providers/deepseek/client.py` — 1649 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/ai/gateway/providers/ollama/client.py` — 1363 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/providers/ollama/client.py` — 1363 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/ai/gateway/providers/wafer/client.py` — 1362 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/providers/kimi/client.py` — 882 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/ai/gateway/providers/nvidia_nim/client.py` — 2762 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/providers/deepseek/client.py` — 1650 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/open_router/client.py` — 4429 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/ai/gateway/providers/kimi/client.py` — 881 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/providers/wafer/client.py` — 1362 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/ai/gateway/providers/lmstudio/client.py` — 501 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/ai/gateway/providers/open_router/client.py` — 4428 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/providers/nvidia_nim/client.py` — 2763 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `config.py` (32 files, 30 unique — ratio 93.8%)

- `./packages/handwriting/config.py` — 11046 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/config.py` — 11046 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/config.py` — 11046 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/xujikai-SentenceExpandAgent/backend/src/config.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/YYHDBL-HelloCodeAgentCli/core/config.py`~~ — 0 bytes — DELETED
- `./tools/ai_fuel/core/config.py` — 12281 bytes — **DO NOT TOUCH**: independent module in active path
- `./labs/omniparse_study/omniparse/web/config.py` — 1471 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/melxy1997-ColumnWriter/config.py`~~ — 0 bytes — DELETED
- `./packages/file_processor/legacy/ocr_unified_v2/config.py` — 12470 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/core/config.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/haoye2-UnivesalAgent/src/agents/config.py`~~ — 0 bytes — DELETED
- `./packages/file_processor/legacy/mobile_review/split/10-backend-api/config.py` — 777 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter13/helloagents-trip-planner/backend/app/config.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Shawnxyxy-HealthRecordAgent/backend/core/config.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/usernamedadad-AutoFlow/backend/app/config.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/rss_digest/src/rss_digest/config.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/meiguanxiHXX-historyReviewAgent/historical_review/config.py`~~ — 0 bytes — DELETED
- `./packages/omniparse/omniparse/web/config.py` — 1470 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/JJason-DeepCastAgent/backend/src/config.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter14/helloagents-deepresearch/backend/src/config.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/backend/config.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/deep_research/src/config.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter15/Helloagents-AI-Town/backend/config.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/tino-chen-HelloClaw/src/api/config.py`~~ — 0 bytes — DELETED
- `./tools/HandwrittenOCR/config.py` — 10798 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/ai-fuel/core/config.py` — 12281 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/939147533-DatabaseAgent/src/config.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/afei-GuessWhoAmI/backend/config.py`~~ — 0 bytes — DELETED
- `./packages/file_processor/config.py` — 15815 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/financial-services/claude-for-msft-365-install/examples/python-bootstrap/config.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/healer-666-Academic-Data-Agent/src/data_analysis_agent/config.py`~~ — 0 bytes — DELETED
- `./apps/handwriting-demo/hf-deploy/app/config.py` — 199 bytes — **DO NOT TOUCH**: independent module in active path

### `main.py` (40 files, 37 unique — ratio 92.5%)

- `./packages/handwriting/src/main.py` — 8220 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/main.py` — 8220 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/src/main.py` — 8220 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/main.py` — 8220 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/main.py` — 4047 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/tino-chen-HelloClaw/src/cli/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Shawnxyxy-HealthRecordAgent/backend/main.py`~~ — 0 bytes — DELETED
- `./packages/file_processor/legacy/ocr_unified_v2/src/main.py` — 7870 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/deep_research/src/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter13/helloagents-trip-planner/backend/app/api/main.py`~~ — 0 bytes — DELETED
- `./packages/file_processor/legacy/mobile_review/split/10-backend-api/main.py` — 13136 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Yixiang-Wu-LearningAgent/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/usernamedadad-AutoFlow/backend/app/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/haoye2-UnivesalAgent/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Shawnxyxy-HealthRecordAgent/backend/api/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/lll0807-CodeTutorAgent/programmer/main.py`~~ — 0 bytes — DELETED
- `./apps/handwriting-demo/variants/handwriting-ocr/main.py` — 4047 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/api/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter9/project/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/melxy1997-ColumnWriter/main.py`~~ — 0 bytes — DELETED
- `./tools/HandwrittenOCR/src/main.py` — 5336 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/939147533-DatabaseAgent/main.py`~~ — 0 bytes — DELETED
- `./packages/handwriting/main.py` — 4047 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/main.py` — 4047 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/xujikai-SentenceExpandAgent/backend/src/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/tino-chen-HelloClaw/src/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/backend/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/afei-GuessWhoAmI/backend/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter14/helloagents-deepresearch/backend/src/main.py`~~ — 0 bytes — DELETED
- `./app/main.py` — 5380 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/lgs-only-NovelGenerator/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/angelen-SoftwareDevHelper/src/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/pamdla-MindEchoAgent/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/alexrunner-DataAnalysisAgent/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/rss_digest/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/zjzhou-SREOnCallAgent/src/api/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/JJason-DeepCastAgent/backend/src/main.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter15/Helloagents-AI-Town/backend/main.py`~~ — 0 bytes — DELETED

### `request.py` (10 files, 9 unique — ratio 90.0%)

- `./packages/ai/gateway/api/web_tools/request.py` — 3352 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/api/web_tools/request.py` — 3352 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/deepseek/request.py` — 16596 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/nvidia_nim/request.py` — 9239 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/kimi/request.py` — 1071 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/providers/open_router/request.py` — 1304 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/ai/gateway/providers/open_router/request.py` — 1304 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/ai/gateway/providers/kimi/request.py` — 1071 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/ai/gateway/providers/deepseek/request.py` — 16596 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/ai/gateway/providers/nvidia_nim/request.py` — 9239 bytes — **DO NOT TOUCH**: independent module in active path

### `server.py` (10 files, 9 unique — ratio 90.0%)

- `./packages/ai/gateway/server.py` — 933 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/server.py` — 933 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter10/weather-mcp-server/server.py`~~ — 0 bytes — DELETED
- `./packages/handwriting/mobile_review/server.py` — 2556 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omniparse/server.py` — 2785 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./labs/omniparse_study/server.py`~~ — 0 bytes — DELETED
- `./packages/file_processor/mobile_review/server.py` — 5236 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/mobile_review/server.py` — 2556 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/legacy/mobile_review/split/02-mobile-review/server.py` — 1766 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/omnifile/mobile_review/server.py` — 2556 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `base.py` (8 files, 7 unique — ratio 87.5%)

- `./packages/ai/gateway/providers/base.py` — 4440 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/providers/base.py` — 4440 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/backend/agents/base.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/YYHDBL-HelloCodeAgentCli/tools/base.py`~~ — 0 bytes — DELETED
- `./packages/doc_processor/skills/ppt/ooxml/scripts/validation/base.py` — 39848 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/skills/xlsx/templates/base.py` — 21964 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Shawnxyxy-HealthRecordAgent/backend/agents/base.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/agents/base.py`~~ — 0 bytes — DELETED

### `pipeline.py` (16 files, 14 unique — ratio 87.5%)

- `./packages/nlp/pipeline.py` — 41449 bytes — **DO NOT TOUCH**: independent module in active path
- `./hf-space/packages/scanner_fixer/src/scanner_fixer/pipeline.py` — 6877 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/scanner_fixer/src/scanner_fixer/pipeline.py` — 6877 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/ai-fuel/export/pipeline.py` — 13757 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/ai_fuel/export/pipeline.py` — 13757 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/usernamedadad-AutoFlow/backend/app/agents/mermaid/pipeline.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/zjzhou-SREOnCallAgent/src/agents/pipeline.py`~~ — 0 bytes — DELETED
- `./omni_medical_suite/pipeline.py` — 5178 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/audit/pipeline.py` — 15715 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/audit/pipeline.py` — 15769 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./app/routers/pipeline.py` — 400 bytes — **DO NOT TOUCH**: independent module in active path
- `./hf-space/packages/nlp/pipeline.py` — 41491 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/download/medical-image-ai-suite/services/ocr/data_collection/pipeline.py` — 44611 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/rss_digest/src/rss_digest/pipeline.py`~~ — 0 bytes — DELETED
- `./packages/training_hub/src/promotion/pipeline.py` — 19952 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/ocr-pipeline/src/core/pipeline.py` — 33937 bytes — **DO NOT TOUCH**: independent module in active path

### `prompts.py` (8 files, 7 unique — ratio 87.5%)

- `./packages/omniparse/omniparse/web/prompts.py` — 8052 bytes — **DO NOT TOUCH**: independent module in active path
- `./labs/omniparse_study/omniparse/web/prompts.py` — 8052 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter14/helloagents-deepresearch/backend/src/prompts.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/JJason-DeepCastAgent/backend/src/prompts.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/melxy1997-ColumnWriter/prompts.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/agents/deep_research/src/prompts.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/xujikai-SentenceExpandAgent/backend/src/agents/prompts.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/healer-666-Academic-Data-Agent/src/data_analysis_agent/prompts.py`~~ — 0 bytes — DELETED

### `sync.py` (8 files, 7 unique — ratio 87.5%)

- `./packages/security/sync/sync.py` — 15980 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/HandwrittenOCR/src/sync.py` — 15980 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/handwriting-demo/variants/handwriting-ocr/src/sync.py` — 16057 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/src/sync.py` — 16057 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/sync.py` — 16057 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/legacy/ocr_unified_v2/src/sync.py` — 16057 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/modules/security/sync/sync.py` — 16057 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/src/sync.py` — 16057 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `cli.py` (6 files, 5 unique — ratio 83.3%)

- `./packages/ocr_postprocess/src/medical_ocr_postprocessor/cli.py` — 13163 bytes — **DO NOT TOUCH**: independent module in active path
- `./hf-space/packages/ocr_postprocess/src/medical_ocr_postprocessor/cli.py` — 13163 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/meiguanxiHXX-historyReviewAgent/historical_review/web/cli.py`~~ — 0 bytes — DELETED
- `./hf-space/packages/scanner_fixer/src/scanner_fixer/cli.py` — 4543 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/scanner_fixer/src/scanner_fixer/cli.py` — 4543 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/gt_core/tools/ocr-groundtruth/src/ocr_groundtruth/cli.py` — 3886 bytes — **DO NOT TOUCH**: independent module in active path

### `exceptions.py` (6 files, 5 unique — ratio 83.3%)

- `./packages/ai/gateway/providers/exceptions.py` — 3103 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/providers/exceptions.py` — 3103 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/core/exceptions.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Shawnxyxy-HealthRecordAgent/backend/core/exceptions.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Yixiang-Wu-LearningAgent/utils/exceptions.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/YYHDBL-HelloCodeAgentCli/core/exceptions.py`~~ — 0 bytes — DELETED

### `test_core.py` (12 files, 10 unique — ratio 83.3%)

- `./packages/core/test_core.py` — 12001 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/doc-processor/packages/core/test_core.py` — 12001 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/packages/core/test_core.py` — 12001 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/test_core.py` — 12033 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/ocr_postprocess/tests/test_core.py` — 8525 bytes — **DO NOT TOUCH**: independent module in active path
- `./tests/unit/test_core.py` — 3889 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/doc_processor/test_core.py` — 10525 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/desktop/test_core.py` — 25761 bytes — **DO NOT TOUCH**: independent module in active path
- `./hf-space/packages/ocr_postprocess/tests/test_core.py` — 8525 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc-processor/desktop/test_core.py` — 3067 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc-processor/test_core.py` — 10525 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/desktop/test_core.py` — 3067 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `active_learning.py` (5 files, 4 unique — ratio 80.0%)

- `./packages/ai/active_learning.py` — 20368 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/active_learning.py` — 32187 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/ai/active_learning.py` — 32187 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/legacy/mobile_review/split/12-active-learning/active_learning.py` — 20999 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/modules/ai/active_learning.py` — 20394 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `hf_app.py` (5 files, 4 unique — ratio 80.0%)

- ~~`./packages/handwriting/hf_app.py`~~ — 0 bytes — DELETED
- ~~`./apps/handwriting-demo/variants/handwriting-ocr/hf_app.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/hf_app.py`~~ — 0 bytes — DELETED
- `./app/hf_app.py` — 78815 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/omnifile/hf_app.py`~~ — 0 bytes — DELETED

### `schemas.py` (5 files, 4 unique — ratio 80.0%)

- `./packages/file_processor/legacy/mobile_review/split/10-backend-api/schemas.py` — 2449 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/ai-fuel/core/schemas.py` — 11317 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/ai_fuel/core/schemas.py` — 11317 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/usernamedadad-AutoFlow/backend/app/models/schemas.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter13/helloagents-trip-planner/backend/app/models/schemas.py`~~ — 0 bytes — DELETED

### `setup.py` (5 files, 4 unique — ratio 80.0%)

- `./packages/bilingual/setup.py` — 963 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/ai-fuel/setup.py` — 38 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/ai_fuel/setup.py` — 38 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/ocr-pipeline/setup.py` — 4831 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/setup.py`~~ — 0 bytes — DELETED

### `database.py` (14 files, 11 unique — ratio 78.6%)

- `./packages/handwriting/src/database.py` — 507 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/database.py` — 507 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/src/database.py` — 507 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/database.py` — 507 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/legacy/ocr_unified_v2/src/database.py` — 10647 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/database.py` — 50954 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./app/config/database.py` — 1712 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/handwriting-demo/hf-deploy/app/database.py` — 7865 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/handwriting/database.py` — 50958 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/database.py` — 50958 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./tools/HandwrittenOCR/src/database.py` — 10610 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/core/database.py`~~ — 0 bytes — DELETED
- `./packages/file_processor/legacy/mobile_review/split/10-backend-api/database.py` — 697 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/omnifile/database.py` — 50958 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `migration.py` (9 files, 7 unique — ratio 77.8%)

- `./packages/core/migration/migration.py` — 20383 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/handwriting-demo/variants/handwriting-ocr/src/migration.py` — 26156 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/src/migration.py` — 26156 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/migration.py` — 26156 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/migration/migration.py` — 20447 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./tools/HandwrittenOCR/src/migration.py` — 20295 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/legacy/ocr_unified_v2/src/migration.py` — 20268 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/modules/core/migration/migration.py` — 20356 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/src/migration.py` — 26455 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `constants.py` (4 files, 3 unique — ratio 75.0%)

- `./packages/ai/gateway/api/web_tools/constants.py` — 602 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/api/web_tools/constants.py` — 602 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/gateway/config/constants.py` — 443 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/ai/gateway/config/constants.py` — 443 bytes — **DO NOT TOUCH**: independent module in active path

### `db_manager.py` (4 files, 3 unique — ratio 75.0%)

- `./packages/core/db_manager.py` — 12731 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/doc-processor/packages/core/db_manager.py` — 12286 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/packages/core/db_manager.py` — 12286 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/db_manager.py` — 12829 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `encryption.py` (8 files, 6 unique — ratio 75.0%)

- `./packages/core/encryption.py` — 7360 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/doc-processor/packages/core/encryption.py` — 7360 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/packages/core/encryption.py` — 7360 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/security/encryption.py` — 8247 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/encryption.py` — 8247 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/security/encryption.py` — 8768 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/security/encryption.py` — 8728 bytes — **DO NOT TOUCH**: independent module in active path
- `./hf-space/packages/core/encryption.py` — 7387 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `engine.py` (4 files, 3 unique — ratio 75.0%)

- `./packages/ai-fuel/engine.py` — 35125 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/ai_fuel/engine.py` — 35125 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/ai_fuel/dedup/engine.py` — 9477 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/ai-fuel/dedup/engine.py` — 9477 bytes — **DO NOT TOUCH**: independent module in active path

### `orchestrator.py` (4 files, 3 unique — ratio 75.0%)

- `./packages/ai-fuel/classifier/orchestrator.py` — 18957 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/ai_fuel/classifier/orchestrator.py` — 18957 bytes — **DO NOT TOUCH**: independent module in active path
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/xujikai-SentenceExpandAgent/backend/src/agents/orchestrator.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/melxy1997-ColumnWriter/orchestrator.py`~~ — 0 bytes — DELETED

### `rate_limit.py` (4 files, 3 unique — ratio 75.0%)

- `./packages/ai/gateway/core/rate_limit.py` — 1754 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/core/rate_limit.py` — 1754 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/ai/gateway/providers/rate_limit.py` — 9291 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/providers/rate_limit.py` — 9291 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `registry.py` (4 files, 3 unique — ratio 75.0%)

- `./packages/ai/gateway/providers/registry.py` — 17491 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/providers/registry.py` — 17491 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/YYHDBL-HelloCodeAgentCli/tools/registry.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/huailishang-AgentPlatformBase/backend/agents/registry.py`~~ — 0 bytes — DELETED

### `sensitive_data_scanner.py` (4 files, 3 unique — ratio 75.0%)

- `./packages/security/sensitive_data_scanner.py` — 12901 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/sensitive_data_scanner.py` — 12703 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/security/sensitive_data_scanner.py` — 12703 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/security/sensitive_data_scanner.py` — 12907 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `tools.py` (4 files, 3 unique — ratio 75.0%)

- `./packages/ai/gateway/core/anthropic/tools.py` — 7966 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/core/anthropic/tools.py` — 7966 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/939147533-DatabaseAgent/src/tools.py`~~ — 0 bytes — DELETED
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter4/tools.py`~~ — 0 bytes — DELETED

### `conftest.py` (7 files, 5 unique — ratio 71.4%)

- `./tests/conftest.py` — 7018 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/handwriting-demo/variants/handwriting-ocr/tests/conftest.py` — 2890 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/tests/conftest.py` — 2890 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/tests/conftest.py` — 2890 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/desktop/conftest.py` — 197 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/handwriting-demo/tests/conftest.py` — 3137 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/tests/conftest.py` — 1098 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `correction.py` (7 files, 5 unique — ratio 71.4%)

- `./packages/benchmark_core/benchmarks/postprocessor/correction.py` — 10598 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/handwriting/src/correction.py` — 30840 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/correction.py` — 30840 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/correction.py` — 30840 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./tools/HandwrittenOCR/src/correction.py` — 6170 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/src/correction.py` — 20071 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/legacy/ocr_unified_v2/src/correction.py` — 14018 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation

### `logger.py` (10 files, 7 unique — ratio 70.0%)

- `./packages/handwriting/src/logger.py` — 17501 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/logger.py` — 17501 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/src/logger.py` — 17501 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/logger.py` — 17501 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- ~~`./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Yixiang-Wu-LearningAgent/utils/logger.py`~~ — 0 bytes — DELETED
- `./packages/file_processor/legacy/ocr_unified_v2/src/logger.py` — 1176 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- ~~`./packages/file_processor/_dev_references/hello-agents/code/chapter15/Helloagents-AI-Town/backend/logger.py`~~ — 0 bytes — DELETED
- `./packages/doc_processor/download/medical-image-ai-suite/src/utils/logger.py` — 3030 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/ocr-pipeline/src/utils/logger.py` — 7237 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/HandwrittenOCR/src/logger.py` — 1177 bytes — **DO NOT TOUCH**: independent module in active path

### `api_server.py` (6 files, 4 unique — ratio 66.7%)

- `./packages/core/api_server.py` — 14638 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/doc-processor/packages/core/api_server.py` — 14638 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/packages/core/api_server.py` — 14638 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/ocr-pipeline/api_server.py` — 11423 bytes — **DO NOT TOUCH**: independent module in active path
- `./hf-space/packages/core/api_server.py` — 14805 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./legacy/api_server.py` — 2852 bytes — **LEGACY REVIEW**: in legacy/ root directory — needs human review

### `arabic_htr.py` (3 files, 2 unique — ratio 66.7%)

- `./packages/vision/htr/arabic_htr.py` — 16091 bytes — **DO NOT TOUCH**: independent module in active path
- `./hf-space/packages/vision/htr/arabic_htr.py` — 16100 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/vision/htr/arabic_htr.py` — 16100 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `batch_ocr.py` (3 files, 2 unique — ratio 66.7%)

- `./packages/vision/batch_ocr.py` — 14379 bytes — **DO NOT TOUCH**: independent module in active path
- `./hf-space/packages/vision/batch_ocr.py` — 14427 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/vision/batch_ocr.py` — 14427 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `core.py` (3 files, 2 unique — ratio 66.7%)

- `./packages/ocr_postprocess/src/medical_ocr_postprocessor/core.py` — 22570 bytes — **DO NOT TOUCH**: independent module in active path
- `./hf-space/packages/ocr_postprocess/src/medical_ocr_postprocessor/core.py` — 22570 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc_processor/skills/ui-ux-pro-max/scripts/core.py` — 10227 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `database_manager.py` (6 files, 4 unique — ratio 66.7%)

- `./packages/core/database_manager.py` — 15519 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/handwriting/modules/core/database_manager.py` — 15600 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/database_manager.py` — 15600 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/modules/core/database_manager.py` — 15600 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/database_manager.py` — 15691 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/core/database_manager.py` — 15689 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `file_fingerprint.py` (6 files, 4 unique — ratio 66.7%)

- `./packages/core/file_fingerprint.py` — 15882 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/file_fingerprint.py` — 15569 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/core/file_fingerprint.py` — 15569 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/modules/core/file_fingerprint.py` — 15569 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/core/file_fingerprint.py` — 15855 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/file_fingerprint.py` — 15906 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `handwriting_db.py` (6 files, 4 unique — ratio 66.7%)

- `./packages/core/handwriting_db.py` — 11572 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/handwriting/modules/core/handwriting_db.py` — 11736 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/handwriting_db.py` — 11736 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/modules/core/handwriting_db.py` — 11736 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/core/handwriting_db.py` — 11270 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/handwriting_db.py` — 11634 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `htr_config.py` (3 files, 2 unique — ratio 66.7%)

- `./packages/file_processor/modules/config/htr_config.py` — 1365 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/config/htr_config.py` — 1365 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/config/htr_config.py` — 1307 bytes — **DO NOT TOUCH**: independent module in active path

### `medical_doc_gui_final.py` (3 files, 2 unique — ratio 66.7%)

- `./packages/doc_processor/desktop/medical_doc_gui_final.py` — 35993 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc-processor/desktop/medical_doc_gui_final.py` — 35993 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/desktop/medical_doc_gui_final.py` — 139948 bytes — **DO NOT TOUCH**: independent module in active path

### `metrics.py` (21 files, 14 unique — ratio 66.7%)

- `./packages/evaluation/metrics.py` — 10047 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/handwriting/src/metrics.py` — 3019 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/metrics.py` — 3019 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/legacy/ocr_unified_v2/src/metrics.py` — 3019 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/src/metrics.py` — 3019 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/metrics.py` — 3019 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/evaluation/metrics.py` — 8743 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/evaluation/metrics.py` — 8743 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/modules/evaluation/metrics.py` — 8743 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/ai-fuel/core/metrics.py` — 6952 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/ai_fuel/core/metrics.py` — 6952 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/HandwrittenOCR/src/metrics.py` — 3019 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/evaluation/metrics.py` — 10088 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/training/utils/metrics.py` — 1450 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./app/core/monitoring/metrics.py` — 6247 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/doc_processor/download/medical-image-ai-suite/src/utils/metrics.py` — 8450 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/training-framework/utils/metrics.py` — 1484 bytes — **DO NOT TOUCH**: independent module in active path
- `./src/evaluation/metrics.py` — 3117 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/trainer-ui/evaluation/metrics.py` — 8723 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/benchmark_core/src/benchmarks/metrics.py` — 9473 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/benchmark_core/benchmarks/core/metrics.py` — 17312 bytes — **DO NOT TOUCH**: independent module in active path

### `parquet_exporter.py` (3 files, 2 unique — ratio 66.7%)

- `./packages/ai-fuel/export/parquet_exporter.py` — 6732 bytes — **DO NOT TOUCH**: independent module in active path
- `./tools/ai_fuel/export/parquet_exporter.py` — 6732 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/trainer-ui/exports/parquet_exporter.py` — 6500 bytes — **DO NOT TOUCH**: independent module in active path

### `pattern_db.py` (6 files, 4 unique — ratio 66.7%)

- `./packages/learning/pattern_db.py` — 8729 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/pattern_db.py` — 18039 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/ai/pattern_db.py` — 18039 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/modules/ai/pattern_db.py` — 18039 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/learning/pattern_db.py` — 8751 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/ai/pattern_db.py` — 17258 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `protected_vocab.py` (3 files, 2 unique — ratio 66.7%)

- `./packages/core/protected_vocab.py` — 7515 bytes — **DO NOT TOUCH**: independent module in active path
- `./hf-space/packages/core/protected_vocab.py` — 7506 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/core/protected_vocab.py` — 7506 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `search_engine.py` (6 files, 4 unique — ratio 66.7%)

- `./packages/core/search_engine.py` — 22663 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/search_engine.py` — 21541 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/core/search_engine.py` — 21541 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/modules/core/search_engine.py` — 21541 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/core/search_engine.py` — 22976 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/core/search_engine.py` — 21836 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `settings.py` (3 files, 2 unique — ratio 66.7%)

- `./packages/ai/gateway/config/settings.py` — 20718 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/modules/ai/gateway/config/settings.py` — 20718 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/ocr-pipeline/config/settings.py` — 8355 bytes — **DO NOT TOUCH**: independent module in active path

### `sync_backend.py` (3 files, 2 unique — ratio 66.7%)

- `./packages/security/sync/sync_backend.py` — 9640 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/legacy/mobile_review/split/02-mobile-review/sync_backend.py` — 9685 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/modules/security/sync/sync_backend.py` — 9685 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `test_integration.py` (6 files, 4 unique — ratio 66.7%)

- `./tests/test_integration.py` — 6982 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_integration.py` — 19800 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/tests/test_integration.py` — 19800 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/tests/test_integration.py` — 19800 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/tests/test_integration.py` — 25714 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/tests/test_integration.py` — 6814 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison

### `test_ocr_engine.py` (6 files, 4 unique — ratio 66.7%)

- `./tests/test_ocr_engine.py` — 5251 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/handwriting/tests/test_ocr_engine.py` — 5141 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_ocr_engine.py` — 5141 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/tests/test_ocr_engine.py` — 5141 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/tests/test_ocr_engine.py` — 5249 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/tests/test_ocr_engine.py` — 4625 bytes — **DO NOT TOUCH**: independent module in active path

### `test_processing.py` (3 files, 2 unique — ratio 66.7%)

- `./packages/doc_processor/desktop/test_processing.py` — 13309 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/doc-processor/desktop/test_processing.py` — 13309 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/desktop/test_processing.py` — 13314 bytes — **DO NOT TOUCH**: independent module in active path

### `finetuning.py` (14 files, 9 unique — ratio 64.3%)

- `./packages/ai/finetuning.py` — 12997 bytes — **DO NOT TOUCH**: independent module in active path
- `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/finetuning.py` — 17802 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/modules/vision/finetuning.py` — 17802 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/modules/vision/finetuning.py` — 17802 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./apps/handwriting-demo/variants/handwriting-ocr/src/finetuning.py` — 4812 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/handwriting/src/finetuning.py` — 4812 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/omnifile/src/finetuning.py` — 4812 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/file_processor/legacy/mobile_review/split/12-active-learning/finetuning.py` — 13065 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/modules/ai/finetuning.py` — 13065 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./hf-space/packages/vision/finetuning.py` — 17955 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./packages/vision/finetuning.py` — 17749 bytes — **DO NOT TOUCH**: independent module in active path
- `./packages/file_processor/legacy/ocr_unified_v2/src/finetuning.py` — 4163 bytes — **LEGACY REVIEW**: in merged-remnant package + legacy/ path — likely safe to delete, needs human confirmation
- `./packages/file_processor/src/finetuning.py` — 5020 bytes — **LEGACY REVIEW**: in merged-remnant package — may be copy of canonical version, needs content comparison
- `./tools/HandwrittenOCR/src/finetuning.py` — 4164 bytes — **DO NOT TOUCH**: independent module in active path

---

## فئة ب — أسماء متخصصة (نسبة النسخ الفريدة ≤ 60%)

**المعيار الكمي:** نسبة النسخ الفريدة / عدد الملفات ≤ 60% → مرشحة قوية لتكرار حقيقي
ناتج عن دمج git subtree. أسماء مثل `active_learning.py`, `ai_corrector.py`, `ocr_engine.py`
هي أسماء متخصصة لمجال OCR/طبي ولا تتكرر صدفة.

**التحليل التالي (diff stats + تواريخ + أحجام) من التقرير الأصلي سليم لهذه الفئة.**
كل مجموعة تحتوي على الأقل زوجًا متطابقًا والباقي متقارب — هذه هي المرشحات الحقيقية للDEDUP.

### `audit_logger.py` (5 files, 3 unique — ratio 60.0%)

- **Primary (keep):** `./packages/audit/audit_logger.py` — 7343 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/audit_logger.py` — 12070 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/security/audit_logger.py`~~ — 12070 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/security/audit_logger.py`~~ — 12070 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/modules/audit/audit_logger.py` — 7397 bytes — 2026-07-06 18:52:25 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/audit_logger.py`: `406 changed lines`
  - primary vs `./packages/file_processor/modules/audit/audit_logger.py`: `19 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `data_augmentation.py` (5 files, 3 unique — ratio 60.0%)

- **Primary (keep):** `./packages/vision/data_augmentation.py` — 30388 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/data_augmentation.py` — 30424 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/data_augmentation.py`~~ — 30424 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/data_augmentation.py`~~ — 30424 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/data_augmentation.py` — 30533 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/data_augmentation.py`: `18 changed lines`
  - primary vs `./hf-space/packages/vision/data_augmentation.py`: `25 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `gradio_ui.py` (5 files, 3 unique — ratio 60.0%)

- **Primary (keep):** `./packages/handwriting/src/gradio_ui.py` — 0 bytes — 2026-07-10 18:00:29 +0000 (DELETED)
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/src/gradio_ui.py`~~ — 0 bytes — 2026-07-10 18:00:29 +0000 (DELETED) → identical to primary, safe to delete
  - ~~`./packages/omnifile/src/gradio_ui.py`~~ — 0 bytes — 2026-07-10 18:00:29 +0000 (DELETED) → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./app/gradio_ui.py` — 4122 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/src/gradio_ui.py` — 0 bytes — 2026-07-10 18:00:29 +0000 (DELETED)
  **Recommendation:** Primary is deleted — consider `./app/gradio_ui.py` as replacement

### `layout_preserving.py` (5 files, 3 unique — ratio 60.0%)

- **Primary (keep):** `./packages/handwriting/modules/export/layout_preserving.py` — 9107 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/export/layout_preserving.py`~~ — 9107 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/modules/export/layout_preserving.py`~~ — 9107 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/mobile_review/split/03-layout-preserving-export/layout_preserving.py` — 4056 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/modules/export/layout_preserving.py` — 9430 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/file_processor/legacy/mobile_review/split/03-layout-preserving-export/layout_preserving.py`: `228 changed lines`
  - primary vs `./packages/file_processor/modules/export/layout_preserving.py`: `6 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `pdf_to_training_data.py` (5 files, 3 unique — ratio 60.0%)

- **Primary (keep):** `./packages/vision/pdf_to_training_data.py` — 32417 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/pdf_to_training_data.py` — 32516 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/pdf_to_training_data.py`~~ — 32516 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/pdf_to_training_data.py`~~ — 32516 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/pdf_to_training_data.py` — 32562 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/pdf_to_training_data.py`: `75 changed lines`
  - primary vs `./hf-space/packages/vision/pdf_to_training_data.py`: `79 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `protected_words.py` (5 files, 3 unique — ratio 60.0%)

- **Primary (keep):** `./packages/nlp/protected_words.py` — 24903 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/protected_words.py` — 25009 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/protected_words.py`~~ — 25009 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/protected_words.py`~~ — 25009 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/protected_words.py` — 25055 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/protected_words.py`: `20 changed lines`
  - primary vs `./hf-space/packages/nlp/protected_words.py`: `22 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `smart_migrator.py` (5 files, 3 unique — ratio 60.0%)

- **Primary (keep):** `./packages/core/smart_migrator.py` — 13724 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/smart_migrator.py` — 14301 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/core/smart_migrator.py`~~ — 14301 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/core/smart_migrator.py`~~ — 14301 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/smart_migrator.py` — 14365 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/smart_migrator.py`: `60 changed lines`
  - primary vs `./hf-space/packages/core/smart_migrator.py`: `61 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `translation_corrector.py` (5 files, 3 unique — ratio 60.0%)

- **Primary (keep):** `./packages/nlp/translation_corrector.py` — 20594 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/translation_corrector.py` — 20673 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/translation_corrector.py`~~ — 20673 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/translation_corrector.py`~~ — 20673 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/translation_corrector.py` — 20698 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/translation_corrector.py`: `24 changed lines`
  - primary vs `./hf-space/packages/nlp/translation_corrector.py`: `25 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `user_manager.py` (5 files, 3 unique — ratio 60.0%)

- **Primary (keep):** `./packages/core/user_manager.py` — 3828 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/file_processor/legacy/mobile_review/split/05-review-systems/user_manager.py` — 3143 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tools/user_manager.py`~~ — 3143 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/user_manager.py` — 3859 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./packages/file_processor/modules/core/user_manager.py`~~ — 3859 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/file_processor/legacy/mobile_review/split/05-review-systems/user_manager.py`: `138 changed lines`
  - primary vs `./hf-space/packages/core/user_manager.py`: `3 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `video_ocr.py` (5 files, 3 unique — ratio 60.0%)

- **Primary (keep):** `./packages/vision/video_ocr.py` — 22872 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/video_ocr.py` — 22884 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/video_ocr.py`~~ — 22884 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/video_ocr.py`~~ — 22884 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/video_ocr.py` — 22892 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/video_ocr.py`: `25 changed lines`
  - primary vs `./hf-space/packages/vision/video_ocr.py`: `23 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `classifier.py` (7 files, 4 unique — ratio 57.1%)

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
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `exporter.py` (7 files, 4 unique — ratio 57.1%)

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
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `feedback.py` (7 files, 4 unique — ratio 57.1%)

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
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `ocr_engine.py` (7 files, 4 unique — ratio 57.1%)

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
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `test_metrics.py` (7 files, 4 unique — ratio 57.1%)

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

### `test_pipeline.py` (7 files, 4 unique — ratio 57.1%)

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
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `summarizer.py` (9 files, 5 unique — ratio 55.6%)

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
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `arabic_nlp_utils.py` (8 files, 4 unique — ratio 50.0%)

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
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `archive_handler.py` (4 files, 2 unique — ratio 50.0%)

- **Primary (keep):** `./packages/security/archive_handler.py` — 30463 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/archive_handler.py` — 30708 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/security/archive_handler.py`~~ — 30708 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/security/archive_handler.py`~~ — 30708 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/archive_handler.py`: `36 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `backup_manager.py` (4 files, 2 unique — ratio 50.0%)

- **Primary (keep):** `./packages/security/backup_manager.py` — 33381 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/backup_manager.py` — 33458 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/security/backup_manager.py`~~ — 33458 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/security/backup_manager.py`~~ — 33458 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/backup_manager.py`: `13 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `code_protector.py` (4 files, 2 unique — ratio 50.0%)

- **Primary (keep):** `./packages/security/code_protector.py` — 22296 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/security/code_protector.py` — 22394 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/security/code_protector.py`~~ — 22394 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/security/code_protector.py`~~ — 22394 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/security/code_protector.py`: `10 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `dataset_generator.py` (6 files, 3 unique — ratio 50.0%)

- **Primary (keep):** `./packages/core/dataset_generator.py` — 14793 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/dataset_generator.py` — 14834 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/core/dataset_generator.py`~~ — 14834 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/core/dataset_generator.py`~~ — 14834 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/core/dataset_generator.py`~~ — 14834 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/dataset_generator.py` — 14860 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/dataset_generator.py`: `28 changed lines`
  - primary vs `./hf-space/packages/core/dataset_generator.py`: `27 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `document_schemas.py` (4 files, 2 unique — ratio 50.0%)

- **Primary (keep):** `./packages/core/document_schemas.py` — 3089 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/doc-processor/packages/core/document_schemas.py`~~ — 3089 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/doc_processor/packages/core/document_schemas.py`~~ — 3089 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/document_schemas.py` — 3207 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/core/document_schemas.py`: `69 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `export.py` (6 files, 3 unique — ratio 50.0%)

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

### `file_organizer.py` (4 files, 2 unique — ratio 50.0%)

- **Primary (keep):** `./packages/security/file_organizer.py` — 19869 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/file_organizer.py` — 19876 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/security/file_organizer.py`~~ — 19876 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/security/file_organizer.py`~~ — 19876 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/file_organizer.py`: `8 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `file_scanner.py` (4 files, 2 unique — ratio 50.0%)

- **Primary (keep):** `./packages/security/file_scanner.py` — 25805 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/security/file_scanner.py` — 25842 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/security/file_scanner.py`~~ — 25842 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/security/file_scanner.py`~~ — 25842 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/security/file_scanner.py`: `7 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `image_preprocessor.py` (6 files, 3 unique — ratio 50.0%)

- **Primary (keep):** `./packages/vision/image_preprocessor.py` — 20889 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/vision/image_preprocessor.py` — 20900 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/image_preprocessor.py`~~ — 20900 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/vision/image_preprocessor.py`~~ — 20900 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/image_preprocessor.py`~~ — 20900 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./apps/ocr-pipeline/src/preprocessing/image_preprocessor.py` — 18213 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/vision/image_preprocessor.py`: `6 changed lines`
  - primary vs `./apps/ocr-pipeline/src/preprocessing/image_preprocessor.py`: `890 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `image_processor.py` (4 files, 2 unique — ratio 50.0%)

- **Primary (keep):** `./packages/core/image_processor.py` — 16509 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/doc-processor/packages/core/image_processor.py`~~ — 16509 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/doc_processor/packages/core/image_processor.py`~~ — 16509 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/image_processor.py` — 16537 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/core/image_processor.py`: `14 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `language_corrector.py` (6 files, 3 unique — ratio 50.0%)

- **Primary (keep):** `./packages/nlp/language_corrector.py` — 11794 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/language_corrector.py` — 11817 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/language_corrector.py`~~ — 11817 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/language_corrector.py`~~ — 11817 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/language_corrector.py`~~ — 11817 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/language_corrector.py` — 11825 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/language_corrector.py`: `18 changed lines`
  - primary vs `./hf-space/packages/nlp/language_corrector.py`: `16 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `language_detector.py` (6 files, 3 unique — ratio 50.0%)

- **Primary (keep):** `./packages/nlp/language_detector.py` — 11330 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/language_detector.py` — 11346 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/language_detector.py`~~ — 11346 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/language_detector.py`~~ — 11346 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/language_detector.py`~~ — 11346 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/language_detector.py` — 11436 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/language_detector.py`: `9 changed lines`
  - primary vs `./hf-space/packages/nlp/language_detector.py`: `10 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `layout_analyzer.py` (6 files, 3 unique — ratio 50.0%)

- **Primary (keep):** `./packages/vision/layout_analyzer.py` — 11647 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/layout_analyzer.py` — 11646 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/layout_analyzer.py`~~ — 11646 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/layout_analyzer.py`~~ — 11646 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/layout_analyzer.py`~~ — 11646 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/layout_analyzer.py` — 11675 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/layout_analyzer.py`: `2 changed lines`
  - primary vs `./hf-space/packages/vision/layout_analyzer.py`: `1 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `mixed_language.py` (6 files, 3 unique — ratio 50.0%)

- **Primary (keep):** `./packages/nlp/mixed_language.py` — 7360 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/nlp/mixed_language.py` — 7211 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/mixed_language.py`~~ — 7211 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/mixed_language.py`~~ — 7211 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/mixed_language.py` — 7394 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./packages/file_processor/modules/nlp/mixed_language.py`~~ — 7394 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/nlp/mixed_language.py`: `10 changed lines`
  - primary vs `./hf-space/packages/nlp/mixed_language.py`: `7 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `preprocessing.py` (6 files, 3 unique — ratio 50.0%)

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

### `process.py` (6 files, 3 unique — ratio 50.0%)

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

### `recognition.py` (6 files, 3 unique — ratio 50.0%)

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

### `reconstruction.py` (12 files, 6 unique — ratio 50.0%)

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

### `result_fusion.py` (6 files, 3 unique — ratio 50.0%)

- **Primary (keep):** `./packages/vision/result_fusion.py` — 17064 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/result_fusion.py` — 17118 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/result_fusion.py`~~ — 17118 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/result_fusion.py`~~ — 17118 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/result_fusion.py`~~ — 17118 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/result_fusion.py` — 17137 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/result_fusion.py`: `23 changed lines`
  - primary vs `./hf-space/packages/vision/result_fusion.py`: `24 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `secure_file_handler.py` (4 files, 2 unique — ratio 50.0%)

- **Primary (keep):** `./packages/security/secure_file_handler.py` — 5497 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/secure_file_handler.py` — 5531 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/security/secure_file_handler.py`~~ — 5531 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/security/secure_file_handler.py`~~ — 5531 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/security/secure_file_handler.py`: `5 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `study_guide.py` (10 files, 5 unique — ratio 50.0%)

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
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `surya_ocr.py` (6 files, 3 unique — ratio 50.0%)

- **Primary (keep):** `./packages/vision/surya_ocr.py` — 6160 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/vision/surya_ocr.py` — 6191 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/surya_ocr.py`~~ — 6191 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/vision/surya_ocr.py`~~ — 6191 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/surya_ocr.py`~~ — 6191 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/surya_ocr.py` — 6192 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/vision/surya_ocr.py`: `9 changed lines`
  - primary vs `./hf-space/packages/vision/surya_ocr.py`: `7 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `table_extractor.py` (6 files, 3 unique — ratio 50.0%)

- **Primary (keep):** `./packages/vision/table_extractor.py` — 11463 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/vision/table_extractor.py` — 11499 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/table_extractor.py`~~ — 11499 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/vision/table_extractor.py`~~ — 11499 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/table_extractor.py`~~ — 11499 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/table_extractor.py` — 11500 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/vision/table_extractor.py`: `9 changed lines`
  - primary vs `./hf-space/packages/vision/table_extractor.py`: `7 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `text_reconstructor.py` (6 files, 3 unique — ratio 50.0%)

- **Primary (keep):** `./packages/vision/text_reconstructor.py` — 22397 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/text_reconstructor.py` — 22456 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/vision/text_reconstructor.py`~~ — 22456 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/text_reconstructor.py`~~ — 22456 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/text_reconstructor.py`~~ — 22456 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/vision/text_reconstructor.py` — 22494 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/text_reconstructor.py`: `5 changed lines`
  - primary vs `./hf-space/packages/vision/text_reconstructor.py`: `7 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `translator.py` (6 files, 3 unique — ratio 50.0%)

- **Primary (keep):** `./packages/nlp/translator.py` — 24992 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/translator.py` — 25033 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/nlp/translator.py`~~ — 25033 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/translator.py`~~ — 25033 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/translator.py`~~ — 25033 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/translator.py` — 25082 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/translator.py`: `11 changed lines`
  - primary vs `./hf-space/packages/nlp/translator.py`: `12 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `watchdog_service.py` (6 files, 3 unique — ratio 50.0%)

- **Primary (keep):** `./packages/core/watchdog_service.py` — 15605 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/watchdog_service.py` — 15674 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/core/watchdog_service.py`~~ — 15674 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/core/watchdog_service.py`~~ — 15674 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/core/watchdog_service.py`~~ — 15674 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/core/watchdog_service.py` — 15764 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/core/watchdog_service.py`: `35 changed lines`
  - primary vs `./hf-space/packages/core/watchdog_service.py`: `35 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

## Needs Human Decision — Grouped by package

*No groups in this category — all 124 partial-duplicate groups contain at least one pair of identical files.*

However, within the auto-deletable groups above, many still have **differing variants** that need human decision. See the diff stats in each group for details.

### `pdf_processor.py` (12 files, 5 unique — ratio 41.7%)

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
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `gemini_refiner.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./packages/ai/gemini_refiner.py` — 8592 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/gemini_refiner.py` — 8629 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/modules/ai/gemini_refiner.py`~~ — 8629 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/ai/gemini_refiner.py`~~ — 8629 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/ai/gemini_refiner.py`~~ — 8629 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/gemini_refiner.py`: `7 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `markdown_exporter.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./packages/export/markdown_exporter.py` — 4537 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/export/markdown_exporter.py` — 4568 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/export/markdown_exporter.py`~~ — 4568 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/export/markdown_exporter.py`~~ — 4568 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/export/markdown_exporter.py`~~ — 4568 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/export/markdown_exporter.py`: `3 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `pattern_matcher.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./packages/ai/pattern_matcher.py` — 14417 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/modules/ai/pattern_matcher.py` — 14449 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/ai/pattern_matcher.py`~~ — 14449 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/ai/pattern_matcher.py`~~ — 14449 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/ai/pattern_matcher.py`~~ — 14449 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/modules/ai/pattern_matcher.py`: `22 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `spell_corrector.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./packages/nlp/spell_corrector.py` — 26439 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/spell_corrector.py` — 26536 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/spell_corrector.py`~~ — 26536 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/nlp/spell_corrector.py`~~ — 26536 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/spell_corrector.py`~~ — 26536 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/nlp/spell_corrector.py`: `21 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `tasks.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./packages/handwriting/tasks.py` — 6024 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tasks.py`~~ — 6024 bytes — 2026-07-06 18:52:26 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/tasks.py`~~ — 6024 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/tasks.py`~~ — 6024 bytes — 2026-07-07 12:21:24 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./packages/file_processor/_dev_references/hello-agents/Co-creation-projects/Apricity-InnocoreAI/api/routes/tasks.py` — 0 bytes — 2026-07-10 17:30:33 +0000 (DELETED)
  **Diffs between unique versions:**
  **Recommendation:** keep packages/ version — primary is in canonical packages/ location

### `test_advanced_pipeline.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./tests/test_advanced_pipeline.py` — 8900 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/tests/test_advanced_pipeline.py` — 8894 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tests/test_advanced_pipeline.py`~~ — 8894 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/tests/test_advanced_pipeline.py`~~ — 8894 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_advanced_pipeline.py`~~ — 8894 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/tests/test_advanced_pipeline.py`: `14 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_arabic_nlp_utils.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./tests/test_arabic_nlp_utils.py` — 6008 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_arabic_nlp_utils.py` — 6007 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_arabic_nlp_utils.py`~~ — 6007 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_arabic_nlp_utils.py`~~ — 6007 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_arabic_nlp_utils.py`~~ — 6007 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_arabic_nlp_utils.py`: `4 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_arabic_rtl.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./tests/test_arabic_rtl.py` — 15120 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/tests/test_arabic_rtl.py` — 15120 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tests/test_arabic_rtl.py`~~ — 15120 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/tests/test_arabic_rtl.py`~~ — 15120 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_arabic_rtl.py`~~ — 15120 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/tests/test_arabic_rtl.py`: `2 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_fusion.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./tests/test_fusion.py` — 14834 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/tests/test_fusion.py` — 14868 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tests/test_fusion.py`~~ — 14868 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/tests/test_fusion.py`~~ — 14868 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_fusion.py`~~ — 14868 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/tests/test_fusion.py`: `7 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `test_gemini_modules.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./tests/test_gemini_modules.py` — 18957 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_gemini_modules.py` — 18946 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_gemini_modules.py`~~ — 18946 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_gemini_modules.py`~~ — 18946 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_gemini_modules.py`~~ — 18946 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_gemini_modules.py`: `46 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_layout_preserving.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./tests/test_layout_preserving.py` — 1726 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/tests/test_layout_preserving.py` — 1723 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tests/test_layout_preserving.py`~~ — 1723 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/tests/test_layout_preserving.py`~~ — 1723 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_layout_preserving.py`~~ — 1723 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/tests/test_layout_preserving.py`: `2 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_markdown_exporter.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./tests/test_markdown_exporter.py` — 1930 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/tests/test_markdown_exporter.py` — 1915 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tests/test_markdown_exporter.py`~~ — 1915 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/tests/test_markdown_exporter.py`~~ — 1915 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_markdown_exporter.py`~~ — 1915 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/tests/test_markdown_exporter.py`: `7 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_pattern_matcher.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./tests/test_pattern_matcher.py` — 4448 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_pattern_matcher.py` — 4447 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_pattern_matcher.py`~~ — 4447 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_pattern_matcher.py`~~ — 4447 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_pattern_matcher.py`~~ — 4447 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_pattern_matcher.py`: `identical`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_performance.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./tests/test_performance.py` — 3703 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_performance.py` — 3810 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_performance.py`~~ — 3810 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_performance.py`~~ — 3810 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_performance.py`~~ — 3810 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_performance.py`: `24 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `test_preprocessor.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./tests/test_preprocessor.py` — 7981 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./packages/handwriting/tests/test_preprocessor.py` — 7979 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/tests/test_preprocessor.py`~~ — 7979 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/tests/test_preprocessor.py`~~ — 7979 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_preprocessor.py`~~ — 7979 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./packages/handwriting/tests/test_preprocessor.py`: `2 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_sensitive_scanner.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./tests/test_sensitive_scanner.py` — 5905 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_sensitive_scanner.py` — 5890 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_sensitive_scanner.py`~~ — 5890 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_sensitive_scanner.py`~~ — 5890 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_sensitive_scanner.py`~~ — 5890 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_sensitive_scanner.py`: `30 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_spell_corrector.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./tests/test_spell_corrector.py` — 5095 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_spell_corrector.py` — 5082 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_spell_corrector.py`~~ — 5082 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_spell_corrector.py`~~ — 5082 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_spell_corrector.py`~~ — 5082 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_spell_corrector.py`: `26 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `test_summarizer.py` (5 files, 2 unique — ratio 40.0%)

- **Primary (keep):** `./tests/test_summarizer.py` — 3943 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_summarizer.py` — 3931 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./packages/file_processor/tests/test_summarizer.py`~~ — 3931 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/tests/test_summarizer.py`~~ — 3931 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/tests/test_summarizer.py`~~ — 3931 bytes — 2026-07-08 22:58:18 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./apps/handwriting-demo/variants/handwriting-ocr/tests/test_summarizer.py`: `24 changed lines`
  **Recommendation:** keep packages/ version — primary appears to be the canonical location

### `ai_corrector.py` (6 files, 2 unique — ratio 33.3%)

- **Primary (keep):** `./packages/nlp/ai_corrector.py` — 13005 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/ai_corrector.py` — 13039 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/ai_corrector.py`~~ — 13039 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/nlp/ai_corrector.py`~~ — 13039 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/ai_corrector.py`~~ — 13039 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/ai_corrector.py`~~ — 13039 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/nlp/ai_corrector.py`: `34 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `arabic_rtl.py` (6 files, 2 unique — ratio 33.3%)

- **Primary (keep):** `./packages/nlp/arabic_rtl.py` — 25928 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/arabic_rtl.py`~~ — 25928 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/modules/nlp/arabic_rtl.py`~~ — 25928 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/handwriting/modules/nlp/arabic_rtl.py`~~ — 25928 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/modules/nlp/arabic_rtl.py`~~ — 25928 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/arabic_rtl.py` — 25966 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/nlp/arabic_rtl.py`: `2 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `entity_extractor.py` (6 files, 2 unique — ratio 33.3%)

- **Primary (keep):** `./packages/nlp/entity_extractor.py` — 22578 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/entity_extractor.py` — 22609 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/entity_extractor.py`~~ — 22609 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/nlp/entity_extractor.py`~~ — 22609 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/entity_extractor.py`~~ — 22609 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/entity_extractor.py`~~ — 22609 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/nlp/entity_extractor.py`: `3 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `mixed_text.py` (6 files, 2 unique — ratio 33.3%)

- **Primary (keep):** `./packages/nlp/mixed_text.py` — 6733 bytes — 2026-07-08 22:58:18 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/mixed_text.py`~~ — 6733 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/modules/nlp/mixed_text.py`~~ — 6733 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/handwriting/modules/nlp/mixed_text.py`~~ — 6733 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/modules/nlp/mixed_text.py`~~ — 6733 bytes — 2026-07-08 22:58:18 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/mixed_text.py` — 6786 bytes — 2026-07-07 18:45:30 +0000
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/nlp/mixed_text.py`: `3 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `normalize.py` (6 files, 2 unique — ratio 33.3%)

- **Primary (keep):** `./packages/vision/normalize.py` — 7750 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/vision/normalize.py` — 7782 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/normalize.py`~~ — 7782 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/vision/normalize.py`~~ — 7782 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/normalize.py`~~ — 7782 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/normalize.py`~~ — 7782 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/vision/normalize.py`: `10 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `review_ui.py` (6 files, 2 unique — ratio 33.3%)

- **Primary (keep):** `./packages/handwriting/src/review_ui.py` — 14900 bytes — 2026-07-07 12:21:28 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/src/review_ui.py`~~ — 14900 bytes — 2026-07-06 18:52:26 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/legacy/ocr_unified_v2/src/review_ui.py`~~ — 14900 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
  - ~~`./packages/file_processor/src/review_ui.py`~~ — 14900 bytes — 2026-07-06 18:52:25 +0000 → identical to primary, safe to delete
  - ~~`./packages/omnifile/src/review_ui.py`~~ — 14900 bytes — 2026-07-07 12:21:24 +0000 → identical to primary, safe to delete
- **Keep (non-primary cluster):** `./tools/HandwrittenOCR/src/review_ui.py` — 14910 bytes — 2026-07-08 22:58:18 +0000
  **Diffs between unique versions:**
  - primary vs `./tools/HandwrittenOCR/src/review_ui.py`: `12 changed lines`
  **Recommendation:** keep newest/largest — newer and larger variant exists; compare content

### `structure.py` (6 files, 2 unique — ratio 33.3%)

- **Primary (keep):** `./packages/core/structure.py` — 10284 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/core/structure.py` — 10323 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/core/structure.py`~~ — 10323 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/core/structure.py`~~ — 10323 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/core/structure.py`~~ — 10323 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/core/structure.py`~~ — 10323 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/core/structure.py`: `13 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `table_detection.py` (6 files, 2 unique — ratio 33.3%)

- **Primary (keep):** `./packages/vision/table_detection.py` — 5957 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/vision/table_detection.py` — 5974 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/vision/table_detection.py`~~ — 5974 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/vision/table_detection.py`~~ — 5974 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/vision/table_detection.py`~~ — 5974 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/vision/table_detection.py`~~ — 5974 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/vision/table_detection.py`: `7 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

### `text_classifier.py` (6 files, 2 unique — ratio 33.3%)

- **Primary (keep):** `./packages/nlp/text_classifier.py` — 15772 bytes — 2026-07-08 22:58:18 +0000
- **Keep (non-primary cluster):** `./hf-space/packages/nlp/text_classifier.py` — 15789 bytes — 2026-07-07 18:45:30 +0000
  - ~~`./apps/handwriting-demo/variants/handwriting-ocr/modules/nlp/text_classifier.py`~~ — 15789 bytes — 2026-07-06 18:52:26 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/file_processor/modules/nlp/text_classifier.py`~~ — 15789 bytes — 2026-07-06 18:52:25 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/handwriting/modules/nlp/text_classifier.py`~~ — 15789 bytes — 2026-07-07 12:21:28 +0000 → identical to cluster member, safe to delete
  - ~~`./packages/omnifile/modules/nlp/text_classifier.py`~~ — 15789 bytes — 2026-07-07 12:21:24 +0000 → identical to cluster member, safe to delete
  **Diffs between unique versions:**
  - primary vs `./hf-space/packages/nlp/text_classifier.py`: `7 changed lines`
  **→ فئة ب — مرشح لتكرار subtree-merge، يحتاج مقارنة محتوى قبل الحذف**

