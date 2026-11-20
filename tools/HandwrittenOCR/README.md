# HandwrittenOCR v5.1

> مشروع استخراج وتصحيح نصوص الخط اليدوي من ملفات PDF - نظام التحسين المستمر
> يدعم: التشغيل المحلي (Offline)، المزامنة بين الأجهزة (Syncthing)، Google Colab، ترحيل البيانات

## المميزات

- **تعرف متعدد المحركات**: TrOCR (أساسي) + EasyOCR (بديل) + Ensemble
- **دعم ثنائي اللغة**: العربية والإنجليزية
- **تصحيح إملائي ذكي**: ar-corrector + pyspellchecker
- **قاموس تصحيح مستمر**: يتعلم من مراجعات المستخدم تلقائياً
- **تجزئة ذكية**: EasyOCR أولاً، الكنتورات كبديل
- **معالجة مسبقة**: تسوية الميل، CLAHE، إزالة الضوضاء، Thresholding
- **واجهة مراجعة**: Jupyter (ipywidgets) أو CLI - تعرض غير المراجعة أولاً
- **تصدير بيانات التدريب**: JSONL مع تقسيم train/val
- **رفع إلى HuggingFace**: مباشرة من الكود
- **تدريب LoRA**: Fine-tune TrOCR على تصحيحات المستخدم
- **إعادة تجميع الجمل**: مع دعم RTL للعربية
- **تخزين مؤقت**: cache_dir + EasyOCR symlink على Drive
- **نظام المزامنة**: Syncthing لمزامنة أوفلاين/أونلاين بين الأجهزة
- **قفل الملفات**: حماية قاعدة البيانات عند العمل من عدة أجهزة
- **REST API**: FastAPI مع 33 نقطة نهاية + واجهة ويب RTL عربية
- **ترحيل البيانات**: دمج تلقائي من النسخ القديمة (قواعد بيانات + تصحيحات + قاموس)

## التثبيت

### على Manjaro/Arch Linux

```bash
# تثبيت اعتماديات النظام
sudo pacman -S tesseract tesseract-data-ara poppler python python-pip base-devel

# إنشاء بيئة افتراضية
mkdir -p ~/Handwritten_OCR_Ultimate && cd ~/Handwritten_OCR_Ultimate
git clone https://github.com/DrAbdulmalek/HandwrittenOCR .
python -m venv ocr_env
source ocr_env/bin/activate
pip install -r requirements.txt
```

### على Ubuntu/Debian

```bash
sudo apt-get install -y poppler-utils tesseract-ocr tesseract-ocr-ara
pip install -r requirements.txt
```

### على Windows

```bash
# ثبّت Tesseract من https://github.com/UB-Mannheim/tesseract/wiki
# وأضفه إلى PATH
pip install -r requirements.txt
```

## الاستخدام

### التشغيل المحلي (Offline)

```bash
# التشغيل الأساسي
python run.py --local

# مع تحديد ملف PDF
python run.py --local --pdf ~/documents/notes.pdf

# مع تحديد نطاق الصفحات
python run.py --local --pdf notes.pdf --pages 1 10

# الاستماع على الشبكة المحلية (للوصول من الجوال)
python run.py --local --host 0.0.0.0

# تعطيل المزامنة
python run.py --local --no-sync
```

### التشغيل عبر CLI (متوافق مع الإصدارات السابقة)

```bash
python run.py --pdf document.pdf --pages 1 10
python run.py --hf-token hf_xxx --cache-dir ./models_cache
```

### في Google Colab

```python
from google.colab import userdata
from config import Config
from src.main import main

config = Config.from_colab_drive(
    pdf_name="document.pdf",
    hf_token=userdata.get("HF_TOKEN")
)
main(config)
```

### خادم API

```bash
# تشغيل خادم FastAPI
cd HandwrittenOCR
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

## المزامنة بين الأجهزة (الجوال + الحاسوب)

### الإعداد باستخدام Syncthing

Syncthing هو حل مجاني ومفتوح المصدر للمزامنة التلقائية بين الأجهزة.

**على الحاسوب (Manjaro):**
```bash
sudo pacman -S syncthing
systemctl --user enable --now syncthing
# افتح الواجهة: http://127.0.0.1:8384
# أضف مجلد المشروع وشاركه مع جوالك عبر QR Code
```

**على الجوال (Android):**
1. نزّل Syncthing من F-Droid أو Google Play
2. امنح صلاحية الوصول لمجلد المشروع
3. اقترن مع الحاسوب عبر QR Code
4. فعّل "Sync when on Wi-Fi only"

### الملفات التي تُزامن

| الملف/المجلد | مزامنة؟ | السبب |
|---|---|---|
| `database/handwriting_data.db` | نعم | بيانات العمل |
| `logs/user_corrections_feedback.csv` | نعم | تصحيحات المستخدم |
| `artifacts/correction_dict.json` | نعم | قاموس التصحيح |
| `exports/` | نعم | المخرجات |
| `input_pdfs/` | نعم | ملفات الإدخال |
| `models_cache/` | لا | كبير جداً (2-4 GB) |
| `runs/` | لا | TensorBoard logs |

### الوصول من الجوال

عند تشغيل الخادم بـ `--host 0.0.0.0`:
1. تأكد أن الجوال والحاسوب على نفس شبكة Wi-Fi
2. افتح من الجوال: `http://192.168.1.X:7860`
3. لمعرفة الـ IP: `ip a` في الطرفية

### قفل الملفات (منع التعارضات)

النظام يحمي قاعدة البيانات تلقائياً عند تفعيل المزامنة:
- إذا حاول جهازان معالجة نفس الملف في وقت واحد، سيظهر خطأ
- يمكنك مراجعة حالة القفل عبر API: `GET /api/sync/status`
- مهلة القفل الافتراضية: 30 ثانية

## نظام التحسين المستمر

```python
from config import Config
from src.database import HandwritingDB
from src.export import export_finetuning_dataset, push_to_huggingface
from src.finetuning import finetune_trocr_lora
from src.reconstruction import reconstruct_sentences
from src.recognition import OCREngine

# 1. معالجة ومراجعة
# ... (شغّل main أولاً، ثم راجع الكلمات)

# 2. تصدير بيانات التدريب
config = Config.from_local()
db = HandwritingDB(config.db_path)
export_finetuning_dataset(db, config.export_dir)

# 3. رفع إلى HuggingFace
push_to_huggingface(config.export_dir, "user/handwriting-dataset", config.hf_token)

# 4. تدريب LoRA
ocr_engine = OCREngine(...)
finetune_trocr_lora(
    ocr_engine.trocr_model, ocr_engine.trocr_processor,
    db, ocr_engine.device, config.lora_save_path
)

# 5. إعادة تجميع الجمل
df_sentences = reconstruct_sentences(db)
```

## هيكل المشروع

```
HandwrittenOCR/
├── config.py              # إعدادات مركزية (v5.0)
├── run.py                 # نقطة الدخول CLI
├── requirements.txt
├── .stignore              # أنماط تجاهل Syncthing
├── src/
│   ├── main.py            # التشغيل الرئيسي
│   ├── preprocessing.py   # معالجة الصور + تجزئة ذكية
│   ├── recognition.py     # Ensemble التعرف
│   ├── correction.py      # تصحيح + قاموس مستمر
│   ├── database.py        # SQLite v3 (مع timestamps)
│   ├── pdf_processor.py   # معالج PDF + حماية المزامنة
│   ├── review_ui.py       # واجهة المراجعة (Jupyter + CLI)
│   ├── export.py          # تصدير + رفع HF
│   ├── finetuning.py      # LoRA training
│   ├── reconstruction.py  # تجميع الجمل + قاموس ثنائي اللغة
│   ├── sync.py            # نظام المزامنة + قفل الملفات
│   ├── migration.py      # ترحيل البيانات من النسخ القديمة
│   ├── metrics.py         # WER/CER metrics
│   └── logger.py          # تسجيل
├── backend/
│   ├── app.py             # FastAPI (33 endpoints)
│   └── start_server.py    # بدء الخادم
├── notebooks/
│   └── handwritten_ocr_colab.ipynb
└── tests/
```

## API Endpoints (v5.1 - 33 نقطة نهاية)

| الطريقة | المسار | الوصف |
|---------|--------|-------|
| GET | `/api/health` | فحص حالة الخادم |
| GET | `/api/stats` | إحصائيات المعالجة |
| POST | `/api/process-pdf` | معالجة ملف PDF |
| GET | `/api/checkpoint` | حالة الاستئناف |
| GET | `/api/words` | قائمة الكلمات |
| PUT | `/api/words/{id}` | تحديث كلمة |
| DELETE | `/api/words/{id}` | حذف كلمة |
| GET | `/api/words/{id}/image` | صورة الكلمة |
| GET | `/api/sentences` | قائمة الجمل |
| PUT | `/api/sentences` | حفظ تصحيحات الجمل |
| GET/POST | `/api/correction-dict` | قاموس التصحيح |
| POST | `/api/export-dataset` | تصدير بيانات التدريب |
| POST | `/api/finetune` | بدء تدريب LoRA |
| POST | `/api/push-huggingface` | رفع إلى HF |
| POST | `/api/auto-export` | تصدير شامل |
| POST | `/api/backup` | نسخة احتياطية |
| GET | `/api/metrics` | WER/CER |
| GET/PUT | `/api/settings` | الإعدادات |
| GET | `/api/sync/status` | حالة المزامنة |
| GET | `/api/sync/config` | إعدادات Syncthing |
| GET | `/api/sync/stignore` | ملف .stignore |
| GET | `/api/network` | معلومات الشبكة |
| GET | `/api/migration/scan` | فحص النسخ القديمة |
| POST | `/api/migration/run` | تشغيل الترحيل |
| POST | `/api/migration/rebuild-dict` | إعادة بناء القاموس |

## التصحيحات المطبقة (مهم - يجب حفظها)

1. `!mv`/`!rm`/`!ln` shell commands -> `shutil.move`/`shutil.rmtree`/`os.symlink`
2. `SpellChecker.correction()` على جمل كاملة -> كلمة بكلمة مع حفظ الترقيم
3. `preprocess_image` ترجع binary فقط -> `(binary, enhanced)`
4. الكلمات تُقطع من الصورة الثنائية -> من `img_bgr` الأصلية
5. EasyOCR يأخذ أول نتيجة -> `max(results, key=lambda r: r[2])`
6. `cv2_imshow` من Colab -> `cv2.imwrite` + مسارات عامة
7. المسارات المرمَّجة يدوياً -> `Config` dataclass
8. `df` محلي يخرج عن التزامن مع DB -> `HandwritingDB` مباشرة
9. Status: `'yes'/'no'` -> `'verified'/'unverified'`
10. DB schema v1 -> v2 -> v3 مع ترقية تلقائية (migration)
11. LoRA -> تحميل تلقائي مع `PeftModel.from_pretrained()` إذا كان adapter موجود
12. Review UI df sync -> `df.drop(df.index[current]).reset_index(drop=True)` + تحديث `prog.max`
13. LoRA -> تحميل تلقائي مع `PeftModel.from_pretrained()` إذا كان adapter موجود
14. ترحيل البيانات -> `DataMigrator` يكشف النسخ القديمة ويرحّل الموثق فقط مع تطبيع status

## الترخيص

MIT License
