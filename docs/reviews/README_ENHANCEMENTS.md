# OmniMedical Suite v2.1 — Enhancement Package

## 📦 محتويات الحزمة

هذه الحزمة تحتوي على **7 تحسينات رئيسية** + **4 ملفات مساعدة** لرفع OmniMedical Suite من v2.0 إلى v2.1.

---

## 🎯 التحسينات السبعة

### 1. OpenAPI/Swagger UI (`services/api/main.py`)
- **الوصف:** وثائق API تفاعلية مع دعم عربي/إنجليزي
- **المميزات:**
  - Swagger UI على `/docs` و ReDoc على `/redoc`
  - تصنيف endpoints حسب المجال (OCR, Medical, Admin)
  - Security schemes (Bearer JWT + API Key)
  - أمثلة تفاعلية لكل endpoint
- **الملف:** `services/api/main.py` (18,735 bytes)

### 2. CONTRIBUTING.md (`CONTRIBUTING.md`)
- **الوصف:** دليل شامل للمساهمين الجدد
- **المميزات:**
  - إعداد بيئة التطوير (Docker + Manual)
  - قواعد الكتابة (Python + TypeScript)
  - أنواع commits المقبولة
  - معايير القبول (Definition of Done)
- **الملف:** `CONTRIBUTING.md` (8,805 bytes)

### 3. BenchmarkSuite JSON (`data/benchmarks/*.json`)
- **الوصف:** 4 ملفات JSON بنتائج اختبارات موضوعية
- **المميزات:**
  - `ocr_fusion_v1_vs_v2.json` — إثبات تحسن +14% في accuracy
  - `medical_context_protector.json` — إثبات منع 99% من الدمج الخاطئ
  - `auto_promotion_engine.json` — تسريع 624x في المراجعة
  - `qdrant_vs_faiss.json` — مقارنة Vector DB
- **الملفات:** 4 JSON files (7,052 bytes total)

### 4. OCR Cache (`packages/vision/ocr_cache.py`)
- **الوصف:** تخزين مؤقت لنتائج OCR باستخدام Redis
- **المميزات:**
  - SHA-256 fingerprinting
  - TTL 24 ساعة مع LRU eviction
  - دعم multi-tenant isolation
  - إحصائيات cache (hits/misses/stores)
- **الملف:** `packages/vision/ocr_cache.py` (7,936 bytes)

### 5. Circuit Breaker (`packages/vision/circuit_breaker.py`)
- **الوصف:** حماية من فشل محركات OCR الخارجية
- **المميزات:**
  - حالات: CLOSED → OPEN → HALF-OPEN
  - إعدادات مخصصة لكل محرك (Mistral: 3 failures, 60s timeout)
  - Registry مركزي لإدارة جميع الـ circuit breakers
  - Metrics و Admin endpoints
- **الملف:** `packages/vision/circuit_breaker.py` (9,946 bytes)

### 6. Per-User Rate Limiter (`packages/security/user_rate_limiter.py`)
- **الوصف:** تقييد الطلبات على مستوى المستخدم (بدلاً من endpoint)
- **المميزات:**
  - Sliding window (عكس fixed window)
  - Tier-based limits (free/standard/premium/enterprise)
  - Burst allowance للـ traffic spikes
  - Penalty box للـ abuse المتكرر
  - Admin override
- **الملف:** `packages/security/user_rate_limiter.py` (9,029 bytes)

### 7. Medical Validator (`packages/medical/medical_validator.py`)
- **الوصف:** تحقق طبي ذكي من النصوص المستخرجة
- **المميزات:**
  - التحقق من منطقية الجرعات (مثلاً: هل 50mg Paracetamol منطقي؟)
  - كشف التعارضات الدوائية
  - التحقق من التسلسل الزمني
  - التحقق من المصطلحات الطبية
  - التحقق من الجانبية (يمين/يسار)
  - دعم LLM-based validation (اختياري)
- **الملف:** `packages/medical/medical_validator.py` (15,336 bytes)

### 8. FHIR/HL7 Exporter (`packages/export/fhir_exporter.py`)
- **الوصف:** تصدير المستندات بصيغ قياسية للقطاع الصحي
- **المميزات:**
  - **FHIR R4 Bundle** — DocumentReference, Patient, Observation, MedicationRequest, Provenance
  - **HL7 v2.5** — ORU^R01, MDM^T02
  - **Custom JSON** — للأنظمة الداخلية
  - LOINC/SNOMED coding
  - SHA-256 integrity hashing
  - Arabic text support
- **الملف:** `packages/export/fhir_exporter.py` (16,517 bytes)

---

## 📚 الملفات المساعدة

### INTEGRATION_GUIDE.md (11,311 bytes)
دليل خطوة بخطوة لدمج جميع التحسينات في المشروع الحالي.

### docker-compose.dev.yml (3,372 bytes)
Docker Compose مُبسَّط للتطوير (Web + API + Redis فقط).

---

## 🚀 طريقة الاستخدام السريعة

```bash
# 1. استخرج الحزمة في جذر المشروع
cd omni-medical-suite

# 2. نسخ الملفات
# (اتبع INTEGRATION_GUIDE.md للتفاصيل الكاملة)

# 3. التشغيل السريع
npm run docker:up
# أو
docker compose -f docker-compose.dev.yml up

# 4. الوصول
# Web UI:     http://localhost:3000
# Swagger:    http://localhost:8000/docs
# ReDoc:      http://localhost:8000/redoc
# Health:     http://localhost:8000/api/v2/health
```

---

## 📊 إحصائيات الحزمة

| المقياس | القيمة |
|---------|--------|
| إجمالي الملفات | 13 |
| إجمالي الحجم | ~105 KB |
| سطور Python الجديدة | ~1,100 |
| سطور Markdown | ~600 |
| JSON benchmarks | 4 |

---

## ⚠️ ملاحظات هامة

1. **Python 3.10+ مطلوب** — استخدم `typing` modern syntax
2. **Redis 7+ مطلوب** — للـ Cache, Rate Limiting, و Circuit Breaker
3. **Tesseract 5+ اختياري** — للـ OCR المحلي
4. **GPU اختياري** — للـ TrOCR fine-tuning فقط

---

## 🔗 روابط مفيدة

- [FastAPI OpenAPI Docs](https://fastapi.tiangolo.com/tutorial/metadata/)
- [FHIR R4 Specification](https://hl7.org/fhir/R4/)
- [HL7 v2.5 Specification](https://hl7.org/implement/standards/product_brief.cfm?product_id=144)
- [Redis Best Practices](https://redis.io/docs/management/)

---

**الإصدار:** 2.1.0-enhancements  
**التاريخ:** 2026-05-27  
**المؤلف:** Dr. Abdulmalek / OmniMedical Suite
