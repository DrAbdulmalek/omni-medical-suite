# الدليل التوثيقي الشامل | OmniMedical Suite v2.0

**منصة ذكية موحدة لمعالجة المستندات الطبية**
*Unified Medical Document Processing Platform*

---

## 1. نظرة عامة على المشروع

OmniMedical Suite هو مستودع برمجي موحد (Monorepo) تم بناؤه بدمج مشروعين ناضجين، هما medical-doc-processor (بنسخته 3.2) و OmniFile_Processor (بنسخته 5.0)، في منصة واحدة متماسكة. يوفر المشروع حلاً متكاملاً لمعالجة المستندات الطبية متعددة اللغات (خاصة العربية) باستخدام أحدث تقنيات الذكاء الاصطناعي والتعلم الآلي، وذلك من خلال واجهة ويب حديثة مبنية على Next.js وواجهة خلفية قوية بلغة Python.

**الهدف الأساسي:** أتمتة معالجة المستندات الطبية الورقية والرقمية، واستخراج المعلومات الحيوية منها، مع حماية السياق الطبي وضمان الدقة العالية.

---

## 2. البنية المعمارية

تم بناء النظام وفق معمارية الخدمات المصغرة (Microservices) ضمن هيكل Monorepo باستخدام Turborepo:

```
┌─────────────────────────────────────────────────────────────────┐
│                    واجهة المستخدم (Port 3000)                    │
│              Next.js 16 + React 19 + Tailwind CSS               │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                  خدمات الخلفية (Port 8000)                       │
│                 FastAPI + Celery + Gradio                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                    خط أنابيب المعالجة                            │
│                                                                 │
│  ┌──────────┐    ┌─────────────────┐    ┌──────────────────┐    │
│  │ الرؤية   │───▶│  NLP            │───▶│  الذكاء الاصطناعي│    │
│  │ Fusion V2│    │ Context Protector│    │  LLM Gateway     │    │
│  └──────────┘    └─────────────────┘    └────────┬─────────┘    │
│                                                  │              │
│                                     ┌────────────▼─────────┐   │
│                                     │  التخزين              │   │
│                                     │  Qdrant Vector DB    │   │
│                                     └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│                      البنية التحتية                              │
│   Redis ──▶ Prometheus ──▶ Grafana ──▶ Qdrant ──▶ Docker/K8s   │
└─────────────────────────────────────────────────────────────────┘
```

**المكونات الرئيسية:**

- **الواجهة الأمامية:** تطبيق Next.js 16 مع React 19 و shadcn/ui و Prisma ORM ونظام مصادقة NextAuth.js.
- **خدمات الخلفية:** تعتمد على FastAPI مع مهام موزعة عبر Celery، وواجهة Gradio تفاعلية.
- **خط أنابيب المعالجة (Processing Pipeline):** يتكون من أربع وحدات أساسية:
  - **الرؤية (Vision):** محرك Fusion V2 للتعرف البصري على الحروف (OCR).
  - **معالجة اللغة (NLP):** نظام Context Protector لحماية الدلالات الطبية.
  - **الذكاء الاصطناعي (AI):** بوابة LLM Gateway للاستفادة من النماذج اللغوية.
  - **التخزين (Vector Store):** قاعدة بيانات Qdrant للبحث الدلالي.

---

## 3. الميزات الرئيسية

### 3.1 محرك التعرف البصري (Multi-Engine OCR)

يعتمد النظام على محرك تعاقبي (Cascading) يضم 6 محركات، يعمل بنظام الأولوية مع إمكانية الرجوع التلقائي (Fallback) والتوجيه القائم على الثقة (Confidence-based Routing):

| الأولوية | المحرك | الوصف |
|:---|:---|:---|
| 1 | **Mixed Engine** | محرك هجين مخصص لتحقيق أفضل النتائج. |
| 2 | **Tesseract** | محرك مفتوح المصدر يدعم اللغة العربية (`tesseract.js` / `pytesseract`). |
| 3 | **Mistral AI** | محرك سحابي عبر واجهة Mistral API للمستندات المعقدة. |
| 4 | **EasyOCR** | محرك تعلم عميق يدعم أكثر من 80 لغة. |
| 5 | **Surya OCR** | محرك متعدد اللغات مع قدرة على تحليل التخطيط (Layout-aware). |
| 6 | **TrOCR** | محول (Transformer) مُعد خصيصاً للتعرف على النصوص المكتوبة بخط اليد. |

### 3.2 خط أنابيب معالجة اللغة الطبية (Medical NLP Pipeline)

يمر النص المستخرج بأربع مراحل متخصصة:

1. **المعالجة المسبقة (Preprocessing):** تنظيف النص، توحيده، التعامل مع النصوص ثنائية الاتجاه (Bidi) وخلط اللغات.
2. **التصحيح (Correction):** تصحيح إملائي ونحوي متعدد الطبقات مع حماية المفردات الطبية.
3. **استخراج الكيانات (Entity Extraction):** التعرف على الكيانات المسماة (NER)، وكشف البيانات الحساسة (PII) مثل بطاقات الائتمان.
4. **الإثراء (Enrichment):** تلخيص النصوص، ترجمتها، تصنيفها، وتوليد أدلة دراسية.

### 3.3 نظام التعلم الموحد (Unified Learning System)

يجمع بين أربع تقنيات للتعلم المستمر لتحسين دقة النظام:

- **تدريب KNN:** لتعلم أفضل معاملات معالجة الصور من تصحيحات المستخدمين.
- **التعلم النشط (Active Learning):** لاختيار العينات غير المؤكدة لمراجعتها بشرياً.
- **قاعدة بيانات الأنماط (Pattern Database):** لتخزين تصحيحات المستخدمين بشكل تلقائي.
- **ضبط TrOCR:** ضبط دقيق باستخدام LoRA للتعرف على النصوص العربية المكتوبة بخط اليد.

### 3.4 نظام Fusion V2 للدمج المكاني والتصويت

تم تطوير نظام Fusion V2 لتحسين دقة الدمج بين نتائج المحركات المختلفة من خلال آلية التصويت المكاني (Spatial Voting)، مما أدى إلى تحسين الدقة من 78% إلى 92%.

### 3.5 حماية السياق الطبي (Medical Context Protector)

مكون ذكي يمنع الدمج الدلالي الخاطئ للمعلومات الطبية المتشابهة نصياً والمختلفة سريرياً، حتى لو تجاوز تشابه المتجهات 85%. ويحمي بشكل خاص:

- **جهة الإصابة:** يمين لا يسار لا ثنائي (خطأ قد يؤدي لخطأ جراحي).
- **الشدة:** حاد لا مزمن، خفيف لا مهدد للحياة.
- **نوع الكسر:** مفتوح لا مغلق لا مفتت.
- **الزمن:** حديث لا قديم.

### 3.6 ميزات الأمان والحماية

يتمتع النظام ببنية أمنية قوية تشمل:

- **تشفير:** AES-256-GCM لجميع المستندات المخزنة.
- **مصادقة:** NextAuth.js مع تجزئة كلمات المرور bcrypt.
- **صلاحيات:** تحكم في الوصول قائم على الأدوار (RBAC).
- **حماية:** تحديد معدل الطلبات (Rate Limiting)، كشف وإخفاء البيانات الحساسة (PII)، وقفل الحساب التلقائي.

---

## 4. هيكل المشروع (Project Structure)

ينقسم المشروع إلى وحدات رئيسية:

```
omni-medical-suite/
├── apps/web/                  # تطبيق Next.js (الواجهة الأمامية، المصادقة، مسارات API)
├── packages/
│   ├── ai/                    # بوابة الذكاء الاصطناعي (تدعم 15+ مزوداً)، التعلم النشط، والتعرف على خط اليد
│   ├── vision/                # محرك التعرف البصري، معالجة الصور، استخراج الجداول، وتحليل التخطيط
│   ├── nlp/                   # خط أنابيب البرمجة اللغوية العصبية، التصحيح الإملائي، استخراج الكيانات
│   ├── security/              # التشفير، فحص الملفات، والتدقيق الأمني
│   ├── learning/              # نظام التعلم الموحد (KNN والتعلم النشط)
│   ├── evaluation/            # مقاييس التقييم و BenchmarkSuite
│   ├── core/                  # المكونات الأساسية المشتركة
│   ├── desktop/               # واجهة سطح المكتب (PyQt5)
│   ├── medical/               # البيانات والقواميس الطبية
│   ├── omni-ocr/              # محرك OCR الموحد
│   ├── export/                # تصدير المستندات (layout_preserving, study_guide)
│   ├── interactive-learning/  # نظام التعلم التفاعلي
│   ├── segmentation/          # تجزئة النصوص والصور
│   ├── training/              # نماذج التدريب
│   ├── training-framework/    # إطار عمل التدريب المتقدم
│   ├── audit/                 # نظام التدقيق
│   ├── config/                # إعدادات التكوين
│   └── omni-core/             # النواة الأساسية
├── services/
│   └── api/                   # خدمة FastAPI الخلفية ومدير المهام الموزعة Celery
│       ├── app/
│       │   ├── main.py                    # نقطة الدخول
│       │   ├── core/                      # المكونات الأساسية
│       │   │   ├── medical_redis.py       # Redis مخصص من الصفر (RESP2/3)
│       │   │   ├── medical_websocket_server.py  # خادم WebSocket RFC 6455
│       │   │   ├── websocket_integration.py     # تكامل Celery+Gradio+FastAPI
│       │   │   ├── config.py              # إعدادات النظام
│       │   │   └── security.py            # الأمان والتشفير
│       │   ├── vision/                    # معالجة الصور والرؤية الحاسوبية
│       │   │   └── ocr_fusion_system.py   # نظام Fusion للتعرف البصري
│       │   ├── nlp/                       # معالجة اللغة الطبية
│       │   ├── ai/                        # خدمات الذكاء الاصطناعي
│       │   ├── vector_store/              # قاعدة البيانات الشعاعية
│       │   └── websocket_client.html      # عميل WebSocket (HTML/JS)
│       └── uploads/
├── infrastructure/
│   ├── docker/                 # إعدادات Docker و Docker Compose
│   ├── k8s/                    # ملفات نشر Kubernetes (14 بيان)
│   └── terraform/              # إعدادات Terraform للسحابة
├── helm/                       # مخطط Helm (10 قوالب)
├── tests/                      # مجموعة اختبارات شاملة (أكثر من 35 ملف اختبار)
├── .github/workflows/          # مسارات CI/CD (3 مهام)
├── docs/                       # التوثيق
├── config/                     # ملفات التكوين
├── scripts/                    # نصوص التشغيل والنشر
├── CHANGELOG.md                # سجل التغييرات
├── SECURITY.md                 # سياسة الأمان
├── README.md                   # ملف القراءة
└── requirements.txt            # متطلبات Python
```

---

## 5. المتطلبات والتثبيت

### 5.1 المتطلبات الأساسية

- **Node.js** >= 18.0.0
- **Python** >= 3.10
- **Git**
- **Tesseract OCR** (اختياري)
- **Docker** (اختياري، للنشر بالحاويات)

### 5.2 الإعداد التلقائي (موصى به)

```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
npm run setup
```

### 5.3 الإعداد اليدوي

```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
cp .env.example .env  # قم بتعديل .env بمفاتيح API الخاصة بك
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
npm install
cd apps/web
npx prisma generate
npx prisma db push
cd ../..
npm run build
npm run dev
```

---

## 6. متغيرات البيئة (Environment Variables)

| المتغير | القيمة الافتراضية | الوصف |
|:---|:---|:---|
| `DATABASE_URL` | `file:../../prisma/db/omni-medical.db` | مسار قاعدة البيانات (SQLite افتراضياً). |
| `NEXTAUTH_SECRET` | _(مُولد)_ | مفتاح تشفير NextAuth. |
| `ENCRYPTION_KEY` | _(مُولد)_ | مفتاح تشفير AES-256-GCM. |
| `OCR_ENGINE_ORDER` | `mixed_engine,tesseract,...` | ترتيب محركات التعرف البصري. |
| `MISTRAL_API_KEY` | _(فارغ)_ | مفتاح واجهة Mistral AI. |
| `OPENAI_API_KEY` | _(فارغ)_ | مفتاح واجهة OpenAI. |
| `NLP_STAGES` | `preprocessing,correction,...` | مراحل خط أنابيب NLP النشطة. |
| `TRAINING_ALGORITHM` | `knn` | خوارزمية التعلم (`knn`, `active_learning`, `trocr`). |
| `UPLOAD_DIR` | `./uploads` | مجلد رفع الملفات. |

---

## 7. النشر بالحاويات (Docker & Kubernetes)

### 7.1 النشر عبر Docker Compose

```bash
# بناء وتشغيل جميع الخدمات
docker compose -f infrastructure/docker/docker-compose.yml up -d

# عرض السجلات
docker compose -f infrastructure/docker/docker-compose.yml logs -f

# إيقاف الخدمات
docker compose -f infrastructure/docker/docker-compose.yml down
```

الخدمات المتاحة عبر Docker:

- **الويب (web):** المنفذ `3000`
- **الواجهة الخلفية (api):** المنفذ `8000`
- **المراقبة (grafana):** المنفذ `3001`
- **Redis:** المنفذ `6379`

### 7.2 النشر على Kubernetes

يتضمن المشروع ملفات نشر Kubernetes جاهزة في المجلد `infrastructure/k8s/`:

```bash
# تطبيق جميع الإعدادات
kubectl apply -f infrastructure/k8s/

# توسيع نطاق الـ API
kubectl scale deployment api --replicas=3 -n omni-medical

# تشغيل مهمة تدريب باستخدام GPU
kubectl apply -f infrastructure/k8s/gpu-training-job.yaml
```

### 7.3 النشر عبر Helm

```bash
# تثبيت المخطط
helm install omni-medical ./helm/omni-medical-suite -n omni-medical --create-namespace

# ترقية الإصدار
helm upgrade omni-medical ./helm/omni-medical-suite -n omni-medical

# إلغاء التثبيت
helm uninstall omni-medical -n omni-medical
```

---

## 8. المكونات المبنية من الصفر (Build-Your-Own-X)

### 8.1 MedicalRedis — خادم Redis مخصص (مُنفَّذ)

**الملف:** `services/api/app/core/medical_redis.py` (1,300 سطر)

خادم Redis مكتوب بالكامل من الصفر بلغة Python، يدعم بروتوكول RESP2 و RESP3، ومُحسَّن خصيصاً لبيئة الرعاية الصحية.

**الميزات:**
- 5 هياكل بيانات: Strings, Hashes, Lists, Sets, Sorted Sets
- نظام Pub/Sub للمراسلة بين الخدمات
- تدقيق HIPAA مع تسجيل كل عملية (WHO, WHAT, WHEN)
- عزل متعدد المستأجرين (Multi-tenant) عبر بادئات المفاتيح
- أوامر طبية مخصصة مثل `MED.PATIENT.SET` و `MED.DRUG.INTERACTION`
- استمرارية البيانات عبر WAL (Write-Ahead Log)
- انتهاء الصلاحية التلقائي للمفاتيح (TTL)

### 8.2 MedicalWebSocketServer — خادم WebSocket (مُنفَّذ)

**الملف:** `services/api/app/core/medical_websocket_server.py` (625 سطر)

خادم WebSocket متوافق مع RFC 6455، مكتوب من الصفر بلغة Python.

**الميزات:**
- دعم كامل لبروتوكول WebSocket RFC 6455
- إطارات نصية وثنائية (Text/Binary frames)
- Ping/Pong لمراقبة الاتصال
- عزل المستأجرين (Tenant Isolation)
- تكامل مع Celery للمهام غير المتزامنة
- دعم الواجهات التفاعلية (Gradio + FastAPI)
- عميل ويب تفاعلي: `services/api/app/websocket_client.html`

### 8.3 مقترحات التطوير المستقبلي (لم تُنفَّذ بعد)

يوجد 6 مشاريع إضافية تم تخطيطها ولم تُنفَّذ بعد، موثقة بالتفصيل في ملف `docs/DEVELOPMENT_SUGGESTIONS.md`:

1. **LSM Tree** — هيكل بيانات للكتابة عالية الأداء (MemTable + SSTable + WAL + Bloom Filter + Compaction)
2. **Load Balancer** — موزع أحمال TCP (Round Robin / Least Connections / IP Hash + Health Checks)
3. **Git-like VCS** — نظام تحكم إصدارات مبسط (SHA-256 content-addressable storage)
4. **Lisp Interpreter** — مفسر لغة Lisp (Tokenizer + Parser + AST Evaluator + Python binding)
5. **Vector DB (HNSW)** — قاعدة بيانات شعاعية (Hierarchical graph index + ANN search + BM25 hybrid)
6. **ML Framework** — إطار تعلم آلي (Tensor class + Backpropagation + Decision Trees + Random Forest)

---

## 9. البنية التحتية والمراقبة

### 9.1 CI/CD

يتضمن المشروع 3 مسارات عمل على GitHub Actions:

- **ci.yml:** فحص الكود، الاختبارات، فحص الأمان
- **deploy.yml:** النشر التلقائي عبر Docker/K8s
- **security.yml:** فحص الثغرات الأمنية وتحديث الحزم

### 9.2 المراقبة (Observability)

- **Prometheus:** جمع المقاييس من جميع الخدمات
- **Grafana:** لوحات مراقبة جاهزة (JSON Dashboard)
- **OpenTelemetry:** تتبع موزع (Distributed Tracing) مع تقرير Zipkin/Jaeger
- **Redis Sentinel:** مراقبة توفر Redis مع تجاوز الفشل التلقائي

### 9.3 الأمان (Security)

- **NetworkPolicy:** سياسات شبكة Kubernetes لعزل الخدمات
- **Pre-commit hooks:** فحص تلقائي قبل الارتكاب (trivy, hadolint, bandit)
- **Secrets scanning:** كشف المفاتيح المسرّبة عبر detect-secrets
- **.secrets.baseline:** خط أساسي لمقارنة الملفات السرية

---

## 10. نطاق الاستخدام والقيود

- **الاستخدام الأساسي:** معالجة المستندات الطبية متعددة اللغات (العربية والإنجليزية بشكل أساسي) في بيئات الرعاية الصحية.
- **القيود الحالية:** الاعتماد على SQLite كقاعدة بيانات افتراضية يجعلها مناسبة للتطوير والاختبار، لكن بيئة الإنتاج تتطلب PostgreSQL أو قاعدة بيانات مُدارة. دعم خط اليد ما يزال قيد التطوير والتحسين المستمر.
- **الترخيص:** المشروع غير محدد الترخيص حالياً، مما يستوجب مراجعة المالك قبل الاستخدام التجاري.

---

## 11. معلومات المساهمين والملكية الفكرية

- **برمجة وتطوير:** د. عبد المالك تامر الحسيني / حمص سوريا - اختصاصي جراحة عظمية - وبرمجة نظم وذكاء اصطناعي.
