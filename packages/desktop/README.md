# معالج الوثائق الطبية — تطبيق سطح المكتب

> معالج تفاعلي لصور المستندات الطبية الممسوحة ضوئياً، يدعم تصحيح الميلان، القص الذكي،
> إزالة الظل، كشف التكرار، والتنسيق الكامل عبر `scanner_fixer`.

## البناء من المصدر

### المتطلبات

```bash
# تبعيات Python
pip install -r requirements.txt

# مكتبة scanner_fixer (مطلوبة للتكامل الكامل)
pip install -e ../scanner_fixer

# PyInstaller (للبناء فقط)
pip install pyinstaller
```

### متطلبات النظام (Manjaro Linux / KDE Plasma)

```bash
# مكتبات Qt النظامية (مطلوبة لتشغيل PySide6)
sudo pacman -S qt6-base qt6-wayland

# Tesseract OCR (اختياري — لكشف أرقام الصفحات)
sudo pacman -S tesseract tesseract-data-eng

# Poppler (اختياري — لدعم PDF)
sudo pacman -S poppler
```

### البناء

```bash
cd packages/desktop
bash build.sh
```

الناتج: `dist/medical-doc-processor` — ملف تنفيذي ELF 64-bit واحد.

### التشغيل بدون بناء

```bash
cd packages/desktop
python medical_doc_gui_final.py
```

## الميزات

| الميزة | الوصف |
|--------|-------|
| 📐 كشف ميلان | يستخدم `scanner_fixer.deskew` (Hough lines) مع احتياط projection |
| ✂️ قص ذكي | يستخدم `scanner_fixer.crop` (morphological) مع احتياط ثنائي المراحل |
| 🔄 تنسيق كامل | `scanner_fixer.normalize` pipeline: deskew + crop + resize |
| 🔍 كشف تكرار | `scanner_fixer.dedup` phash — يُنتج تقرير CSV |
| 🖼️ إزالة رمادي | يُزيل حدود الماسح الرمادية |
| 🔎 مقارنة | مقارنة قبل/بعد |
| 💾 حفظ ذكي | OCR + ترقيم صفحات تلقائي |
| 🤖 تعلم تكيفي | KNN + TrainingDataCollector |
| 📊 تحليل دفعي | حفظ تلقائي لكل الصور |

## الاختبارات

```bash
cd packages/desktop
pytest test_core.py -v
```

## هيكل الملفات

```
packages/desktop/
├── medical_doc_gui_final.py   # التطبيق الرئيسي (مصدر الحقيقة الوحيد)
├── test_core.py               # اختبارات الوحدة
├── test_processing.py         # اختبارات المعالجة
├── conftest.py                # إعدادات pytest
├── requirements.txt           # تبعيات Python
├── build_executable.spec      # إعدادات PyInstaller
├── build.sh                   # سكربت البناء
├── README.md                  # هذا الملف
├── install.sh                 # سكربت التثبيت
└── region_selector.py         # محدد المناطق
```

## التراجع (Fallback)

عند عدم توفر `scanner_fixer`، يعود التطبيق تلقائياً للمنطق الداخلي الأصلي:
- **كشف الميلان**: projection profile (طريقة التباين الأصلية)
- **القص الذكي**: طريقة ثنائية المراحل (find_page_bounds + content detection)

هذا يضمن عمل التطبيق حتى بدون `scanner_fixer` مثبتاً.
