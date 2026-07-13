# STATE_OF_TRUTH.md — آخر تحديث: 2026-07-14

> **كل نموذج AI (Z.ai، Claude، Mistral، Grok، أو أي آخر) يجب أن يقرأ هذا الملف أولاً قبل أي تعديل على هذا المستودع، ويُحدِّثه بعد كل تغيير جوهري.**

---

## التطبيق الرسمي

`app/gradio_full_hitl.py` (944 سطر) — **التطبيق الرسمي المُعتمَد للإنتاج**. يحتوي 10 وظائف كاملة: رفع صورة → OCR ensemble، تصحيح HybridSpellChecker، تدقيق Jais LLM، NER طبي، حفظ HF Dataset، تحديث القاموس، إعادة تدريب Jais NER، ترجمة طبية (4 اتجاهات)، حاسبة CER/WER، Before/After comparison.

## تطبيق تجريبي منفصل

`app/advanced_review_app.py` — تطبيق تجريبي جديد بتبويبات Compare/Search/Review. **غير مُعتمَد للإنتاج بعد.** القيود المعروفة: لا يدعم رفع الصور، لا يملك Jais LLM proofreading، لا يحفظ في HF Dataset، لا يملك ترجمة طبية، لا يملك تحديث القاموس/إعادة تدريب NER. انظر `GRADIO_HITL_CHANGES_REVIEW.md` (الخيار C — القرار النهائي).

> **ملاحظة فرع:** فرع `integrate/genspark-field-dedup` دُمج لـ `main` بـ `--no-ff` في commit `d8c854d` (2026-07-14). القرار: الخيار C — `gradio_full_hitl.py` لم يُستبدَل.

## الحزم النشطة في packages/ (لا تكرار مضمون — لكن تكرار هيكلي موجود بحاجة مراجعة)

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

## تطبيقات Gradio (تم التنظيف — من 43 إلى 20)

**المحتفظ بها (3):**
- `app/gradio_full_hitl.py` — **التطبيق الرسمي المُعتمَد** (944 سطر، 10 وظائف)
- `app/advanced_review_app.py` — تطبيق تجريبي منفصل (Compare / Search / Review) — غير مُعتمَد للإنتاج بعد
- `hf-space/app.py` — نسخة HF Space محسّنة للمعالجة CPU

**تم حذف 24 ملفاً** (نسخ مكررة + إيجابيات كاذبة). انظر `GRADIO_APPS_DECISION.md`.

**18 ملفاً معلقاً تحتاج مراجعة بشرية** — مقسمة إلى 5 مجموعات (A-E) في GRADIO_APPS_DECISION.md.

## آخر 10 تغييرات جوهرية

| Hash | التاريخ | الوصف | المنفِّذ |
|---|---|---|---|
| `d8c854d` | 2026-07-14 | **دمج integrate/genspark-field-dedup → main** (الخيار C: 12 commit، 34 ملف، +3390 سطر) | Z.ai |
| `03d5f94` | 2026-07-14 | استعادة gradio_full_hitl.py + تصحيح كل المراجع (الخيار C) | Z.ai |
| `8645576` | 2026-07-14 | LLM postprocess pipeline + active learning loop + Git LFS | Z.ai |
| `973979c` | 2026-07-14 | runtime-aware EngineRegistry + Qdrant smoke test | Z.ai |
| `881e63e` | 2026-07-14 | إصلاح STATE_OF_TRUTH + lazy-import packages/vision | Z.ai |
| `6402fab` | 2026-07-14 | GRADIO_HITL_CHANGES_REVIEW للمراجعة | Z.ai |
| `bca55d4` | 2026-07-14 | تحديث STATE_OF_TRUTH بـ commit hashes الفعلية | Z.ai |
| `5dcdf9b` | 2026-07-14 | نقل qdrant-client من core لاختياري [search] | Z.ai |
| `c440683` | 2026-07-14 | اختبار + إصلاح: field-aware dedup يحل حالة الحافة | Z.ai |
| `25171e8` | 2026-07-14 | إصلاح: إنشاء scanner_fixer_wrapper.py المفقود | Z.ai |
| `993e0bf` | 2026-07-14 | تنظيف pyproject/requirements/docs/tests | Z.ai |
| `e7c662b` | 2026-07-13 | تحديث routing بـ Qwen/QARI/Nougat + fallback chains | Z.ai |
| `5b00450` | 2026-07-13 | دمج rtl_utils + field_extractor + compare_raw_vs_printed + weighted dedup + Qdrant search + advanced_review_app | Z.ai |
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

## ملخص دمج integrate/genspark-field-dedup (2026-07-14)

### ما دُمج (الوحدات المستقلة القيّمة):
| الوحدة | الملفات | الوظيفة |
|--------|---------|---------|
| RTL fixing | `src/ocr/rtl_utils.py` | إصلاح اتجاه النص العربي بعد OCR |
| Field extraction | `src/ocr/field_extractor.py` | استخراج الحقول الطبية (اسم المريض، التاريخ، التشخيص...) |
| Deduplication | `src/ocr/deduplication.py` | WeightedMedicalDeduplicator بأوزان حقلية |
| Engine registry | `packages/core/engine_registry.py` | 7 adapters + runtime probe + filter_by_ram |
| Engine router update | `packages/core/engine_router.py` | Qwen/QARI/Nougat routing + registry integration |
| LLM postprocess | `src/llm/postprocess_pipeline.py` | خط أنابيب ما بعد OCR (Gemma/Jais) |
| Active learning | `packages/ai/active_learning_loop.py` | حلقة تعلم فعال من تصحيحات البشر |
| Vision lazy imports | `packages/vision/__init__.py` | __getattr__ بدل 14 eager import |
| Preprocessing | `omni_medical_suite/preprocessing/` | scanner_fixer_wrapper + compare_raw_vs_printed |
| Git LFS | `.gitattributes` | تتبع الصور الطبية والبيانات الكبيرة |
| Tests | 7 ملفات اختبار جديدة | 42 اختبار (RTL, field, dedup, router, postprocess, AL, Qdrant) |

### ما لم يُدمَج / بقي كما كان:
- `app/gradio_full_hitl.py` — 944 سطر، 10 وظائف — **لم يتغير** (الخيار C)

### ما بقي "تجريبيًا منفصلًا":
- `app/advanced_review_app.py` — تطبيق بـ 3 تبويبات (Compare/Search/Review) — غير مُعتمَد للإنتاج

### قرارات معلَّقة تحتاج مراجعة بشرية

1. **124 ملفاً مختلفاً جزئياً** — انظر `DUPLICATE_VERIFICATION_REPORT.md` قسم "مختلف جزئياً". يحتاج قراراً بشرياً لكل ملف: هل النسخة في packages/ الأساسية أم النسخة في الحزم المدمجة أحدث؟

2. **18 تطبيق Gradio معلّق** — انظر `GRADIO_APPS_DECISION.md` للتوصيات المجمّعة (5 مجموعات A-E).

3. **ruff auto-fix دفعة واحدة على 12,846 مشكلة** — تم تنفيذها بلا مراجعة بشرية فردية. قد تحتوي تغييرات سلوكية غير مقصودة.

4. **3 أخطاء منطقية في tmx_processor.py** — تم توثيق الأسباب الجذرية في PYTEST_REPORT.md:
   - `test_detect_medical_category_fracture`: regex `CT` بدون حد كلمة يطابق "ct" داخل "fracture"
   - `test_detect_medical_category_generic`: regex `test` بدون حد كلمة يطابق الكلمة العادية "test"
   - `test_export_to_json`: `{k: row[k] for k in row}` على sqlite3.Row يعطي قيماً لا أسماء أعمدة

5. **فشل اختبارات بسبب تبعيات ثقيلة** — `packages/vision/__init__.py` يستورد 14 وحدة بـ eager imports بما فيها `batch_ocr` (يتطلب torch) و `medical_ocr_gradio` (يتطلب gradio). تم تحويلها إلى lazy imports في commit لاحق. الاختبارات المعنية: `test_arabic_rtl.py` وغيرها.

6. **~50 ملف requirements*.txt قديمة** — تم تقليل الجذر (`requirements-dev.txt`) إلى compatibility wrapper، لكن بقية الملفات القديمة ما زالت بحاجة ترحيل تدريجي إلى `pyproject.toml` extras. انظر `docs/DEPENDENCY_STRATEGY.md`.

7. **المراجع المكسورة في المستودعات البعيدة** — تم إصلاح المراجع المحلية فقط. repos البعيدة (repo-sync-toolkit، medical-ocr-trainer-hf، intelli-file-manager، sync-github) تحتاج إصلاحاً مباشراً على GitHub.
## ⚠️ قاعدة صارمة: فحص استيراد إلزامي بعد أي حذف جماعي

**منذ: 2026-07-11 (بعد اكتشاف 73 استيرادًا مكسورًا بسبب commit 93185df)**

> **أي حذف جماعي لملفات "مكررة" (MD5 أو غير ذلك) يجب أن يتبعه فورًا — في نفس commit — تشغيل فعلي لاختبار استيراد كل حزمة متأثرة.** المطابقة الحرفية للمحتوى (MD5) لا تعني أن الاستيراد آمن — الملف قد يكون مطلوبًا محليًا بواسطة `__init__.py` في مسار مختلف عن المسار الذي احتُفظ بالنسخة الأساسية فيه.

### سكربت الفحص الإلزامي
بعد أي حذف جماعي، نفّذ:
```python
import os, re
PACKAGES = ['packages/handwriting', 'packages/file_processor', 'packages/omnifile']
for pkg in PACKAGES:
    modules_dir = os.path.join(pkg, 'modules')
    if not os.path.isdir(modules_dir): continue
    for mod in sorted(os.listdir(modules_dir)):
        mod_path = os.path.join(modules_dir, mod)
        if not os.path.isdir(mod_path): continue
        init = os.path.join(mod_path, '__init__.py')
        if not os.path.exists(init): continue
        with open(init) as f: content = f.read()
        for m in re.finditer(r'from modules\.(\w+)\.(\w+) import', content):
            fpath = os.path.join(modules_dir, m.group(1), m.group(2) + '.py')
            if not os.path.exists(fpath):
                print(f'BROKEN: {pkg}/modules/{mod}/__init__.py -> {fpath}')
```
النتيجة يجب أن تكون دائمًا: **صفر**.

## 🔶 سؤال معماري مفتوح (يحتاج قرار Malek)

الوضع الحالي: `packages/handwriting/modules/vision/__init__.py` يستورد `from modules.vision.ocr_engine import OCREngine` — أي يتوقع `ocr_engine.py` محليًا داخل شجرة handwriting. لكن النسخة "الأساسية" المفردة موجودة في `packages/vision/ocr_engine.py`. الحل الفوري كان نسخ الملف محليًا (73+3 ملف).

**السؤال:** هل التصميم الصحيح طويل المدى هو:
- **(أ)** الاحتفاظ بنسخ محلية في كل حزمة مدمجة (الحل الحالي — بسيط لكنه يُضعِف التناسق)؟
- **(ب)** تعديل كل `__init__.py` للاستيراد من الموقع المركزي `packages/vision/ocr_engine.py` بدل النسخ المحلية (نظيف معماريًا لكنه يحتاج تعديل مئات الاستيرادات وإعادة اختبار شاملة)؟
- **(ج)** إزالة الحزم المدمجة بالكامل واستبدالها بـ symlinks أو إعادة توجيه imports؟

هذا قرار معماري لـMalek — الإصلاح الحالي (أ) هو الحل الآمن الفوري فقط.
