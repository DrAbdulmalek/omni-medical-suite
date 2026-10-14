<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 85 | حُفظ: 2026-10-08 -->

# C-00 — OCR Consolidation Pre-Flight (omni-ocr-core)

# ⚠️ توضيح صادق قبل البدء

**لا أستطيع تنفيذ المراجعة بنفسي** — ليس لدي وصول إلى `/home/z/my-project/repos/omni-medical-suite` أو أي من مستودعاتك الأخرى. أنا نموذج لغوي في محادثة، ولا أستطيع تشغيل `git`, `find`, `grep`, أو قراءة ملفاتك.

**لكن ما أستطيع تقديمه هو الأهم:**

1. **برومبت تدقيق شامل** يجعلك تكتشف كل المشاكل بنفسك.
2. **تصميم معماري كامل** للمستودع المركزي الجديد `omni-ocr-core`.
3. **خطة ترحيل تفصيلية** لدمج كل وحدات OCR من كل الأماكن.
4. **خطة استدعاء موحدة** تجعل المستودع المركزي قابلاً للاستدعاء من أي مشروع.

---

# MASTER PROMPT — OCR Consolidation & Repository Audit
## Omni Medical Suite — بناء مستودع OCR مركزي واستدعاؤه من كل مكان

> **تعليمات:** انسخ كل ما أسفل هذا السطر وأرسله إلى Z.ai كما هو. البرومبت مصمم بـ Stop-Gates صارمة، ولا يبدأ أي تنفيذ قبل اجتياز التدقيق الكامل.

---

## 0. الهوية والنطاق

أنت الآن تعمل كـ:

- **Repository Archaeologist**
- **Senior Software Architect**
- **Python Packaging Engineer**
- **Refactoring Specialist**
- **Dependency Graph Analyst**
- **Test Infrastructure Engineer**

**المشروع المركزي:** إنشاء مستودع `omni-ocr-core` يجمع **كل وحدات OCR** من كل الأماكن، بحيث يمكن استدعاؤه من أي مستودع يحتاجه عبر واجهة موحدة.

**النتيجة المستهدفة:**

```
مستودع واحد مركزي
        ↓
يستدعيه:
  - omni-medical-suite
  - أي مشروع آخر
  - أي خدمة مستقبلية
```

**⚠️ نمط التنفيذ:** `AUDIT-FIRST` — لا تعديل كود، لا إنشاء ملفات إنتاجية، لا commit، لا push حتى تنتهي من التدقيق وتحصل على موافقة صريحة.

---

## 1. القواعد غير القابلة للتفاوض

### 1.1 ممنوع تماماً

- ❌ تعديل `main`.
- ❌ تعديل أي مستودع قائم قبل اكتمال التدقيق.
- ❌ حذف أي ملف أو مجلد.
- ❌ نقل أي ملف من مكانه.
- ❌ تثبيت أي حزمة (`pip`, `npm`, `cargo`).
- ❌ تشغيل auto-fix.
- ❌ commit أو push.
- ❌ إنشاء فروع جديدة.
- ❌ تشغيل أي خدمة (`server.py`, `train_server.py`).
- ❌ تحميل أي نموذج.
- ❌ استدعاء أي API خارجي.
- ❌ إرسال أي بيانات خارج الجهاز.
- ❌ ادعاء أن شيئاً "مُنفَّذ" قبل اجتياز Stop-Gate.

### 1.2 إلزامي

- ✅ Evidence لكل ادعاء (مسار + رقم سطر، أو أمر + مخرجه).
- ✅ جرد كامل لكل ملف OCR في كل مستودع.
- ✅ رسم Dependency Graph حقيقي.
- ✅ تحديد كل تعارض محتمل.
- ✅ تحديد كل كود مكرر.
- ✅ اقتراح معمارية موحدة.
- ✅ أسئلة صريحة عند الغموض.

### 1.3 العمل في فرع `audit/ocr-consolidation`

إذا كان موجوداً، أبلغ عنه. إذا لم يوجد، أنشئه بعد موافقة المستخدم.

**⚠️ لا تلمس `main`.**

---

## 2. Phase C-00 — Pre-Flight Verification

### 2.1 الأوامر الإلزامية

```bash
# المستودع الرئيسي
test -d /home/z/my-project/repos/omni-medical-suite
git -C /home/z/my-project/repos/omni-medical-suite status
git -C /home/z/my-project/repos/omni-medical-suite branch --show-current
git -C /home/z/my-project/repos/omni-medical-suite log -n 5 --oneline
git -C /home/z/my-project/repos/omni-medical-suite remote -v
```

### 2.2 اكتشاف المستودعات الأخرى

```bash
# ابحث عن كل مستودعات git في مساحة العمل
find /home/z -maxdepth 5 -type d -name ".git" 2>/dev/null | head -20
find /home/z -maxdepth 5 -type d -name "*.git" 2>/dev/null | head -10
ls -la /home/z/my-project/repos/ 2>/dev/null
ls -la /home/z/my-project/ 2>/dev/null
```

### 2.3 اكتشاف وحدات OCR في كل مكان

```bash
# ابحث عن ملفات OCR في كل المستودعات
find /home/z -type f -name "*.py" 2>/dev/null | xargs grep -l "tesseract\|paddle\|easyocr\|trocr\|olmocr" 2>/dev/null | head -50

# ابحث عن ملفات OCRResult و OCR contracts
find /home/z -type f -name "*.py" 2>/dev/null | xargs grep -l "class OCRResult\|OCRResult\s*=" 2>/dev/null | head -20

# ابحث عن engines و adapters
find /home/z -type d -name "*engine*" -o -type d -name "*ocr*" -o -type d -name "*extract*" 2>/dev/null | head -30
```

### 2.4 المخرج

تقرير نصي:

```
=== C-00 — PRE-FLIGHT ===

MAIN_REPO:              /home/z/my-project/repos/omni-medical-suite
MAIN_REPO_STATUS:       <clean | dirty>
MAIN_REPO_BRANCH:       <branch>
MAIN_REPO_HEAD:         <sha>
MAIN_REPO_REMOTE:       <url>

OTHER_REPOS_FOUND:      <count>
  - <path 1>
  - <path 2>
  - ...

OCR_FILES_FOUND:        <count>
OCR_CONTRACTS_FOUND:    <count>
ENGINES_DIRS_FOUND:     <count>

STATUS: OK | BLOCKED

NEXT: WAIT FOR EXPLICIT AUTHORIZATION FOR C-01
```

**STOP-GATE C-00:** لا تبدأ C-01 قبل موافقة صريحة.

---

## 3. Phase C-01 — Full OCR Inventory

**الهدف:** جرد **كل** ملف/مكوّن OCR في كل المستودعات، بدون استثناء.

### 3.1 الجرد التفصيلي

لكل مستودع اكتشفته، أنتج جدولاً:

| # | الملف/المكوّن | المسار الكامل | النوع | الحجم | آخر تعديل | الغرض | يعمل؟ |
|---|---|---|---|---|---|---|---|
| 1 | `ocr_contract.py` | `.../omni_ocr/contract/` | Contract | | | تعريف OCRResult | ⚠️ |
| 2 | `tesseract_engine.py` | `.../engines/tesseract/` | Engine | | | محرك Tesseract | ⚠️ |
| 3 | `paddle_engine.py` | `.../engines/paddle/` | Engine | | | محرك Paddle | ⚠️ |
| ... | | | | | | | |

**الأنواع الممكنة:**
- `Contract` — تعريف OCRResult، interfaces.
- `Engine` — محرك OCR (Tesseract, Paddle, EasyOCR, TrOCR).
- `Adapter` — غلاف حول محرك خارجي.
- `Router` — يقرر أي محرك يستخدم.
- `Normalizer` — تطبيع النص (RTL، Arabic).
- `Provenance` — تسجيل مصدر النتيجة.
- `Validation` — التحقق من الجودة.
- `Post-processor` — تحسين النتائج.
- `Utility` — أدوات مساعدة.
- `Test` — اختبارات.
- `Config` — إعدادات.
- `Script` — سكربت تشغيلي.

### 3.2 فحص كل ملف

لكل ملف في الجدول، استخدم:

```bash
# فحص الاستيرادات
head -50 <file> | grep "import\|from"

# فحص Class/Function
grep -E "^class |^def " <file>

# فحص الاعتماديات
grep -E "tesseract|paddle|easyocr|torch|transformers|fitz|PyMuPDF|PIL|opencv" <file>

# فحص الاختبارات الموجودة
find <dir> -name "test_*.py" -o -name "*_test.py"
```

### 3.3 اكتشاف التكرار

```bash
# ابحث عن ملفات مكررة بالاسم
find /home/z -type f -name "*ocr*.py" -o -name "*engine*.py" -o -name "*adapter*.py" 2>/dev/null | sort

# ابحث عن كود متشابه
grep -r "def.*ocr\|class.*OCR" /home/z --include="*.py" 2>/dev/null | head -50

# ابحث عن OCRResult
grep -r "OCRResult" /home/z --include="*.py" 2>/dev/null | head -30
```

### 3.4 المخرج

```
docs/audit/OCR-C01_FULL_INVENTORY.md
```

**يحتوي:**

1. جدول الجرد الكامل (كل ملف OCR في كل مستودع).
2. تحليل التكرار (ما هو مكرر، أين، بأي شكل).
3. تحليل الاعتماديات المتقاطعة.
4. تحليل التعارضات (versions مختلفة، contracts مختلفة).
5. مخطط `Dependency Graph` (Mermaid).
6. الملفات اليتيمة (لا يستوردها أحد).
7. الملفات الحرجة (يستوردها الجميع).

### 3.5 Definition of Done — C-01

- [ ] كل مستودع تم فحصه.
- [ ] كل ملف OCR مسجّل في الجدول.
- [ ] كل ملف له نوع محدد.
- [ ] Dependency Graph مرسوم.
- [ ] التكرارات محددة.
- [ ] التعارضات محددة.
- [ ] الملفات الحرجة محددة.
- [ ] الملفات اليتيمة محددة.

**STOP-GATE C-01:** لا تنتقل إلى C-02 قبل موافقة صريحة.

---

## 4. Phase C-02 — Conflict & Duplication Analysis

**الهدف:** تحليل دقيق لكل تعارض وتكرار.

### 4.1 تحليل التعارضات

لكل زوج من الملفات المتعارضة:

| الملف A | الملف B | نوع التعارض | الشدة | التأثير | القرار المقترح |
|---|---|---|---|---|---|
| `contract/ocr_result.py` (v1) | `contract/ocr_result.py` (v2) | Schema مختلف | CRITICAL | كسر التوافق | ADOPT الأحدث |
| `engines/tesseract.py` | `engines/tesseract_adapter.py` | تكرار كود | HIGH | صعوبة صيانة | MERGE |
| `router.py` (repo A) | `router.py` (repo B) | منطق مختلف | HIGH | سلوك غير متسق | UNIFY |

### 4.2 تحليل التكرار

لكل كود مكرر:

```python
# ابحث عن دوال متشابهة
# مثال: find_similar("def preprocess", "def clean_image", threshold=0.8)
```

**الأنواع:**
- **Duplicate:** نسخة طبق الأصل.
- **Near-duplicate:** اختلافات طفيفة.
- **Fork:** نسخة معدّلة بشكل كبير.
- **Superset:** واحد يحتوي الآخر.

### 4.3 تحليل التعارضات في الإصدارات

```bash
# قارن requirements.txt بين المستودعات
diff /repo-a/requirements.txt /repo-b/requirements.txt

# ابحث عن تعارضات في versions
grep -E "transformers==|torch==|paddle" /repo-*/requirements.txt
```

**جدول التعارضات:**

| الحزمة | repo A | repo B | repo C | التوافق | الحل |
|---|---|---|---|---|---|
| transformers | 4.35.0 | 4.57.3 | — | ❌ | توحيد إلى 4.57.3 |
| torch | 2.0.0 | 2.7.0 | — | ❌ | توحيد إلى 2.7.0 |
| paddlepaddle | 2.5.0 | — | 2.6.0 | ❌ | توحيد إلى 2.6.0 |

### 4.4 المخرج

```
docs/audit/OCR-C02_CONFLICTS_AND_DUPLICATION.md
```

### 4.5 Definition of Done — C-02

- [ ] كل تعارض مسجّل.
- [ ] كل تكرار مصنّف.
- [ ] كل تعارض في versions موثق.
- [ ] قرار مقترح لكل بند.
- [ ] خطة حل مقترحة.

**STOP-GATE C-02:** لا تنتقل إلى C-03 قبل موافقة صريحة.

---

## 5. Phase C-03 — Central Repository Design

**الهدف:** تصميم `omni-ocr-core` — المستودع المركزي الجديد.

### 5.1 المعمارية المقترحة

```
omni-ocr-core/                            ← مستودع جديد
├── README.md
├── LICENSE                                (MIT)
├── pyproject.toml                         (PEP 621)
├── requirements.txt
├── .gitignore
├── .github/
│   └── workflows/
│       ├── test.yml
│       └── publish.yml
├── src/
│   └── omni_ocr/
│       ├── __init__.py
│       ├── __version__.py
│       │
│       ├── contract/                      ← العقود الموحدة
│       │   ├── __init__.py
│       │   ├── result.py                  (OCRResult)
│       │   ├── extraction_result.py       (ExtractionResult)
│       │   ├── metadata.py
│       │   ├── provenance.py
│       │   └── interfaces.py              (AbstractEngine, AbstractBackend)
│       │
│       ├── engines/                       ← محركات OCR
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── tesseract/
│       │   │   ├── __init__.py
│       │   │   └── engine.py
│       │   ├── paddle/
│       │   ├── easyocr/
│       │   ├── trocr/
│       │   ├── olmocr/
│       │   └── handwriting/               ← AHW
│       │       ├── __init__.py
│       │       ├── arabic_trocr.py
│       │       └── utils.py
│       │
│       ├── extraction/                    ← طبقة استخراج المستندات
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── xberg_backend.py
│       │   ├── docling_backend.py
│       │   └── stirling_preprocess.py
│       │
│       ├── routing/                       ← القرارات
│       │   ├── __init__.py
│       │   ├── router.py
│       │   ├── rules.py
│       │   └── profiles.py                (LITE, STANDARD, HANDWRITING, MEDICAL)
│       │
│       ├── normalization/                 ← التطبيع
│       │   ├── __init__.py
│       │   ├── arabic.py                  (RTL, diacritics)
│       │   ├── mixed_script.py            (Arabic + English)
│       │   └── digits.py
│       │
│       ├── validation/                    ← التحقق
│       │   ├── __init__.py
│       │   ├── medical_rules.py
│       │   ├── critical_tokens.py
│       │   └── quality_gate.py
│       │
│       ├── provenance/                    ← التتبع
│       │   ├── __init__.py
│       │   ├── ledger.py
│       │   └── registry.py
│       │
│       ├── io/                            ← قراءة/كتابة
│       │   ├── __init__.py
│       │   ├── pdf_reader.py
│       │   ├── image_reader.py
│       │   └── batch.py
│       │
│       ├── config/                        ← الإعدادات
│       │   ├── __init__.py
│       │   ├── settings.py
│       │   └── profiles.py
│       │
│       └── api/                           ← الواجهة العامة
│           ├── __init__.py
│           ├── ocr.py                     (execute)
│           ├── extract.py                 (extract)
│           └── batch.py                   (batch_execute)
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── fixtures/
│   ├── test_contract.py
│   ├── test_engines/
│   ├── test_routing/
│   ├── test_normalization/
│   ├── test_validation/
│   ├── test_provenance/
│   └── test_api/
│
└── docs/
    ├── ARCHITECTURE.md
    ├── API.md
    ├── CONTRIBUTING.md
    ├── ENGINES.md
    ├── PROFILES.md
    └── examples/
        ├── basic_usage.py
        ├── batch_processing.py
        └── custom_engine.py
```

### 5.2 الواجهة العامة (Public API)

هذه هي الواجهة التي سيستدعيها كل مستودع خارجي:

```python
# src/omni_ocr/api/ocr.py
"""
Public API — الواجهة الموحدة لكل مستهلكي omni_ocr
"""

from omni_ocr.contract.result import OCRResult
from omni_ocr.routing.router import Router
from omni_ocr.config.settings import Settings


def execute(
    source: str,
    profile: str = "standard",
    **kwargs
) -> OCRResult:
    """
    يستدعي OCR على ملف واحد.

    Args:
        source: مسار ملف (PDF, image, ...)
        profile: LITE | STANDARD | HANDWRITING | MEDICAL | FULL
        **kwargs: خيارات إضافية

    Returns:
        OCRResult مع provenance كامل
    """
    settings = Settings.from_profile(profile, **kwargs)
    router = Router(settings)
    engine = router.select(source)
    result = engine.execute(source)
    return result


def extract(
    source: str,
    profile: str = "document",
    output_format: str = "markdown",
    **kwargs
) -> "ExtractionResult":
    """
    يستدعي طبقة الاستخراج (Xberg, Docling, ...).

    Args:
        source: مسار ملف
        profile: document | xberg | docling
        output_format: text | markdown | json | structured

    Returns:
        ExtractionResult موحدة
    """
    from omni_ocr.extraction import get_backend
    backend = get_backend(profile)
    return backend.extract(source, output_format=output_format, **kwargs)


def batch_execute(
    sources: list[str],
    profile: str = "standard",
    parallel: int = 1,
    **kwargs
) -> list[OCRResult]:
    """معالجة دفعات."""
    from omni_ocr.io.batch import process_batch
    return process_batch(sources, profile, parallel, **kwargs)
```

### 5.3 مثال استدعاء من مستودع خارجي

```python
# في omni-medical-suite
from omni_ocr import execute, extract, batch_execute

# سطر واحد
result = execute("scan.pdf", profile="handwriting")

# مستند كامل
extraction = extract("report.pdf", profile="document", output_format="markdown")

# دفعة
results = batch_execute(["p1.pdf", "p2.pdf"], profile="medical")
```

### 5.4 المخرج

```
docs/audit/OCR-C03_CENTRAL_REPO_DESIGN.md
```

**يحتوي:**

1. الهيكل الكامل (كما فوق).
2. الواجهة العامة (Public API).
3. كل Contract بالتفصيل.
4. كل Engine interface.
5. Routing logic.
6. Profiles المحددة.
7. مثال استدعاء من مستودع خارجي.
8. الاستراتيجية: كيف يستهلك كل مستودع `omni-ocr-core`؟

### 5.5 Definition of Done — C-03

- [ ] الهيكل كامل.
- [ ] Public API محدد.
- [ ] كل contract موثق.
- [ ] Routing logic موثق.
- [ ] Profiles موثقة.
- [ ] أمثلة استدعاء موجودة.
- [ ] استراتيجية التوزيع محددة.

**STOP-GATE C-03:** لا تنتقل إلى C-04 قبل موافقة صريحة.

---

## 6. Phase C-04 — Migration Strategy

**الهدف:** خطة تفصيلية لنقل كل ملف OCR من مستودعه الحالي إلى `omni-ocr-core`، بدون كسر أي شيء.

### 6.1 استراتيجية التوزيع

**3 خيارات:**

| الخيار | الميزة | العيب | القرار |
|---|---|---|---|
| **A. PyPI Private** | `pip install` بسيط | يحتاج private registry | ⚠️ للاحقًا |
| **B. Git Dependency** | `pip install git+https://...` | يحتاج صلاحيات | ✅ **الآن** |
| **C. Submodule** | كود مع المستهلك | تعقيد في المزامنة | ❌ معقد |
| **D. Local Editable** | `pip install -e ./omni-ocr-core` | للتطوير المحلي | ✅ للمطورين |
| **E. Release Wheel** | ملف `.whl` | يدوي | ⚠️ للإصدارات الثابتة |

**القرار الموصى به:** `B` للإنتاج + `D` للتطوير.

**طريقة الاستهلاك في `omni-medical-suite/pyproject.toml`:**

```toml
[project]
dependencies = [
    "omni-ocr-core @ git+https://github.com/DrAbdulmalek/omni-ocr-core@v0.1.0",
]
```

**طريقة التطوير:**

```bash
pip install -e ../omni-ocr-core
```

### 6.2 Migration Map

لكل ملف في الجرد (C-01):

| الملف الأصلي | المسار الأصلي | الملف الجديد | الإجراء | الملاحظات |
|---|---|---|---|---|
| `ocr_result.py` | `.../omni_ocr/contract/` | `omni-ocr-core/src/omni_ocr/contract/result.py` | MOVE | + دمج الحقول الجديدة |
| `tesseract.py` | `.../omni_ocr/engines/` | `omni-ocr-core/src/omni_ocr/engines/tesseract/engine.py` | MOVE | + adapt to interface |
| `router.py` | `.../omni_ocr/routing/` | `omni-ocr-core/src/omni_ocr/routing/router.py` | MOVE + MERGE | دمج مع الـrouters الأخرى |
| ... | | | | |

**الإجراءات الممكنة:**
- `MOVE` — نقل مباشر.
- `MOVE+MERGE` — نقل مع دمج.
- `MOVE+REFACTOR` — نقل مع إعادة هيكلة.
- `DELETE` — حذف (مكرر).
- `KEEP` — إبقاء (خاص بالمشروع).
- `REPLACE` — استبدال بنسخة جديدة.

### 6.3 Backward Compatibility

**الأساس:** كل مستودع يستخدم `omni-ocr-core` يجب أن يستمر بالعمل دون تغيير كوده الخارجي.

**الحل:** Shim layer

```python
# في omni-medical-suite/packages/omni_ocr/__init__.py
"""
⚠️ DEPRECATED — انتقل إلى omni_ocr الجديد
هذا الملف يضمن التوافق الخلفي.
"""

import warnings
warnings.warn(
    "packages/omni_ocr has moved to omni-ocr-core. "
    "Please update: pip install git+.../omni-ocr-core",
    DeprecationWarning,
    stacklevel=2
)

# إعادة التصدير من الحزمة الجديدة
from omni_ocr import execute, extract, batch_execute, OCRResult

__all__ = ["execute", "extract", "batch_execute", "OCRResult"]
```

### 6.4 خطة التنفيذ على مراحل

| المرحلة | المدة | المخرج | شرط الانتقال |
|---|---|---|---|
| **C-04.1** | أسبوع | إنشاء `omni-ocr-core` + Contract + Tests | Contract يعمل |
| **C-04.2** | أسبوع | نقل Tesseract + Paddle + EasyOCR | 3 محركات تعمل |
| **C-04.3** | أسبوع | نقل TrOCR + AHW | Handwriting يعمل |
| **C-04.4** | أسبوع | نقل OLMoCR + Xberg adapter | Document layer يعمل |
| **C-04.5** | أسبوع | نقل Routing + Normalization | Router يعمل |
| **C-04.6** | أسبوع | نقل Validation + Provenance | Medical safety يعمل |
| **C-04.7** | أسبوع | Shim layer في omni-medical-suite | لا كسر |
| **C-04.8** | أسبوع | Tests شاملة + Documentation | كل شيء يعمل |

**المجموع:** 8 أسابيع.

### 6.5 Rollback Strategy

كل مرحلة لها Rollback:

```bash
# إذا فشلت C-04.2:
git -C omni-medical-suite revert <commit-sha>
# أو
pip uninstall omni-ocr-core
pip install -e omni-medical-suite/packages/omni_ocr  # النسخة القديمة
```

### 6.6 المخرج

```
docs/audit/OCR-C04_MIGRATION_STRATEGY.md
```

### 6.7 Definition of Done — C-04

- [ ] استراتيجية التوزيع محددة.
- [ ] Migration Map كامل.
- [ ] Backward compatibility مضمون.
- [ ] خطة التنفيذ على مراحل.
- [ ] Rollback plan لكل مرحلة.
- [ ] شروط النقل محددة.
- [ ] حدود المخاطر موثقة.

**STOP-GATE C-04:** لا تنتقل إلى C-05 قبل موافقة صريحة.

---

## 7. Phase C-05 — Fix Errors Plan

**الهدف:** خطة إصلاح كل الأخطاء المكتشفة في C-01 و C-02.

### 7.1 تصنيف الأخطاء

| # | الخطأ | الفئة | الشدة | الملف | الإصلاح المقترح |
|---|---|---|---|---|---|
| 1 | Duplicate OCRResult contract | معمارية | CRITICAL | 3 ملفات | توحيد في `omni-ocr-core` |
| 2 | Version conflicts | اعتماديات | HIGH | `requirements.txt` | توحيد versions |
| 3 | Missing tests | اختبارات | HIGH | كل المحركات | إضافة tests |
| 4 | Hardcoded paths | هندسة | MEDIUM | `server.py` | استخدام config |
| 5 | Missing RTL support | معمارية | HIGH | Normalization | إضافة `arabic.py` |
| 6 | No provenance in some engines | تتبع | MEDIUM | `easyocr.py` | إضافة provenance |
| 7 | Silent fallbacks | سلامة | CRITICAL | `router.py` | رفع الأخطاء صراحةً |
| 8 | No medical validation | سلامة طبية | CRITICAL | — | إضافة `medical_rules.py` |
| 9 | API keys in code | أمن | CRITICAL | ملفات متفرقة | نقل إلى `.env` |
| 10 | No offline mode guarantee | خصوصية | HIGH | engines | فرض offline |

### 7.2 خطة الإصلاح

**لكل خطأ:**

| البند | القيمة |
|---|---|
| **ID** | C-05-NNN |
| **الخطأ** | وصف |
| **الموقع** | مسار دقيق |
| **الشدة** | CRITICAL / HIGH / MEDIUM / LOW |
| **الأثر** | ماذا يفشل؟ |
| **الإصلاح** | خطوات محددة |
| **الاختبار** | كيف نتحقق؟ |
| **الوقت المتوقع** | ساعات |
| **الأولوية** | 1 (الأول) → N (الأخير) |

### 7.3 ترتيب الإصلاحات

**القاعدة:**

1. **CRITICAL أولاً** — الأمان، الحماية، صحة البيانات.
2. **HIGH ثانيًا** — الأداء، التوافق، عدم الكسر.
3. **MEDIUM ثالثًا** — الصيانة، الجودة.
4. **LOW أخيرًا** — التحسينات.

### 7.4 المخرج

```
docs/audit/OCR-C05_ERRORS_AND_FIXES.md
```

### 7.5 Definition of Done — C-05

- [ ] كل خطأ مصنّف.
- [ ] كل خطأ له إصلاح محدد.
- [ ] كل إصلاح له اختبار.
- [ ] ترتيب الأولويات واضح.
- [ ] الوقت المتوقع محدد.
- [ ] المخاطر موثقة.

**STOP-GATE C-05:** لا تنتقل إلى C-06 قبل موافقة صريحة.

---

## 8. Phase C-06 — Final Integration Plan

**الهدف:** خطة موحدة تجمع كل ما سبق.

### 8.1 المخرج

```
docs/audit/OCR-C06_FINAL_INTEGRATION_PLAN.md
```

**يحتوي:**

1. **Executive Summary** (صفحة واحدة).
2. **الجرد الكامل** (من C-01).
3. **التعارضات والتكرارات** (من C-02).
4. **تصميم omni-ocr-core** (من C-03).
5. **خطة الترحيل** (من C-04).
6. **خطة الإصلاح** (من C-05).
7. **الجدول الزمني الكامل** (8-10 أسابيع).
8. **المخاطر والتخفيف**.
9. **الأسئلة المفتوحة للمستخدم (≥10)**.
10. **Next Steps**.

### 8.2 Definition of Done — C-06

- [ ] كل الأقسام موجودة.
- [ ] لا تناقضات.
- [ ] كل ادعاء يحمل دليلاً.
- [ ] الأسئلة المفتوحة واضحة.
- [ ] Next Steps محددة.

**STOP-GATE C-06 — FINAL:** بعد C-06، STOP. **لا تنفيذ.**

---

## 9. الاستراتيجيات الموصى بها للاستدعاء

### 9.1 من `omni-medical-suite`

```toml
# pyproject.toml
[project]
dependencies = [
    "omni-ocr-core @ git+https://github.com/DrAbdulmalek/omni-ocr-core@v0.1.0",
]
```

```python
# في server.py
from omni_ocr import execute, extract

def process_upload(file):
    result = execute(file, profile="handwriting")
    return result.to_dict()
```

### 9.2 من أي مستودع آخر

```bash
# التثبيت
pip install git+https://github.com/DrAbdulmalek/omni-ocr-core@v0.1.0

# أو للتطوير
pip install -e /path/to/omni-ocr-core
```

```python
# الاستخدام
from omni_ocr import execute

result = execute("document.pdf", profile="medical")
print(result.text)
print(result.provenance)  # من أي محرك، أي إصدار
```

### 9.3 النسخ المتعددة (إذا احتجت)

```toml
# requirements-prod.txt
omni-ocr-core @ git+https://github.com/DrAbdulmalek/omni-ocr-core@v0.1.0

# requirements-dev.txt
-e /path/to/local/omni-ocr-core
```

### 9.4 الإصدارات (Versioning)

اتبع **SemVer:**

- `v0.1.0` — Alpha (التطوير).
- `v0.5.0` — Beta.
- `v1.0.0` — Stable (Contract ثابت).
- `v1.1.0` — إضافة محرك جديد (backward compatible).
- `v2.0.0` — تغيير في Contract (breaking).

---

## 10. STOP GATES — قائمة كاملة

| البوابة | الشرط |
|---|---|
| **C-00** | المستودع غير موجود → STOP |
| **C-01** | الجرد غير كامل → STOP |
| **C-02** | التعارضات غير محددة → STOP |
| **C-03** | التصميم غير موافق عليه → STOP |
| **C-04** | خطة الترحيل غير واقعية → STOP |
| **C-05** | الإصلاحات غير محددة → STOP |
| **C-06** | الحزمة النهائية ناقصة → STOP |

**لا تنتقل بين المراحل قبل موافقة صريحة من المستخدم.**

---

## 11. صيغة الرد الأولى المتوقعة

```
=== OCR CONSOLIDATION — C-00 PRE-FLIGHT ===

MAIN_REPO:              /home/z/my-project/repos/omni-medical-suite
MAIN_REPO_STATUS:       <clean | dirty>
MAIN_REPO_BRANCH:       <branch>
MAIN_REPO_HEAD:         <sha>

OTHER_REPOS_FOUND:      <count>
  - <path 1>
  - <path 2>

OCR_FILES_FOUND:        <count>
OCR_CONTRACTS_FOUND:    <count>
ENGINES_DIRS_FOUND:     <count>

STATUS: OK | BLOCKED

If BLOCKED:
  Reason: <exact>
  Recommended action: <what user should do>

NEXT: WAIT FOR EXPLICIT AUTHORIZATION FOR C-01
```

---

## 12. المبدأ النهائي

```
مستودع واحد مركزي.
عقد واحد موحّد.
استدعاء واحد من كل مكان.

لا تكرار.
لا تعارض.
لا كسر.

كل خطوة موثقة.
كل قرار له دليل.
كل مرحلة لها Rollback.

AUDIT FIRST → DESIGN → MIGRATE → TEST → SHIP.

لا كود قبل التدقيق.
لا دمج قبل التصميم.
لا إصدار قبل الاختبار.
```

**ابدأ الآن بـC-00 فقط. ثم توقف وانتظر موافقة صريحة قبل C-01.**

---

## 📌 ملاحظة أخيرة للمستخدم

**بعد إتمام C-06 ستكون لديك خطة كاملة،** لكن التنفيذ الفعلي هو 8-10 أسابيع إضافية. أنصحك بـ:

1. **راجع التقرير كاملاً** قبل الموافقة على أي شيء.
2. **ابدأ بـC-04.1 فقط** (إنشاء `omni-ocr-core` + Contract + Tests).
3. **لا تنقل أي محرك** قبل أن تعمل الـContract بشكل مستقر.
4. **استخدم `pip install -e` للتطوير** لتجنب إعادة النشر.
5. **احتفظ بـ`omni-medical-suite` كمرجع** حتى يستقر المركزي.

**إذا أردت، أستطيع إعداد سكربت `bootstrap.sh`** ينشئ الهيكل الأساسي لـ`omni-ocr-core` في دقيقة واحدة. أخبرني.
