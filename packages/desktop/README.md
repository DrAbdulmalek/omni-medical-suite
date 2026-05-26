# 🏥 معالج الوثائق الطبية — الإصدار v12 المدمج

## ✨ الميزات الرئيسية

### معالجة الصور
- **قص ذكي ثنائي المراحل** — يزيل حدود الماسح الرمادي ثم يكشف المحتوى (Vectorized numpy، أسرع 100×)
- **كشف الميلان** مع إزالة الحدود الرمادية أولاً (لا زوايا خاطئة من حواف الماسح)
- **إزالة الظل** بطريقة التشكل المورفولوجي (Morphological)
- **تحسين حدة الصور** بخوارزمية USM (Unsharp Mask)
- **تقييم جودة شامل** — وضوح، تباين، كثافة الحواف، نسبة المحتوى، سطوع

### واجهة PyQt5 التفاعلية
- **LazyImage** — تحميل كسول + كاش ذاكرة لتوفير الموارد
- **محدد منطقة رقم الصفحة** — تحديد يدوي مع اختبار OCR فوري
- **حفظ تلقائي تسلسلي** بـ QTimer (لا تجميد للواجهة)
- **إلغاء عمليات الدُفعات** في أي وقت
- **لقطات شاشة** لأي عنصر ويدجت
- **سحب وإفلات** للملفات والمجلدات
- **دعم PDF** (تحويل كل صفحة إلى صورة)

### نظام التعلم التكيفي
- **AdaptiveLearner** — تعلم بسيط بالتشابه (4 معالم)
- **TrainingDataCollector** — KNN بـ 30 معلم + تنبؤ بالإعدادات المثلى
- **ImageFeatureExtractor** — استخراج 30 معلم (هيستوغرام، تدرج، إسقاطات)

### OCR متعدد المناطق
- استخراج رقم الصفحة من 8 مواقع افتراضية
- دعم منطقة مخصصة واحدة أو مناطق متعددة
- **كشف المكررات** بـ Perceptual Hash (imagehash)

## 🚀 التثبيت والتشغيل

### التثبيت التلقائي
```bash
cd packages/desktop
chmod +x install.sh
./install.sh
```

### التثبيت اليدوي
```bash
cd packages/desktop
python3 -m venv .venv --system-site-packages
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### التشغيل
```bash
source .venv/bin/activate
python medical_doc_gui.py
```

## 🧪 تشغيل الاختبارات

```bash
cd packages/desktop
source .venv/bin/activate
QT_QPA_PLATFORM=offscreen pytest -q
```

أو تشغيل ملف اختباري محدد:
```bash
pytest test_core.py -v           # اختبارات الوحدة الأساسية
pytest test_core_extra.py -v     # اختبارات إضافية (find_page_bounds, LazyImage)
pytest test_processing.py -v     # اختبارات معالجة الصور
```

## ⌨️ الاختصارات
| المفتاح | الوظيفة |
|---------|----------|
| `Ctrl+Z` | تراجع |
| `Ctrl+Y` | إعادة |
| `Ctrl+S` | حفظ الصورة الحالية |
| `→` / `←` | التنقل بين الصفحات |
| `Ctrl+D` | كشف الميلان وتصحيحه |
| `Ctrl+G` | قص ذكي |
| `F11` | ملء الشاشة |

## 📁 هيكل الملفات

```
packages/desktop/
├── medical_doc_gui.py        # الملف الرئيسي — الواجهة + المعالجة + التعلم
├── medical_doc_gui_final.py  # نسخة مطابقة (للتوافق مع الاستيرادات القديمة)
├── region_selector.py        # محدد منطقة رقم الصفحة (موديول مستقل)
├── requirements.txt          # المتطلبات
├── install.sh                # سكربت التثبيت التلقائي
├── conftest.py               # إعدادات pytest
├── test_core.py              # اختبارات الوحدة الأساسية
├── test_core_extra.py        # اختبارات إضافية
├── test_processing.py        # اختبارات معالجة الصور
└── README.md                 # هذا الملف
```

## 📦 المتطلبات

### Python Packages
- PyQt5 >= 5.15.0
- opencv-python-headless >= 4.8.0
- numpy >= 1.24.0
- pytesseract >= 0.3.10
- Pillow >= 9.0.0
- imagehash >= 4.3.0
- pdf2image >= 1.16.0 (اختياري)
- pytest >= 7.0.0 (للاختبارات)

### حزم النظام
- Tesseract OCR مع بيانات العربية والإنجليزية
- Poppler utilities (لتحويل PDF)

## 📄 الترخيص
MIT License
