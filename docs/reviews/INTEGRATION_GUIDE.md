# دليل دمج التحسينات — OmniMedical Suite v2.1

هذا الدليل يشرح خطوة بخطوة كيفية دمج التحسينات السبعة في المشروع الحالي.

---

## 📦 ملخص التحسينات

| # | التحسين | الملف الجديد | الملف المُعدَّل |
|---|---------|-------------|----------------|
| 1 | **OpenAPI/Swagger UI** | — | `services/api/main.py` |
| 2 | **CONTRIBUTING.md** | `CONTRIBUTING.md` | — |
| 3 | **BenchmarkSuite JSON** | `data/benchmarks/*.json` | — |
| 4 | **OCR Cache** | `packages/vision/ocr_cache.py` | `services/api/main.py` |
| 5 | **Circuit Breaker** | `packages/vision/circuit_breaker.py` | `services/api/main.py` |
| 6 | **Per-User Rate Limiter** | `packages/security/user_rate_limiter.py` | `services/api/main.py` |
| 7 | **Medical Validator** | `packages/medical/medical_validator.py` | `services/api/main.py` |
| 8 | **FHIR/HL7 Exporter** | `packages/export/fhir_exporter.py` | `services/api/main.py` |

---

## 1️⃣ دمج OpenAPI/Swagger UI

### الخطوات:

```bash
# 1. استبدل services/api/main.py بالنسخة المُحسَّنة
cp services/api/main.py services/api/main.py.backup
cp enhancements/services/api/main.py services/api/main.py

# 2. تثبيت dependencies الإضافية (إن لم تكن مثبتة)
pip install redis

# 3. تشغيل الخدمة
uvicorn services.api.main:app --reload --port 8000
```

### الوصول:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

### ما الجديد:
- وثائق عربية/إنجليزية في وصف الـ API
- تصنيف endpoints حسب المجال (OCR, Medical, Admin)
- أمثلة تفاعلية لكل endpoint
- Security schemes (Bearer + API Key)

---

## 2️⃣ دمج CONTRIBUTING.md

```bash
# نسخ الملف إلى جذر المشروع
cp enhancements/CONTRIBUTING.md ./CONTRIBUTING.md

# لا حاجة لتعديلات إضافية — جاهز للاستخدام
```

---

## 3️⃣ دمج BenchmarkSuite JSON

```bash
# نسخ نتائج الاختبارات
mkdir -p data/benchmarks
cp enhancements/data/benchmarks/*.json data/benchmarks/

# إضافة إلى .gitignore (اختياري — إذا كنت تريد تحديثها يدوياً)
# لا تُضفها إلى .gitignore — هذه ملفات مرجعية
```

### الاستخدام:
```python
import json

# قراءة نتائج OCR Fusion
with open("data/benchmarks/ocr_fusion_v1_vs_v2.json") as f:
    results = json.load(f)

print(f"Fusion V2 accuracy: {results['results']['ocr_fusion']['v2_spatial_confidence']['overall_accuracy']}")
# Output: 0.92
```

---

## 4️⃣ دمج OCR Cache

### الخطوات:

```bash
# 1. نسخ الموديول
cp enhancements/packages/vision/ocr_cache.py packages/vision/ocr_cache.py

# 2. تفعيل Redis (إذا لم يكن مفعلاً)
# في .env:
# REDIS_URL=redis://localhost:6379

# 3. تعديل services/api/main.py لاستخدام الـ Cache
```

### تعديل services/api/main.py:

أضف في الأعلى:
```python
from packages.vision.ocr_cache import OCRCache
```

في lifespan:
```python
ocr_cache = await OCRCache.init(redis_client)
app.state.ocr_cache = ocr_cache
```

في endpoint `/api/v2/ocr/process`:
```python
@app.post("/api/v2/ocr/process")
async def process_document(...):
    cache = request.app.state.ocr_cache
    file_hash = OCRCache.compute_file_hash(content)
    engine_config = OCRCache.serialize_engine_config(
        engine_order or ["mixed_engine", "tesseract"],
        params.language_hint
    )

    # Check cache
    cached = await cache.get(file_hash, engine_config, tenant_id=user.get("tenant_id"))
    if cached:
        return {"status": "success", "source": "cache", "result": cached.result}

    # Process...
    result = await ocr_engine.process(...)

    # Store in cache
    await cache.set(file_hash, engine_config, result, confidence=0.94)

    return {"status": "success", "source": "live", "result": result}
```

---

## 5️⃣ دمج Circuit Breaker

### الخطوات:

```bash
cp enhancements/packages/vision/circuit_breaker.py packages/vision/circuit_breaker.py
```

### تعديل services/api/main.py:

أضف:
```python
from packages.vision.circuit_breaker import CircuitBreakerRegistry, CircuitBreakerError
```

في lifespan:
```python
await CircuitBreakerRegistry.init(redis_client)
```

في OCR engine wrapper:
```python
async def call_mistral_ocr(image_bytes):
    cb = CircuitBreakerRegistry.get("mistral")
    return await cb.call(mistral_api.process, image_bytes)
```

في exception handler (موجود بالفعل في النسخة المُحسَّنة):
```python
@app.exception_handler(CircuitBreakerError)
async def circuit_breaker_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content={
            "error": "Service temporarily unavailable",
            "engine": exc.engine_name,
            "retry_after": exc.retry_after
        },
        headers={"Retry-After": str(exc.retry_after)}
    )
```

---

## 6️⃣ دمج Per-User Rate Limiter

### الخطوات:

```bash
cp enhancements/packages/security/user_rate_limiter.py packages/security/user_rate_limiter.py
```

### تعديل services/api/main.py:

النسخة المُحسَّنة تحتوي على `rate_limit_user` dependency جاهزة. فقط تأكد من:

1. أن Redis يعمل
2. أن المستخدمين لديهم حقل `tier` في JWT payload

### تكوين الـ Tiers (في .env أو قاعدة البيانات):

```python
TIERS = {
    "free": {"requests": 10, "window": 60, "burst": 2},
    "standard": {"requests": 100, "window": 60, "burst": 10},
    "premium": {"requests": 500, "window": 60, "burst": 50},
    "enterprise": {"requests": 2000, "window": 60, "burst": 200},
}
```

---

## 7️⃣ دمج Medical Validator

### الخطوات:

```bash
cp enhancements/packages/medical/medical_validator.py packages/medical/medical_validator.py
```

### تعديل services/api/main.py:

النسخة المُحسَّنة تحتوي على endpoint جاهز:
```python
@app.post("/api/v2/medical/validate")
async def validate_medical_text(...)
```

### الاستخدام المباشر:
```python
from packages.medical.medical_validator import MedicalValidator

validator = MedicalValidator(llm_gateway=ai_gateway)
result = await validator.validate(
    text="Paracetamol 50mg مرتين يومياً",
    context="prescription",
    language="ar"
)

print(result.is_valid)  # False (جرعة منخفضة جداً)
print(result.issues[0].message)  # "جرعة paracetamol (50mg) أقل من الحد الأدنى"
```

### توسيع قاعدة بيانات الأدوية:

عدّل `DRUG_DOSAGES` في `medical_validator.py`:
```python
DRUG_DOSAGES = {
    "your_drug": {"min_mg": X, "max_mg": Y, "unit": "mg", "frequency": "daily"},
}
```

---

## 8️⃣ دمج FHIR/HL7 Exporter

### الخطوات:

```bash
cp enhancements/packages/export/fhir_exporter.py packages/export/fhir_exporter.py
```

### تعديل services/api/main.py:

النسخة المُحسَّنة تحتوي على endpoint جاهز:
```python
@app.post("/api/v2/medical/fhir/export")
async def export_fhir(...)
```

### الاستخدام المباشر:
```python
from packages.export.fhir_exporter import FHIRExporter, MedicalEntity, PatientInfo, DocumentMetadata

exporter = FHIRExporter()

# FHIR R4
bundle = exporter.to_fhir_r4(
    text="المريض يعاني من ارتفاع ضغط الدم...",
    entities=[
        MedicalEntity(type="diagnosis", text="hypertension", code="38341003", confidence=0.92),
        MedicalEntity(type="medication", text="amlodipine", confidence=0.88)
    ],
    patient=PatientInfo(id="p-123", name="أحمد محمد", gender="male"),
    metadata=DocumentMetadata(
        document_id="doc-456",
        source_type="discharge",
        created_at="2026-05-20",
        processed_at="2026-05-27",
        ocr_confidence=0.94,
        validator_confidence=0.87,
        language="ar"
    )
)

# HL7 v2
hl7_msg = exporter.to_hl7_v2(
    text="...",
    entities=[...],
    patient=PatientInfo(...),
    message_type="ORU^R01"
)
```

---

## 🔧 تعديلات إضافية مطلوبة

### 1. requirements.txt

أضف:
```
redis>=5.0.0
```

### 2. .env.example

أضف:
```bash
# Rate Limiting Tiers
RATE_LIMIT_TIER_FREE=10
RATE_LIMIT_TIER_STANDARD=100
RATE_LIMIT_TIER_PREMIUM=500
RATE_LIMIT_TIER_ENTERPRISE=2000

# OCR Cache
OCR_CACHE_TTL=86400
OCR_CACHE_MAX_ENTRIES=10000

# Circuit Breaker
CIRCUIT_BREAKER_ENABLED=true
CIRCUIT_BREAKER_MISTRAL_THRESHOLD=3
CIRCUIT_BREAKER_MISTRAL_TIMEOUT=60

# Medical Validator
MEDICAL_VALIDATOR_ENABLED=true
MEDICAL_VALIDATOR_LLM_ENABLED=false

# FHIR Export
FHIR_DEFAULT_FORMAT=fhir_r4
```

### 3. docker-compose.dev.yml (مُبسَّط)

أنشئ `docker-compose.dev.yml`:
```yaml
version: "3.8"
services:
  web:
    build:
      context: .
      dockerfile: infrastructure/docker/Dockerfile.web
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=file:./db/omni-medical.db
      - NEXTAUTH_URL=http://localhost:3000
    volumes:
      - ./apps/web:/app/apps/web
      - ./packages:/app/packages

  api:
    build:
      context: .
      dockerfile: infrastructure/docker/Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=file:./db/omni-medical.db
      - REDIS_URL=redis://redis:6379
    volumes:
      - ./services/api:/app/services/api
      - ./packages:/app/packages
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  redis_data:
```

---

## ✅ قائمة التحقق النهائية

بعد الانتهاء من الدمج، تأكد من:

- [ ] `services/api/main.py` يعمل بدون أخطاء
- [ ] Swagger UI متاح على `http://localhost:8000/docs`
- [ ] Redis يعمل (`redis-cli ping` → `PONG`)
- [ ] OCR Cache يُخزّن النتائج (اختبر بنفس الملف مرتين)
- [ ] Circuit Breaker يُغلق بعد 3 محاولات فاشلة
- [ ] Rate Limiter يُرجع `429` بعد تجاوز الحد
- [ ] Medical Validator يكتشف جرعات غير منطقية
- [ ] FHIR Export يُنتج Bundle صالح
- [ ] جميع الاختبارات تمر: `pytest tests/ -v`

---

## 🆘 استكشاف الأخطاء

### مشكلة: "Redis connection refused"
**الحل:** تأكد من تشغيل Redis:
```bash
docker compose -f docker-compose.dev.yml up redis
# أو
redis-server
```

### مشكلة: "ModuleNotFoundError: packages.vision.ocr_cache"
**الحل:** أضف `packages/` إلى PYTHONPATH:
```bash
export PYTHONPATH="${PYTHONPATH}:$(pwd)/packages"
# أو في .env:
PYTHONPATH=/app/packages
```

### مشكلة: "Circuit breaker always open"
**الحل:** افحص حالة الـ circuit breaker:
```bash
curl http://localhost:8000/api/v2/admin/circuit-breakers
```
وأعد تعيينها:
```python
await CircuitBreakerRegistry.reset_all()
```

---

**هل تحتاج مساعدة؟** افتح issue في المستودع مع تفاصيل الخطأ ونسخة OmniMedical Suite التي تستخدمها.
