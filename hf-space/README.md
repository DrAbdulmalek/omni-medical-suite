---
title: Omni Medical OCR
emoji: 🏥
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: true
license: mit
---

# Omni Medical OCR

نظام متكامل لاستخراج وتصحيح النصوص الطبية العربية باستخدام AI.

## Pipeline

**رفع صورة → تنظيف → OCR → تدقيق LLM → استخراج الكيانات (NER) → حفظ**

## الميزات

- **Preprocessing**: تنظيف الصور الطبية (إزالة الظلال، تصحيح الميل، تحسين التباين)
- **OCR Ensemble**: PaddleOCR + TrOCR + EasyOCR + Tesseract + Surya
- **LLM Proofreading**: تصحيح سياقي باستخدام Jais-13B
- **Medical NER**: استخراج أدوية، أمراض، أعراض، جرعات، تواريخ
- **HITL**: واجهة Gradio للتصحيح البشري
- **Continuous Learning**: تحديث القاموس + إعادة التدريب التلقائي

## المتطلبات

- GPU: 24GB+ لتفعيل Jais (اختياري)
- HuggingFace Token: للحفظ في Dataset

## متغيرات البيئة

| المتغير | الوصف | الافتراضي |
|---------|-------|-----------|
| `ENABLE_LLM` | تفعيل Jais (يتطلب GPU) | `false` |
| `HF_TOKEN` | رمز HuggingFace | - |

## المطور

Dr. Abdulmalek Tamer Al-husseini

## الترخيص

MIT License