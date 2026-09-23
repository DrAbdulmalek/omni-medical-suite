# GitHub Codespaces — تشغيل فوري في المتصفح (PLANNED)

**الحالة: PLANNED — لم يُفتح أي Codespace في هذه المرحلة التوثيقية.**

## لماذا Codespaces؟
- **فوري**: مستودع كامل + بيئة Python في ~3 دقائق، من أي جهاز/متصفح — الحل
  الأمثل لمشكلة فقدان البيئات المحلية (resets).
- **بلا بطاقة**: ضمن الحصة المجانية لحساب GitHub Free (≈120 core-hours +
  15GB storage شهريًا — **Source:** docs.github.com/about-billing-for-github-codespaces · **Status: UNVERIFIED**).
- **آمن نسبيًا**: بيئة معزولة تُحذف؛ لا PHI (قاعدة ثابتة).

## المواصفات المجانية (تقريبية — UNVERIFIED)
2 vCPU / 8GB RAM / 32GB disk افتراضًا (قابل للرفع بمضاعفة استهلاك الساعات).
الحصة الشهرية ≈ **60 ساعة تشغيل على نواتين** (120 core-hours).

## ما يعمل / ما لا يعمل

| يعمل ✅ | لا يعمل ❌ |
|---|---|
| تصحيح قصاصات (correction server) | تدريب TrOCR حقيقي (بلا GPU + RAM محدود أمام أوزان كاملة — تجربة ATR أثبتت OOM بـ1GB، و8GB تكفي dry_run/base بحذر) |
| تقطيع PDFs (segment_batch) على عينات اصطناعية | خدمات 24/7 (ينتهي/يتوقف) |
| تطوير/اختبار ATR + docs | تنزيل أوزان ضخمة بشكل متكرر (storage 32GB) |
| dry_run/smoke tests | رفع PHI (ممنوع قطعًا) |

## تحذيرات
- ⚠️ حد 60 ساعة/شهر: أغلق الـCodespace فور الانتهاء (يحاسب على وقت التشغيل).
- ⚠️ `.devcontainer/post-create.sh` في هذا الفرع **سيُشغَّل تلقائيًا** عند أول
  فتح Codespace (يثبت متطلبات) — راجعه قبل الفتح؛ لا أسرار/لا PHI/لا خدمات خارجية فيه.
- ⚠️ الملفات غير المحفوظة في /workspace تضيع عند حذف الـCodespace — commit/push دائمًا.

## الملفات
- [SETUP_GUIDE.md](SETUP_GUIDE.md) — خطوات الفتح والتشغيل
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — المشاكل الشائعة
