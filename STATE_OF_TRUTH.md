# STATE_OF_TRUTH.md — آخر تحديث: 2026-07-16

> **كل نموذج AI (Z.ai، Claude، Mistral، Grok، أو أي آخر) يجب أن يقرأ هذا الملف أولاً قبل أي تعديل على هذا المستودع، ويُحدِّثه بعد كل تغيير جوهري.**

---

## حالة الدمج — Merge Status

| الفرع | الحالة | Merge Commit |
|---|---|---|
| `cleanup/final-pending-items` | ✅ مُدمج في main (merge commit `46fd895`) | تم الدفع في `e6b450d` |

آخر تحقق: `2026-07-16T22:46 UTC+3` — `import app.gradio_full_hitl` ناجح، صفر كسر استيراد.

---

## التطبيق الرسمي

`app/gradio_full_hitl.py` (944 سطر) — **التطبيق الرسمي المُعتمَد للإنتاج**. يحتوي 10 وظائف كاملة: رفع صورة → OCR ensemble، تصحيح HybridSpellChecker، تدقيق Jais LLM، NER طبي، حفظ HF Dataset، تحديث القاموس، إعادة تدريب Jais NER، ترجمة طبية (4 اتجاهات)، حاسبة CER/WER، Before/After comparison.

## تطبيق تجريبي منفصل

`app/advanced_review_app.py` — تطبيق تجريبي جديد بتبويبات Compare/Search/Review. **غير مُعتمَد للإنتاج بعد.** القيود المعروفة: لا يدعم رفع الصور، لا يملك Jais proofreading، لا يحفظ في HF Dataset، لا يملك ترجمة طبية، لا يملك تحديث القاموس/إعادة تدريب NER. انظر `GRADIO_HITL_CHANGES_REVIEW.md` (الخيار C — القرار النهائي).

## الحزم النشطة في packages/

| الحزمة | الوظيفة |
|---|---|
| `core` | المحرك الأساسي: engine_router (محدّث بـ Qwen/QARI/Nougat), **engine_registry** (runtime-aware availability checks + healthcheck), corrections_manager, base_db |
| `vision` | معالجة الصور: image_preprocessor, arabic_segmenter, batch_ocr |
| `nlp` | معالجة اللغة: spell_corrector, translation_corrector, arabic_rtl, arabic_nlp_utils |
| `src/ocr` | الوحدات الأساسية الجديدة: rtl_utils, field_extractor, deduplication |
| `omni_medical_suite/preprocessing` | مقارنة raw vs printed + wrappers للمعالجة المسبقة |
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

## تشغيل سريع — Quick Start

```bash
# 1. تثبيت التبعيات
pip install -e ".[dev]"

# 2. تشغيل التطبيق الرسمي
python app/gradio_full_hitl.py

# 3. تشغيل التطبيق التجريبي (اختياري)
python app/advanced_review_app.py

# 4. الاختبارات
pytest tests/ -x
```

> **للتاريخ الكامل للدمجات والتنظيف:** انظر `MERGE_HISTORY.md`
> **للمشاكل المفتوحة والقرارات المعلقة:** انظر `OPEN_ISSUES.md`