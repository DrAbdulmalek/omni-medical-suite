# Scanner Fixer Pro v2.0 + Hugging Face Integration

## نظرة عامة

نظام متكامل لمعالجة الصور المسحوبة (Scanner Fixer) مع ربط كامل بـ Hugging Face Space و GitHub Repos.

## المكونات

### 1. GitHub Repos المدمجة (Omni Medical Suite)

| Repository | الحالة | الوصف |
|-----------|--------|-------|
| `omni-medical-suite` | **نشط** | المنصة الرئيسية المتكاملة |
| `scanner-fixer` | **نشط** | معالجة الصور المسحوبة (Pre-OCR) |
| `medical-ocr-postprocessor` | **مؤرشف** | دُمج في omni-medical-suite |
| `medical-handwriting-ocr` | **نشط** | OCR للخط اليد |
| `medical-ocr-trainer` | **نشط** | تدريب النماذج |

### 2. Hugging Face Space

- **Space**: `DrAbdulmalek/medical-ocr-demo`
- **الوظيفة**: OCR + HITL (Human-in-the-Loop) + Auto Collection

### 3. Datasets على HF

| Dataset | الوصف | الأعمدة |
|---------|-------|---------|
| `arabic-medical-ocr-corrections` | تصحيحات بشرية | image, incorrect_text, correct_text, category |
| `scanner-fixer-logs` | سجلات المعالجة | original_image, processed_image, metrics |
| `arabic-medical-ocr-training-pairs` | أزواج تدريب | image, text, category, font_type |

## الملفات المنشأة

```
scanner-fixer-pro/
├── desktop_scanner_fixer_pro_v2.py    # التطبيق الرئيسي (Tkinter + HF)
├── hf_connector.py                     # موصل HF Space API
├── hf_auto_dataset.py                  # إنشاء وإدارة Datasets
├── gradio_scanner_app.py               # واجهة ويب بديلة
├── requirements.txt                     # المتطلبات
├── build_exe.bat                        # بناء .exe
└── README.md                            # هذا الملف
```

## التثبيت

```bash
# 1. تثبيت المتطلبات
pip install -r requirements.txt

# 2. تعيين HF Token (اختياري للمساحات العامة)
set HF_TOKEN=your_token_here

# 3. تشغيل التطبيق
python desktop_scanner_fixer_pro_v2.py
```

## الاستخدام

### الوضع المحلي (بدون إنترنت)
1. اختر "Local Only"
2. حمل صورة
3. اضغط "Process + OCR"

### الوضع الهجين (محلي + HF)
1. أدخل HF Token
2. اضغط "Connect to HF"
3. اختر "Local + HF OCR"
4. المعالجة محلية + OCR عبر HF

### إرسال تصحيحات
1. صحح النص يدوياً
2. اختر التصنيف
3. اضغط "Send Correction to HF"

### إنشاء Dataset جديد
1. اضغط "Create Dataset"
2. يُنشأ تلقائياً على HF

## بناء ملف تنفيذي (.exe)

```bash
# Windows
build_exe.bat

# أو يدوياً:
pyinstaller --onefile --windowed --name "ScannerFixerPro" desktop_scanner_fixer_pro_v2.py
```

## API Reference

### HF Connector
```python
from hf_connector import HFConnector

client = HFConnector(
    space_name="DrAbdulmalek/medical-ocr-demo",
    hf_token="YOUR_TOKEN"
)
client.connect_to_space()
result = client.process_image_via_hf("image.jpg", mode="standard")
```

### Dataset Manager
```python
from hf_auto_dataset import HFAutoDatasetManager

manager = HFAutoDatasetManager(hf_token="YOUR_TOKEN")
manager.create_dataset("corrections")
manager.add_correction_record(
    dataset_name="DrAbdulmalek/arabic-medical-ocr-corrections",
    image_path="image.jpg",
    incorrect_text="خطأ",
    correct_text="صحيح"
)
```

## الميزات المتقدمة

- **Batch Processing**: معالجة مجلد كامل
- **Auto Dataset Creation**: إنشاء Dataset تلقائي
- **Local Backup**: حفظ احتياطي محلي إذا فشل الاتصال
- **Metrics Logging**: تسجيل مقاييس المعالجة
- **Multi-mode**: Local / Hybrid / HF Direct

## الترخيص

MIT License - جزء من Omni Medical Suite
