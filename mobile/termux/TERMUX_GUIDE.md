# 📱 دليل Termux الكامل — OmniMedical Suite على Android

> شغّل OmniMedical OCR مباشرة على هاتفك Android عبر Termux.
> يعمل **offline** بعد التثبيت — لا حاجة لـ AppImage ولا APK.

---

## 🎯 لماذا Termux؟

| الحل | يعمل على Android? | ملاحظة |
|------|-------------------|--------|
| ❌ AppImage | لا | x86_64 فقط — هاتفك ARM64 |
| ⚠️ APK (Kivy) | نعم، لكن يحتاج بناء على Ubuntu | معقد للبناء |
| ✅ PWA (HF Space) | نعم | يحتاج إنترنت |
| ✅ **Termux** (هذا الدليل) | **نعم، فوراً** | **offline، سريع، native** |

**المزايا**:
- 🔋 يعمل offline (بعد تثبيت النماذج)
- 🚀 سريع (native ARM64، لا emulation)
- 💾 كل البيانات على هاتفك
- 🆓 لا يحتاج Root

---

## 📋 المتطلبات

- هاتف Android 9.0+ (ARM64 — كل الهواتف الحديثة).
- مساحة تخزين: ~500 MB للتثبيت.
- RAM: 2 GB+ موصى به.
- إنترنت للتثبيت فقط (≈300 MB تنزيل).

---

## 1️⃣ تثبيت Termux

### الطريقة الموصى بها (F-Droid)

> ⚠️ **لا تثبّت Termux من Play Store** — الإصدار هناك قديم وغير مدعوم.

1. افتح [F-Droid](https://f-droid.org) على هاتفك.
2. ثبّت F-Droid (إن لم يكن مثبتاً).
3. ابحث عن **Termux** في F-Droid.
4. ثبّته.

### أو من GitHub مباشرة

1. اذهب إلى: [github.com/termux/termux-app/releases](https://github.com/termux/termux-app/releases)
2. نزّل أحدث `termux-app_v0.118.x+github-debug_arm64-v8a.apk`.
3. افتح APK → Install (فعّل Unknown Sources إن لزم).

---

## 2️⃣ تثبيت OmniMedical (One-liner)

افتح Termux وانسخ هذا السطر:

```bash
pkg install -y git curl && \
curl -fsSL https://raw.githubusercontent.com/DrAbdulmalek/omni-medical-suite/main/mobile/termux/install_termux.sh | bash
```

سيظهر لك menu:
```
اختر وضع التثبيت:
  1) Termux native (أسرع، يستخدم pkg مباشرة)
  2) proot-distro Ubuntu ARM64 (أكثر توافقاً مع المشروع الأم)
  3) Exit
```

اختر **1** (Termux native) للسرعة، أو **2** (Ubuntu) للتطابق الكامل مع بيئة المشروع.

### أو: تثبيت تفاعلي

```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite/mobile/termux
bash install_termux.sh
```

المدة المتوقعة: **5-10 دقائق** (تنزيل ~300 MB).

---

## 3️⃣ التشغيل

### الطريقة 1: اختصار omni-ocr

بعد التثبيت، شغّل:

```bash
omni-ocr
```

سيظهر:
```
🚀 Starting OmniMedical OCR on port 7860...
📱 Open in browser: http://localhost:7860
⏹  Stop with: omni-stop
```

### الطريقة 2: تشغيل مباشر

```bash
cd ~/omni_workspace
python termux_app.py --port 7860
```

### فتح الواجهة في المتصفح

1. افتح **Chrome / Firefox** على هاتفك.
2. اذهب إلى: **`http://localhost:7860`**
3. سترى Gradio UI كامل.

> 💡 **نصيحة**: احفظ الصفحة في Bookmarks لتسهيل الوصول.

---

## 4️⃣ استخدام التطبيق

### تبويب Trainer (Handwriting)

1. **📤 ارفع صورة / PDF** — اختر من ملفات هاتفك.
2. **🌐 اختر اللغة** — `ara+eng` (افتراضي للنصوص الطبية العربية).
3. **🔄 اضغط معالجة** — ستظهر الكلمات المُستخرجة في المعرض.
4. **📝 عدّل النص** في حقل "التصحيح".
5. **💾 اضغط حفظ التصحيح** — يُحفظ في SQLite + JSONL.
6. **📊 اضغط إحصائيات** — لعرض التقدّم.

### تبويب Scanner (Scanner Fixer)

#### صورة واحدة:
1. ارفع صورة ممسوحة.
2. اختر الوضع: `all` (موصى) أو `deskew` فقط أو `crop` فقط.
3. اضغط **🔄 معالجة**.

#### Batch + ZIP:
1. ارفع عدة صور.
2. اختر الوضع.
3. اضغط **🔄 معالجة Batch** — سيُنشأ ملف ZIP في `~/omni_workspace/exports/`.

### تبويب Tools

- **SHA256**: احسب hash لأي ملف.
- **معلومات النظام**: مسارات الملفات + إعدادات Tesseract.

---

## 5️⃣ الوصول من الكمبيوتر (نفس الشبكة)

إذا أردت فتح الواجهة من لابتوب على نفس Wi-Fi:

```bash
# في Termux:
ifconfig | grep inet   # ابحث عن IP، مثلاً 192.168.1.5
omni-ocr               # لكن عدّل termux_app.py لـ host="0.0.0.0"
```

أو شغّل بشكل صريح:

```bash
cd ~/omni_workspace
python termux_app.py --host 0.0.0.0 --port 7860
```

ثم على اللابتوب: `http://192.168.1.5:7860`.

---

## 6️⃣ إنشاء اختصار على الشاشة الرئيسية

### الطريقة 1: Termux:Widget (موصى بها)

1. ثبّت **Termux:Widget** من [F-Droid](https://f-droid.org/packages/com.termux.widget/).
2. في Termux:
   ```bash
   mkdir -p ~/.shortcuts
   cat > ~/.shortcuts/OmniMedical.sh << 'EOF'
   #!/data/data/com.termux/files/usr/bin/bash
   termux-wake-lock
   omni-ocr
   EOF
   chmod +x ~/.shortcuts/OmniMedical.sh
   ```
3. على الشاشة الرئيسية:
   - Long-press → **Widgets** → **Termux:Widget** → **Add shortcut**.
   - اختر `OmniMedical.sh`.

الآن لديك أيقونة تفتح التطبيق بنقرة واحدة!

### الطريقة 2: PWA-style

1. افتح `http://localhost:7860` في Chrome.
2. Menu (⋮) → **Add to Home screen**.
3. سمّها "OmniMedical".

> ملاحظة: يتطلب هذا أن يكون الخادم يعمل في Termux.

---

## 7️⃣ الأوامر المتاحة

بعد التثبيت، هذه الأوامر متاحة في أي مكان في Termux:

| الأمر | الوظيفة |
|------|--------|
| `omni-ocr` | يفتح Gradio UI على المنفذ 7860 |
| `omni-ocr 8080` | يفتح على منفذ مخصص |
| `omni-stop` | يوقف الخادم |
| `omni-update` | يحدّث المشروع + Python packages |
| `omni-ocr --share` | ينشئ رابط Gradio عام (مؤقت 72 ساعة) |

> إذا لم تعمل الأوامر، شغّل: `source ~/.bashrc` ثم أعد المحاولة.

---

## 8️⃣ استكشاف الأخطاء

### المشكلة: `omni-ocr: command not found`

```bash
# أضف ~/bin إلى PATH
echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# تحقق
which omni-ocr
```

### المشكلة: `tesseract: command not found` أو `ara.traineddata not found`

```bash
# في Termux native:
pkg install tesseract tesseract-data

# في proot Ubuntu:
proot-distro login ubuntu -- bash -c "apt install -y tesseract-ocr tesseract-ocr-ara"
```

### المشكلة: `cv2.error: OpenCV(4.9.0) ... libGL.so.1`

استخدم `opencv-python-headless` (بدون GUI):

```bash
pip uninstall -y opencv-python
pip install opencv-python-headless==4.9.0.80
```

### المشكلة: `pdf2image.exceptions.PDFInfoNotInstalledError`

```bash
# Termux native:
pkg install poppler

# proot Ubuntu:
proot-distro login ubuntu -- bash -c "apt install -y poppler-utils"
```

### المشكلة: المنفذ 7860 محجوز

```bash
omni-ocr 8080   # استخدم منفذ آخر
```

### المشكلة: الذاكرة تنفد (OOM)

```bash
# قلل حجم الصور قبل المعالجة
# أو استخدم swap file (يحتاج Root)
# أو شغّل في proot Ubuntu بدلاً من Termux native

# فحص الذاكرة:
free -h
```

### المشكلة: التطبيق يتعطل بعد فترة

```bash
# فعّل wake lock لمنع Android من قتل العملية
termux-wake-lock

# أو أضفها لبداية ~/.shortcuts/OmniMedical.sh
```

### المشكلة: نص OCR فارغ

```bash
# تحقق من تثبيت لغة Tesseract العربية
tesseract --list-langs

# إن لم تجد ara:
pkg install tesseract-data    # Termux
# أو
apt install tesseract-ocr-ara # Ubuntu proot
```

---

## 9️⃣ التحديثات

### تحديث المشروع

```bash
omni-update
```

يحدّث:
- كود المشروع (git pull).
- Python packages.
- ملف `termux_app.py`.

### تحديث Termux نفسه

```bash
pkg update && pkg upgrade
```

### حذف التثبيت بالكامل

```bash
# إيقاف الخادم
omni-stop

# حذف المشروع
rm -rf ~/omni-medical-suite ~/omni_workspace ~/bin/omni-*

# إلغاء تثبيت Python packages (اختياري)
pip uninstall -y gradio opencv-python-headless pytesseract pdf2image transformers torch
```

---

## 🔟 مقارنة الأداء

| المهمة | Termux native | proot Ubuntu | HF Space |
|--------|--------------|--------------|----------|
| بدء التشغيل | ~3 ثوان | ~10 ثوان | 30-60 ثوان (cold start) |
| OCR لصورة 1MB | ~1.5 ثانية | ~2.5 ثانية | ~2 ثانية (شبكة) |
| Batch 10 صور | ~15 ثانية | ~25 ثانية | ~20 ثانية |
| PDF 5 صفحات | ~8 ثوان | ~12 ثانية | ~10 ثوان |
| استهلاك RAM | 200-400 MB | 300-500 MB | — |
| يعمل offline | ✅ | ✅ | ❌ |

---

## 1️⃣1️⃣ ميزات متقدمة

### ربط مع HF Space (مزامنة التصحيحات)

```bash
# بعد جمع ≥25 تصحيح، صدّرها
cd ~/omni_workspace
python -c "
import json
corrections = []
with open('exports/corrections.jsonl', encoding='utf-8') as f:
    for line in f:
        corrections.append(json.loads(line))
print(f'Exported {len(corrections)} corrections')
"

# ثم ارفعها لـ HF dataset:
huggingface-cli login --token $HF_TOKEN
huggingface-cli upload DrAbdulmalek/omni-corrections corrections.jsonl
```

### Fine-Tuning على الهاتف (تجريبي)

```bash
# ثبّت accelerate + peft
pip install accelerate peft

# شغّل Fine-Tuning script (من Colab notebook)
# ⚠️ يحتاج 4GB+ RAM، قد يفصل Android العملية
python fine_tune.py --jsonl corrections.jsonl --output models/
```

### تفعيل الإشعارات (Termux:API)

```bash
pkg install termux-api

# في termux_app.py، أضف:
import subprocess
def notify(title, msg):
    subprocess.run(["termux-notification", "--title", title, "--content", msg])

# استدعها عند اكتمال OCR:
notify("OmniMedical", "✅ OCR مكتمل")
```

---

## 1️⃣1️⃣.5 التوحيد مع البنية الموحّدة (v1.1.1+)

بدءًا من v1.1.1، تطبيق Termux لم يعد يُعيد تنفيذ منطق معالجة الصور وحفظ التصحيحات
بشكل معزول. بل يستخدم **نفس المكتبات** التي يستخدمها:

- **`packages/desktop/medical_doc_gui_final.py`** (تطبيق سطح المكتب)
- **`packages/core/mobile/server.py`** (خادم PWA)

### ما الذي تغيّر؟

| المنطق | قبل v1.1.1 (معزول) | بعد v1.1.1 (موحَّد) |
|--------|---------------------|----------------------|
| `deskew()` | minAreaRect محلي | `scanner_fixer.deskew.deskew()` (Hough + std guard) |
| `text_aware_crop()` | أكبر contour محلي | `scanner_fixer.crop.auto_crop()` (morphological) |
| `denoise()` / `enhance_contrast()` | cv2 مباشرة | `scanner_fixer.enhance.{remove_noise, enhance_contrast_clahe}()` |
| `save_correction()` | SQLite محلي خاص + JSONL | `CorrectionsDictManager.add()` + `WordCorrectionDB.save_batch()` |
| `get_stats()` | عدّ من SQLite المحلي | `WordCorrectionDB.stats()` (دقة، جلسات، لغات) |

### لماذا يهمّك هذا؟

1. **حلقة التعلّم الموحّدة**: كل تصحيح تُدخله على Termux يُغذّي نفس قاعدة بيانات
   `WordCorrectionDB` التي يستخدمها خادم PWA (إذا شغّلته على نفس الـ workspace).
   هذا يعني أن النموذج التالي سيستفيد من تصحيحاتك حتى لو لم تمرّ بخادم PWA.

2. **خوارزميات أفضل**: `scanner_fixer.deskew` يستخدم Hough line transform مع
   standard-deviation guard، وهو أدقّ بكثير من minAreaRect على الصفحات النصّية.

3. **استثناء متعمَّد لـ OCR engine**: يستمر التطبيق في استخدام `pytesseract`
   مباشرة (وليس `EngineRegistry`/`OCRService` من `app/services/`). السبب:
   `EngineRegistry` يسحب PaddleOCR (~500MB) و EasyOCR (~400MB) كتبعيات اختيارية،
   وهو وزن غير عملي على هاتف Android ARM64 محدود الموارد. `pytesseract` +
   `tesseract-data-arabic` (من `pkg install tesseract-data`) أسرع تثبيتًا وأخفّ.

### التشخيص

شغّل التطبيق وانظر لسجلّ الإقلاع:

```
2026-07-19 12:58:01 [INFO] OmniMedical.Termux: Repo root discovered: /home/.../omni-medical-suite
2026-07-19 12:58:03 [INFO] OmniMedical.Termux: scanner_fixer loaded — image processing delegated to unified library
2026-07-19 12:58:03 [INFO] OmniMedical.Termux: Learning loop wired: CorrectionsDictManager + WordCorrectionDB (shared with PWA server)
```

إذا رأيت `Repo root NOT discovered — running in standalone mode`، فهذا يعني أن
التطبيق لم يجد المستودع. تأكّد من:
- تثبيت المشروع في `~/omni-medical-suite` (الإعداد الافتراضي)
- أو ضبط `OMNI_REPO_ROOT` يدويًا: `export OMNI_REPO_ROOT=/path/to/omni-medical-suite`

في الوضع المستقل، يعود التطبيق للتنفيذ المحلي القديم (OpenCV مباشرة + SQLite محلي).
هذا يضمن بقاء الملف قابلًا للتشغيل حتى لو نُسخ وحده بدون المستودع.

---

## 1️⃣2️⃣ الأمان والخصوصية

- ✅ **كل المعالجة محلية** — لا تُرسل أي بيانات للإنترنت.
- ✅ **التصحيحات محفوظة على هاتفك** — SQLite + JSONL في `~/omni_workspace/`.
- ✅ **لا تتبّع، لا analytics**.
- ⚠️ **قبل مشاركة الـ workspace**: راجع `corrections.jsonl` فقد يحتوي على بيانات طبية حساسة.

---

## 📞 الدعم

- 🐛 Bug: [افتح issue](https://github.com/DrAbdulmalek/omni-medical-suite/issues/new?labels=termux)
- 💬 سؤال: `drabdulmalek@proton.me`
- 📖 وثائق المشروع: [README.md](../../README.md)

---

## 📚 مراجع

- [Termux Wiki](https://wiki.termux.com/)
- [proot-distro docs](https://github.com/termux/proot-distro)
- [Tesseract Arabic](https://github.com/tesseract-ocr/tessdata)
- [Gradio for mobile](https://www.gradio.app/guides/sharing-your-app)

---

**تم الإعداد بـ ❤️ لخدمة الممارسين الطبيين العرب** — يعمل على هاتفك، offline، بلا قيود.
