# Readiris Teacher Pipeline — خط أنابيب المعلّم (Readiris)

تحويل مخرجات Readiris النصية إلى بيانات تدريب للنماذج الخاصة بالمشروع
(TrOCR / PaddleOCR / CRNN / نماذج تصحيح لاحقة)، مع معمارية هجينة للإنتاج.
هذه الحزمة **المكافئ المباشر** لخط معلّم ABBYY (`tools/abbyy_teacher`، PR #168)
لمن لا يملك ترخيص ABBYY، وتبني على **نفس العقد** (نفس نماذج البيانات ونفس مخطط JSONL).

> **ملاحظة قانونية**: Readiris (IRIS/Canon) نظام مغلق المصدر ولا ينشر مواصفة
> XML علنية مثل ALTO/PAGE. هذه الحزمة **لا تنقل أي أوزان أو كود أو ثنائيات من
> Readiris**؛ هي تستهلك فقط ملفات التصدير النصية (TXT / HTML / RTF) الناتجة عن
> **نسخة مرخصة أو تجريبية رسمية** يعمل بها مالك المستودع على مستنداته هو،
> وتحوّلها إلى أصول تدريب. كل أمر CLI يستوعب تصديراً يمرّ عبر **بوابة ترخيص**
> إجبارية: `--i-own-license` + متغير البيئة `READIRIS_LICENSE_CONFIRMED=1`.
> يمنع منعاً باتاً إدخال مثبتات أو ثنائيات أو أرقام تسلسلية للبرنامج في أي مستودع.

---

## الفرق عن معلّم ABBYY (#168) — قرارات معمارية

| الجانب | abbyy_teacher (#168) | readiris_teacher (هذه الحزمة) |
|---|---|---|
| صيغ الإدخال | ALTO / PAGE / FineReader XML (مواصفات علنية + إحداثيات + ثقة) | TXT / HTML / RTF (نصية؛ الإحداثيات في HTML المتموضع فقط) |
| بوابة الترخيص | توثيق قانوني في README | بوابة إجبارية عند التشغيل (flag + env) لغلقة الصيغة |
| Pillow | مطلوب عند الاستيراد | استيراد كسول — التحليل/المحاذاة/البناء تعمل بلا Pillow |
| بلا إحداثيات | غير وارد (XML دائماً يحمل إحداثيات) | TXT/RTF نصوص فقط: `has_geometry=False` → قص/YOLO يتخطّى بأمان (`lines_to_pairs` بديل JSONL) |
| اسم المحرك الاحتياطي في cascade | `abbyy_fallback` | `readiris_fallback` |
| Provenance | — | `export_sha256` (sha256 لملف التصدير) يُضاف إضافياً للسجلات |

العقد المشترك ثابت: نفس حقول `CorrectionPair` (`ocr_text, corrected_text,
language, source_file, page_num, confidence, created_at`) ونفس مخطط
`data.jsonl` — مخارج المعلمين اثنين تتغذى على بوابة التدريب نفسها دون أي تحويل.

---

## المنهجيات المدعومة (نفس أربع منهجيات #168)

### 1) توليد بيانات تدريب عالية الجودة (Teacher-Student / Pseudo-Labeling)
- عالج مستنداتك الممسوحة في نسختك المرخصة من Readiris وصادِر **TXT** لكل صفحة
  (الأفضل للنص)، أو **HTML** إن أردت إحداثيات كتل/أسطر، أو **RTF** للنص المنسق.
- الحزمة تحوّل هذا إلى:
  - قصاصات أسطر وكلمات مع `manifest.jsonl` (HTML المتموضع فقط).
  - `data.jsonl` بمخطط `training-data/corrections/handwriting_gt.jsonl` نفسه
    (الحقول الحاكمة + الإضافية: `bbox, crop_path, level, source_format, export_sha256`).

### 2) معالجة النصوص العربية (Text Alignment + تصحيح الأخطاء)
- مخرجات Readiris تعمل كـ **Ground Truth Baseline**؛ قارنها بنص موثوق عبر
  `difflib.SequenceMatcher` + Levenshtein لإنتاج أزواج `(ocr_text ->
  corrected_text)` مع CER لكل زوج (دوال مطابقة لمعلم ABBYY حرفياً).
- RTF: فك ترميز `\'hh` بترميز عربي ويندوز (cp1256 افتراضياً، غيّره بـ
  `--rtf-codepage`) و`\'uN` Unicode.

### 3) تحليل البنية (Layout Analysis) — HTML المتموضع فقط
- كتل HTML ذات `style="left/top/width/height"` تُصدَّر **YOLO**
  (`labels/*.txt` مطبَّعة إلى [0,1]). صيغ بلا إحداثيات تُعيد `None`
  («لا تسميات لهذه الصيغة» — ليست خطأ).

### 4) النماذج الهجينة (Fallback / Cascading)
- `CascadeRouter` بنفس العتبات (0.92/0.60): ثقة عالية → **النموذج الخاص**،
  منخفضة → **نسخة Readiris المرخصة محلياً كـ Fallback**، والرمادية → **HITL**.
- تنبيه: TXT/RTF بلا ثقة (0.0) — كل الأسطر ستقع في bucket الـfallback؛ تعامل
  معها كـ«لا إشارة ثقة» لا كحكم نموذج.

---

## مخطط خط الأنابيب

```
[مستندات خام للمالك]
      │  (Readirs مرخص محلياً — خارجي، يدوي أو مؤتمت)
      ▼
[TXT | HTML | RTF]  ← تصدير من نسختك المرخصة
      │   parse_readiris_export()   ← بوابة ترخيص على CLI
      ▼
[PageAnnotation موحد]  ← geometry اختيارية (HTML) + export_sha256
      │
      ├────────► [قصاصات + manifest]  ← cropping.py (HTML فقط)
      ├────────► [محاذاة مع نص موثوق] ← alignment.py → correction pairs
      ▼
[dataset_builder.py]   data.jsonl + layout/labels/*.txt (YOLO عند توفر هندسة)
      ▼
[تدريب النموذج: Fine-tuning]  ثم  [Cascade: student / review / readiris_fallback]
```

---

## الاستخدام

### المتطلبات
```bash
pip install -r tools/readiris_teacher/requirements.txt   # Pillow فقط (للـcrop)
# التحليل والمحاذاة وبناء البيانات تعمل بمكتبة Python القياسية وحدها
```

### بوابة الترخيص (إجبارية)
```bash
export READIRIS_LICENSE_CONFIRMED=1     # إقرار بيئي
# + --i-own-license في كل أمر (إقرار صريح لكل تشغيل)
# بدونها: الخطأ 2 مع رسالة LICENSE_NOTICE
```

### أوامر CLI
```bash
# من جذر المستودع

# 1) تلخيص ملف تصدير (يتعرف تلقائياً على الصيغة)
python -m tools.readiris_teacher parse --export exports/page_01.html \
    --i-own-license --json summary.json

# 2) قص القصاصات (أسطر + كلمات) — يحتاج HTML متموضعاً + صورة الصفحة
python -m tools.readiris_teacher crop --export exports/page_01.html \
    --image scans/page_01.png --out-dir training-data/crops/page1 --i-own-license

# 3) محاذاة مخرجات Readiris مع نص موثوق → أزواج تصحيح
python -m tools.readiris_teacher align --export exports/page_01.txt \
    --truth-text trusted/page_01.txt --out training-data/corrections/readiris_pairs.jsonl \
    --i-own-license

# 4) الخط الكامل: JSONL دائماً؛ قصاصات + YOLO عند توفر الإحداثيات
python -m tools.readiris_teacher build --export exports/page_01.html \
    --image scans/page_01.png --out-dir dataset/page1 --i-own-license

# 5) تقرير التوجيه الهجين لصفحة
python -m tools.readiris_teacher cascade --export exports/page_01.html --i-own-license
```

### الاستخدام البرمجي
```python
from tools.readiris_teacher import (
    parse_readiris_export, lines_to_pairs, write_ocr_jsonl,
    line_pairs_from_trusted_text, build_layout_yolo, CascadeRouter,
)

ann = parse_readiris_export("exports/page_01.html")   # TXT أو HTML أو RTF
print(ann.summary())                                   # {"lines": 24, "has_geometry": true, ...}

# صيغ نصية بلا إحداثيات: JSONL على مستوى الأسطر مباشرة
rows = lines_to_pairs(ann, source_file="page_01.txt")
write_ocr_jsonl(rows, "training-data/corrections/readiris_pairs.jsonl")

# HTML متموضع: محاذاة + YOLO كما في معلم ABBYY
pairs = line_pairs_from_trusted_text(ann, trusted_text, source_file="page_01.png")
build_layout_yolo(ann, "dataset/layout/", image_path="scans/page_01.png", level="block")

router = CascadeRouter()
print(router.route_student_result([("نص", 0.97), ("غامض", 0.41)]).counts)
# {"student": 1, "review": 0, "readiris_fallback": 1}
```

---

## بنية الحزمة

```
tools/readiris_teacher/
├── __init__.py         # الواجهة العامة
├── models.py           # BBox / Word / TextLine / PageAnnotation ... (عقد #168 + export_sha256)
├── export_parsing.py   # محللات TXT + HTML + RTF (تعرف تلقائي، stdlib فقط)
├── licensing.py        # بوابة الترخيص (flag + env)
├── cropping.py         # قص القصاصات (Pillow كسول، حارس geometry)
├── alignment.py        # CER + محاذاة + أزواج تصحيح + guess_language
├── dataset_builder.py  # JSONL (مخطط training-data) + YOLO + DATASET_CARD + lines_to_pairs
├── cascade.py          # CascadeRouter: student / review / readiris_fallback
├── cli.py              # python -m tools.readiris_teacher ...
└── requirements.txt    # Pillow فقط (للـcrop)
```

## نقاط التكامل مع المشروع

| النقطة | المسار | كيف |
|---|---|---|
| عقد بيانات التصحيح | `training-data/corrections/handwriting_gt.jsonl` | نفس حقول JSONL تماماً |
| معلم ABBYY | `tools/abbyy_teacher` (PR #168) | نفس النماذج والمخطط — مخارج قابلة للدمج |
| بوابة التدريب | مراجعة → confirm → تصدير `oms.pattern.v1` | السجلات تدخل `review=open` ثم confirm |
| مصحح LLM القائم | `src/llm/ollama_proofreader.py` | أزواج `ocr_text/corrected_text` جاهزة للتقييم |
| المراجعة البشرية | خدمات review/HITL القائمة | منطقة "review" في الموجّه |
| مجموعات HF | `app/services/hf_dataset_service.py` | `load_dataset("json", data_files=...)` مباشرة |

## الصيغ المدعومة

| الصيغة | الإحداثيات | الثقة | ملاحظات |
|---|---|---|---|
| TXT (صفحة/ملف) | ✗ (أصفار) | ✗ (0.0) | الأسطر نص منطقي؛ الأفضل للتصحيح والمحاذاة |
| HTML | ✓ إن وُجدت كتل `style` متموضعة | ✗ (0.0) | `<img src>` → `image_filename`؛ فاصل صفحات → صفحات متعددة |
| RTF | ✗ | ✗ | فك `\'hh` (cp1256) و`\'uN`؛ تخطي fonttbl/colortbl/`{\*...}` |

ملاحظات تقنية:
- كل الثقات تُطبَّع إلى `[0,1]`؛ الغياب = `0.0` («غير معلومة» لا «صفر ثقة»).
- HTML متعدد الصفحات: `parse_readiris_export()` يعيد الأولى،
  و`parse_readiris_export_all()` يعيد الكل (فواصل page-break/hr).
- Arabic RTL: النصوص تُخزَّن كما هي منطقياً كما أخرجها Readiris.
- لا شبكة، لا تبعيات خارجية في التحليل: `html.parser` + regex للـRTF.
