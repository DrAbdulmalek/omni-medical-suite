# المشاكل المفتوحة والخطوات القادمة — Open Issues

آخر تحديث: 2026-07-14

---

## ✅ مشاكل تم حلها (للتوثيق)

| المشكلة | الحل | Commit |
|---------|------|--------|
| RTL fixing بعد OCR | `src/ocr/rtl_utils.py` | `d8c854d` |
| Qdrant integration | `packages/core/engine_registry.py` + smoke test | `973979c` |
| qdrant-client استيراد ثقيل | نقل لاختياري `[search]` extra | `5dcdf9b` |
| Vision eager imports (14 استيراد) | `__getattr__` lazy loading | `8645576` / `881e63e` |
| 73 استيراد مكسور بعد حذف جماعي | استعادة 3 ملفات + إصلاح 3 استيراد | `a35eaa1` / `46fd895` |
| 85 ملف مكرر 100% | حذف + فحص استيراد إلزامي | `f8dab72` |
| field-aware dedup حالة الحافة | إصلاح + اختبار | `c440683` |
| scanner_fixer_wrapper.py مفقود | إنشاء الملف | `25171e8` |

---

## 🟡 قرارات معلقة تحتاج مراجعة بشرية

### 1. ~18 ملف في CATEGORY_B_FINAL_PENDING.md
فروقات وظيفية حقيقية (>10 أسطر) تحتاج قراراً بشرياً لكل ملف. تم تقليصها من 117.

### 2. 162 ملف في LEGACY_REVIEW_FINAL.md
داخل `variants/` و `hf-space/` و `legacy/api_server.py`. لا توجد استيرادات خارجية لكنها تحتاج مراجعة محتوى قبل الحذف.

### 3. 9 استيرادات مكسورة سابقة (commit `12b6cd2`)
تسمية مجلدات: `data-prep` vs `data_prep` و `omni-ocr` vs `omni_ocr`. ليست ناتجة عن التنظيف — مشكلة تسمية أصلية.

### 4. ruff auto-fix دفعة واحدة على 12,846 مشكلة
تم تنفيذها بلا مراجعة بشرية فردية. قد تحتوي تغييرات سلوكية غير مقصودة. يُنصح بمراجعة diff الكامل.

### 5. 3 أخطاء منطقية في tmx_processor.py
تم توثيق الأسباب الجذرية في `PYTEST_REPORT.md`:
- `test_detect_medical_category_fracture`: regex `CT` بدون حد كلمة يطابق "ct" داخل "fracture"
- `test_detect_medical_category_generic`: regex `test` بدون حد كلمة يطابق الكلمة العادية "test"
- `test_export_to_json`: `{k: row[k] for k in row}` على `sqlite3.Row` يعطي قيماً لا أسماء أعمدة

### 6. ~50 ملف requirements*.txt قديمة
تم تقليل الجذر (`requirements-dev.txt`) إلى compatibility wrapper، لكن بقية الملفات القديمة ما زالت بحاجة ترحيل تدريجي إلى `pyproject.toml` extras. انظر `docs/DEPENDENCY_STRATEGY.md`.

### 7. المراجع المكسورة في المستودعات البعيدة
تم إصلاح المراجع المحلية فقط. repos البعيدة (repo-sync-toolkit، medical-ocr-trainer-hf، intelli-file-manager، sync-github) تحتاج إصلاحاً مباشراً على GitHub.

---

## 🔶 سؤال معماري مفتوح (يحتاج قرار Malek)

الوضع الحالي: `packages/handwriting/modules/vision/__init__.py` يستورد `from modules.vision.ocr_engine import OCREngine` — أي يتوقع `ocr_engine.py` محليًا داخل شجرة handwriting. لكن النسخة "الأساسية" المفردة موجودة في `packages/vision/ocr_engine.py`. الحل الفوري كان نسخ الملف محليًا (73+3 ملف).

**السؤال:** هل التصميم الصحيح طويل المدى هو:
- **(أ)** الاحتفاظ بنسخ محلية في كل حزمة مدمجة (الحل الحالي — بسيط لكنه يُضعِف التناسق)؟
- **(ب)** تعديل كل `__init__.py` للاستيراد من الموقع المركزي `packages/vision/ocr_engine.py` بدل النسخ المحلية (نظيف معماريًا لكنه يحتاج تعديل مئات الاستيرادات وإعادة اختبار شاملة)؟
- **(ج)** إزالة الحزم المدمجة بالكامل واستبدالها بـ symlinks أو إعادة توجيه imports؟

> **الإصلاح الحالي (أ) هو الحل الآمن الفوري فقط — هذا قرار معماري لـ Malek.**

---

## 🏗️ دين هيكلي — Structural Debt

### تكرار جزئي في الحزم المُدمجة
رغم التنظيف، بقيت تكرارات جزئية في:
- `packages/file_processor/` — vs `packages/core/` و `packages/vision/`
- `packages/handwriting/` — نسخ محلية من ملفات Python
- `packages/omnifile/` — تكرار جزئي
- `packages/doc-processor/` / `packages/doc_processor/` — نسخ من `core/`
- `packages/bilingual/` — نسخ من `nlp/`

### تسمية غير متسقة
- `data-prep` vs `data_prep` (kebab-case vs snake_case)
- `omni-ocr` vs `omni_ocr`
- `doc-processor` vs `doc_processor`

---

## 🗺️ خارطة طريق مقترحة

1. **مراجعة الـ 18 ملف المعلق** (CATEGORY_B_FINAL_PENDING.md) — قرار بشري لكل ملف
2. **مراجعة الـ 162 ملف legacy** (LEGACY_REVIEW_FINAL.md) — حذف أو أرشفة
3. **توحيد تسمية المجلدات** — اختيار kebab-case أو snake_case وتطبيقه
4. **حل السؤال المعماري (أ/ب/ج)** — قرار من Malek
5. **مراجعة ruff auto-fix diff** — التأكد من عدم تغييرات سلوكية
6. **إصلاح 3 أخطاء tmx_processor.py** — regex bounds + sqlite3.Row
7. **ترحيل requirements*.txt** — إلى `pyproject.toml` extras تدريجياً
8. **إصلاح المراجع المكسورة في المستودعات البعيدة** — على GitHub
9. **حل التكرار الجزئي في الحزم المُدمجة** — بعد قرار المعمار