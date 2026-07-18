# STATE_OF_TRUTH.md — آخر تحديث: 2026-07-18

> **كل نموذج AI (Z.ai، Claude، Mistral، Grok، أو أي آخر) يجب أن يقرأ هذا الملف أولاً قبل أي تعديل على هذا المستودع، ويُحدِّثه بعد كل تغيير جوهري.**

---

## حالة الدمج — Merge Status

| الفرع | الحالة | تفاصيل |
|---|---|---|
| `cleanup/final-pending-items` | ✅ مُدمج في main | merge commit `46fd895` |
| `feature/desktop-scanner-unify-package` | ✅ مُدمج في main | scanner_fixer integration + PyInstaller + QShortcut fix |
| `backup/lost-monorepo-work-0273fc2` | ✅ فرع احتياطي | 275 التزام — يتطابق مع main HEAD |
| `backup/current-main-dictionaries` | ✅ فرع احتياطي | القواميس المنفصلة (قُلبت إلى omni-medical-dictionaries) |

آخر تحقق: `2026-07-18` — صفر كسر استيراد في `packages.*` (1486 ملف فُحص)، `0273fc2` موجود.

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
تاريخ الفحص: 2026-07-18
ملفات Python المفحوصة: 1486
استيرادات packages.* مكسورة: 0 ✅
استيرادات hyphenated (data-prep, omni-ocr): 0 ✅ (أُعيدت تسميتها)
ملاحظة: 202 استيراد src.* في التطبيقات الفرعية — استيرادات داخلية تعمل من مجلد التطبيق
```

---

> **للتاريخ الكامل للدمجات والتنظيف:** انظر `MERGE_HISTORY.md`
> **للمشاكل المفتوحة والقرارات المعلقة:** انظر `OPEN_ISSUES.md`
