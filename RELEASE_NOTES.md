# 🚀 Release Notes — Omni Medical Suite v1.0.0

**تاريخ الإصدار:** 9 يوليو 2026
**الحالة:** `Release Candidate` (مرشح للإصدار النهائي)
**الرخصة:** MIT
**المستودع:** https://github.com/DrAbdulmalek/omni-medical-suite
**Hugging Face Space:** https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr

---

## 🎯 نبذة عن الإصدار

هذا هو الإصدار الأول المستقر من **Omni Medical Suite** — منصة متكاملة لمعالجة الصور الطبية، استخراج النصوص (OCR) باللغتين العربية والإنجليزية، مع تصحيح بشري (HITL)، وتعلم مستمر.

يهدف هذا المشروع إلى توفير حل مفتوح المصدر لتحويل الوثائق الطبية المكتوبة بخط اليد أو المطبوعة إلى نصوص رقمية منظمة، مع الحفاظ على الخصوصية وقابلية التوسع.

---

## ✨ الميزات الرئيسية

### 🖼️ معالجة الصور (Scanner Fixer)
- تصحيح المنظور (Perspective Correction)
- إزالة الميلان (Deskew)
- إزالة الضوضاء والظلال
- قص الحواف التلقائي
- معالجة دفعية للصور

### 🔍 OCR متعدد المحركات
- **PaddleOCR** (الدقة العالية للعربية)
- **EasyOCR** (خفة وسرعة)
- **Tesseract** (محرك مفتوح المصدر)
- **TrOCR** (مخصص للخط اليدوي)
- **دمج ذكي** (Ensemble Voting)

### 🧠 معالجة النصوص
- **Normalization عربية متقدمة** (تشكيل، همزات، أرقام)
- **Medical Dictionary Mapping** (مصطلحات طبية، اختصارات)
- **WordNet Integration** (قاموس إنجليزي-عربي)

### 🤖 التدقيق والتصحيح (Proofreading)
- **LLM Proofreading** (Jais-13B / Gemma عبر Ollama)
- **Spell Checker** (مع Medical Dictionary)
- **Hybrid NER** (أدوية، أمراض، جرعات، أعراض)

### 👤 Human-in-the-Loop (HITL)
- **واجهة Gradio** لرفع الصور وتصحيح النصوص
- **حفظ تلقائي** في Hugging Face Dataset
- **Auto Data Collector** لجمع التصحيحات

### 📈 التعلم المستمر
- **Retraining Pipeline** (أسبوعي)
- **Medical Dictionary Auto-Update**
- **Benchmark Suite** (CER/WER/Medical Term Accuracy)

### 🛡️ الأمان والخصوصية
- **JWT Authentication** مع Refresh Tokens
- **Token Revocation** (Blacklist)
- **RBAC** (Admin/Moderator/User)
- **Audit Logs** + Request ID
- **CORS** قائمة صريحة
- **Trusted Hosts** مفعّل

### 📊 المراقبة والصيانة
- **Prometheus Metrics** (10+ مقاييس)
- **Grafana Dashboards** (OCR Performance)
- **Sentry Error Tracking**
- **Structured Logging** (JSON)
- **Health Checks** (Liveness, Readiness)
- **Alertmanager** (7 قواعد تنبيه)
- **Backup Strategy** (Git bundles + DB dumps, 30-day retention)

### 🐳 النشر والتوزيع
- **Docker Compose** (جاهز للإنتاج)
- **Hugging Face Spaces** (Auto-deploy عبر GitHub Actions)
- **GitHub Actions** (CI/CD + Security Scanning + Dependabot)
- **Multi-stage Dockerfile** (تحسين الحجم)

---

## 📦 هيكل المشروع

```
omni-medical-suite/
├── apps/                       # تطبيقات قابلة للتشغيل
│   ├── api/                    # FastAPI (backend)
│   ├── web/                    # Next.js (frontend)
│   ├── trainer-ui/             # Gradio HITL
│   ├── handwriting-demo/       # عرض خط اليد
│   └── ocr-pipeline/           # خط أنابيب OCR
├── packages/                   # مكتبات قابلة لإعادة الاستخدام
│   ├── scanner_fixer/          # معالجة الصور
│   ├── ocr_core/               # محركات OCR
│   ├── gt_core/                # Ground Truth
│   ├── benchmark_core/         # معايير التقييم
│   ├── training_hub/           # منصة التدريب
│   ├── text_core/              # معالجة النصوص
│   ├── core/                   # الوظائف المشتركة
│   └── medical/                # القواميس والمعالجة الطبية
├── services/                   # خدمات خلفية
│   ├── worker/                 # RQ Worker
│   ├── scheduler/              # جدولة المهام
│   ├── retraining/             # إعادة التدريب
│   └── dataset_builder/        # بناء مجموعة البيانات
├── infra/                      # البنية التحتية
│   ├── monitoring/             # Prometheus + Grafana
│   └── docker/                 # ملفات Docker
├── hf-space/                   # ملفات Hugging Face Space
├── scripts/                    # أدوات التشغيل والصيانة
├── config/                     # إعدادات المراقبة والتنبيهات
├── desktop/                    # تطبيق PyQt6
├── docs/                       # التوثيق
│   ├── RUNBOOK.md              # دليل العمليات
│   └── ARCHITECTURE.md         # الوثيقة المعمارية
├── app/                        # خلفية FastAPI الأساسية
│   ├── core/                   # إعدادات أساسية + logging
│   └── routers/                # API endpoints (health, auth, etc.)
└── .github/workflows/          # GitHub Actions CI/CD
```

---

## 🧪 الاختبارات

| المقياس | النتيجة |
|---------|---------|
| **إجمالي الاختبارات** | 320 |
| **ناجحة** | 278 (86.9%) |
| **فاشلة** | 3 (domain logic في dictionary_manager) |
| **مهملة** | 39 (تعتمد على torch/العرض) |
| **Ruff** | 4,559 تحذير (تم إصلاح 12,846 تلقائياً) |
| **Mypy** | يعمل (لا أخطاء حرجة) |

---

## ⚙️ المتطلبات

### النظام
- **Python** 3.10+
- **Node.js** 18+ (للـ frontend)
- **Docker** 20.10+ (للنشر)
- **Git** 2.30+

### المكتبات الأساسية
- FastAPI, Uvicorn
- OpenCV, PyTesseract, PaddleOCR, EasyOCR
- Transformers, PyTorch
- Gradio, Streamlit
- SQLAlchemy, AsyncPG
- Redis, RQ
- Prometheus Client, Sentry SDK

---

## 🚀 التثبيت السريع

```bash
# 1. استنساخ المستودع
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite

# 2. إنشاء البيئة الافتراضية
python -m venv venv
source venv/bin/activate

# 3. تثبيت الاعتماديات
pip install -e .[api,ml,dev]

# 4. تشغيل التطبيق
python app/gradio_full_hitl.py

# أو باستخدام Docker
docker-compose up gradio
```

---

## 📝 سجل التغييرات

### v1.0.0 (9 يوليو 2026)

#### البنية والهيكلة
- **إضافة** Monorepo موحد مع 8+ حزم أساسية
- **إضافة** `pyproject.toml` موحد مع extras (api, ml, dev, ops)
- **تحسين** تنظيم المستودعات (من 46 إلى 15 مستودع على GitHub)

#### OCR ومعالجة الصور
- **إضافة** دعم OCR متعدد المحركات (PaddleOCR، EasyOCR، Tesseract، TrOCR)
- **إضافة** Scanner Fixer متقدم (تصحيح المنظور، إزالة الميلان، إزالة الظلال)
- **إضافة** Ensemble Voting للدمج الذكي بين المحركات

#### النصوص والذكاء الاصطناعي
- **إضافة** Normalization عربية متقدمة
- **إضافة** Medical Dictionary Mapping مع NER
- **إضافة** LLM Proofreading (Jais-13B عبر Hugging Face)
- **إضافة** Spell Checker مع Medical Dictionary

#### الواجهات
- **إضافة** Human-in-the-Loop (Gradio HITL)
- **إضافة** تطبيق سطح مكتب PyQt6
- **إضافة** واجهة Streamlit للجوال

#### النشر
- **إضافة** Docker Compose للإنتاج (7 خدمات)
- **إضافة** نشر على Hugging Face Spaces (Docker SDK)
- **إضافة** GitHub Actions CI/CD (Auto-deploy)
- **إضافة** Multi-stage Dockerfile مع PaddleOCR pre-cache

#### المراقبة والصيانة
- **إضافة** Prometheus + Grafana monitoring stack
- **إضافة** Sentry Error Tracking
- **إضافة** Structured JSON Logging مع request ID
- **إضافة** Health Checks (Liveness, Readiness, Full)
- **إضافة** Alertmanager مع 7 قواعد تنبيه
- **إضافة** Backup System (PostgreSQL + Redis + Files, 30-day retention)
- **إضافة** Update Checker (GitHub releases)
- **إضافة** Dependabot (شهري) + Security Scan (أسبوعي)

#### الأمان
- **إضافة** JWT Authentication مع Refresh Tokens
- **إضافة** RBAC (Admin/Moderator/User)
- **إضافة** CORS صريح + Trusted Hosts
- **إضافة** Token Revocation (Blacklist)
- **إصلاح** إزالة الأسرار المكشوفة

#### التوثيق
- **إضافة** RUNBOOK.md (دليل العمليات)
- **إضافة** MAINTENANCE_LOG.md (جدول الصيانة)
- **إضافة** MONITORING.md (دليل المراقبة الكامل)
- **إضافة** MAINTENANCE.md (7 Runbooks + خطة DR)
- **تحسين** README.md مع أقسام النشر والمراقبة

#### جودة الكود
- **إصلاح** Ruff auto-fix: إصلاح 12,846 من 17,326 تحذير
- **إصلاح** 16 اختبار فاشل (إضافة Path import + تصحيح assertions)
- **تثبيت** httpx2 و rapidfuzz

### v0.9.0 (قبل الدمج)
- إصدارات فردية لكل مكون
- بنية متفرقة (22+ مستودعاً)

---

## ⚠️ المشاكل المعروفة

| المشكلة | الحالة | الحل |
|---------|--------|------|
| 3 اختبارات فاشلة (domain logic) | 🟡 منطقية | تحديث تصنيف القاموس الطبي |
| 4,559 تحذير Ruff متبقية | 🟡 جارية | معظمها في legacy/tools |
| Docker غير مختبر في CI | 🟡 بيئة | اختبار محلياً |
| Desktop App يحتاج X11 | 🟡 بيئة | اختبار على نظام مع خادم عرض |
| غياب النماذج المدربة العامة | 🟡 قادم | تدريب ورفع TrOCR baseline |

---

## 🤝 المساهمة

نرحب بمساهماتكم! يرجى قراءة [CONTRIBUTING.md](./CONTRIBUTING.md) أولاً.

### المطورون
- **Dr. Abdulmalek Al-Husseini** — المؤسس والمطور الرئيسي

### الشكر
- **جامعة هونغ كونغ (HKUDS)** — للإلهام من مشروع AI-Researcher
- **Google Gemini** و **Claude** — للمساعدة في التطوير والمراجعة

---

## 📄 الترخيص

هذا المشروع مرخص بموجب [MIT License](./LICENSE) — حر الاستخدام مع الإشارة إلى المصدر.

---

## 📞 الدعم

- **GitHub Issues**: https://github.com/DrAbdulmalek/omni-medical-suite/issues
- **Hugging Face Space**: https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr

---

**🩺 معاً نبني مستقبل الذكاء الاصطناعي الطبي العربي.**