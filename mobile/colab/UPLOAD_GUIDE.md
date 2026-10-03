# 📤 رفع OmniMedical_Colab.ipynb — دليل خطوة بخطوة

> كيف ترفع الـ Notebook إلى Google Drive / GitHub / HuggingFace Spaces.

---

## 🅰️ الطريقة 1: رفع لـ Google Colab مباشرة (الأسرع)

1. **افتح [colab.research.google.com](https://colab.research.google.com/)**.
2. من القائمة: **File → Upload notebook**.
3. اختر `OmniMedical_Colab.ipynb` من جهازك.
4. انتظر ثوانٍ — سيفتح Notebook بالكامل.
5. **Runtime → Change runtime type → T4 GPU**.
6. **Runtime → Run all** (أو Shift+Enter خلية بخلية).

✅ **مزايا**: لا حاجة لتثبيت شيء، جاهز فوراً.
❌ **عيوب**: يُفصل بعد 12 ساعة، الـ outputs تُحفظ في جلستك فقط.

---

## 🅱️ الطريقة 2: حفظ في Google Drive (للاحتفاظ بالنتائج)

1. ارفع Notebook كما في الطريقة 1.
2. **File → Save a copy in Drive**.
3. سيُحفظ في: `My Drive/Colab Notebooks/OmniMedical_Colab.ipynb`.
4. للوصول لاحقاً: **File → Open notebook → Google Drive**.

✅ **مزايا**: Notebook محفوظ، يمكن تعديله لاحقاً، المشاركة سهلة.

---

## 🅲️ الطريقة 3: رفع لـ GitHub (للتوزيع)

```bash
# من جهازك
cd omni-medical-suite/mobile/colab
git add OmniMedical_Colab.ipynb
git commit -m "feat: add unified Colab notebook (Trainer + Scanner + Fine-Tune + APK Build)"
git push origin main
```

ثم للوصول المباشر عبر Colab:
```
https://colab.research.google.com/github/DrAbdulmalek/omni-medical-suite/blob/main/mobile/colab/OmniMedical_Colab.ipynb
```

✅ **مزايا**: رابط دائم، يظهر في README، CI يمكن أن يبني APK منه.

---

## 🅳️ الطريقة 4: رفع لـ HuggingFace Spaces (للتشغيل الدائم)

1. اذهب إلى [huggingface.co/new-space](https://huggingface.co/new-space).
2. **Name**: `omnimedical-colab`.
3. **SDK**: `Jupyter` (أو `Gradio` لو تريد UI ثابت).
4. **Visibility**: Public.
5. ارفع `OmniMedical_Colab.ipynb` عبر واجهة HF.
6. أضف `requirements.txt`:

```txt
gradio==4.19.2
opencv-python-headless==4.9.0.80
pytesseract==0.3.10
pdf2image==1.17.0
transformers==4.40.2
torch==2.2.1
```

7. **Create Space** → سيعمل على `https://drabdulmalek-omnimedical-colab.hf.space`.

✅ **مزايا**: تشغيل دائم، رابط قابل للمشاركة.
❌ **عيوب**: حجم محدود (50GB)، لا يدعم بناء APK داخل الـ Space.

---

## 🅴️ الطريقة 5: مشاركة مباشرة عبر رابط nbviewer

بعد رفع Notebook لـ GitHub:
```
https://nbviewer.org/github/DrAbdulmalek/omni-medical-suite/blob/main/mobile/colab/OmniMedical_Colab.ipynb
```

يعرض كـ HTML ثابت (للقراءة فقط، لا تشغيل).

---

## 📋 Checklist قبل الرفع

- [ ] Notebook يفتح بدون أخطاء (افتحه في Jupyter محلياً للتحقق).
- [ ] كل الخلايا لها `@title` واضح.
- [ ] لا توكنات حساسة (HF_TOKEN, GITHUB_PAT) مكتوبة مباشرة — استخدم متغيرات.
- [ ] ترخيص مذكور في الـ markdown الأول.
- [ ] روابط GitHub/HF صحيحة.

---

## 🚀 بعد رفع Notebook

1. **اخبر المستخدمين بالرابط**.
2. **أضف لـ README.md الرئيسي** قسم "Try on Colab":
   ```markdown
   ## 🚀 جرب على Colab
   [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](
   https://colab.research.google.com/github/DrAbdulmalek/omni-medical-suite/blob/main/mobile/colab/OmniMedical_Colab.ipynb)
   ```
3. **تتبّع الاستخدام**: GitHub insights → Traffic → Clones.

---

## 🆘 مشاكل شائعة

| المشكلة | الحل |
|---------|------|
| `Notebook validation failed: cells[*].source must be array` | تأكد أن .ipynb JSON صحيح (افتحه في Jupyter) |
| `Colab can't find GPU` | Runtime → Change runtime type → T4 → Save |
| `pip install fails` | أضف `!pip install --upgrade pip` في أول خلية |
| `Buildozer timeout` | ابقَ مفعّلاً، حرك الماوس كل 30 دقيقة |

---

**تم بناء ❤️ بواسطة Dr. Abdulmalek** — [github.com/DrAbdulmalek](https://github.com/DrAbdulmalek)
