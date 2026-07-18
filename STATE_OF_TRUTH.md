# STATE_OF_TRUTH.md — آخر تحديث: 2026-07-19

> **كل نموذج AI (Z.ai، Claude، Mistral، Grok، أو أي آخر) يجب أن يقرأ هذا الملف أولاً قبل أي تعديل على هذا المستودع، ويُحدِّثه بعد كل تغيير جوهري.**

---

## حالة الدمج — Merge Status

| الفرع | الحالة | تفاصيل |
|---|---|---|
| `cleanup/final-pending-items` | ✅ مُدمج في main | merge commit `46fd895` |
| `feature/desktop-scanner-unify-package` | ✅ مُدمج في main | scanner_fixer integration + PyInstaller + QShortcut fix |
| `backup/lost-monorepo-work-0273fc2` | ✅ فرع احتياطي | 275 التزام — يتطابق مع main HEAD |
| `backup/current-main-dictionaries` | ✅ فرع احتياطي | القواميس المنفصلة (قُلبت إلى omni-medical-dictionaries) |
| `fix/pdf-ocr-processor-paddle-device` | ✅ مُدمج في main | merge `6d46e62` — PaddleOCR `device='cpu'` (PaddleOCR 3.x compat) |
| `unify/pdf-ocr-processor-engine-registry` | ✅ مُدمج في main | merge `5f979fd` — `_run_ocr()` via `EngineRegistry` |
| `refactor/scripts-pdf-ocr-thin-wrapper` | ✅ مُدمج في main | merge `3af9b9a` — `scripts/pdf_ocr_processor.py` thin wrapper |
| `test/pdf-ocr-processor-suite` | ✅ مُدمج في main | merge `38fdd60` — 15/15 tests pass |
| `chore/unify-mobile-and-learning` | ✅ مُدمج في main | merge `8b06c41` — 25 duplicate files → `packages/core/mobile/` |
| `feat/mobile-server-wire-app-services` | ✅ مُدمج في main | merge `6f40d4e` — server.py shares `app.services.*` |
| `docs/mobile-learning-loop` | ✅ مُدمج في main | merge `14f1b94` — `docs/MOBILE_LEARNING_LOOP.md` |
| `feat/activate-pwa-docker` | ✅ مُدمج في main | merge `1831b27` (final HEAD) — PWA + Dockerfile.mobile |
| `feature/mobile-learning-loop` (umbrella) | 🗑️ محذوف | لم يعد ضروريًا بعد الدمج المباشر للثمانية |

**آخر HEAD على `main`:** `1831b27` (Merge feat/activate-pwa-docker) — `2026-07-19`
آخر تحقق: `2026-07-19` — صفر كسر استيراد مُستحدَث (تفاصيل أدناه)، `app.gradio_full_hitl` يستورد بنجاح، خادم الجوال يمر بالاختبار الحيّ (counter incremented 3 → 4).

---

## جولة الدمج الكبيرة 2026-07-19 — pdf_ocr_processor + Mobile Learning Loop

### النطاق
دمج 8 فروع متسلسلًا في `main` بترتيب الاعتماد المنطقي (عمل الجوال مبني على عمل pdf_ocr_processor). كل دمج بـ`--no-ff` لضمان commit منفصل لكل فرع في تاريخ `main`.

### التحقق بعد كل دمج (8/8 نجح)

| # | الفرع | التحقق المباشر | النتيجة |
|---|---|---|---|
| 1 | `fix/pdf-ocr-processor-paddle-device` | `from scanner_fixer.pdf_ocr_processor import PDFOCRProcessor` | OK-1 ✅ |
| 2 | `unify/pdf-ocr-processor-engine-registry` | نفس الاستيراد بعد توحيد `EngineRegistry` | OK-2 ✅ |
| 3 | `refactor/scripts-pdf-ocr-thin-wrapper` | `python3 scripts/pdf_ocr_processor.py --help` | OK-3 ✅ |
| 4 | `test/pdf-ocr-processor-suite` | `pytest packages/scanner_fixer/tests/test_pdf_ocr_processor.py -v` | 15/15 passed ✅ |
| 5 | `chore/unify-mobile-and-learning` | فحص استيراد شامل (25 ملف محذوف) | 1 fix (`packages.core.mobile` created)، 0 regression ✅ |
| 6 | `feat/mobile-server-wire-app-services` | فحص استيراد شامل + `import packages.core.mobile.server` | 1 fix (`packages.core.mobile.server` يعمل عبر `app.services.*`)، 0 regression ✅ |
| 7 | `docs/mobile-learning-loop` | فحص استيراد شامل | 0 fix، 0 regression ✅ |
| 8 | `feat/activate-pwa-docker` | فحص استيراد شامل | 0 fix، 0 regression ✅ |

### التحقق النهائي الشامل (post-merge-8)

**فحص الاستيراد الشامل** (`/home/z/my-project/scripts/comprehensive_import_check.py`):
- ملفات `__init__.py` مُكتشفة في `packages/` و`app/`: شامل
- الوحدات المُختبرة: شامل (curated + discovered)
- **النتيجة: 95 فشل، 0 مُستحدَث** (كلها موجودة سابقًا على `origin/main` — `torch`/`sqlalchemy`/`streamlit` غير منصّبة + 50 استيراد intra-package `modules.` لكل الحزم القديمة)
- فرق الـSHA-failures بين `origin/main` (pre-merge) و`main` (post-merge-8): **0 جديد، 0 محذوف**

**`app.gradio_full_hitl` استيراد حيّ**: ✅ يعمل (`IMPORT_OK`)
- المكونات المحمَّلة: OCR engines (Tesseract OK، PaddleOCR skip — paddleocr غير منصّب)، HybridSpellChecker v7.1، ImagePreprocessor، HF Dataset save (مُعطّل لعدم توفر HF libs)
- التحذير الوحيد: `JWT_SECRET_KEY is using default value` — إعداد إنتاجي، لا يؤثر على الاستيراد

**`pytest` الكامل** (`--ignore=tests/test_build_training_data.py --ignore=tests/test_mobile_review_server.py`):
- **Baseline (`origin/main`):** 85 failed, 440 passed, 46 skipped, 4 errors
- **Post-merge (`main` @ `1831b27`):** 85 failed, 440 passed, 46 skipped, 4 errors
- **الفرق:** 0 — نفس أسماء الاختبارات الفاشلة byte-for-byte (verified via `diff` exit 0)
- الملفان المُتجاهلان: لديهما أخطاء استيراد موجودة سابقًا (`tools.build_training_data` غير موجود، `from mobile_review import server` لا يعمل من `origin/main` نفسه قبل هذه الجولة)

**الاختبار الحيّ لخادم الجوال** (`/home/z/my-project/scripts/live_mobile_server_test.py`):
- بدء Flask server على port عشوائي → `/health` 200 (`app_services_loaded: true`, `learning_loop_loaded: true`)
- GET `/stats` (initial) → `active_learning.total_corrections: 3`
- POST `/save` بقائمة تصحيح واحد (Shape A) → 200، استجابة: `corrections_dict_added: 1`, `word_trainer_added: 1`, `active_learning_added: 1` — كل ثلاثة sinks في learning loop اشتعلت
- GET `/stats` (after) → `active_learning.total_corrections: 4`
- **النتيجة: counter ازداد 3 → 4 ✅** — learning loop حيّ ويعمل فعليًا

### بقايا معروفة (pre-existing — ليست من هذه الجولة)
- 50 استيراد `from modules.X import Y` داخل الحزم القديمة (omnifile, handwriting, training, etc.) — نمط استيراد intra-package قديم، لا يكسر `app.gradio_full_hitl`
- 11 استيراد يتطلب `torch` (غير منصّب في بيئة Z.ai)
- 8 استيراد `from engine import X` (نمط intra-package قديم)
- 3 استيراد يتطلب `sqlalchemy` (لتطبيقات الـAPI غير الافتراضية)
- `tests/test_build_training_data.py` + `tests/test_mobile_review_server.py` — أخطاء collection موجودة قبل الجولة

---

---

## التطبيقات الرسمية

### 1. `app/gradio_full_hitl.py` — HITL الإنتاج
944 سطر. 10 وظائف كاملة: رفع صورة → OCR ensemble، تصحيح HybridSpellChecker، تدقيق Jais LLM، NER طبي، حفظ HF Dataset، تحديث القاموس، إعادة تدريب Jais NER، ترجمة طبية (4 اتجاهات)، حاسبة CER/WER، Before/After comparison.

### 2. `app/advanced_review_app.py` — Advanced Review (محدّث)
6 تبويبات متكاملة مع scanner_fixer:
- **🔬 معالج الصور**: Before/After لصورة واحدة عبر scanner_fixer pipeline (deskew + crop + enhance + rotate)
- **📦 معالجة دفعية**: Batch processing لدليل كامل + ZIP + PDF + معاينة عشوائية
- **🔍 كشف التكرار**: phash dedup detection + تقرير CSV
- **⚖️ مقارنة**: مقارنة نص خام/معالج/مرجعي
- **🔎 بحث**: Qdrant semantic search + local fallback
- **📋 مراجعة**: RTL fix + field extraction + engine routing

يستخدم `gr.State` فقط (لا `self.`). يدعم Manjaro (poppler + tesseract).

### 3. `packages/desktop/medical_doc_gui_final.py` — Desktop (PySide6)
3231 سطر. تكامل scanner_fixer مع fallback:
- `auto_detect_skew()`: scanner_fixer.deskew أولاً، ثم projection profile
- `smart_auto_crop()`: scanner_fixer.crop أولاً، ثم two-phase method
- `_do_full_normalize()`: تنسيق كامل عبر scanner_fixer.normalize
- `_do_dedup()`: كشف مكررات عبر scanner_fixer.dedup phash
- QShortcut مُصلح (من QtGui بدل QtWidgets — PySide6 6.11+)

---

## الحزم النشطة في packages/

| الحزمة | الوظيفة |
|---|---|
| `core` | المحرك الأساسي: engine_router (محدّث بـ Qwen/QARI/Nougat), **engine_registry** (runtime-aware availability checks + healthcheck), corrections_manager, base_db, **mobile/server.py** (Flask + PWA + Docker — يشارك `app.services.*` ويغذّي learning loop) |
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
| `data_prep` | تجهيز البيانات (كان data-prep، أُعيدت تسميته) |
| `segmentation` | تقسيم المستندات |
| `training` / `training-framework` / `training_hub` | أنابيب تدريب النماذج |
| `learning` / `interactive-learning` | تعلم تفاعلي |
| `benchmark_core` | إطار قياس الأداء |
| `ocr_postprocess` | معالجة ما بعد OCR |
| `omni_ocr` | OCR شامل (كان omni-ocr، أُعيدت تسميته) |
| `scanner_fixer` | إصلاح الصور الممسوحة: deskew, crop, normalize, dedup, enhance, batch, pipeline |
| `desktop` | تطبيق سطح المكتب PySide6 + PyInstaller + AppImage |
| `config` | إعدادات المشروع |
| `gt_core` | بيانات الحقيقة الأرضية (ground truth) |
| `doc_processor` | معالج الوثائق (كان doc-processor، أُعيدت تسميته) |

---

## الميزات الجاهزة — Feature Checklist

| الميزة | الحالة | التفاصيل |
|---|---|---|
| scanner_fixer integration (Gradio) | ✅ جاهز | Before/After + Batch + PDF + ZIP + Dedup + Random Preview |
| scanner_fixer integration (Desktop) | ✅ جاهز | deskew + crop + normalize + dedup مع fallback |
| PyInstaller ELF build | ✅ جاهز | `packages/desktop/build.sh` → `dist/medical-doc-processor` |
| AppImage build | ✅ جاهز | `packages/desktop/build_appimage.sh` → `MedicalDocProcessor.AppImage` |
| QShortcut fix (PySide6 6.11+) | ✅ جاهز | منقول من QtWidgets إلى QtGui |
| Import cleanup (hyphen→underscore) | ✅ جاهز | data-prep→data_prep, omni-ocr→omni_ocr, doc-processor→doc_processor |
| Git history restored | ✅ جاهز | 275 التزام محفوظ، backup branches على remote |
| Dictionary separation | ✅ جاهز | omni-medical-dictionaries مستودع منفصل |

---

## أوامر التشغيل على مانجارو

```bash
# ═══ التثبيت ═══
sudo pacman -S poppler tesseract tesseract-data-ara python-pip
pip install -e packages/scanner_fixer
pip install -r packages/desktop/requirements.txt

# ═══ تشغيل Gradio ═══
python app/advanced_review_app.py          # http://localhost:7860

# ═══ تشغيل Desktop ═══
python packages/desktop/medical_doc_gui_final.py

# ═══ بناء ELF ═══
cd packages/desktop && bash build.sh       # → dist/medical-doc-processor

# ═══ بناء AppImage ═══
cd packages/desktop && bash build_appimage.sh  # → MedicalDocProcessor-1.0.0-x86_64.AppImage

# ═══ الاختبارات ═══
pytest tests/ -x
```

---

## فحص الاستيراد — Import Audit

```
تاريخ الفحص: 2026-07-19 (post-merge-8 على main @ 1831b27)
منهجية الفحص: /home/z/my-project/scripts/comprehensive_import_check.py
  - مسح كل __init__.py في packages/ و app/
  - استيراد فعلي لكل وحدة عبر importlib.import_module
  - مقارنة contre baseline (origin/main @ 46296c3 قبل الجولة)
ملفات Python المفحوصة: 1486+
الوحدات المُختبرة: شامل (__init__.py المُكتشفة + curated CRITICAL_MODULES)

النتيجة:
  - baseline failures (pre-merge): 97
  - post-merge-8 failures:         95  (تحسّن بصافي وحدتين)
  - وحدات أُصلِحت بالجولة: 2 (packages.core.mobile, packages.core.mobile.server)
  - وحدات كُسِرت بالجولة: 0 ✅

الفشل المتبقي (pre-existing — ليس من هذه الجولة):
  - 50× from modules.X import Y (intra-package قديم في omnifile/handwriting/training)
  - 11× requires torch (غير منصّب)
  -  8× from engine import X (intra-package قديم)
  -  3× requires sqlalchemy (غير منصّب)
  - 23× متفرقات (benchmarks.structure, tools.build_training_data, etc.)

استنتاج: صفر كسر استيراد مُستحدَث من جولة الدمج هذه.
```

---

> **للتاريخ الكامل للدمجات والتنظيف:** انظر `MERGE_HISTORY.md`
> **للمشاكل المفتوحة والقرارات المعلقة:** انظر `OPEN_ISSUES.md`
