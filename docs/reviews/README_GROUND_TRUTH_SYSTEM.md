# نظام استيراد Ground Truth للتدريب
## Ground Truth Import & Training System

---

## 🎯 نظرة عامة

هذا النظام يحول ملفات **Word/RTF/PDF** المُنتجة بواسطة:
- **ABBYY FineReader**
- **ReadIRIS**
- **PDF Grabber**

إلى **أرضية حقيقية (Ground Truth)** للتدريب والتحسين المستمر لنظام OCR.

---

## 📦 الملفات

| الملف | الوصف |
|-------|-------|
| `import_ground_truth.py` | استيراد ملفات Word/RTF/HTML كـ GT |
| `gt_comparison_engine.py` | مقارنة OCR مع GT + توليد تقارير |
| `font_glyph_validator.py` | التحقق من الحروف باستخدام بيانات الخطوط |
| `training_pipeline_manager.py` | مدير أنبوب التدريب الكامل |

---

## 🚀 سير العمل

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ ABBYY           │     │ استيراد GT      │     │ قاعدة بيانات   │
│ (Word .docx)    │────▶│ import_ground_  │────▶│ Ground Truth   │
│                 │     │ truth.py        │     │                │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                        │
┌─────────────────┐     ┌──────────────────┐         │
│ ReadIRIS        │     │ استيراد GT      │         │
│ (RTF .rtf)      │────▶│                  │─────────┘
│                 │     └──────────────────┘
└─────────────────┘              │
                                 │
┌─────────────────┐     ┌──────▼───────────┐     ┌─────────────────┐
│ PDF Grabber     │     │ مقارنة + تحليل  │     │ بيانات تدريب   │
│ (glyphs.json)   │────▶│ gt_comparison_   │────▶│ Training Pairs  │
│                 │     │ engine.py        │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                 ┌────────────────────────┘
                                 │
                        ┌────────▼───────────┐
                        │ تصحيح تلقائي      │
                        │ font_glyph_        │
                        │ validator.py       │
                        └────────────────────┘
```

---

## 📖 الاستخدام

### 1️⃣ استيراد ملف ABBYY Word

```bash
python import_ground_truth.py abbyy_output.docx --output gt_abbyy.txt
```

### 2️⃣ استيراد ملف ReadIRIS RTF

```bash
python import_ground_truth.py readiris_output.rtf --output gt_readiris.txt
```

### 3️⃣ دمج مصادر متعددة

```bash
python import_ground_truth.py abbyy.docx readiris.rtf --merge --output merged_gt.txt
```

### 4️⃣ استخراج الخطوط من PDF

```bash
python import_ground_truth.py document.pdf --mode font-extract --output fonts.json
```

### 5️⃣ مقارنة OCR مع Ground Truth

```bash
python gt_comparison_engine.py --gt gt_abbyy.txt --ocr ocr_output.txt --output report.json
```

**مع توليد قاموس تصحيح تلقائي:**
```bash
python gt_comparison_engine.py --gt gt.txt --ocr ocr.txt --generate-dict --output dict.json
```

**مع توليد بيانات تدريب:**
```bash
python gt_comparison_engine.py --gt gt.txt --ocr ocr.txt --generate-training --output training.json
```

### 6️⃣ التحقق من الحروف باستخدام الخطوط

```bash
python font_glyph_validator.py --fonts fonts.json --ocr ocr.txt --output corrected.txt
```

### 7️⃣ تشغيل الأنبوب الكامل

```bash
python training_pipeline_manager.py --gt abbyy.docx --image doc.jpg --run-all
```

---

## 📊 مخرجات النظام

| الملف | الوصف |
|-------|-------|
| `ground_truth.txt` | النص الصحيح المستخرج |
| `ground_truth.json` | بيانات منظمة مع metadata |
| `report_*.json` | تقارير المقارنة (CER/WER) |
| `report_*_dict.json` | قاموس تصحيح تلقائي |
| `report_*_training.json` | أزواج تدريب |
| `training_pairs.json` | بيانات تدريب مجمعة |
| `training_pairs.csv` | تصدير CSV |

---

## 🔧 متطلبات التشغيل

```bash
pip install python-docx striprtf beautifulsoup4 PyMuPDF
```

---

## 🎯 الفائدة من كل تطبيق

| التطبيق | المخرج | الاستخدام |
|---------|--------|----------|
| **ABBYY FineReader** | `.docx` دقيق | GT أساسي — أعلى دقة |
| **ReadIRIS** | `.rtf` منظم | GT ثانوي — للتحقق |
| **PDF Grabber** | `glyphs.json` | التحقق من الحروف + الخطوط |

---

## 💡 مثال عملي

```bash
# 1. استخرج GT من ABBYY
python import_ground_truth.py "page_588_abbyy.docx" --output gt_588.txt

# 2. شغّل OCR
python snippet_cli.py process "Scanned Document-588.jpg" --engine paddleocr

# 3. قارن النتائج
python gt_comparison_engine.py     --gt gt_588.txt     --ocr ocr_output.txt     --output benchmark_588.json     --generate-dict     --generate-training

# 4. صحّح باستخدام الخطوط (إن وجدت)
python font_glyph_validator.py     --fonts fonts_588.json     --ocr ocr_output.txt     --output ocr_corrected.txt

# 5. دمّج في القاموس
# أضف `dict.json` إلى `arabic_medical_dict.json`
```

---

## 🔄 التحسين المستمر

كلما زادت الملفات المستوردة:
1. يتوسع **قاموس التصحيح** تلقائياً
2. تتحسن **دقة OCR** بشكل تدريجي
3. يتعلم النظام **أنماط أخطاء جديدة**

---

**الإصدار:** 1.0.0 | **التاريخ:** 2026-06-04
