# دليل دمج نظام القصاصات التفاعلي في medical_doc_gui

## نظرة عامة

هذا النظام يحول صورة النص إلى **قصاصات نصية (snippets)**، كل قصاصة مقابلها:
- صورة مقتطعة من المستند الأصلي
- النص المقروء بالـ OCR
- حقل قابل للتعديل من قبل المستخدم
- نظام تعلم يتعلم من كل تصحيح

## الملفات

| الملف | الوصف |
|-------|-------|
| `ocr_snippet_trainer.py` | المحرك الأساسي — التجزئة، OCR، التعلم |
| `snippet_review_ui.py` | واجهة Tkinter التفاعلية |
| `snippet_cli.py` | واجهة سطر الأوامر |
| `arabic_medical_dict.json` | القاموس الطبي |

## التثبيت

```bash
pip install opencv-python pillow pytesseract easyocr paddleocr
pip install arabic-reshaper python-bidi
```

## الدمج في medical_doc_gui (3 خطوات)

### الخطوة 1: استيراد المحرك

```python
# في أعلى medical_doc_gui_v13.py
from ocr_snippet_trainer import OCRSnippetTrainer

# تهيئة عالمية
trainer = OCRSnippetTrainer(
    db_path="data/ocr_snippets.db",
    dictionary_path="data/arabic_medical_dict.json"
)
```

### الخطوة 2: تعديل دالة المعالجة

```python
def process_image_with_snippets(self, image_path):
    """معالجة الصورة بالقصاصات مع إمكانية المراجعة."""

    # 1. معالجة الصورة إلى قصاصات
    snippets = trainer.process_image(image_path)

    # 2. عرض القصاصات للمستخدم
    self.show_snippet_review_dialog(snippets)

    # 3. بعد المراجعة، دمج النصوص المصححة
    corrected_text = "\n".join(
        s.corrected_text for s in snippets
    )

    return corrected_text
```

### الخطوة 3: إضافة نافذة المراجعة

```python
def show_snippet_review_dialog(self, snippets):
    """نافذة مراجعة القصاصات."""
    dialog = tk.Toplevel(self.root)
    dialog.title("مراجعة نصوص OCR")
    dialog.geometry("1000x700")

    current = [0]  # mutable index

    def show_snippet(idx):
        s = snippets[idx]
        img_label.config(image=s.photo)  # تحميل الصورة
        ocr_label.config(text=f"OCR: {s.ocr_text}")
        text_widget.delete("1.0", tk.END)
        text_widget.insert("1.0", s.corrected_text)
        status_label.config(text=f"{idx+1} / {len(snippets)}")

    def save_and_next():
        s = snippets[current[0]]
        corrected = text_widget.get("1.0", tk.END).strip()

        # حفظ التصحيح والتعلم منه
        result = trainer.submit_correction(s.id, corrected)

        # الانتقال للتالي
        if current[0] < len(snippets) - 1:
            current[0] += 1
            show_snippet(current[0])
        else:
            dialog.destroy()

    # ... (عناصر الواجهة)
```

## سير العمل الكامل

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  صورة      │────▶│  تجزئة      │────▶│  قصاصات    │
│  مستند     │     │  (Contour)   │     │  نصية      │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                │
┌─────────────┐     ┌──────────────┐     ┌─────▼──────┐
│  نص نهائي  │◀────│  دمج نصوص  │◀────│  مراجعة   │
│  مصحح      │     │  مصححة      │     │  المستخدم │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                  │
                                         ┌────────▼────────┐
                                         │  تعلم الأنماط   │
                                         │  PatternLearner │
                                         └─────────────────┘
```

## أوامر CLI

```bash
# معالجة صورة
python snippet_cli.py process document.jpg --method contour --engine paddleocr

# مراجعة تفاعلية
python snippet_cli.py review --limit 20

# تصحيح نص
python snippet_cli.py correct "الشثل الدماغي"

# إحصائيات
python snippet_cli.py stats

# تصدير بيانات التدريب
python snippet_cli.py export training_data.json
```

## الواجهة التفاعلية (GUI)

```bash
python snippet_review_ui.py
```

**اختصارات لوحة المفاتيح:**
- `← →` — التنقل بين القصاصات
- `Enter` — حفظ التصحيح
- `Space` — تأكيد صحة النص
- `Escape` — تخطي

## قاعدة البيانات

SQLite database: `ocr_snippets.db`

**الجداول:**
- `snippets` — القصاصات مع OCR + تصحيح المستخدم
- `patterns` — الأنماط المتعلمة
- `learning_log` — سجل أحداث التعلم

## التوسع المستقبلي

1. **TrOCR Fine-tuning** — استخدام بيانات التدريب لضبط نموذج TrOCR
2. **Active Learning** — اختيار العينات الأكثر فائدة للمراجعة
3. **Multi-user** — دعم مراجعين متعددين مع توافق الآراء
4. **Cloud sync** — مزامنة قاعدة البيانات مع الخادم
