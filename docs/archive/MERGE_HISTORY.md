# سجل الدمج والتغييرات الهيكلية — Merge History

آخر تحديث: 2026-07-14

---

## آخر 20 تغييرًا جوهريًا

| Hash | التاريخ | الوصف | المنفِّذ |
|---|---|---|---|
| `46fd895` | 2026-07-14 | **دمج cleanup/final-pending-items → main** (إصلاح 3 استيراد مكسور + تنظيف 8360 سطر) | Z.ai |
| `a35eaa1` | 2026-07-14 | إصلاح: استعادة 3 ملفات محذوفة خطأ (table_extractor, code_protector, file_scanner) | Z.ai |
| `c3923e8` | 2026-07-14 | Handwriting Trainer app + training data samples (10 pages, 3 languages) | Z.ai |
| `12b6cd2` | 2026-07-14 | DeduplicationPipeline (RTL→Field→Dedup + confidence scoring) | Z.ai |
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

---

## دمج integrate/genspark-field-dedup (2026-07-14)

فرع `integrate/genspark-field-dedup` دُمج لـ `main` بـ `--no-ff` في commit `d8c854d`. القرار: **الخيار C** — `gradio_full_hitl.py` لم يُستبدَل.

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
| Vision lazy imports | `packages/vision/__init__.py` | `__getattr__` بدل 14 eager import |
| Preprocessing | `omni_medical_suite/preprocessing/` | scanner_fixer_wrapper + compare_raw_vs_printed |
| Git LFS | `.gitattributes` | تتبع الصور الطبية والبيانات الكبيرة |
| Tests | 7 ملفات اختبار جديدة | 42 اختبار (RTL, field, dedup, router, postprocess, AL, Qdrant) |

### ما لم يُدمَج / بقي كما كان:
- `app/gradio_full_hitl.py` — 944 سطر، 10 وظائف — **لم يتغير** (الخيار C)

### ما بقي "تجريبيًا منفصلًا":
- `app/advanced_review_app.py` — تطبيق بـ 3 تبويبات (Compare/Search/Review) — غير مُعتمَد للإنتاج

---

## تنظيف تطبيقات Gradio: من 43 إلى 7

| القرار | العدد | التفاصيل |
|--------|-------|---------|
| KEEP (إنتاجي) | 7 | gradio_full_hitl.py, advanced_review_app.py, hf-space/app.py + 4 أدوات مستقلة |
| DELETE | 26 | نسخ مكررة + إيجابيات كاذبة |
| ARCHIVE | 8 | نقل لـ research/prototypes/ (بما فيها hf_app.py الجديد) |
| INTEGRATED | 2 | batch_correction_ui.py + dual_ocr_interface.py (مصدر في gradio_extended.py) |
| STILL PENDING | 0 | جميع الـ 43 ملف حُسم |

انظر `GRADIO_APPS_DECISION.md` للجدول الكامل بالأدلة.

---

## تنظيف التكرارات الهيكلية في الحزم (المرحلة 1–3)

**تقارير المرحلة 1:** `DUPLICATE_VERIFICATION_REPORT.md` — 85 متطابق، 124 مختلف جزئياً، 122 بالاسم فقط.

### حزم مُدمَجة تحتوي تكراراً هيكلياً (تم التنظيف الجزئي):

| الحزمة | الإجراء | الباقي |
|--------|---------|--------|
| `packages/file_processor/` | حُذف `_dev_references/` (200MB) + 85 ملف مكرر 100% | تكرار جزئي يحتاج مراجعة |
| `packages/handwriting/` | نسخ Gradio حُذفت | تكرار جزئي لمفات Python |
| `packages/omnifile/` | نسخ Gradio حُذفت | تكرار جزئي |
| `packages/doc-processor/` / `packages/doc_processor/` | — | نسخ من core/ (تكرار جزئي) |
| `apps/handwriting-demo/variants/handwriting-ocr/` | نسخ Gradio حُذفت | — |
| `hf-space/packages/` | ملفات مكررة حُذفت (scanner_fixer, vision, core, nlp) | — |
| `packages/bilingual/` | — | نسخ من nlp/ (تكرار جزئي) |

### تنظيف شامل (المرحلة 3) — commit `f8dab72` (2026-07-11):
- حذف 200MB+ من الملفات المكررة
- حذف 85 ملف مكرر بنسبة 100%
- حذف 52 workflow GitHub Actions قديمة
- حذف 24 تطبيق Gradio مكرر
- إصلاح ~105 مرجع استيراد مكسور

---

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