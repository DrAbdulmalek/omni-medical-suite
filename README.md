<p align="center">
  <h1>🏥 Omni Medical Suite</h1>
  <strong>منصة متكاملة لمعالجة الصور والنصوص الطبية العربية</strong><br/>
  <sub>Scanner Fixer · OCR Fusion · Handwriting Recognition · Spell Checker · Medical Dictionary · Auto Retraining</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python" />
  <img src="https://img.shields.io/badge/Gradio-5.x-orange?style=flat-square&logo=gradio" />
  <img src="https://img.shields.io/badge/Arabic-RTL-blueviolet?style=flat-square" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" />
  <img src="https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square" />
</p>

<p align="center">
  <a href="#-المميزات">المميزات</a> ·
  <a href="#-الاستخدام-السريع">الاستخدام</a> ·
  <a href="#-الهيكل">الهيكل</a> ·
  <a href="#-التوثيق">التوثيق</a> ·
  <a href="#-النشر">النشر</a>
</p>

---

> **⚠️ ملاحظة مهمة**: جميع الصور الطبية يجب تمريرها أولاً عبر
> [scanner-fixer](https://github.com/DrAbdulmalek/scanner-fixer) لتصحيح الميل والاقتصاص التلقائي
> وتقليل الضوضاء **قبل** معالجة OCR.

---

## ✨ المميزات

| الميزة | الوصف |
|--------|-------|
| 📸 **Scanner Fixer** | تصحيح الميل والانحراف والاقتصاص التلقائي للصور الممسوحة |
| ✍️ **Handwriting Recognition** | التعرف على الخط العربي الطبي (TrOCR + Custom Models) |
| 🔤 **OCR Fusion V2** | دمج نتائج عدة محركات OCR لتحقيق أعلى دقة |
| 🛡️ **Medical Context Protection** | حماية المصطلحات الطبية من التصحيح الخاطئ |
| ✅ **Spell Checker** | فحص وإصلاح الأخطاء الإملائية بالسياق الطبي |
| 📖 **Medical Dictionary** | قاموس طبي عربي + WordNet للتدقيق اللغوي |
| 🤖 **LLM Proofreading** | مراجعة عبر Jais ونماذج اللغة الكبيرة |
| 📊 **NER** | استخراج الكيانات المسماة من النصوص الطبية |
| 🔄 **Auto Retraining** | جمع بيانات تلقائي + إعادة تدريب النماذج |
| 🧪 **Evaluation Suite** | أدوات قياس الأداء والمقارنة بين النماذج |

## 🚀 الاستخدام السريع

```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
pip install -r requirements.txt
python app/gradio_full_hitl.py
```

ثم افتح `http://localhost:7860` في المتصفح.

## 📁 الهيكل

```
omni-medical-suite/
├── app/                    # واجهة Gradio الرئيسية
│   ├── gradio_full_hitl.py # التطبيق الكامل (Human-in-the-Loop)
│   └── gradio_ui.py        # واجهة بديلة
├── src/                    # الوحدات الأساسية
│   ├── ocr/                # محركات OCR والدمج
│   ├── ner/                # استخراج الكيانات المسماة
│   ├── llm/                # تكامل نماذج اللغة الكبيرة
│   └── layout/             # تحليل تخطيط المستندات
├── packages/               # حزم Python فرعية
├── tools/                  # أدوات مساعدة
├── scripts/                # سكريبتات التشغيل والجمع والتدريب
├── dictionaries/           # قواميس طبية + WordNet
├── config/                 # إعدادات النماذج والمعالجة
├── tests/                  # اختبارات الوحدات والتكامل
├── docs/                   # التوثيق الكامل
├── hf-space/               # إعدادات HuggingFace Space
├── docker/                 # ملفات Docker للنشر
├── .github/                # GitHub Actions CI/CD
└── benchmarks/             # نتائج تقييم الأداء
```

## 📝 التوثيق

| الملف | المحتوى |
|-------|---------|
| `docs/` | توثيق تفصيلي لكل وحدة |
| `PIPELINE.md` | شرح خط المعالجة الكامل |
| `MODES.md` | أوضاع التشغيل المختلفة |
| `DEPLOY.md` | دليل النشر |
| `CONTRIBUTING.md` | إرشادات المساهمة |
| `MODEL_CARD.md` | بطاقة النموذج |
| `CHANGELOG.md` | سجل التغييرات |

## 🐳 النشر

### Docker (مُوصى به)
```bash
docker-compose -f docker-compose.lite.yml up -d
```

### HuggingFace Space
انظر `hf-space/` للإعدادات والنشر المباشر.

### التطوير المحلي
```bash
make dev
```

## 🏗️ المتطلبات

- Python 3.10+
- CUDA (اختياري، لتسريع GPU)
- 8+ GB RAM (16+ GB مُوصى بها للنماذج الكبيرة)

## 📜 الرخصة

هذا المشروع مرخص تحت رخصة [MIT](LICENSE).

---

<p align="center">
  <sub>الملفات البنية التحتية المحذوفة محفوظة في
  <a href="https://github.com/DrAbdulmalek/future-dev-ideas">future-dev-ideas</a>
  (قابلة للاسترجاع كاملاً عبر علامة الأمان)</sub>
</p>