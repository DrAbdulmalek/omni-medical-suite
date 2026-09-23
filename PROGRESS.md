# PROGRESS — ATR Phase (Arabic TrOCR Advanced Features)

> ذاكرة المشروع ضد فقدان الجلسة (env resets). تُحدَّث بعد كل مرحلة ثم commit + push فوري.
> الفرع: `feature/atr-trocr-advanced` — **ممنوع لمس main**. القاعدة: لا force push، لا rewrite، لا دمج من الوكيل.

## جدول المراحل (يُحدَّث مع كل مرحلة)

| Phase | Feature | Status | Commit | Tests | Notes |
|---|---|---|---|---|---|
| ATR-01 | Pre-Flight + PROGRESS.md | DONE | (هذا الـcommit) | n/a | فرع جديد من origin/main `39640a6` |
| ATR-02 | F4 Batch PDF — segment_batch.py + merge_batches.py | PENDING | - | 0/0 | إعادة بناء ahw/segment.py موثقة |
| ATR-03 | F1 AraBERT Tokenizer — ahw/arabic_trocr.py | PENDING | - | 0/0 | dry_run + محاولة تنزيل حقيقية |
| ATR-04 | F3 Training UI — train_server.py + dashboard | PENDING | - | 0/0 | + correction_server.py (تتطلبها F2) |
| ATR-05 | F2 Docker — Dockerfile.atr + docker-compose.yml | PENDING | - | 0/0 | STRUCTURE_ONLY: لا docker في البيئة |
| ATR-06 | Integration Smoke Test | PENDING | - | 0/0 | PDF اصطناعي 3 صفحات، بلا PHI |
| ATR-07 | Final Report | PENDING | - | 0/0 | |

## ما تبقى (Remaining)

- تنفيذ ATR-02 → ATR-07 بالترتيب دون توقف (AUTONOMOUS MODE).
- تدوير التوكن المؤقت من المالك بعد انتهاء المهمة.

## بيئة Pre-Flight (مثبتة 2026-09-23)

- Python 3.12.14 — **torch/transformers/flask غير مثبتة نظاميًا** → venv: `/home/z/my-project/venvs/atr` (بـ `--system-site-packages`).
- متاح نظاميًا: pymupdf (fitz)، opencv 4.13.0، pandas 2.2.3، openpyxl، pytest 9.0.2.
- Docker: **غير متوفر** → ATR-05 = STRUCTURE_ONLY + اختبار YAML/Dockerfile ساكن.
- GPU: لا يوجد → CPU فقط.
- القرص: ~7.9GB حرة (فوق حد 2GB).
- بيانات اعتماد GitHub: ملف محلي موجود (بصمة `sha256:5821a50287a8c836…`) — يُستخدم عبر credential helper مؤقت، **لا يُطبع أبدًا**.
- المستودع shallow clone؛ origin/main = `39640a6dbba741eaf13e078dad64719e147ea79b` (مؤكد بـ ls-remote).

## ملاحظة إعادة بناء (Reconstruction Note) — مهمة

الملفات المرجعية في الماستر برومبت (`segment.py`, `train_trocr.py`, `server.py`, `output/S001`)
**غير موجودة في المستودع** (فُقدت مع env reset سابق — سابقة M001 الموثقة). الموقف المتخذ:

- تُعاد بناؤها وفق مواصفات هذا الماستر برومبت: `ahw/segment.py` (preprocess/detect_layout/extract_words)
  + `segment_batch.py` + `merge_batches.py` + `train_server.py`.
- المرجع الحي المستخدم لإعادة البناء: أداة تجزئة S001 v7 الباقية محليًا خارج المستودع
  (`/home/z/my-project/data/handwriting-ar/tools/segment_words_s001.py`) + `ArabicWordSegmenter`
  الموجود فعلًا في `hf-space/packages/vision/htr/word_segmenter.py`.
- الانحراف موثق في RECONSTRUCTION.md داخل حزمة الـHandoff لكل مرحلة — لا صمت ولا fallback.

## قواعد ثابتة

1. main = `39640a6` لا يُلمس. فرع واحد: `feature/atr-trocr-advanced`.
2. لا تعديل على محركات OCR القائمة (Tesseract/Paddle/EasyOCR/OLMoCR) ولا الـcontract ولا OCRResult.
3. الاختبارات القائمة تبقى خضراء — لا إضعاف assertions ولا حذف اختبارات.
4. التوكن لا يُطبع نهائيًا — بصمة SHA-256 فقط عند الحاجة.
5. كل commit يليه: push → تحقق `ls-remote` بالـSHA → تحديث هذا الملف → Handoff Bundle.
6. فحص أسرار قبل كل push: `ghp_/sk-/AKIA/BEGIN.*PRIVATE`.
