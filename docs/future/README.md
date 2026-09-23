# Future Infrastructure & Deployment Plan — Documentation Package

> ## ⚠️ تحذير بارز / PROMINENT WARNING
> **هذه وثائق تخطيط فقط — لا شيء منها منفَّذ.**
> **PLANNED — NOT IMPLEMENTED.** No script here was executed, no service
> provisioned, no account created, no credential generated, nothing tested.
> كل ملف يحمل حالته صراحةً، وكل رقم يحمل مصدره ووسم تحققه.

## Executive Summary / الملخص التنفيذي

حزمة تخطيط مستقبلية لتشغيل منظومة Omni Medical Suite (وحزمة AHW للخط اليدوي
العربي) خارج الأجهزة المؤقتة، عبر أربع مسارات مكمِّلة:

| # | المسار | الغاية | الحالة |
|---|---|---|---|
| 1 | **VPS Options + Hybrid Architecture** ([vps/](vps/)) | اختيار استضافة دائمة منخفضة/صفرية التكلفة ومعمارية هجينة VPS↔Colab↔GitHub | PLANNED |
| 2 | **GitHub Codespaces** ([codespaces/](codespaces/)) | تشغيل فوري في المتصفح (تصحيح/تطوير) بلا جهاز محلي قوي | PLANNED |
| 3 | **Oracle Cloud Deployment Kit** ([oracle/](oracle/)) | حزمة نشر خطوة-بخطوة (00→11) لخادم Always-Free | PLANNED |
| 4 | **VPS ↔ Colab Training Pipeline** ([colab-pipeline/](colab-pipeline/)) | تدريب دوري تلقائي على GPU مجاني مع وسيط GitHub مشفّر | PLANNED |

**لماذا؟** بيئات العمل الحالية مؤقتة (تُفقد الملفات بعد كل reset)، ولا GPU
دائمًا، ولا خدمة 24/7. هذه الحزمة تمهّد نقل: التصحيح (HITL) إلى خادم دائم،
والتدريب إلى Colab/GPU، والنماذج إلى إصدارات مُتحقَّق منها (SHA256 + promote/rollback).

## Evidence Convention (قاعدة الأدلة — §5.1)

كل ادعاء تقني/رقمي في هذه الحزمة يوثَّق كالتالي:

```
Source: <رابط المصدر الرسمي>
Verified: NOT LIVE-VERIFIED (session was DOCUMENTATION_ONLY — zero external calls)
Status: UNVERIFIED — re-confirm at execution time
```

أرقام الخطط المجانية (Oracle/GitHub/Colab…) **تتغير مع الزمن** — اعتبر كل رقم
تقريبيًا وتحقق من المصدر الرسمي قبل التنفيذ الفعلي. لا يوجد في هذه الحزمة أي
ادعاء بحالة PROVEN لأن شيئًا لم يُنفَّذ أو يُختبر.

## Table of Contents / جدول المحتويات

```
docs/future/
├── README.md                  ← (هذا الملف) البوابة الرئيسية
├── vps/                       ← 12 ملفًا: المزودون، المعمارية الهجينة، التكلفة،
│                                 المخاطر، الأمن، الخصوصية، خارطة V-0..V-7، Runbook
├── codespaces/                ← 3 ملفات: لماذا/إعداد/استكشاف أخطاء
├── oracle/                    ← 14 ملفًا: 00-prerequisites → 11-troubleshooting
│                                 + ROLLBACK_PLAN
└── colab-pipeline/            ← 7 ملفات: المعمارية، الأمن (GPG)، إعدادات
                                  VPS/Colab/GitHub، سير العمل اليومي/الأسبوعي
```

المساندات خارج docs/ (قوالب **غير منفذة** — رؤوس `TEMPLATE ONLY` إلزامية):

```
.devcontainer/            ← إعداد Codespaces (يُشغَّل تلقائيًا عند فتح Codespace — راجع تحذيراته)
.gitpod.yml               ← بديل Gitpod
deploy/oracle/*.template  ← 10 قوالب نشر
deploy/configs/*.template ← nginx + systemd×2 + .env
automation/**             ← قوالب خط VPS↔Colab (تصدير/تشفير/سحب/ترقية + notebook + workflows)
scripts/*.template        ← فحوص دخان/تحقق بنيوي
```

## Proposed Timeline / الجدول الزمني المقترح

| المرحلة | المدة | المخرج | شرط الانتقال |
|---|---|---|---|
| V-0 | أسبوع | تسجيل Oracle (أو بديل) | نجاح التسجيل |
| V-1 | أسبوع | SSH + Nginx + SSL | اتصال آمن موثق |
| V-2 | أسبوع | نشر خدمات AHW 24/7 | uptime مستقر |
| V-3 | أسبوع | Migration بيانات التصحيح | تحقق سلامة البيانات |
| V-4 | أسبوع | Backup + Monitoring | إشعارات تعمل |
| V-5 | أسبوع | Docker (اختياري) | حاويات تعمل |
| V-6 | أسبوع | Colab integration | تدريب آلي واحد ناجح |
| V-7 | أسبوع | Full production | استقرار أسبوعين |

## File Tree الكامل

[انظر §3 من أمر المهمة — مطابق حرفيًا لما أُنشئ في هذا الفرع]

## Governance Record (لهذه الحزمة)

- DOCUMENTATION_ONLY: لم يُنفَّذ أي سكربت، لم تُثبَّت أي حزمة، لم تُشغَّل أي خدمة،
  لم يَتصل الوكيل بأي خادم/سحابة/Colab، لم تُولَّد credentials، لم تُنزَّل أوزان.
- الفرع: `feature/future-infrastructure-plan` من `main@39640a6` (ليس من HEAD
  المحجوب `8920f8f` الخاص بإصلاحات PR #136 — فصل تام بين المهمتين).
- لا PHI ولا بيانات حقيقية في أي ملف.
