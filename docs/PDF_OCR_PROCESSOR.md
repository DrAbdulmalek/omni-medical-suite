# 📄 PDF OCR Processor — توثيق

## وصف النظام

نظام **PDF OCR Processor** هو أداة متكاملة لاستخراج النص والمسارد من ملفات PDF الطبية. يجمع بين:

- **OCR متقدم** (Tesseract) مع ضبط تلقائي لمعاملات PSM و DPI
- **معالجة مسبقة** للصور عبر scanner_fixer (تصحيح الميل، قص تلقائي، تطبيع، تحسين التباين)
- **استخراج المسارد** الثنائية اللغة (عربي-إنجليزي) تلقائياً
- **حفظ النتائج** في تنسيقات متعددة (TXT, CSV, JSON)
- **تكامل مع نظام التسجيل المتقدم** (advanced_logger)

## المتطلبات

### حزم النظام (Manjaro)
```bash
sudo pacman -S tesseract tesseract-data-ara tesseract-data-eng poppler
```

### حزم Python
```bash
pip install -r requirements/ml.txt
# أو يدوياً:
pip install pytesseract pdf2image PyMuPDF pdfplumber opencv-python Pillow numpy pandas img2pdf
```

## الاستخدام

### الطريقة 1: تشغيل مباشر
```bash
cd ~/omni-medical-suite

# معالجة كل PDF في data/
python3 scripts/pdf_ocr_processor.py

# ملف واحد
python3 scripts/pdf_ocr_processor.py --input report.pdf

# مع ضبط تلقائي وإخراج مخصص
python3 scripts/pdf_ocr_processor.py --input report.pdf --auto-tune --output ~/my_output/
```

### الطريقة 2: باستخدام سكربت التشغيل
```bash
# معالجة data/
./scripts/run_ocr.sh

# مع توكن ومسار مخصص
./scripts/run_ocr.sh ghp_your_token /path/to/pdfs/
```

### الطريقة 3: من Python
```python
from scripts.pdf_ocr_processor import PDFOCRProcessor

proc = PDFOCRProcessor(
    output_dir="~/glossaries_output",
    language="ara+eng",
    auto_tune=True,
    normalize_images=True,
)

# ملف واحد
result = proc.process_pdf("medical_report.pdf")
print(f"Pages: {result['pages']}, Entries: {result['entries_found']}")

# مجلد كامل
results = proc.process_directory("data/")
```

## خيارات سطر الأوامر

| الخيار | الوصف | افتراضي |
|--------|-------|----------|
| `--input, -i` | مسار ملف PDF أو مجلد | `data/` |
| `--output, -o` | مجلد الإخراج | `~/glossaries_output` |
| `--language, -l` | لغة OCR لـ Tesseract | `ara+eng` |
| `--no-auto-tune` | تعطيل الضبط التلقائي | (مفعّل) |
| `--no-normalize` | تعطيل المعالجة المسبقة | (مفعّلة) |
| `--psm` | PSM mode يدوي (3, 4, 6, 11) | تلقائي |
| `--dpi` | DPI يدوي (200, 300, 400) | تلقائي |
| `--verbose, -v` | تسجيل مفصّل | (معطّل) |

## المخرجات

بعد المعالجة، ستجد في مجلد الإخراج:

```
~/glossaries_output/
├── report.txt               # النص الكامل المستخرج
├── report.csv               # المسارد (term_arabic, term_english, source)
├── report.json              # النتيجة الكاملة (JSON)
├── combined_glossary.csv    # مسارد موحدة من كل الملفات
├── combined_glossary.json   # مسارد موحدة (JSON)
└── OCR_PROCESSING_LOG.md    # سجل المعالجة
```

### تنسيق CSV
```csv
term_arabic,term_english,source
مرض,disease,report.pdf
علاج,treatment,report.pdf
تشخيص,diagnosis,report.pdf
```

### تنسيق JSON
```json
{
  "file": "report.pdf",
  "pages": 15,
  "entries_found": 42,
  "best_config": {"psm": 6, "dpi": 300, "language": "ara+eng"},
  "processing_time_seconds": 45.2,
  "glossary_entries": [
    {"term_arabic": "مرض", "term_english": "disease", "source": "report.pdf"}
  ]
}
```

## الضبط التلقائي

يستخدم النظام **ضبطاً تلقائياً** لمعاملات OCR للحصول على أفضل نتائج:

### ما يتم تجربته
- **PSM** (Page Segmentation Mode): قيم 3, 4, 6, 11
- **DPI** (Dots Per Inch): قيم 200, 300, 400
- **المعالجة المسبقة**: deskew + crop + enhance عبر scanner_fixer

### كيفية العمل
1. يأخذ الصفحة الأولى من PDF
2. يجرّب كل التوليفات الممكنة (4 PSM × 3 DPI = 12 تجربة)
3. يقيم جودة النص المستخرج بناءً على:
   - طول النص (أطول = أفضل عادةً)
   - نسبة الأحرف العربية
   - عدد الكلمات
   - تناسق أطوال الأسطر
4. يختار أفضل إعداد
5. يستخدم نفس الإعداد لجميع الصفحات

### تجاوز الضبط التلقائي
```bash
# استخدام PSM=4 و DPI=400 يدوياً
python3 scripts/pdf_ocr_processor.py --input report.pdf --psm 4 --dpi 400
```

## استخراج المسارد

يبحث النظام تلقائياً عن أنماط ثنائية اللغة في النص المستخرج:

| النمط | مثال |
|-------|-------|
| `العربية = English` | مرض = disease |
| `العربية - English` | علاج - treatment |
| `العربية : English` | تشخيص : diagnosis |
| `العربية\tEnglish` | جراحة\t surgery |

### آلية الاستخراج
1. يحلل كل سطر في النص المستخرج
2. يبحث عن أنماط الفصل (=, -, :, tab)
3. يحدد الجانب العربي والجانب الإنجليزي تلقائياً
4. يزيل التكرارات
5. يضيف اسم الملف المصدر لكل مُدخلة

## دمج مع نظام التسجيل

عندما يكون `scripts/advanced_logger.py` متاحاً، يسجّل المعالج تلقائياً:
- اسم الملف المعالج
- عدد الصفحات والمُدخلات
- الإعداد المستخدم
- وقت المعالجة

السجلات تُحفظ في `logs/user_actions/actions_YYYYMMDD.jsonl`.

## استكشاف الأخطاء

### Tesseract غير مثبت
```bash
sudo pacman -S tesseract tesseract-data-ara tesseract-data-eng
tesseract --list-langs  # تحقق
```

### pdf2image / poppler غير متاح
```bash
sudo pacman -S poppler
pip install pdf2image
```

### لا توجد ملفات PDF
```bash
mkdir -p data/
cp /path/to/pdfs/*.pdf data/
```

### خطأ في PyMuPDF
```bash
pip install PyMuPDF --upgrade
```

## البنية التقنية

```
PDF File
    │
    ├── PyMuPDF (fitz) ──→ صور PIL (سريع، مُفضّل)
    │
    └── pdf2image (poppler) ──→ صور PIL (احتياطي)
          │
          ▼
    scanner_fixer pipeline
    ├── detect_skew_angle()
    ├── auto_crop()
    ├── enhance_for_ocr()
    └── normalize_scanned_image()
          │
          ▼
    Tesseract OCR
    ├── Auto-tune: PSM × DPI grid search
    └── Best config → process all pages
          │
          ▼
    Post-processing
    ├── Arabic RTL fixing (optional)
    ├── Glossary extraction (regex patterns)
    └── Export (TXT, CSV, JSON)
```

## الترخيص

MIT License — جزء من Omni Medical Suite
