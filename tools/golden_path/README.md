# Golden Path UI — skeleton (S2-T1 / S2-T2)

> العقد: marathon-suite/docs/plans/2026-10-08-genspark-execution-contract-v4.md
> القرار: marathon-suite/docs/plans/golden-path-ui-decision.md — **Gradio محلي أولًا**
> الحالة: **PARTIALLY_PROVEN** — هيكل قابل للعكس، لم يُنفذ على PDF حقيقي بعد.

## الغرض

ثلاث خطوات فقط، بلا أي نداء شبكة:
1. رفع صورة وصفة/تقرير.
2. OCR عبر ocr-core (عبر `OCREngineAdapter` — نقطة تبديل المحرك).
3. تصحيح بشري + حفظ محلي **بنسق `--- filename.jpg ---` الذي يستهلكه
   `packages/vision/dataset_builder.py` مباشرة** (الحلقة تُغلق من أول يوم).

## تشغيل

```bash
pip install "gradio>=4.44,<5.0.0"
pip install "marathon-ocr-core[tesseract] @ git+https://github.com/DrAbdulmalek/ocr-core.git"
python tools/golden_path/ui_app.py      # يلتصق بـ 127.0.0.1:7861 فقط
```

## LOCAL_ONLY (S2-T4)

- الربط الافتراضي `127.0.0.1` مع `share=False` — لا منفذ عام أبدًا.
- اختبار اعتراض المقابس الآلي الكامل (صفر حزم صادرة عبر دورة E2E) = المهمة S2-T4
  المستقلة، يتطلب بيئة تنفيذ حقيقية — **ليس مشمولًا في هذا الهيكل**.

## التراجع

حذف `tools/golden_path/` بالكامل = صفر أثر (لا يستورد أحد هذا المجلد).
