# PROGRESS — ATR Phase (Arabic TrOCR Advanced Features)

> ذاكرة المشروع ضد فقدان الجلسة (env resets). تُحدَّث بعد كل مرحلة ثم commit + push فوري.
> الفرع: `feature/atr-trocr-advanced` — **ممنوع لمس main**. القاعدة: لا force push، لا rewrite، لا دمج من الوكيل.

## جدول المراحل (يُحدَّث مع كل مرحلة)

| Phase | Feature | Status | Commit | Tests | Notes |
|---|---|---|---|---|---|
| ATR-01 | Pre-Flight + PROGRESS.md | DONE | 11da6ac | n/a | فرع جديد من origin/main `39640a6` |
| ATR-01b | Parallel-Session Reconciliation (Qwen) | DONE | 558dda5 | n/a | تبنّي عمل Z.ai + تحقق مستقل من ATR-02 في بيئة Qwen — `docs/atr/ATR-01b-RECONCILIATION.md` |
| ATR-02 | F4 Batch PDF — segment_batch.py + merge_batches.py | DONE | b49a742 | 4/4 (مُدّعى) → **4/4 مُتحقَّق مستقلًا** في بيئة Qwen (py3.11/transformers 4.57.6)؛ المجموعة الكاملة 759 passed، صفر انحدار | + إعادة بناء ahw/segment.py موثقة + GT prefill RTL |
| ATR-03 | F1 AraBERT Tokenizer — ahw/arabic_trocr.py | DONE | acf86b3 | 4/4 dry_run (Z.ai) | real-load مُثبت (Z.ai): resize 50265→64000 + reinit كامل + forward 0.8s CPU |
| ATR-04 | F3 Training UI — train_server.py + dashboard | ADOPTED | 21b0ba5 | 15/15 (Qwen) + تحقق Z.ai 15/15 (transformers 5.12.1) | **تولّت Qwen** (توقف Z.ai بعد ATR-03 @15:02:59Z)؛ +correction_server.py + نواة ahw/train_trocr.py (smoke/full) + smoke حقيقي داخل الاختبارات |
| ATR-05 | F2 Docker — Dockerfile.atr + docker-compose.atr.yml | ADOPTED | 70e5982 | 12/12 (Qwen) + تحقق Z.ai 12/12 | STRUCTURE_ONLY (لا docker في البيئتين)؛ أسماء ATR منفصلة كي لا تستبدل Dockerfile/docker-compose.yml الجذرية؛ sidecar `Dockerfile.atr.dockerignore` (لا لمس لـ .dockerignore القائم)؛ + requirements-atr.txt |
| ATR-06 | Integration Smoke Test | DONE | 11967da | 3/3 (+ سكربت مستقل PASS) | PDF اصطناعي 3ص → دفعات → دمج → تصحيحات → تدريب dry_run؛ **أصلح درز تكامل**: مسار القصاصة batch-aware (`<batch>/crops/x.png`) في train_trocr + correction_server؛ loss تنازلي 2.85→2.69؛ 0 تنزيل/0 شبكة/0 PHI |
| ATR-04b | مصالحة Z.ai — توافق transformers 5.x + إصلاح مسارات الدمج + سكربت probe | DONE | cc9fea8+bc6f740 | **35/35 + تكاملي الجلسة الموازية** | إصلاح dry_run لـ5.x (PreTrainedTokenizerFast)؛ crop_path: اعتُمد عقد ATR-06 (مسار عارٍ + حل batch-aware عند المستهلك) وإلغى إصلاح المنتِج في merge_batches بعد فشل اختبار ATR-06 التكاملي — عقد واحد موحد؛ التزام scripts/atr_probe_models.py؛ تعارض دليل الـpin موثق في requirements-atr.txt |
| ATR-04c | مصالحة Qwen — إصلاح dry_run عبر الإصدارات (post-processor [CLS]/[SEP]) | DONE | ba77ba4 | **38/38 على transformers 4.57.6** | rebuild Z.ai لـ5.x جعل الكلمة المفردة توكنًا واحدًا بلا CLS/SEP → **loss=0 على 4.57.6** (يعمل صدفةً على 5.12.1)؛ أُضيف `TemplateProcessing` — وفيّ للـ AraBERT الحقيقي ويعبر 4.x+5.x؛ **لم يُرفع transformers** (قاعدة 1.3)؛ pin `<5` أُزيل (dual-evidence) |
| ATR-07 | Final Report (UNIFIED dual-session) | DONE | 8f2235f+1ce2d7a+ba77ba4 | n/a | `docs/atr/ATR-07-FINAL-REPORT.md` — تقرير موحَّد (Z.ai+Qwen): الطقم 38/38 على 4.57.6 و5.12.1، real-load 2.67GB (Z.ai)، ATR-04c، PERSISTENCE=OK، HOW TO RUN |
| ATR-07c | Report-Integrity Corrections (مراجعة تدقيقية خارجية) | DONE | (this commit) | n/a | 9 تصحيحات توثيقية: VERIFICATION block بـ SHAs كاملة + MATCH؛ فصل declared-vs-validated لـ transformers؛ صياغة Git دقيقة للـadditive؛ تقسيم deps (جديد vs معاد استخدامه)؛ إزالة بصمة التوكن؛ tiered persistence (Git PROVEN / bundles local / remote archival NOT ESTABLISHED)؛ ATR-03 real-load "Z.ai-env only"؛ لا تغيير كود/اختبارات بعد ba77ba4 |

## ✅ المهمة مكتملة (ATR-01 → ATR-07)

كل المراحل السبع DONE ومدفوعة لـ origin/feature/atr-trocr-advanced. إجمالي اختبارات ATR:
**38/38 خضراء**؛ المجموعة الكاملة **793 passed** مع مجموعة فشل مطابقة لـ baseline (صفر انحدار).
التفاصيل والحالات (PROVEN/PARTIALLY/BLOCKED): `docs/atr/ATR-07-FINAL-REPORT.md`.

**نقطتا انتباه للمالك:**
1. ⚠️ التوكن المستخدم للـ push مكشوف في السجلات — **ألغِه/دوّره فورًا**.
2. F1 real-weight training (2.67GB) و F2 docker build: PARTIALLY PROVEN — يتطلبان
   بيئة بـ RAM/GPU + docker (sandbox الحالي محدوده 1GB RAM وبلا docker). الكود كامل
   ومُختبَر بنيويًا/dry_run؛ يبقى الإثبات الحقيقي على بيئة المالك.

## ما تبقى (Remaining)

- ✅ **لا شيء — المهمة مكتملة** (ATR-01→ATR-07 كلها DONE ومدفوعة).
- ما يبقى على المالك (خارج نطاق sandbox): (أ) إلغاء/تدوير التوكن المكشوف؛
  (ب) إثبات real-weight training (F1) و docker build (F2) على بيئة بـ RAM/GPU/docker؛
  (ج) مراجعة PR ودمج `feature/atr-trocr-advanced` ← main عند الموافقة.
- ملاحظة تدقيق: docstring في `ahw/arabic_trocr.py` يشير إلى `scripts/atr_probe_models.py`
  وهو **غير مُلتزم** (بقي في بيئة Z.ai) — مرجع معلق موثق، لا يعطل أي اختبار.

## بيئة Pre-Flight (مثبتة 2026-09-23)

### بيئة Z.ai (الجلسة الأولى — ATR-01/02)

- Python 3.12.14 — **torch/transformers/flask غير مثبتة نظاميًا** → venv: `/home/z/my-project/venvs/atr` (بـ `--system-site-packages`).
- متاح نظاميًا: pymupdf (fitz)، opencv 4.13.0، pandas 2.2.3، openpyxl، pytest 9.0.2.
- Docker: **غير متوفر** → ATR-05 = STRUCTURE_ONLY + اختبار YAML/Dockerfile ساكن.
- GPU: لا يوجد → CPU فقط.
- القرص: ~7.9GB حرة (فوق حد 2GB).
- بيانات اعتماد GitHub: ملف محلي موجود (بصمة `sha256:5821a50287a8c836…`) — يُستخدم عبر credential helper مؤقت، **لا يُطبع أبدًا**.
- المستودع shallow clone؛ origin/main = `39640a6dbba741eaf13e078dad64719e147ea79b` (مؤكد بـ ls-remote).

### بيئة Qwen (الجلسة المستمرة — ATR-01b فما بعد)

- Sandbox مختلف: المستودع في `/home/user/omni-medical-suite` (clone كامل، ليس shallow).
- Python 3.11.2 + venv `/home/user/.venv`: torch **2.14.0+cpu**, transformers **4.57.6** (pin مقصود —
  5.x يكسر API مسودات TrOCR؛ يحقق قيد المستودع `>=4.36.0`), pymupdf 1.28.2 (`import fitz` يعمل
  مع تحذير deprecation), flask-socketio 5.6.1, jiwer 4.0.0, pytest 8.x (+asyncio,+timeout).
- Docker: غير متوفر (كما في بيئة Z.ai) → ATR-05 STRUCTURE_ONLY.
- القرص: ~6.7GB حرة بعد torch — تكفي تنزيل الأوزان ضمن سقف 4GB.
- Baseline موثق: `164 failed, 755 passed, 48 skipped, 26 errors` (كلها pre-existing — deps
  اختيارية ناقصة)؛ بعد ATR-02: `759 passed` ونفس مجموعة الفشل حرفيًا → صفر انحدار.
- أوامر إعادة بناء البيئة الكاملة: `docs/atr/ATR-01-PREFLIGHT-AUDIT.md` §5 + أدلة Pre-Flight §1-§8.
- ⚠️ ملاحظة snapshot: حجم المستودع 698MB يتجاوز سقف snapshots البيئة (128MB) → Handoff
  Bundles في `/home/user/download/OMNI-EXECUTION/handovers/<sha>/` هي الذاكرة الاحتياطية الفعلية.

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
