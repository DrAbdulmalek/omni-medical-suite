# دليل الترحيل من المشاريع القديمة
# Migration Guide

## نظرة عامة

تم دمج ثلاثة مشاريع مستقلة في مشروع موحد واحد: **Medical Doc Suite**.

## المشاريع المدمجة

| المشروع | النوع | الحالة |
|---------|-------|--------|
| `medical-doc-processor` | ويب + سطح مكتب | ✅ القاعدة الرئيسية |
| `medical-document-scanner` | سطح مكتب (PyQt5) | ✅ تم الدمج |
| `medical-doc-webapp` | ويب (موبايل أولاً) | ✅ تم الدمج |

## ما تم دمجه

### من medical-document-scanner
- ✅ خوارزمية `LazyImage` للتحميل الكسول
- ✅ `SkewWorker` و `ThumbnailWorker` (QThread)
- ✅ نظام التعلم `AdaptiveLearner` + `TrainingDataCollector`
- ✅ كشف المكررات بـ Perceptual Hash
- ✅ تقييم شامل للجودة (6 مقاييس)
- ✅ معالجة الدفعات غير الحاجبة (QTimer)
- ✅ اختبارات `test_core.py`

### من medical-doc-webapp
- ✅ تصميم متجاوب (موبايل أولاً)
- ✅ دعم الوضع الداكن (next-themes)
- ✅ تحسينات واجهة المستخدم

## التحسينات المضافة

### الخوارزميات المحسّنة
- `find_page_bounds`: Median-only (أكثر موثوقية)
- `auto_detect_skew`: تحقق 5% + نطاق ±5°
- `smart_auto_crop`: مرحلتين (حدود + محتوى)

### ميزات جديدة
- صفحة "دمج المشاريع" في لوحة التحكم
- نظام تدريب خط اليد (PDF → كلمات → تصحيح)
- مساعد الذكاء الاصطناعي (z-ai-web-dev-sdk)
- CI/CD مع GitHub Actions
- توثيق شامل (عربي/إنجليزي)

## هيكل الملفات الجديد

```
medical-doc-processor/
├── apps/                      # (مخطط للمستقبل)
│   ├── web/                   # تطبيق الويب
│   └── desktop/               # تطبيق سطح المكتب
├── desktop/
│   ├── medical_doc_gui_final.py   # ← التطبيق الموحد المحسّن
│   ├── medical_doc_scanner.py     # ← النسخة الأصلية
│   └── requirements.txt
├── src/
│   ├── app/                   # Next.js App Router
│   ├── components/            # React Components
│   └── lib/                   # Utilities & Algorithms
├── docs/
│   ├── ARCHITECTURE.md        # ← هيكلية النظام
│   ├── ALGORITHMS.md          # ← توثيق الخوارزميات
│   └── MIGRATION.md           # ← هذا الملف
├── scripts/
│   ├── build-all.sh           # ← بناء جميع التطبيقات
│   ├── test-all.sh            # ← تشغيل جميع الاختبارات
│   ├── sync-algorithms.sh     # ← مزامنة الخوارزميات
│   └── deploy.sh              # ← نشر موحد
├── .github/workflows/
│   ├── ci.yml                 # ← اختبار مستمر
│   └── release.yml            # ← إصدارات تلقائية
└── test_core.py               # ← اختبارات موحدة
```

## تشغيل المشروع

### تطبيق الويب
```bash
bun install
bun run dev
# افتح http://localhost:3000
```

### تطبيق سطح المكتب
```bash
cd desktop
pip install -r requirements.txt
python medical_doc_gui_final.py
```

### تشغيل الاختبارات
```bash
bash scripts/test-all.sh
# أو بشكل منفصل:
bun run lint                    # TypeScript
python3 -m pytest test_core.py  # Python
```

## أرشفة المشاريع القديمة

بعد التأكد من عمل المشروع الموحد بشكل صحيح:

1. أضف إشعار الدمج في README كل مشروع قديم:
```markdown
> ⚠️ تم دمج هذا المشروع في [medical-doc-processor](https://github.com/DrAbdulmalek/medical-doc-processor)
```

2. أرشف المستودع من إعدادات GitHub:
```
Settings → Danger Zone → Archive this repository
```

3. لا تحذف المستودعات — الأرشفة تحافظ على:
   - سجل Git الكامل
   - القضايا وطلبات السحب
   - إمكانية الاستعادة
