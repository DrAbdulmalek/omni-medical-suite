# STATE_OF_TRUTH.md — آخر تحديث: 2026-07-11

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

### حزم مُدمَجة تحتوي تكراراً هيكلياً (تم التنظيف الجزئي)
هذه الحزم كانت تحمل نسخاً من ملفات من packages/ أعلاه. بعد التنظيف:
- `packages/file_processor/` — _dev_references/ حُذف (200MB). 85 ملف مكرر 100% حُذف. بقي تكرار جزئي يحتاج مراجعة.
- `packages/handwriting/` — نسخ Gradio حُذفت. بقي تكرار جزئي لمفات Python.
- `packages/omnifile/` — نسخ Gradio حُذفت. بقي تكرار جزئي.
- `packages/doc-processor/` / `packages/doc_processor/` — نسخ من core/ (تكرار جزئي)
- `apps/handwriting-demo/variants/handwriting-ocr/` — نسخ Gradio حُذفت
- `hf-space/packages/` — ملفات مكررة حُذفت (scanner_fixer, vision, core, nlp)
- `packages/bilingual/` — نسخ من nlp/ (تكرار جزئي)

**تقارير المرحلة 1:** DUPLICATE_VERIFICATION_REPORT.md (85 متطابق، 124 مختلف جزئياً، 122 بالاسم فقط)

## تطبيقات Gradio (تم التنظيف — من 43 إلى 19)

**المحتفظ بها (2):**
- `app/gradio_full_hitl.py` — التطبيق الرسمي المعتمد
- `hf-space/app.py` — نسخة HF Space محسّنة للمعالجة CPU

**تم حذف 24 ملفاً** (نسخ مكررة + إيجابيات كاذبة). انظر `GRADIO_APPS_DECISION.md`.

**18 ملفاً معلقاً تحتاج مراجعة بشرية** — مقسمة إلى 5 مجموعات (A-E) في GRADIO_APPS_DECISION.md.

## آخر 10 تغييرات جوهرية

| Hash | التاريخ | الوصف | المنفِّذ |
|---|---|---|---|
| `f8dab72` | 2026-07-11 | المرحلة 3: تنظيف شامل — حذف 200MB+، 85 ملف مكرر، 52 workflow، 24 Gradio، ~105 مرجع مكسور | Z.ai |
| `f4e4393` | 2026-07-11 | المرحلة 1: 4 تقارير تحقق (تكرار، workflows، مراجع، pytest) | Z.ai |
| `8573ddd` | 2026-07-09 | حذف manjaro-care/reset-net (مستودعات مستقلة الآن) | Z.ai |
| `a4db688` | 2026-07-08 | سقالة تدريب TrOCR | Z.ai |
| `a8c35ec` | 2026-07-08 | RELEASE_NOTES.md + DEPLOYMENT_GUIDE.md | Z.ai |
| `1485e3d` | 2026-07-08 | ruff auto-fix (12,846 مشكلة) + إصلاح اختبارات | Z.ai |
| `b343be6` | 2026-07-07 | Phase 7: Monitoring (Prometheus/Grafana/Sentry) | Z.ai |
| `5d1da4e` | 2026-07-07 | Phase 7: _logging, alerting, backup, Dependabot | Z.ai |
| `ccbae3d` | 2026-07-06 | Phase 6: HF Spaces deployment | Z.ai |
| `2d97d1c` | 2026-07-05 | Phase 5: 270/332 اختبار ناجح | Z.ai |

## قرارات معلَّقة تحتاج مراجعة بشرية

1. **124 ملفاً مختلفاً جزئياً** — انظر `DUPLICATE_VERIFICATION_REPORT.md` قسم "مختلف جزئياً". يحتاج قراراً بشرياً لكل ملف: هل النسخة في packages/ الأساسية أم النسخة في الحزم المدمجة أحدث؟

2. **18 تطبيق Gradio معلّق** — انظر `GRADIO_APPS_DECISION.md` للتوصيات المجمّعة (5 مجموعات A-E).

3. **ruff auto-fix دفعة واحدة على 12,846 مشكلة** — تم تنفيذها بلا مراجعة بشرية فردية. قد تحتوي تغييرات سلوكية غير مقصودة.

4. **3 أخطاء منطقية في tmx_processor.py** — تم توثيق الأسباب الجذرية في PYTEST_REPORT.md:
   - `test_detect_medical_category_fracture`: regex `CT` بدون حد كلمة يطابق "ct" داخل "fracture"
   - `test_detect_medical_category_generic`: regex `test` بدون حد كلمة يطابق الكلمة العادية "test"
   - `test_export_to_json`: `{k: row[k] for k in row}` على sqlite3.Row يعطي قيماً لا أسماء أعمدة

5. **91 فشل اختبار بسبب تبعيات مفقودة** — torch/transformers/interactive_learning. تحتاج إضافة `@pytest.mark.skipif` أو تثبيت التبعيات.

6. **~50 ملف requirements*.txt قديمة** — يمكن حذفها بعد تحديث Dockerfiles لاستخدام pyproject.toml extras. انظر `docs/DEPENDENCY_STRATEGY.md`.

7. **المراجع المكسورة في المستودعات البعيدة** — تم إصلاح المراجع المحلية فقط. repos البعيدة (repo-sync-toolkit، medical-ocr-trainer-hf، intelli-file-manager، sync-github) تحتاج إصلاحاً مباشراً على GitHub.