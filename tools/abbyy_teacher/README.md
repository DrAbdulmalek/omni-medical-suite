# ABBYY FineReader Teacher Pipeline — خط أنابيب المعلّم

تحويل مخرجات ABBYY FineReader المدقّقة إلى بيانات تدريب للنماذج الخاصة بالمشروع
(TrOCR / PaddleOCR / CRNN / نماذج تصحيح لاحقة)، مع معمارية هجينة للإنتاج.

> **ملاحظة قانونية**: ABBYY FineReader نظام مغلق المصدر. هذه الحزمة **لا تنقل
> أي أوزان أو كود من ABBYY**؛ هي تستهلك فقط ملفات XML الناتجة عنه
> (ALTO / PAGE / FineReader XML) بعد مراجعة بشرية، وتحوّلها إلى أصول تدريب.

---

## المنهجيات الأربع المدعومة

### 1) توليد بيانات تدريب عالية الجودة (Teacher-Student / Pseudo-Labeling)
- أدخل المستندات الممسوحة إلى ABBYY FineReader وصادِر النتائج بصيغة
  **ALTO XML** أو **PAGE XML** أو **FineReader XML**.
- الملفات تمنحك **إحداثيات Bounding Boxes دقيقة** للأسطر والكلمات مع النص
  المقابل لها + درجات الثقة (WC / conf / charConfidence) + أعلام
  Suspicious.
- الحزمة تحوّل هذا إلى:
  - قصاصات أسطر وكلمات مع ملف `manifest.jsonl` يربط الصورة بالنص.
  - ملف `data.jsonl` بمخطط متوافق مع `training-data/corrections/handwriting_gt.jsonl`
    الحالي (الحقول: `ocr_text, corrected_text, language, source_file,
    page_num, confidence, created_at` + حقول إضافية: `bbox, crop_path,
    level, source_format`).
- استخدم الناتج لتدريب نموذجك المتخصص (Student Model) عبر Fine-tuning.

### 2) معالجة النصوص العربية والمعقدة (Text Alignment + تصحيح الأخطاء)
- مخرجات ABBYY تعمل كـ **Ground Truth Baseline**.
- قارنها مع نص موثوق (نسخة بشرية أو مصدر رسمي) عبر خوارزميات المحاذاة
  (`difflib.SequenceMatcher` + Levenshtein) لإنتاج أزواج
  `(ocr_text -> corrected_text)` بتغطية CER لكل زوج.
- الأزواج الناتجة تصلح لتدريب نماذج **تصحيح أخطاء OCR**
  (Seq2Seq أو LLM proofreader — راجع `src/llm/ollama_proofreader.py` القائم).

### 3) تحليل البنية (Layout Analysis & Segmentation)
- إحداثيات المناطق من ABBYY تُصدَّر بصيغة **YOLO** (`labels/*.txt` مطبَّعة
  إلى [0,1]) لتدريب نماذج تجزئة المستندات (YOLO-Doc / LayoutLM) لتحديد
  الفقرات والعناوين والجداول والصور قبل إرسالها لنموذج OCR.

### 4) النماذج الهجينة (Fallback / Cascading Architecture)
- موجِّه `CascadeRouter` يوزّع وحدات OCR حسب الثقة:
  - ثقة ≥ `accept` (افتراضي 0.92) → **النموذج الخاص** (توفير تكلفة وسرعة).
  - ثقة < `escalate` (افتراضي 0.60) → **ABBYY FineReader SDK/Engine كـ Fallback**
    لحين نضج النموذج المستقل.
  - المنطقة الرمادية → **مراجعة بشرية HITL** (يتكامل مع خدمات المراجعة القائمة).

---

## مخطط خط الأنابيب

```
[مستندات خام]
      │  (ABBYY FineReader Engine/CLI — خارجي، يدوي أو مؤتمت)
      ▼
[XML/JSON: BBoxes + Text + Confidence]  ← ALTO | PAGE | FineReader XML
      │   parse_abbyy_xml()
      ▼
[قص الأسطر/الكلمات + ربطها بالنص]      ← cropping.py (قصاصات + manifest.jsonl)
      │
      ├────────────► [محاذاة مع نص موثوق] ← alignment.py → correction pairs (تصحيح)
      ▼
[تنسيق بيانات التدريب]                 ← dataset_builder.py
      │   data.jsonl (HuggingFace)  +  layout/labels/*.txt (YOLO)
      ▼
[تدريب نموذجك: Fine-tuning]            ← TrOCR / PaddleOCR / CRNN / YOLO-Doc
      │
      ▼
[Cascade في الإنتاج]                   ← cascade.py: student / review / ABBYY fallback
```

---

## الاستخدام

### المتطلبات
```bash
pip install -r tools/abbyy_teacher/requirements.txt   # lxml, Pillow فقط
```

### أوامر CLI
```bash
# من جذر المستودع

# 1) تلخيص ملف تصدير (يتعرف تلقائياً على الصيغة)
python -m tools.abbyy_teacher parse --xml exports/page1.xml --json summary.json

# 2) قص القصاصات (أسطر + كلمات) من صورة الصفحة
python -m tools.abbyy_teacher crop --xml exports/page1.xml \
    --image scans/page1.png --out-dir training-data/crops/page1

# 3) محاذاة مخرجات ABBYY مع نص موثوق → أزواج تصحيح
python -m tools.abbyy_teacher align --xml exports/page1.xml \
    --truth-text trusted/page1.txt --out training-data/corrections/abbyy_pairs.jsonl

# 4) الخط الكامل: قصاصات + JSONL + تسميات YOLO (block + line)
python -m tools.abbyy_teacher build --xml exports/page1.xml \
    --image scans/page1.png --out-dir dataset/page1

# 5) تقرير التوجيه الهجين لصفحة
python -m tools.abbyy_teacher cascade --xml exports/page1.xml
```

### الاستخدام البرمجي
```python
from tools.abbyy_teacher import (
    parse_abbyy_xml, crop_segments, build_layout_yolo,
    line_pairs_from_trusted_text, write_ocr_jsonl, CascadeRouter,
)

ann = parse_abbyy_xml("exports/page1.xml")          # ALTO أو PAGE أو FineReader XML
print(ann.summary())                                 # {"lines": 24, "words": 210, ...}

crops = crop_segments(ann, "scans/page1.png", "crops/", levels=("line", "word"))

pairs = line_pairs_from_trusted_text(ann, trusted_text, source_file="page1.png")
write_ocr_jsonl(pairs, "training-data/corrections/abbyy_pairs.jsonl")

build_layout_yolo(ann, "dataset/layout/", image_path="scans/page1.png", level="block")

router = CascadeRouter()
report = router.route_student_result([("نص", 0.97), ("غامض", 0.41)])
print(report.counts)     # {"student": 1, "review": 0, "abbyy_fallback": 1}
```

---

## بنية الحزمة

```
tools/abbyy_teacher/
├── __init__.py         # الواجهة العامة
├── models.py           # BBox / Word / TextLine / TextBlock / PageAnnotation ...
├── xml_parsing.py      # محللات ALTO + PAGE + FineReader XML (تعرف تلقائي)
├── cropping.py         # قص القصاصات + manifest.jsonl
├── alignment.py        # CER + محاذاة + أزواج تصحيح + guess_language
├── dataset_builder.py  # JSONL (مخطط training-data) + YOLO layout + DATASET_CARD
├── cascade.py          # CascadeRouter: student / review / abbyy_fallback
├── cli.py              # python -m tools.abbyy_teacher ...
└── requirements.txt
```

## نقاط التكامل مع المشروع

| النقطة | المسار | كيف |
|---|---|---|
| عقد بيانات التصحيح | `training-data/corrections/handwriting_gt.jsonl` | نفس حقول JSONL تماماً |
| مصحح LLM القائم | `src/llm/ollama_proofreader.py` | أزواج `ocr_text/corrected_text` جاهزة للتقييم |
| المدرب اليدوي | `apps/handwriting-trainer` | القصاصات تسرّع مراجعة الكلمات |
| المراجعة البشرية | خدمات review/HITL القائمة | منطقة "review" في الموجّه |
| مجموعات HF | `app/services/hf_dataset_service.py` | `load_dataset("json", data_files=...)` مباشرة |

## صيغ XML المدعومة

| الصيغة | الجذر | الإحداثيات | الثقة |
|---|---|---|---|
| ALTO XML | `{http://www.loc.gov/standards/alto}` | `HPOS/VPOS/WIDTH/HEIGHT` | `WC` (0-1) |
| PAGE XML | `{http://schema.primaresearch.org/PAGE/gts/pagecontent}` | `Coords points` (مضلع) | `TextEquiv@conf` |
| FineReader XML | `{http://www.abbyy.com/FineReader_xml}` | `left/top/right/bottom` على `charParams` | `charConfidence` (0-100) + `suspicious` |

ملاحظات تقنية:
- كل الثقات تُطبَّع إلى `[0,1]` (تُقبل مقاييس 0-100 تلقائياً).
- الملفات متعددة الصفحات: `parse_abbyy_xml()` يعيد الصفحة الأولى،
  و`parse_abbyy_xml_all()` يعيد الكل.
- Arabic RTL: النصوص تُخزَّن كما هي منطقياً؛ إعادة البناء البصري للسطر
  تعتمد ترتيب عناصر XML كما أخرجها ABBYY.
