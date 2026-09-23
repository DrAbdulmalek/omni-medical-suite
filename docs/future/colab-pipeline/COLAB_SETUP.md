# COLAB SETUP (V-6 · PLANNED)

القالب: `automation/colab/train_arabic_trocr.ipynb.template` (outline JSON — TEMPLATE ONLY).

## الخطوات (وقت التنفيذ مستقبلًا)
1. افتح Notebook جديدًا (أو انسخ القالب) → Runtime: **T4 GPU**.
2. **Secrets** (مفاتيح Colab Secrets — لا في خلايا):
   - `GH_TOKEN` (ضيّق: releases:write لمستودع models + contents:read لـdatasets)
   - `GPG_PASSPHRASE` (أو المفتاح الخاص مشفرًا — حسب نمط SECURITY.md)
3. الخلايا (outline في القالب):
   1. تثبيت (torch/transformers pins كما في requirements-atr.txt — إصدارات **مُثبتة 4.57.6/5.12.1**).
   2. سحب dataset مشفر عبر `gh` (أحدث release/asset).
   3. فك التشفير **في الذاكرة/tmp** + تحقق SHA256 مقابل manifest.
   4. بناء النموذج: مسار `ahw/arabic_trocr.load_model_with_arabic_tokenizer` (فرع ATR بعد الدمج).
   5. تدريب (epochs حسب الحجم؛ checkpoints كل epoch تُرفع — مقاومة انقطاع Colab).
   6. تقييم CER/WER (jiwer) على test split (بلا تسرب صفحات — عقد split_by_source_page).
   7. حفظ safetensors + metrics.json + SHA256SUMS.
   8. رفع GitHub Release `trocr-arabic-v<n>`.
   9. (اختياري) webhook/repository_dispatch لإعلام VPS.
4. **أول تشغيل = بيانات اصطناعية** (إثبات خط) قبل أي corpus حقيقي.

## قيود Colab الواقعية
- جلسات تنقطع (T4 free ~ ساعات) → checkpoints إلزامية.
- RAM/VRAM: base model + batch صغير؛ large → Pro+ أو RunPod (ALTERNATIVES).
- الحصة اليومية متغيرة → جدولة مرنة (أسبوعية لا يومية).
