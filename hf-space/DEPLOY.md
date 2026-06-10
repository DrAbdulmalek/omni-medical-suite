# 🚀 نشر المنصة على Hugging Face Spaces

## خطوات النشر

### 1. تثبيت الأدوات
```bash
pip install huggingface_hub
```

### 2. تسجيل الدخول
```bash
huggingface-cli login
# أدخل التوكن الخاص بك من: https://huggingface.co/settings/tokens
```

### 3. إنشاء Space جديد
```bash
huggingface-cli repo create medical-ocr-demo --type space --space_sdk docker
```

### 4. نسخ الملفات إلى Space
```bash
git clone https://huggingface.co/spaces/DrAbdulmalek/medical-ocr-demo
cd medical-ocr-demo

# نسخ ملفات النشر من المستودع الرئيسي
cp -r ../../omni-medical-suite/hf-space/* .

git add .
git commit -m "Initial Medical OCR Space deployment"
git push
```

### 5. انتظر البناء
بعد بضع دقائق، سيكون الرابط جاهزاً:
**https://huggingface.co/spaces/DrAbdulmalek/medical-ocr-demo**

## ⚙️ الإعدادات الموصى بها

| الإعداد | القيمة المقترحة |
|---------|----------------|
| SDK | Docker |
| Hardware | T4 Small (للتجربة) أو CPU basic (مجاني) |
| License | MIT |
| Visibility | Public |

## 🔗 بعد النشر

- **API التفاعلية**: `https://huggingface.co/spaces/DrAbdulmalek/medical-ocr-demo/docs`
- **حالة المنصة**: `https://huggingface.co/spaces/DrAbdulmalek/medical-ocr-demo/health`
- **تصحيح نص**: `POST /correct` مع JSON body
