# GRADIO_HITL_CHANGES_REVIEW.md — مراجعة تعديلات `app/gradio_full_hitl.py`

**مراجعة مطلوبة من Malek قبل الدمج النهائي**

---

## ملخص التغيير

| المقياس | القيمة |
|--------|-------|
| الملف الأصلي (main) | 944 سطر |
| الملف الجديد (branch) | 11 سطر |
| الأسطر المحذوفة | 938 |
| الأسطر المضافة | 5 (تعليق + import + if main) |
| النسبة | **-98.8%** |

## المحتوى الجديد (كاملًا)

```python
"""Compatibility shim for the previous Gradio entrypoint.

The canonical Gradio UI now lives in ``app/advanced_review_app.py`` with the
three review-oriented tabs requested in the July 2026 refactor.
"""

from app.advanced_review_app import demo


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
```

## الوظائف المفقودة (كانت في النسخة الأصلية 944 سطر)

| # | الوظيفة | أهمية | موجودة في `advanced_review_app.py`؟ |
|---|---------|--------|--------------------------------------|
| 1 | رفع صورة → preprocessing → OCR ensemble (PaddleOCR + Tesseract) | **حرجة** | ❌ لا |
| 2 | تصحيح إملائي هجين (HybridSpellChecker v7.1) | **حرجة** | ❌ لا |
| 3 | تدقيق LLM بـ Jais (ENABLE_LLM=true) | مهمة | ❌ لا |
| 4 | استخراج كيانات طبية (NER) | مهمة | ❌ لا |
| 5 | حفظ التصحيحات في HF Dataset | مهمة | ❌ لا |
| 6 | تحديث القاموس الطبي من التصحيحات | متوسطة | ❌ لا |
| 7 | إعادة تدريب Jais NER | متوسطة | ❌ لا |
| 8 | ترجمة طبية (4 اتجاهات مع تصحيح) | متوسطة | ❌ لا |
| 9 | حاسبة CER/WER مع jiwer | متوسطة | ❌ لا |
| 10 | Before/After comparison | منخفضة | ❌ لا (يوجد Compare tab لكن بنهج مختلف) |

**الخلاصة: 10 وظائف لم تُنقَل إلى `advanced_review_app.py` — الشيم يُحمِّل فقط `demo` لكنه لا يوفر أيًا من الوظائف الأصلية.**

## التأثير على المراجع

12 ملفًا آخر في المستودع تُشير إلى `gradio_full_hitl.py`:

| الملف | نوع الإشارة | التأثير |
|-------|-------------|---------|
| `STATE_OF_TRUTH.md` | وثيقة | ✅ مُحدَّث ("compatibility shim") |
| `README.md` | وثيقة | ✅ مُحدَّث (يُشير لـ `advanced_review_app.py`) |
| `docs/ROADMAP_2026_Q3.md` | وثيقة | ✅ يذكر التحويل صراحة |
| `docs/DEPLOYMENT.md` | وثيقة | ⚠️ قد يحتاج تحديث |
| `docs/RELEASE_NOTES.md` | وثيقة | ⚠️ تاريخي — لا حاجة لتغيير |
| `Dockerfile.review` | Docker | ⚠️ يُشير لـ `gradio_full_hitl.py` — سيُشغّل `advanced_review_app.py` عبر الشيم |
| `requirements/gradio.txt` | متطلبات | ✅ مُحدَّث |
| `GRADIO_APPS_DECISION.md` | قرار | ⚠️ يحتاج إعادة تقييم — كان التطبيق "المعتمد" |
| `VERIFICATION_LOG.md` | سجل | تاريخي |
| `CONTRIBUTING.md` | مساهمة | ⚠️ قد يُشير للأمر القديم |
| `app/gradio_extended.py` | كود | ⚠️ يحتاج مراجعة |
| `apps/handwriting-demo/README.md` | وثيقة HF | تاريخي |

## المخاطر

### 1. دُخّال تام (Breaking) لـ Dockerfile.review
```dockerfile
CMD ["python", "app/gradio_full_hitl.py"]
```
سيُشغّل `advanced_review_app.py` عبر الشيم — لكن هذا التطبيق يتطلب `QdrantMedicalSearch` و `EngineRouter` و `ArabicMedicalFieldExtractor` في مستوى الوحدة العليا. إذا فشل أي استيراد، سيفشل Docker container بالكامل.

### 2. فقدان وظيفة رفع الصور
`advanced_review_app.py` يعمل بالنص فقط (3 حقول نصية). النسخة الأصلية كانت تقبل رفع صور فعلية عبر `gr.Image(type="numpy")`. هذا يعني أن طريق معالجة الصور → OCR → تصحيح مفقود بالكامل في الواجهة الجديدة.

### 3. `from app.advanced_review_app import demo`
هذا استيراد قد يفشل في بعض سياقات التشغيل:
- إذا لم تكن `gradio` مُثبَّتة (النسخة الأصلية كانت تتعامل مع `ImportError` بـ gradio)
- إذا لم تكن `QdrantMedicalSearch` قادرة على الاستيراد (رغم الـ fallback)

## التوصية

**3 خيارات أمام Malek:**

### الخيار A — احتفظ بالشيم لكن أضف تحذيرًا (موصى به)
```python
"""Compatibility shim ..."""
import warnings
warnings.warn(
    "app/gradio_full_hitl.py is deprecated — use app/advanced_review_app.py",
    DeprecationWarning,
    stacklevel=2,
)
from app.advanced_review_app import demo
```
**المخاطرة:** المستخدمون الذين يعتمدون على الوظائف الأصلية (رفع صور، Jais، HF save) سيكتشفون أنها مفقودة فقط في وقت التشغيل.

### الخيار B — استبدل الشيم بنسخة محدّثة تحتفظ بالوظائف الحرجة
نقل الوظائف الـ 10 المفقودة إلى `advanced_review_app.py` أو إلى ملف جديد `app/full_pipeline_app.py`. هذا يتطلب عملًا إضافيًا لكنه يحافظ على التوافق الكامل.

### الخيار C — لا تدمج هذا التغيير — أبقِ `gradio_full_hitl.py` كما هو على main
أبقِ الفرع الجديد يضيف فقط الوحدات الجديدة (`rtl_utils`, `field_extractor`, `deduplication`, `engine_router` تحديث) و `advanced_review_app.py` كتطبيق إضافي جديد بدل بديل.

---

**⏳ بانتظار قرار Malek.**