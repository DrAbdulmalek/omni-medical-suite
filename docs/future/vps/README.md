# VPS Package — Overview (PLANNED, NOT IMPLEMENTED)

حزمة اختيار وتشغيل VPS لمنظومة Omni Medical Suite / AHW.
**الحالة: PLANNED — لم يُنفَّذ أي شيء منها.**

## ماذا / لماذا / متى

- **ماذا:** خادم دائم (يفضَّل مجاني: Oracle Always Free) يشغّل خدمات التصحيح
  والتقطيع 24/7، مع معمارية هجينة تربطه بـ Colab (تدريب GPU) وGitHub (وسيط
  مشفّر + نسخ احتياطي).
- **لماذا:** البيئات الحالية مؤقتة (فقدان ملفات بعد كل reset)، بلا GPU دائم،
  وبلا خدمة متصلة.
- **متى:** وفق خارطة [ROLLOUT_ROADMAP.md](ROLLOUT_ROADMAP.md) — V-0..V-7 (≈8 أسابيع).

## ملفات الحزمة

| الملف | المحتوى |
|---|---|
| [FREE_VPS_OPTIONS.md](FREE_VPS_OPTIONS.md) | جدول المزودين + ملاءمة سوريا + تجاوز عقبات الدفع (خيارات مشروعة) |
| [HYBRID_ARCHITECTURE.md](HYBRID_ARCHITECTURE.md) | مخطط Mermaid + أدوار المكوّنات + تدفقا البيانات |
| [INTEGRATION_POINTS.md](INTEGRATION_POINTS.md) | جدول تكامل ملفات المشروع الحالية (IMPLEMENTATION: NOT NOW) |
| [COST_ANALYSIS.md](COST_ANALYSIS.md) | 3 سيناريوهات شهرية/سنوية |
| [RISK_REGISTER.md](RISK_REGISTER.md) | سجل المخاطر والتخفيف |
| [SECURITY_CHECKLIST.md](SECURITY_CHECKLIST.md) | 10+ بنود إلزامية قبل أي نشر |
| [PRIVACY_COMPLIANCE.md](PRIVACY_COMPLIANCE.md) | PHI: المسموح/الممنوع/الاضطراري |
| [ROLLOUT_ROADMAP.md](ROLLOUT_ROADMAP.md) | V-0..V-7 بشروط انتقال |
| [ALTERNATIVES.md](ALTERNATIVES.md) | بدائل عند فشل Oracle/GPU/التخزين |
| [FAQ.md](FAQ.md) | 10+ أسئلة |
| [DEPLOYMENT_RUNBOOK.md](DEPLOYMENT_RUNBOOK.md) | قوالب أوامر (TEMPLATE ONLY — DO NOT EXECUTE) |

## ملخص سريع

القرار المقترح: **Oracle Always Free (ARM Ampere)** كخادم أساسي إن نجح التسجيل،
و**GitHub Codespaces** كبديل تطويري فوري، و**Colab** للتدريب فقط. التفاصيل
والأدلة (بوسم UNVERIFIED — أرقام الخطط المجانية تتغير) في FREE_VPS_OPTIONS.
