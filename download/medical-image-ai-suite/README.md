# Medical Image AI Suite

> منصة متكاملة لتجهيز ومعالجة الصور الطبية وتدريب نماذج الذكاء الاصطناعي

## نبذة عن المشروع

مشروع **Medical Image AI Suite** هو بيئة عمل Python متكاملة مصممة خصيصاً للتعامل مع الصور الطبية (أشعة سينية، طبقي محوري، رنين مغناطيسي) بصيغتي DICOM و JPG، واستغلالها في تدريب نماذج ذكاء اصطناعي متقدمة.

### المحاور الأربعة

| المحور | الوصف | الحالة |
|--------|-------|--------|
| **توحيد البيانات** | تحويل DICOM/JPG إلى مصفوفات NumPy موحدة | ✅ |
| **تعلّم شبه خاضع للإشراف** | استخراج إشارات تدريب ضعيفة من التقارير | ✅ |
| **توليد بيانات اصطناعية** | توسيع البيانات باستخدام MedGAN | ✅ |
| **توليد تقارير تلقائية** | نماذج VLM لإنشاء تقارير من الصور | ✅ |

## هيكل المشروع

```
medical-image-ai-suite/
├── configs/
│   └── config.yaml              # إعدادات المشروع
├── src/
│   ├── preprocessing/
│   │   ├── dicom_handler.py     # معالجة ملفات DICOM
│   │   ├── image_handler.py     # معالجة صور JPG/PNG
│   │   └── text_handler.py      # تنظيف ومعالجة التقارير النصية
│   ├── ner/
│   │   ├── arabic_ner.py        # استخراج الكيانات الطبية العربية
│   │   └── medical_entities.py  # قاموس الكيانات الطبية
│   ├── semisupervised/
│   │   ├── weak_labels.py       # استخراج الإشارات الضعيفة
│   │   └── trainer.py           # مدرب شبه خاضع للإشراف
│   ├── synthetic/
│   │   └── medgan.py            # توليد صور طبية اصطناعية
│   ├── reportgen/
│   │   └── vlm_reporter.py      # توليد التقارير بالذكاء الاصطناعي
│   └── utils/
│       ├── logger.py            # نظام التسجيل
│       └── metrics.py           # مقاييس التقييم
├── notebooks/
│   └── 01_medical_pipeline.ipynb  # دفتر Colab تفاعلي
├── main_pipeline.py             # نقطة الدخول الموحدة
├── requirements.txt
├── Makefile
└── tests/
```

## التثبيت والتشغيل

### المتطلبات
- Python 3.10+
- CUDA 11.8+ (اختياري لوظائف GPU)

### التثبيت السريع
```bash
# استنساخ المشروع
git clone <repo-url>
cd medical-image-ai-suite

# تثبيت التبعيات
pip install -r requirements.txt

# أو باستخدام Makefile
make install
```

### التشغيل السريع
```bash
# تشغيل خط أنابيب المعالجة الكامل
python main_pipeline.py --phase 1 --input ./data/raw --output ./data/processed

# استخراج الكيانات من التقارير
python main_pipeline.py --phase 2 --input ./data/reports

# تدريب نموذج شبه خاضع للإشراف
python main_pipeline.py --phase 2 --mode train

# توليد بيانات اصطناعية
python main_pipeline.py --phase 3 --mode generate --num 100

# توليد تقارير من الصور
python main_pipeline.py --phase 4 --input ./data/processed
```

### دفتر Colab
افتح `notebooks/01_medical_pipeline.ipynb` في Google Colab للتجربة الفورية.

## الصيغ المدعومة

| الصيغة | القراءة | الكتابة | ملاحظات |
|--------|---------|---------|---------|
| DICOM (.dcm) | ✅ | ✅ | مع دعم كامل للـ metadata |
| JPEG (.jpg) | ✅ | ✅ | مع Windowing ذكي |
| PNG (.png) | ✅ | ✅ | |
| NIfTI (.nii) | ✅ | ✅ | لبيانات 3D |
| NPY (.npy) | ✅ | ✅ | مصفوفات NumPy |

## الترخيص
MIT License - راجع ملف LICENSE للتفاصيل.
