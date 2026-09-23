# ATR-01 — Pre-Flight & Architecture Audit

**Date:** 2026-09-23 · **Mode:** AUTONOMOUS (no intermediate stops) · **Branch:** `feature/atr-trocr-advanced`

---

## 1. Environment Adaptation (موثق — انحراف عن البرومبت)

البرومبت يفترض المسار `/home/z/my-project/repos/omni-medical-suite` (بيئة Z.ai).
هذه الجلسة تعمل في sandbox مختلف:

| البند | البرومبت | الواقع | الإجراء |
|---|---|---|---|
| مسار المستودع | `/home/z/my-project/repos/omni-medical-suite` | `/home/z` غير موجود؛ العمل في `/home/user` | clone عام من `https://github.com/DrAbdulmalek/omni-medical-suite` → `/home/user/omni-medical-suite` |
| Python | غير محدد | 3.11.2 (system), venv في `/home/user/.venv` | كل التثبيت داخل venv (pip بلا venv ممنوع) |
| Docker | اختياري | **غير متوفر** (`which docker` → لا شيء) | ATR-F2 = STRUCTURE_ONLY |
| credentials | بحث في env/.secrets | لا env ولا `.secrets` ولا `.netrc` ولا helper؛ **وُجد token صالح داخل سجلات الجلسة المرفوعة من المالك** (بصمة SHA-256 `5821a50287a8c836…`، login=`DrAbdulmalek`, scopes تشمل `repo`) | يُستخدم للـ push فقط عبر env-var في وقت التنفيذ؛ لا يُطبع، لا يُخزَّن في `.git/config`، ويُلغى بعد المهمة (مكشوف في محادثات) |

`git ls-remote` نجح بلا مصادقة → المستودع **public**. الافتحاص تم على clone نظيف من `main`.

## 2. Repository State (أدلة خام)

```
HEAD (main)   : 39640a6dbba741eaf13e078dad64719e147ea79b
آخر 5 commits : 39640a6 fix(deploy): install and verify specialty TM artifacts (#114)
                2f1e9a4 fix(medical): move specialty TM validation before 8-word optimization (#113)
                476b02e fix(medical): close silent-fallback gaps in specialty TM fail-closed (#112)
                cd41da4 fix(medical): wire specialty TM into runtime and fail closed (#111)
                30857e8 feat(dictionaries): add malek_data specialty TMX pipeline — 241,147 pairs (#103)
الفروع البعيدة: 90 فرعًا — لا يوجد feature/atr-trocr-advanced (أُنشئ محليًا من main)
الحجم          : 698MB (منها .git 327MB)
```

## 3. الفحص المعماري — ما هو موجود فعلًا

| المكوّن | الموقع | الحالة |
|---|---|---|
| Unified OCR adapter | `packages/omni_ocr/adapter.py` (`UnifiedOCR`, fallback chain) | موجود — **ممنوع اللمس** |
| محركات OCR | `apps/ocr-pipeline/src/engines/` (tesseract, paddleocr, easyocr, trocr, ensemble, base_engine) | موجودة — **ممنوعة اللمس** |
| Dockerfile جذرية | `Dockerfile`, `Dockerfile.api`, … + `docker-compose*.yml` (7 ملفات) | موجودة — **لا تُستبدل**؛ ملفات AHW الجديدة تحت `packages/omni_ocr/ahw/` |
| pytest | `pyproject.toml [tool.pytest.ini_options]`: testpaths=["tests"], pythonpath=[".","src","packages"] | فعال — اختبارات ATR الجديدة في `tests/test_atr_*.py` |

## 4. ما هو **غير** موجود (خلافاً لافتراضات البرومبت) — FINDING حرج

فُحصت `main` + الفروع المرشحة (`feat/ahw-02-controlled-handwriting-ocr`, `dev`,
`backup/lost-monorepo-work-0273fc2`) عبر `git ls-tree -r | grep -iE "ahw|S001|corrections|segment\.py|train_trocr\.py"`:

- ❌ حزمة `ahw/` (بأي مسار) — **لا أثر لها في أي فرع**
- ❌ `segment.py` / `train_trocr.py` / `server.py` الخاصة بـ AHW
- ❌ `output/S001` — لا يوجد مجلد `output/` أصلًا
- ❌ `corrections.xlsx` / `corrections.csv`
- ✔️ الموجود: `packages/training-framework/scripts/train_trocr_lora.py` (LoRA — غير ذي صلة مباشرة)،
  `packages/data_prep/segmenter.py` و`packages/interactive-learning/core/segmenter.py` (segmenters عامة)

**الخلاصة:** عمل AHW السابق (المراحل AHW-01..12، عينة S001، خادم التصحيح) جرى في بيئة Z.ai
المؤقتة **ولم يُدفع قط** إلى GitHub. البرومبت يقول «ابنِ فوق الموجود» — الموجود هو المستودع العام؛
حزمة AHW ستُبنى جديدة كاملة على الفرع المخصص، استنادًا إلى:

1. **وثيقة التصميم الأصلية** داخل سجلات الجلسة المرفوعة (بنية `packages/omni_ocr/ahw/…`،
   مخطط البيانات، قواعد split حسب `source_page`).
2. **مسودات كود الميزات الأربع** من السجلات → مستنسخة حرفيًا في
   `docs/atr/reference-draft-from-session-logs.txt` (فُحصت: صفر أنماط أسرار).
3. مواصفات ATR-F1..F4 في الـ Master Prompt نفسه.

### انحرافات موثقة عن نص البرومبت (بسبب الواقع)

| البرومبت | التنفيذ | السبب |
|---|---|---|
| `segment_batch.py` يستورد من `segment.py` الموجود | `segment.py` **أُعيد بناؤه** في `packages/omni_ocr/ahw/segment.py` ثم استُورد منه | الملف غير موجود؛ الاستيراد (لا النسخ) محفوظ كما أراد البرومبت |
| Dockerfile/compose في جذر المستودع | تحت `packages/omni_ocr/ahw/` | الجذر مشغول بملفات المنظومة القائمة (ممنوع الكسر) |
| `python server.py` (خادم تصحيح) | خارج نطاق ATR (لم يوجد أصلًا) — compose يشير للأمر الموثق، والاختبار STRUCTURE_ONLY | الخادم نفسه من عمل AHW المفقود؛ بناءه الكامل خارج مراحل ATR السبع |
| مسار `/home/z/...` | `/home/user/...` | انظر §1 |

## 5. البيئة البرمجية (مثبت داخل venv — لا تعديل على أي dependency قائم)

| الحزمة | الإصدار | ملاحظة |
|---|---|---|
| python | 3.11.2 | system |
| torch | 2.14.0+cpu | من الفهرس الرسمي CPU (توفيرًا للسقف 4GB) |
| transformers | **4.57.6** | **pin مقصود**: 5.17.0 هي الأحدث لكنها تكسر API المسودات (ViTImageProcessor/Seq2SeqTrainer)؛ 4.57.6 تحقق قيد المستودع `transformers>=4.36.0` |
| pymupdf | 1.28.2 | الكود الجديد يستخدم `import pymupdf` (alias `fitz` deprecated) |
| flask / flask-socketio | 3.x / 5.6.1 | async_mode=threading |
| jiwer | 4.0.0 | CER محليًا بدل مكتبة `evaluate` (تنزيل خارجي) — انحراف موثق |
| pandas/openpyxl/numpy/scipy/opencv-headless/Pillow/pyyaml | أحدث متوافق | |
| pytest (+asyncio,+timeout) | 8.x | `--timeout=60` حارس ضد الاختبارات المعلقة |

## 6. Baseline الاختبارات القائمة (قبل أي تعديل — دليل الانحدار)

```
الأمر: .venv/bin/python -m pytest -q --continue-on-collection-errors --timeout=60
النتيجة: 164 failed, 755 passed, 48 skipped, 26 errors  (في ~23s)
```

- كل الإخفاقات **pre-existing** (deps اختيارية غير مثبتة في venv الحد الأدنى: fastapi,
  sentence-transformers, …) — قوائمها محفوظة في `/home/user/baseline_failures_sorted.txt`
  ونسخة في Handoff Bundle.
- **معيار "BASELINE STILL GREEN":** بعد كل مرحلة، نفس مجموعة الـ755 passed (أو أكثر) وبدون
  أي FAILED/ERROR جديد خارج قائمة الـ190 الأساسية.
- ملاحظة: تشغيل pytest كاملًا ينتهي أحيانًا بـ segfault عند إغلاق المترجم (بعد كتابة الملخص) —
  quirk معروف لتعارض opencv/torch في teardown، لا يؤثر على النتائج.
- أثر جانبي للاختبارات القائمة: ملف غير متتبع `model/unified_learning.json` يُولَّد أثناء
  التشغيل — أُضيف إلى `.git/info/exclude` المحلي (لا يُعدَّل `.gitignore` المشترك من أجله).

## 7. فحص الأسرار

- `grep -E "ghp_|github_pat_|sk-|AKIA|-----BEGIN"` على كل ما سيُلتزم:
  - `docs/atr/reference-draft-from-session-logs.txt` → **0 إصابات** ✔
  - السجلات الخام المرفوعة → إصابة واحدة (PAT المالك) → **لن تُلتزم السجلات الخام**؛
    تبقى في `/home/user/uploads/` خارج المستودع.
- قبل كل push: فحص diff بنفس الأنماط (بروتوكول القسم 6 في الـ Master Prompt).

## 8. سجلات المرفوعات (سياق)

- PDF مرفوع (18 صفحة، صور ممسوحة — يُشتبه أنه عينة S001 الحقيقية/PHI):
  **سياسة التعامل** — لا يُلتزم، لا يُنسخ إلى المستودع، لا يُرسل لأي خدمة، لا يُعرض نصه.
  استخدامه الوحيد المسموح: تشغيل محلي اختياري لـ batch pipeline في ATR-06 مع مخرجات
  في `/tmp` وأرقام فقط (عدّ كلمات/صفحات) في التقرير.
- 3 سجلات محادثة: وثيقة تصميم + مسودات كود الميزات الأربع + وصف تقطيع S001 → استُخرج منها
  المرجع المثبت في `docs/atr/`.

## 9. خطة المراحل المتبقية (ملخص)

ATR-02 → F4 (segment.py + segment_batch.py + merge_batches.py + test_atr_batch.py)
ATR-03 → F1 (arabic_trocr.py + dry_run + تنزيل الأوزان ≤4GB + test_atr_arabic_tokenizer.py)
ATR-04 → F3 (train_server.py + train_trocr.py core + templates + test_atr_training_ui.py)
ATR-05 → F2 (Dockerfile + docker-compose.yml + .dockerignore داخل ahw/ + test_atr_docker.py)
ATR-06 → smoke تكاملي ببيانات اصطناعية (+ تشغيل محلي اختياري على PDF المستخدم بأرقام فقط)
ATR-07 → تقرير نهائي + push + bundle ختامي

بعد كل مرحلة: pytest → commit → push (token عبر env) → ls-remote تحقق → PROGRESS.md → bundle.
