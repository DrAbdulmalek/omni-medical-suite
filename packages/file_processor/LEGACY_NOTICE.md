# ⚠️ Legacy Repository — Migration Notice (Corrected 2026-07-05)

> **Status**: 🟡 Legacy — merge into omni-medical-suite decided, **not yet executed**
> **Migration Target**: [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite)
> **Last Updated**: 2026-07-05

## الوضع الفعلي (تصحيح لنسخة سابقة من هذا الملف)

النسخة السابقة من هذا الملف كانت تصف خطة نقل تتضمن مستودعات وملفات **غير موجودة فعلياً**
(`medical-ocr-trainer`, `handwriting-ocr-model`, `omni-medical-suite/docs/MIGRATION.md`)،
وتقترح نقل هذا المشروع إلى بنية (React dashboard منفصل، K8s ضمن omni-medical-suite) **تم
حذفها بالفعل من omni-medical-suite** في مراجعة لاحقة لأنها لم تكن مستخدَمة قط.

## القرار الحالي (فعلي، لا افتراضي)

- **الوجهة**: دمج ضمن [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) فقط.
- **الحالة**: قرار مُتخَذ، **الدمج البرمجي الفعلي لم يبدأ بعد**. هذا الملف توثيق نية، لا سجل إنجاز.
- **لماذا لم يبدأ فوراً**: المشروع يحتوي 3478 ملفاً وبنية مختلفة جذرياً (Streamlit+React+FastAPI+Celery)
  عن omni-medical-suite (Gradio + مكتبات بايثون مباشرة). يحتاج جرداً منفصلاً لتحديد ما هو
  فعلاً مفيد وغير مكرَّر (خصوصاً `modules/nlp/spell_corrector.py` الذي يبدو مكرِّراً لوظيفة
  `packages/core/spell_checker.py` الموجودة أصلاً في omni-medical-suite) قبل نقل أي كود.

## ما لا يزال نشطاً هنا مؤقتاً

كل شيء لا يزال هنا كما هو حتى إتمام الجرد والدمج الفعلي. لا تعتمد على أي جدول زمني حتى
يُنفَّذ الدمج فعلياً ويُوثَّق هنا بكوميت حقيقي قابل للتحقق.

## Contact

Dr Abdulmalek Tamer Al-husseini — Abdulmalek.husseini@gmail.com
