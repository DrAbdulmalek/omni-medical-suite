# 🔧 تحسين Medical OCR Trainer لـ Hugging Face Spaces Free Tier

## المشاكل التي تم حلها

### 1. ❌ AxiosError 403 عند رفع الملفات
**السبب:** Streamlit يُفعّل `enableXsrfProtection` افتراضياً، لكن Hugging Face proxy لا يمرّر XSRF token بشكل صحيح.

**الحل:** 
- إضافة `.streamlit/config.toml` مع `enableXsrfProtection = false`
- إضافة `--server.enableXsrfProtection=false` في `Dockerfile` CMD

### 2. ❌ فقدان البيانات عند إعادة تشغيل الحاوية
**السبب:** كانت المسارات النسبية (`uploads/`, `crops/`, `data/`) تُحذف مع إعادة تشغيل الحاوية.

**الحل:** 
- تغيير المسارات لتستخدم `/data/` على Hugging Face Spaces (المجلد الوحيد الدائم)
- إضافة `IS_HF_SPACE = os.environ.get("SPACE_ID") is not None` للكشف التلقائي

### 3. ❌ فشل البناء بسبب نفاد RAM (16GB limit)
**السبب:** `requirements.txt` كان يحتوي على TrOCR (~1.5GB) + Surya (~800MB) + torch CUDA (~10GB).

**الحل:**
- حذف TrOCR، Surya، transformers، sentencepiece
- استخدام `torch --index-url https://download.pytorch.org/whl/cpu` (CPU-only)
- تثبيت torch أولاً في Dockerfile قبل باقي المتطلبات

### 4. ❌ Dockerfile معقد ويحتوي على `pre_download_models.py` المعطل
**السبب:** `pre_download_models.py` كان يحاول تحميل نماذج TrOCR/Surya التي لا نستخدمها.

**الحل:**
- حذف `pre_download_models.py`
- تبسيط Dockerfile مع تحميل مسبق لـ PaddleOCR + EasyOCR فقط

---

## 📁 الملفات المعدّلة

| الملف | التغييرات |
|---|---|
| `app.py` | مسارات `/data/`، 3 محركات افتراضية، تحسينات HF |
| `requirements.txt` | حذف TrOCR/Surya/torchvision، إضافة opencv-python-headless |
| `Dockerfile` | تبسيط، torch CPU-only، إعدادات Streamlit الصحيحة |
| `.streamlit/config.toml` | **جديد** — تعطيل XSRF، CORS، إعدادات المنفذ |
| `pre_download_models.py` | **حذف** — غير ضروري |

---

## 🧪 اختبار

```bash
# بناء محلي
docker build -t medical-ocr-hf .
docker run -p 7860:7860 -v $(pwd)/data:/data medical-ocr-hf

# فتح http://localhost:7860
# جرب رفع صورة — يجب أن يعمل بدون 403
```

---

## ⚠️ ملاحظات

- **البيانات الحالية ستُفقد** عند التبديل إلى `/data/` (متوقع)
- **TrOCR/Surya غير متاحين** على Free Tier (يحتاجان ترقية إلى Pro)
- **أول تشغيل** قد يستغرق 2-3 دقائق لتحميل نماذج PaddleOCR/EasyOCR
