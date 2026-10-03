# Medical Document Processor + Mistral AI Integration

## نظرة عامة

هذا المشروع يدمج بين:
- **محرك معالجة الصور المحلي** (OpenCV + Tesseract) - للمعالجة السريعة
- **Mistral AI OCR 3** - للـ OCR المتقدم مع دعم الجداول والصور
- **Document Classification** - تصنيف تلقائي لنوع المستند
- **Structured Extraction** - استخراج منظم باستخدام Pydantic schemas
- **FHIR R4** - تحويل البيانات إلى معيار الرعاية الصحية

## المميزات الجديدة

| الميزة | الوصف | النقطة النهاية |
|--------|-------|---------------|
| **Mistral OCR 3** | OCR متقدم يدعم PDF + HTML tables + base64 images | `POST /mistral/ocr` |
| **Document Classification** | تصنيف تلقائي: admission, vitals, lab, prescription, radiology | `POST /mistral/classify` |
| **Structured Extraction** | استخراج منظم حسب نوع المستند | `POST /mistral/extract` |
| **FHIR Generation** | تحويل إلى FHIR R4 Bundle | مدمج في `/mistral/extract` |
| **Batch Processing** | معالجة دفعة مع rate limiting | `POST /mistral/batch` |
| **Fallback** | إذا فشل Mistral، يعود للمحرك المحلي | تلقائي |

## التثبيت السريع

```bash
# 1. نسخ الملفات
./setup_mistral.sh

# 2. إعداد المتغيرات البيئية
cp .env.example .env.local
# عدل MISTRAL_API_KEY في .env.local

# 3. تشغيل
python packages/core/api_server.py --port 8000
```

## أمثلة الاستخدام

### 1. OCR متقدم (Mistral)
```bash
curl -X POST "http://localhost:8000/mistral/ocr" \
  -F "file=@patient_packet.pdf"
```

### 2. تصنيف المستند
```bash
curl -X POST "http://localhost:8000/mistral/classify" \
  -F "file=@unknown_document.pdf"
```

### 3. استخراج + FHIR
```bash
curl -X POST "http://localhost:8000/mistral/extract" \
  -F "file=@vitals_sheet.pdf" \
  -F "doc_type=vitals"
```

### 4. معالجة كاملة (محلي + Mistral)
```bash
curl -X POST "http://localhost:8000/process" \
  -F "file=@document.jpg" \
  -F 'options={
    "deskew": true,
    "auto_crop": true,
    "use_mistral": true,
    "mistral_structured": true,
    "encrypt": true,
    "patient_id": "P-001"
  }'
```

## أنواع المستندات المدعومة

| النوع | Schema | FHIR Resources |
|-------|--------|---------------|
| `admission_form` | PatientDemographics | Patient |
| `vitals` | VitalSigns | Observation[] |
| `lab_results` | LabReport | DiagnosticReport + Observation[] |
| `prescription` | Prescription | MedicationRequest[] |
| `radiology` | RadiologyFinding | ImagingStudy |

## البنية التقنية

```
Electron App
    ↓ IPC
Python Bridge (FastAPI)
    ├── Local Engine (OpenCV + Tesseract)
    │   ├── Deskew / Crop / Blur Detection
    │   └── AES-256-GCM Encryption
    └── Mistral AI Engine (HTTP API)
        ├── OCR 3 (PDF + Tables + Images)
        ├── Document Classification
        ├── Structured Extraction (Pydantic)
        └── FHIR R4 Conversion
    ↓
SQLite (WAL mode) / PostgreSQL
```

## الأمان

- **AES-256-GCM** لتشفير الملفات
- **PBKDF2** (480,000 iteration) لاشتقاق المفاتيح
- **WAL mode** لقاعدة البيانات
- **لا يُرسل البيانات** إلى Mistral إلا بـ `use_mistral=true`
- **Fallback محلي** إذا فشل الاتصال

## الترخيص

MIT License - انظر LICENSE
