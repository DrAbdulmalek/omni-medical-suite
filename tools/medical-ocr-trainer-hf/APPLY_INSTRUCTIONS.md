# 🚀 تعليمات التطبيق

## الخطوة 1: استخراج الملفات

استخرج محتويات هذا المجلد (`medical-ocr-trainer-hf-optimized/`) إلى مستودعك:

```bash
cd medical-ocr-trainer-hf

# نسخ الملفات الجديدة
cp /path/to/medical-ocr-trainer-hf-optimized/app.py .
cp /path/to/medical-ocr-trainer-hf-optimized/requirements.txt .
cp /path/to/medical-ocr-trainer-hf-optimized/Dockerfile .
cp /path/to/medical-ocr-trainer-hf-optimized/.streamlit/config.toml .streamlit/

# حذف الملفات القديمة غير الضرورية
rm -f pre_download_models.py

# git add
git add app.py requirements.txt Dockerfile .streamlit/config.toml
git rm pre_download_models.py || true
git commit -m "Optimize for HF Free Tier: fix 403 upload, /data/ paths, remove heavy engines"
git push
```

## الخطوة 2: Factory Rebuild على Hugging Face

1. افتح: https://huggingface.co/spaces/DrAbdulmalek/medical-ocr-trainer/settings
2. اضغط **"Factory Rebuild"**
3. انتظر 5-10 دقائق

## الخطوة 3: اختبار

1. افتح: https://huggingface.co/spaces/DrAbdulmalek/medical-ocr-trainer
2. ارفع صورة JPG/PNG صغيرة (~100KB)
3. يجب أن يعمل بدون "AxiosError 403"

---

## 📋 قائمة التحقق

- [ ] `app.py` — مسارات `/data/` ✅
- [ ] `requirements.txt` — بدون TrOCR/Surya ✅
- [ ] `Dockerfile` — torch CPU-only ✅
- [ ] `.streamlit/config.toml` — `enableXsrfProtection = false` ✅
- [ ] `pre_download_models.py` — محذوف ✅
- [ ] Factory Rebuild منفذ ✅
