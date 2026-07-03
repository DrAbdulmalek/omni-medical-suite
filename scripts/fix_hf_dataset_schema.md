# Fix HuggingFace Dataset Schema — إصلاح مخطط بيانات هوجينج فيس

## 🇬🇧 English

### The Problem

The HuggingFace dataset `arabic-medical-ocr-corrections` fails in the dataset viewer with a `DatasetGenerationError` / `CastError`.  
This happens because the JSONL source file contains **inconsistent schemas** across rows:

| Issue | Example |
|---|---|
| **Missing columns** | Some rows lack `source` or `correction_type` |
| **Extra columns** | Some rows have `ocr_text`, `fixed_text`, `src` instead of canonical names |
| **Type mismatches** | `language` is `int` in some rows and `str` in others |

HuggingFace Datasets infers the schema from the first few rows. When later rows don't match, the viewer crashes.

### How to Run the Fix Script

```bash
# Basic usage
python scripts/fix_hf_dataset_schema.py \
    --input  raw_data.jsonl \
    --output fixed_data.jsonl

# With a custom dataset card output directory
python scripts/fix_hf_dataset_schema.py \
    --input  raw_data.jsonl \
    --output fixed_data.jsonl \
    --card-dir ./hf-repo
```

The script will:
1. Load and analyze the JSONL file
2. Print a detailed schema report (missing/extra columns, type mismatches)
3. Normalize every row to the canonical schema
4. Write the fixed JSONL file
5. Generate a `dataset_card.md` ready for HuggingFace

### Canonical Schema

All output rows conform to:

| Column | Type | Description |
|---|---|---|
| `original_text` | `str` | Raw OCR text |
| `corrected_text` | `str` | Corrected text |
| `source` | `str` | Data source (default: `unknown`) |
| `language` | `str` | Language code (default: `ar`) |
| `correction_type` | `str` | Correction category (default: `general`) |

### How to Re-upload to HuggingFace

```bash
# 1. Install the Hub library
pip install huggingface_hub

# 2. Create or clone your dataset repo
huggingface-cli repo create arabic-medical-ocr-corrections --type dataset
git clone https://huggingface.co/datasets/<your-username>/arabic-medical-ocr-corrections
cd arabic-medical-ocr-corrections

# 3. Copy the fixed file and dataset card
cp /path/to/fixed_data.jsonl ./data/train.jsonl
cp /path/to/dataset_card.md ./README.md

# 4. Commit and push
git add .
git commit -m "Fix schema: normalize to canonical columns, resolve type mismatches"
git push
```

After pushing, the HuggingFace dataset viewer will automatically re-build and the `CastError` will be resolved.

---

## 🇸🇦 العربية

### المشكلة

مجموعة بيانات `arabic-medical-ocr-corrections` على هوجينج فيس تفشل في عارض البيانات مع خطأ `DatasetGenerationError` / `CastError`.  
السبب هو أن ملف JSONL المصدر يحتوي على **مخطط غير متسق** بين الصفوف:

| المشكلة | مثال |
|---|---|
| **أعمدة مفقودة** | بعض الصفوف تفتقر إلى `source` أو `correction_type` |
| **أعمدة إضافية** | بعض الصفوف تحتوي على `ocr_text` أو `fixed_text` بدلاً من الأسماء القياسية |
| **تناقض في الأنواع** | `language` عدد صحيح في بعض الصفوف ونص في أخرى |

هوجينج فيس تستنتج المخطط من أول صفوف. عندما لا تتطابق الصفوف اللاحقة، يتعطل العارض.

### كيفية تشغيل سكريبت الإصلاح

```bash
# الاستخدام الأساسي
python scripts/fix_hf_dataset_schema.py \
    --input  raw_data.jsonl \
    --output fixed_data.jsonl

# مع مجلد مخصص لبطاقة البيانات
python scripts/fix_hf_dataset_schema.py \
    --input  raw_data.jsonl \
    --output fixed_data.jsonl \
    --card-dir ./hf-repo
```

السكريبت يقوم بـ:
1. تحميل وتحليل ملف JSONL
2. طباعة تقرير تفصيلي عن المخطط (أعمدة مفقودة/إضافية، تناقض الأنواع)
3. توحيد كل صفوف إلى المخطط القياسي
4. كتابة ملف JSONL المُصلح
5. إنشاء `dataset_card.md` جاهز لهوجينج فيس

### المخطط القياسي

كل صفوف المخرجات تتوافق مع:

| العمود | النوع | الوصف |
|---|---|---|
| `original_text` | `str` | النص الخام من OCR |
| `corrected_text` | `str` | النص المصحح |
| `source` | `str` | مصدر البيانات (الافتراضي: `unknown`) |
| `language` | `str` | رمز اللغة (الافتراضي: `ar`) |
| `correction_type` | `str` | فئة التصحيح (الافتراضي: `general`) |

### كيفية إعادة الرفع إلى هوجينج فيس

```bash
# 1. تثبيت مكتبة Hub
pip install huggingface_hub

# 2. إنشاء أو استنساخ مستودع البيانات
huggingface-cli repo create arabic-medical-ocr-corrections --type dataset
git clone https://huggingface.co/datasets/<your-username>/arabic-medical-ocr-corrections
cd arabic-medical-ocr-corrections

# 3. نسخ الملف المُصلح وبطاقة البيانات
cp /path/to/fixed_data.jsonl ./data/train.jsonl
cp /path/to/dataset_card.md ./README.md

# 4. إرسال ودفع التغييرات
git add .
git commit -m "Fix schema: normalize to canonical columns, resolve type mismatches"
git push
```

بعد الدفع، سيعيد عارض هوجينج فيس بناء البيانات تلقائياً وسيتم حل خطأ `CastError`.