# STATE_OF_TRUTH.md — آخر تحديث: 2026-07-09

> **كل نموذج AI (Z.ai، Claude، Mistral، Grok، أو أي آخر) يجب أن يقرأ هذا الملف أولاً قبل أي تعديل على هذا المستودع، ويُحدِّثه بعد كل تغيير جوهري.**

---

## التطبيق الرسمي الوحيد

`app/gradio_full_hitl.py` (944 سطر) — واجهة Gradio متكاملة تضم:
- OCR بصري (PaddleOCR + Tesseract ensemble)
- تصحيح إملائي هجين (HybridSpellChecker)
- ترجمة طبية عربية-إنجليزية
- حاسبة CER/WER لتقييم دقة النص المُستخرَج
- واجهة HITL (Human-in-the-Loop) للمراجعة والتصحيح اليدوي

## الحزم النشطة في packages/ (لا تكرار مضمون — لكن تكرار هيكلي موجود بحاجة مراجعة)

| الحزمة | الوظيفة |
|---|---|
| `core` | المحرك الأساسي: engine_router, corrections_manager, base_db |
| `vision` | معالجة الصور: image_preprocessor, arabic_segmenter, batch_ocr |
| `nlp` | معالجة اللغة: spell_corrector, translation_corrector, arabic_rtl, arabic_nlp_utils |
| `medical` | معالجة خاصة بالطب: tmx_processor, bgl_converter |
| `security` | أمان: archive_handler, backup_manager |
| `audit` | تدقيق: audit_logger |
| `ai` | بوابة LLM: gateway/providers, account_pool |
| `ai-fuel` | أنظمة AI إضافية: classifier, segmenter, dedup, active_learning |
| `bilingual` | دعم ثنائي اللغة |
| `evaluation` | مقاييس التقييم (CER/WER) |
| `export` | تصدير النتائج |
| `data-prep` | تجهيز البيانات |
| `segmentation` | تقسيم المستندات |
| `training` / `training-framework` / `training_hub` | أنابيب تدريب النماذج |
| `learning` / `interactive-learning` | تعلم تفاعلي |
| `benchmark_core` | إطار قياس الأداء |
| `ocr_postprocess` | معالجة ما بعد OCR |
| `omni-ocr` | OCR شامل |
| `scanner_fixer` | إصلاح الصور الممسوحة |
| `desktop` | دعم تطبيق سطح المكتب |
| `config` | إعدادات المشروع |
| `gt_core` | بيانات الحقيقة الأرضية (ground truth) |

### حزم مُدمَجة تحتوي تكراراً هيكلياً مع packages/ الأصلية (تحتاج مراجعة بشرية)
هذه الحزم تحمل نسخاً من ملفات من packages/ أعلاه. تم رصدها في DUPLICATE_FILES_REPORT.txt:
- `packages/file_processor/` — نسخ ضخمة من معظم الحزم أعلاه + مراجع تعليمية (200MB `_dev_references/`)
- `packages/handwriting/` — نسخ من vision/, nlp/, security/, ai/
- `packages/omnifile/` — نسخ من nlp/, vision/, core/
- `packages/doc-processor/` / `packages/doc_processor/` — نسخ من core/
- `apps/handwriting-demo/variants/handwriting-ocr/` — نسخ من nlp/, vision/, security/
- `hf-space/packages/` — نسخ من nlp/, vision/, core/, ocr_postprocess/, scanner_fixer/
- `packages/bilingual/` — نسخ من nlp/

### محتوى لا علاقة له بالمشروع (تحتاج حذف بمراجعة بشرية)
- `packages/file_processor/_dev_references/hello-agents/` (157MB) — كود تعليمي عن وكلاء AI بمشاريع مساهمين عشوائيين
- `packages/file_processor/_dev_references/9router/` (7.6MB) — مشروع توجيه/بروكسي منفصل
- **المجموع: ~200MB من مواد مرجعية لا علاقة لها بـ OCR طبي**

## تطبيقات Gradio الموجودة حالياً (43 ملفاً يحتوي import gradio)

**الرسمي:**
- `app/gradio_full_hitl.py` — التطبيق المعتمد

**في المسار `app/`:**
- `app/gradio_ui.py` (152 سطر)
- `app/hf_app.py` (1990 سطر)

**في `apps/`:**
- `apps/ocr-demo/app.py`
- `apps/ocr-pipeline/app.py`
- `apps/ocr-pipeline/app/gradio_hitl.py`
- `apps/handwriting-demo/app.py`
- `apps/handwriting-demo/hf-deploy/app/gradio_app.py`
- `apps/handwriting-demo/variants/handwriting-ocr/app.py`
- `apps/handwriting-demo/variants/handwriting-ocr/hf_app.py`
- `apps/handwriting-demo/variants/handwriting-ocr/src/gradio_ui.py`
- `apps/trainer-ui/app.py`
- `apps/trainer-ui/hf-variant/app.py`

**في `hf-space/`:**
- `hf-space/app.py`
- `hf-space/packages/vision/medical_ocr_gradio.py`

**في الحزم المكررة:**
- `packages/file_processor/hf_app.py`, `src/gradio_ui.py`, `run.py`, `app.py`
- `packages/file_processor/modules/ui/gradio_app.py`, `dual_ocr_interface.py`, `batch_correction_ui.py`
- `packages/file_processor/legacy/translation_corrector/app.py`
- `packages/handwriting/hf_app.py`, `src/gradio_ui.py`, `app.py`
- `packages/omnifile/hf_app.py`, `src/gradio_ui.py`
- `packages/vision/medical_ocr_gradio.py`
- `packages/nlp/translation_corrector/arabic_translation_processor.py`
- `desktop/gradio_scanner_app.py`
- `notebooks/omnimedical_gradio_ui.py`
- `labs/omniparse_study/omniparse/demo.py`, `server.py`
- `packages/omniparse/demo.py`, `server.py`
- `packages/doc_processor/download/medical-image-ai-suite/gradio_phase2_enhanced.py`, `omni_gradio_fusion_v3.py`
- `tools/ops/telegram_forwarder/app.py`

## آخر 10 تغييرات جوهرية

| Hash | التاريخ | الوصف | المنفِّذ |
|---|---|---|---|
| `8573ddd` | 2026-07-09 | حذف manjaro-care/reset-net (مستودعات مستقلة الآن) | Z.ai |
| `a4db688` | 2026-07-08 | سقالة تدريب TrOCR | Z.ai |
| `a8c35ec` | 2026-07-08 | RELEASE_NOTES.md + DEPLOYMENT_GUIDE.md | Z.ai |
| `1485e3d` | 2026-07-08 | ruff auto-fix (12,846 مشكلة) + إصلاح اختبارات | Z.ai |
| `b343be6` | 2026-07-07 | Phase 7: Monitoring (Prometheus/Grafana/Sentry) | Z.ai |
| `5d1da4e` | 2026-07-07 | Phase 7:_logging, alerting, backup, Dependabot | Z.ai |
| `ccbae3d` | 2026-07-06 | Phase 6: HF Spaces deployment | Z.ai |
| `2d97d1c` | 2026-07-05 | Phase 5: 270/332 اختبار ناجح | Z.ai |
| `32917dd` | 2026-07-04 | Phase 4: Docker + docker-compose + CI/CD | Z.ai |
| `b950e52` | 2026-07-04 | Phase 3: Desktop App + Gradio Jais UI | Z.ai |

## قرارات معلَّقة تحتاج مراجعة بشرية

1. **344 ملفاً مكرراً بالاسم** — انظر `DUPLICATE_FILES_REPORT.txt` في `/download/`. قبل حذف أي منها، يجب:
   - تشغيل `diff` حرفي لكل زوج للتأكد من التطابق 100%
   - تحديد المسار "الأساسي" لكل ملف (packages/ أم file_processor/ أم غيره)
   - حذف النسخ غير الأساسية فقط بعد التأكد

2. **200MB محتوى `_dev_references/`** — لا علاقة له بـ OCR طبي. يحتاج حذفاً كاملاً بعد تأكيد المستخدم.

3. **43 تطبيق Gradio** — فقط `app/gradio_full_hitl.py` معتمَد. الباقي يحتاج مراجعة لتحديد: هل يُحتفظ بأي منها كـ"نسخة بديلة" أم يُحذف؟

4. **ruff auto-fix دفعة واحدة على 12,846 مشكلة** — تم تنفيذها بلا مراجعة بشرية فردية. قد تحتوي تغييرات سلوكية غير مقصودة.

5. **باقي اختبارات 3 فاشلة** — في `packages/medical/tmx_processor.py` (منطق مجال، ليس خطأ بيئة). تحتاج مراجعة منطقية.

6. **المستودعات المنفصلة المسترجَعة:**
   - `DrAbdulmalek/manjaro-care` — مستقل الآن
   - `DrAbdulmalek/reset-net` — مستقل الآن
   - وسم الأمان على omni-medical-suite: `pre-remove-dup-sys`