# 🏥 Medical OCR Ecosystem — خريطة المشاريع

> **منظومة متكاملة للتعرف الضوئي على الخط اليدوي الطبي**
> Integrated Ecosystem for Medical Handwriting OCR

## 📊 خريطة المشاريع / Project Map

| # | المشروع | الدور | الحالة | اللغة |
|---|--------|------|--------|-------|
| 1 | [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) | المنصة الرئيسية المتكاملة | ✅ `active` | Next.js + FastAPI |
| 2 | [medical-ocr-postprocessor](https://github.com/DrAbdulmalek/medical-ocr-postprocessor) | مكتبة تصحيح OCR ثنائية اللغة | ✅ `active` | Python (pip) |
| 3 | [medical-handwriting-ocr](https://github.com/DrAbdulmalek/medical-handwriting-ocr) | خط إنتاج OCR متقدم | ✅ `active` | FastAPI + React |
| 4 | [medical-ocr-trainer](https://github.com/DrAbdulmalek/medical-ocr-trainer) | أداة تدريب وجمع بيانات بشرية | ✅ `active` | Streamlit |
| 5 | [medical-ocr-trainer-hf](https://github.com/DrAbdulmalek/medical-ocr-trainer-hf) | نسخة نشر على Hugging Face | 📦 `deployment-only` | Streamlit |
| 6 | [medical-ocr-benchmarks](https://github.com/DrAbdulmalek/medical-ocr-benchmarks) | معيار قياس موحد | ✅ `active` | Python (pip) |
| 7 | [medical-ocr-ground-truth](https://github.com/DrAbdulmalek/medical-ocr-ground-truth) | بيانات أساس للتدريب والقياس | ✅ `active` | JSONL + Python |
| 8 | [medical-doc-processor](https://github.com/DrAbdulmalek/medical-doc-processor) | معالج مستندات (قديم) | ⚠️ `legacy` | Electron + React |
| 9 | [OmniFile_Processor](https://github.com/DrAbdulmalek/OmniFile_Processor) | منصة ملفات ذكية (قديم) | ⚠️ `legacy` | Python + Multi-UI |
| 10 | [IntelliFile-app](https://github.com/DrAbdulmalek/IntelliFile-app) | مدير ملفات ذكي | ✅ `active` (مستقل) | Python + PySide6 |
| 11 | [omniparse](https://github.com/DrAbdulmalek/omniparse) | محلل متعدد الوسائط | 📚 `experimental` | Python |
| 12 | [omniparse-study](https://github.com/DrAbdulmalek/omniparse-study) | دراسة تحليلية | 📚 `archived` | Notes |

## 🏗️ البنية المعمارية / Architecture

```
┌───────────────────────────────────────────────────────────┐
│                    USER INTERFACES                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Next.js  │  │ Streamlit│  │ React    │  │ Gradio    │  │
│  │ (Suite)  │  │(Trainer) │  │(Handwrit)│  │(HF Space) │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬─────┘  │
└───────┼──────────────┼──────────────┼──────────────┼─────┘
        │              │              │              │
┌───────▼──────────────▼──────────────▼──────────────▼─────┐
│                    API LAYER                               │
│  ┌──────────────────┐  ┌────────────────────────────────┐ │
│  │  FastAPI Backend │  │  Postprocessor Library (pip)   │ │
│  │  (handwriting)   │  │  correct_text() | mask_phi()   │ │
│  └──────────────────┘  └────────────────────────────────┘ │
└────────────────────────────────┬───────────────────────────┘
                                 │
┌────────────────────────────────▼───────────────────────────┐
│                    DATA PIPELINE                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Ground   │  │ Trainer  │  │ Bench-   │  │ Diction- │  │
│  │ Truth    │──│ Collect  │──│ marks    │  │ aries    │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└───────────────────────────────────────────────────────────┘
```

## 🔗 مصفوفة التبعيات / Dependency Matrix

| المشروع | يعتمد على | يُستخدم بواسطة |
|---------|-----------|---------------|
| omni-medical-suite | postprocessor | المستخدم النهائي |
| medical-handwriting-ocr | postprocessor, القواميس | المستخدم النهائي |
| medical-ocr-trainer | benchmarks (اختياري) | trainer-hf |
| medical-ocr-trainer-hf | trainer | HF Spaces |
| medical-ocr-postprocessor | — | suite, handwriting, trainer |
| medical-ocr-benchmarks | ground-truth (بيانات) | trainer, suite |
| medical-ocr-ground-truth | — | benchmarks, trainer |

## 🚀 إرشادات الاستخدام / Usage Guide

### للمستخدم النهائي / For End Users
```bash
# 1. استخدم المنصة الرئيسية
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite && make dev
```

### للتطوير / For Developers
```bash
# 2. استخدم مكتبة التصحيح
pip install medical-ocr-postprocessor

# 3. قياس الأداء
pip install medical-ocr-benchmarks
medocr-bench --engines paddleocr --check-ci
```

### لتدريب النماذج / For Training
```bash
# 4. أداة التدريب التفاعلية
git clone https://github.com/DrAbdulmalek/medical-ocr-trainer.git
cd medical-ocr-trainer && streamlit run app.py

# 5. نسخة HF (تجربة سريعة)
# https://huggingface.co/spaces/DrAbdulmalek/medical-ocr-trainer
```

### للخط اليدوي / For Handwriting OCR
```bash
# 6. خط إنتاج متقدم
git clone https://github.com/DrAbdulmalek/medical-handwriting-ocr.git
cd medical-handwriting-ocr/colab_medical_ocr_lite && ./run_demo.sh
```

## 📦 الحزم المتاحة / Available Packages

| الحزمة | التثبيت | الوظيفة |
|--------|---------|--------|
| `medical-ocr-postprocessor` | `pip install medical-ocr-postprocessor` | تصحيح OCR |
| `medical-ocr-benchmarks` | `pip install medical-ocr-benchmarks` | قياس الأداء |

## 📈 مؤشرات الجودة / Quality Metrics

| المقياس | القيمة المستهدفة |
|---------|----------------|
| CER (معدل خطأ الحروف) | < 5% (عربي), < 3% (إنجليزي) |
| WER (معدل خطأ الكلمات) | < 8% (عربي), < 5% (إنجليزي) |
| Medical Term Accuracy | > 90% |
| CI/CD Coverage | 6 مستودعات نشطة |
| Test Cases (Benchmarks) | 50+ حالة (عربي + إنجليزي + مختلط) |

## 🏷️ حالات المستودعات / Repo Status Legend

- ✅ `active` — نشط ومُحدَّث
- ⚠️ `legacy` — قديم (استخدم البديل المُشار)
- 📦 `deployment-only` — للنشر فقط (لا تطوّر هنا)
- 📚 `experimental` — تجريبي
- 📚 `archived` — مؤرشف (للقراءة فقط)

## 📅 تاريخ التطوير / Development Timeline

| التاريخ | الإنجاز |
|---------|---------|
| 2026-06-06 | إكمال إعادة الهيكلة الكاملة للمنظومة |
| 2026-06-06 | ربط handwriting-ocr بمكتبة postprocessor |
| 2026-06-06 | Docker Compose + Makefile لـ omni-medical-suite |
| 2026-06-06 | GitHub Actions CI/CD لـ handwriting-ocr |
| 2026-06-06 | Nightly Benchmarks لـ benchmarks |
| 2026-06-06 | Release v0.1.0 لـ medical-ocr-postprocessor |
| 2026-06-03 | إنشاء ground-truth + benchmarks + بيانات حوكمة |
| 2026-06-02 | تحويل postprocessor إلى حزمة pip |
| 2026-06-02 | تبسيط Lite mode لـ handwriting-ocr |
