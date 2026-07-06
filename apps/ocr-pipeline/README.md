# Omni Medical OCR Pipeline

**نظام OCR طبي عربي متكامل** لمعالجة الوصفات الطبية والمستندات اليدوية.

### المميزات الرئيسية
- 4 محركات OCR (Tesseract + EasyOCR + PaddleOCR + TrOCR)
- تصحيح ذكي (HybridSpellChecker + Jais LLM)
- معالجة متقدمة للصور (deskew, CLAHE, إزالة الخطوط)
- واجهة Gradio + API + تطبيق سطح مكتب
- حفظ تلقائي في Hugging Face Datasets
- دعم كامل للخط اليدوي العربي

### التشغيل السريع

```bash
git clone https://github.com/DrAbdulmalek/omni-medical-ocr-pipeline.git
cd omni-medical-ocr-pipeline
pip install -r requirements.txt
cp .env.example .env
python app/gradio_hitl.py
```