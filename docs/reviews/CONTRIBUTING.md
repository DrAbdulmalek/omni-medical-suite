# Contributing to OmniMedical Suite

شكراً لاهتمامك بالمساهمة في OmniMedical Suite! هذا الدليل يُفصّل كيفية إعداد بيئة التطوير وإرسال مساهماتك.

---

## 📋 جدول المحتويات

- [متطلبات مسبقة](#متطلبات-مسبقة)
- [إعداد بيئة التطوير](#إعداد-بيئة-التطوير)
  - [الطريقة المُوصى بها: Docker Compose](#الطريقة-المُوصى-بها-docker-compose)
  - [الإعداد اليدوي](#الإعداد-اليدوي)
- [هيكل المشروع](#هيكل-المشروع)
- [قواعد الكتابة](#قواعد-الكتابة)
  - [Python](#python)
  - [TypeScript / Next.js](#typescript--nextjs)
- [إجراء التغييرات](#إجراء-التغييرات)
- [الاختبارات](#الاختبارات)
- [إرسال Pull Request](#إرسال-pull-request)
- [التواصل](#التواصل)

---

## متطلبات مسبقة

قبل البدء، تأكد من تثبيت:

| الأداة | الإصدار المطلوب | الرابط |
|--------|----------------|--------|
| Node.js | ≥ 18.0.0 | [nodejs.org](https://nodejs.org) |
| Python | ≥ 3.10 | [python.org](https://python.org) |
| Git | latest | [git-scm.com](https://git-scm.com) |
| Docker | ≥ 24.0 (اختياري) | [docker.com](https://docker.com) |
| Tesseract OCR | ≥ 5.0 (اختياري للـ OCR المحلي) | [tesseract-ocr](https://github.com/tesseract-ocr/tesseract) |

> **للمستخدمين العرب:** إذا كنت تعمل على Windows، تأكد من إضافة Tesseract إلى `PATH` النظام.

---

## إعداد بيئة التطوير

### الطريقة المُوصى بها: Docker Compose

أسرع طريقة للبدء دون تثبيت dependencies يدوياً:

```bash
# 1. Clone المستودع
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite

# 2. إنشاء ملف البيئة
cp .env.example .env

# 3. تشغيل الخدمات الأساسية فقط (Next.js + FastAPI + SQLite)
docker compose -f docker-compose.dev.yml up

# 4. فتح التطبيق
# Web UI: http://localhost:3000
# API Docs (Swagger): http://localhost:8000/docs
# API Docs (ReDoc): http://localhost:8000/redoc
```

> **ملاحظة:** ملف `docker-compose.dev.yml` يشغل فقط الخدمات الأساسية (بدون Redis/Qdrant) للمبتدئين. للإنتاج استخدم `docker-compose.yml` الرئيسي.

### الإعداد اليدوي

إذا كنت تفضل الإعداد اليدوي:

#### الخطوة 1: Python Backend

```bash
# إنشاء virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# تثبيت dependencies
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# تثبيت Tesseract language packs (العربية + الإنجليزية)
# Ubuntu/Debian:
sudo apt-get install tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng

# macOS:
brew install tesseract tesseract-lang
```

#### الخطوة 2: Node.js Frontend

```bash
# تثبيت dependencies
npm install

# إعداد Prisma
cd apps/web
npx prisma generate
npx prisma db push --skip-generate
cd ../..

# بناء المشروع
npm run build
```

#### الخطوة 3: تشغيل الخدمات

```bash
# Terminal 1: Next.js (port 3000)
npm run dev

# Terminal 2: FastAPI (port 8000)
source venv/bin/activate
uvicorn services.api.main:app --reload --port 8000

# Terminal 3: Redis (اختياري — للـ cache و rate limiting)
redis-server
```

---

## هيكل المشروع

```
omni-medical-suite/
├── apps/web/              # Next.js 16 — الواجهة الأمامية
├── services/api/          # FastAPI — الخلفية
├── packages/
│   ├── ai/                # بوابة LLM (15+ مزود)
│   ├── vision/            # OCR + Computer Vision
│   ├── nlp/               # معالجة اللغة الطبية
│   ├── medical/           # التحقق الطبي + FHIR/HL7
│   ├── security/          # التشفير + Rate Limiting
│   ├── learning/          # KNN + Active Learning
│   └── export/            # التصدير بصيغ متعددة
├── data/                  # قواميس وملفات ثابتة
├── tests/                 # اختبارات (pytest)
└── infrastructure/        # Docker + K8s
```

**قاعدة مهمة:** كل `package` يجب أن يكون مستقلاً — لا تعتمد على `apps/web` مباشرة.

---

## قواعد الكتابة

### Python

- **اللغة:** Python 3.10+ مع type hints
- **Linter:** `ruff` (line length: 120)
- **Formatter:** `black`
- **الوثائق:** Google-style docstrings (بالإنجليزية للكود، التعليقات بالعربية مسموح)

```python
"""Example of good Python docstring."""

def process_medical_text(
    text: str,
    language: str = "ar",
    enable_validation: bool = True
) -> dict[str, Any]:
    """Process medical text through NLP pipeline.

    Args:
        text: The input medical text.
        language: Language code ('ar', 'en', or 'auto').
        enable_validation: Whether to run medical validation.

    Returns:
        Dictionary containing processed text, entities, and validation results.

    Raises:
        ValueError: If text is empty or language is unsupported.
    """
    if not text:
        raise ValueError("Text cannot be empty")
    # ...
```

### TypeScript / Next.js

- **اللغة:** TypeScript strict mode
- **Linter:** ESLint + Prettier
- **المكونات:** Functional components with hooks
- **التسمية:** PascalCase للمكونات، camelCase للدوال

---

## إجراء التغييرات

### فروع العمل (Branching)

```bash
# إنشاء فرع جديد
git checkout -b feature/اسم-الميزة

# أو للإصلاحات:
git checkout -b fix/وصف-الإصلاح
```

### أنواع الـ commits المقبولة

| البادئة | الاستخدام |
|---------|----------|
| `feat:` | ميزة جديدة |
| `fix:` | إصلاح خلل |
| `docs:` | تعديل وثائق |
| `test:` | إضافة/تعديل اختبارات |
| `refactor:` | إعادة هيكلة بدون تغيير وظيفي |
| `perf:` | تحسين أداء |
| `security:` | إصلاح أمني |

**مثال:**
```bash
git commit -m "feat: add FHIR R4 export for medical documents"
git commit -m "fix: correct Arabic RTL text rendering in PDF export"
```

---

## الاختبارات

### تشغيل الاختبارات

```bash
# Python tests
source venv/bin/activate
pytest tests/ -v

# مع coverage
pytest tests/ --cov=packages --cov-report=html

# اختبارات محددة
pytest tests/test_ocr.py -v
pytest tests/test_arabic_rtl.py -v
pytest tests/test_medical_validator.py -v  # جديد

# Node.js tests
npm run test
```

### إضافة اختبارات جديدة

- كل `package` جديد يجب أن يتضمن `tests/test_<package>.py`
- اختبارات التكامل (integration) تُوضع في `tests/test_integration.py`
- اختبارات الأداء (performance) تُوضع في `tests/test_performance.py`

---

## إرسال Pull Request

1. **تحديث الفرع:**
   ```bash
   git fetch origin
   git rebase origin/main
   ```

2. **تشغيل الاختبارات:**
   ```bash
   pytest tests/ -v
   npm run lint
   npm run build
   ```

3. **إرسال PR:**
   - العنوان: واضح ومختصر (بالإنجليزية)
   - الوصف:
     - ما الذي يُغيّره؟
     - لماذا؟
     - كيف اختبرته؟
     - هل يحتاج إلى تحديث الوثائق؟

4. **Review:**
   - يتطلب PR موافقة **2 reviewers**
   - CI يجب أن يمر (lint → test → build → security scan)

---

## التواصل

- **Issues:** [GitHub Issues](https://github.com/DrAbdulmalek/omni-medical-suite/issues)
- **Discussions:** [GitHub Discussions](https://github.com/DrAbdulmalek/omni-medical-suite/discussions)
- **البريد:** drabdulmalek@example.com (استبدله ببريدك الفعلي)

---

## 🏆 معايير القبول (Definition of Done)

قبل دمج أي PR، يجب استيفاء:

- [ ] الكود يتبع style guide
- [ ] اختبارات unit مُضافة وتمر
- [ ] اختبارات integration تمر (إن أمكن)
- [ ] الوثائق مُحدّثة (README أو docstrings)
- [ ] لا يوجد regression في الأداء
- [ ] Security scan نظيف (no secrets, no vulnerabilities)
- [ ] Reviewer واحد على الأقل وافق

---

**شكراً لمساهمتك في تحسين معالجة المستندات الطبية! 🩺**
