# MISSING_SOURCE_FILES.md
# Generated: 2026-07-11

ملفات لم تكن موجودة في النسخ الأساسية (`packages/{module}/`) عند تشغيل سكربت الاستعادة.
تم استعادتها من git history (commit قبل الحذف).

## الملفان

| الملف | المستهدف | المصدر (من التاريخ) | السطور | ملاحظة |
|-------|----------|---------------------|--------|--------|
| `packages/file_processor/modules/vision/medical_ocr_gradio.py` | file_processor/vision | `f8dab72^` (قبل التنظيف الشامل) | 105 | Gradio tab for Medical OCR — لم يُنسخ أبدًا إلى `packages/vision/` |
| `packages/file_processor/modules/core/progress_tracker.py` | file_processor/core | `f8dab72^` (قبل التنظيف الشامل) | 2006 | تتبع تقدم المعالجة — فريد لـ file_processor، لا يوجد في `packages/core/` |

## سبب عدم وجودهما في packages/ الأساسية

هذان الملفان كانا موجودين **فقط** في `packages/file_processor/` ولم يُنسخا أبداً إلى الحزم المركزية
(`packages/vision/`, `packages/core/`). لذلك عند حذف النسخ "المكررة" في commit 93185df،
لم يُحتفظ بهما في أي مكان — حُذفا بالكامل.

تم استعادتهما من git history (pre-deletion commit `f8dab72^`).
