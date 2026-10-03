# دليل تثبيت OmniMedical Android

> دليل خطوة بخطوة لبناء وتثبيت تطبيق OmniMedical Android على هاتفك.

---

## 📋 المتطلبات (Requirements)

### على الكمبيوتر (Build Host)

| المتطلب | الإصدار | ملاحظة |
|---------|--------|--------|
| OS | Ubuntu 22.04+ / Debian 12+ / Manjaro 23+ | Windows: استخدم WSL2 |
| RAM | 4 GB+ | 8 GB موصى به |
| Disk | 6 GB free | SDK + NDK + artifacts |
| Python | 3.11 | ليس 3.12 (م مشاكل في recipes) |
| Java | JDK 17 | ليس 11 |
| Internet | ✓ مطلوب للتنزيل الأول | ~2 GB download |

### على الهاتف (Target Device)

| المتطلب | الإصدار |
|---------|--------|
| Android | 7.0 (API 24) أو أحدث |
| Architecture | arm64-v8a (موصى) أو armeabi-v7a |
| Storage | 200 MB free |
| RAM | 2 GB+ |

---

## 1️⃣ إعداد بيئة البناء

### Ubuntu / Debian

```bash
# تحديث الحزم
sudo apt update && sudo apt upgrade -y

# تثبيت التبعيات
sudo apt install -y \
    build-essential \
    ccache \
    git \
    zip unzip \
    openjdk-17-jdk \
    autoconf libtool pkg-config \
    zlib1g-dev \
    libncurses5-dev libncursesw5-dev \
    cmake libffi-dev libssl-dev \
    android-tools-adb android-tools-fastboot

# تثبيت Python 3.11 (إن لم يكن مثبتاً)
sudo apt install -y python3.11 python3.11-dev python3.11-venv python3-pip

# إنشاء virtualenv
python3.11 -m venv ~/venvs/omnimedical
source ~/venvs/omnimedical/bin/activate

# تثبيت buildozer + أدوات البناء
pip install --upgrade pip
pip install \
    "buildozer==1.5.0" \
    "cython==0.29.36" \
    "virtualenv" \
    "sh" \
    "jinja2" \
    "six" \
    "huggingface_hub==0.20.3"
```

### Manjaro / Arch

```bash
sudo pacman -S --needed \
    base-devel \
    ccache \
    jdk17-openjdk \
    android-tools \
    python python-pip

pip install --user \
    "buildozer==1.5.0" \
    "cython==0.29.36" \
    "huggingface_hub==0.20.3"
```

### Windows (WSL2)

```powershell
# في PowerShell كمسؤول
wsl --install -d Ubuntu-22.04
# ثم اتبع خطوات Ubuntu أعلاه داخل WSL
```

### macOS (غير موصى به)

```bash
brew install python@3.11 openjdk@17
brew install --cask android-platform-tools
pip install "buildozer==1.5.0" "cython==0.29.36"
```

---

## 2️⃣ استنساخ المشروع وتنزيل النماذج

```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite/mobile/android

# تنزيل النماذج (~140 MB، مرة واحدة)
python download_models.py
```

**ملاحظة**: بعض النماذج تتطلب تسجيل دخول إلى HuggingFace:
```bash
huggingface-cli login
# أدخل token من https://huggingface.co/settings/tokens
```

---

## 3️⃣ بناء APK

### البناء الكامل (debug)

```bash
./build_apk.sh debug
```

الخطوات الداخلية:
1. `python prebuild.py` — فحص الملفات + توليد الأيقونات
2. `buildozer -v android debug` — البناء (20–40 دقيقة أول مرة)
3. `python postbuild.py` — فحص الحجم + حساب SHA256

### البناء اليدوي

```bash
# تنظيف أي بناء سابق
buildozer android clean

# بناء verbose
buildozer -v android debug 2>&1 | tee build.log

# متابعة التقدّم
tail -f build.log
```

### البناء المتقدّم (release موقّع)

```bash
# 1. توليد keystore (مرة واحدة)
keytool -genkey -v \
    -keystore omnimedical-release.keystore \
    -alias omnimedical \
    -keyalg RSA -keysize 2048 \
    -validity 10000

# 2. تحديد كلمة المرور كمتغير بيئة
export KEYSTORE_PASS="your-password"

# 3. إزالة التعليق عن أسطر key.store في buildozer.spec
# 4. البناء
./build_apk.sh release
```

---

## 4️⃣ تثبيت APK على الهاتف

### تفعيل USB Debugging

1. `Settings → About phone`
2. اضغط `Build number` 7 مرات
3. ارجع: `Settings → Developer options`
4. فعّل `USB debugging`

### الطريقة 1: ADB (موصى بها)

```bash
# توصيل الهاتف عبر USB
adb devices
# يجب أن ترى جهازاً في القائمة

# تثبيت APK
adb install -r bin/OmniMedical-1.1.0-arm64-v8a-debug.apk

# تشغيل التطبيق
adb shell am start -n com.omnimedical.omnimedical/MainActivity

# متابعة السجلات
adb logcat -s python
```

### الطريقة 2: buildozer deploy

```bash
./build_apk.sh deploy
# يثبّت + يشغّل تلقائياً
```

### الطريقة 3: نقل يدوي

```bash
# نسخ APK إلى التخزين القابل للوصول
adb push bin/OmniMedical-1.1.0-arm64-v8a-debug.apk /sdcard/Download/

# على الهاتف: افتح مدير الملفات → Download → اضغط على APK
```

### الطريقة 4: مشاركة لاسلكية (بدون USB)

```bash
# تشغيل خادم HTTP مؤقت
cd bin && python3 -m http.server 8000

# على الهاتف (نفس الشبكة): افتح المتصفح
# http://<computer-ip>:8000/OmniMedical-1.1.0-arm64-v8a-debug.apk
```

---

## 5️⃣ أول تشغيل

عند فتح التطبيق لأول مرة:

1. **شاشة البداية**: شعار OmniMedical (2 ثانية).
2. **تبويب Handwriting** يظهر افتراضياً.
3. إذا لم تكن النماذج مثبتة، يظهر إشعار:
   > "النماذج غير مكتملة — افتح تبويب Models"

### تنزيل النماذج داخل التطبيق

1. اضغط **Models** في الشريط السفلي.
2. اضغط **Download All Models**.
3. انتظر حتى يكتمل التنزيل (~140 MB، يتطلب Wi-Fi).
4. ستظهر علامة ✓ بجانب كل نموذج.

> 💡 **نصيحة**: إذا كنت قد بنيت APK مع `python download_models.py` مسبقاً،
> فالنماذج تكون مضمّنة ولا تحتاج للتنزيل.

---

## 6️⃣ استخدام التطبيق

### تبويب Handwriting Trainer

1. اضغط **اختر صورة خط اليد**.
2. اختر صورة من معرض الهاتف.
3. اضغط **تشغيل OCR**.
4. عدّل النص المستخرج في الحقل.
5. اضغط **حفظ التصحيح** → يُضاف لقاعدة البيانات.
6. بعد 25 تصحيح، يُفعّل زر **Fine-Tune**.

### تبويب Scanner Fixer

1. اختر **صورة** أو **PDF** أو **Batch** (مجلد).
2. اضغط **Deskew** لتصحيح الميل.
3. اضغط **Auto-Crop** للاقتصاص التلقائي.
4. اضغط **Text-Aware Crop** للمعالجة الكاملة.
5. اضغط **ZIP Export** لتصدير كل الصور المعالَجة.

### تبويب Models

- عرض حالة كل نموذج.
- زر **Download All** لتنزيل الكل.
- زر **Toggle Offline Mode** لتشغيل/إطفاء الـ offline.
- معلومات الحجم الكلّي.

### تبويب Settings

- معلومات التطبيق + المسارات.
- تبديل Theme (Light/Dark).
- فتح WebView للاتصال بـ Gradio Server محلي.
- مسح الكاش.

---

## 7️⃣ حل المشاكل الشائعة

### المشكلة: البناء يفشل في تنزيل NDK

```
ERROR: Could not download NDK
```

**الحل**:
```bash
# تنزيل يدوي
wget https://dl.google.com/android/repository/android-ndk-r25b-linux.zip
unzip android-ndk-r25b-linux.zip -d ~/
export ANDROIDNDKPATH=~/android-ndk-r25b
echo 'export ANDROIDNDKPATH=~/android-ndk-r25b' >> ~/.bashrc
```

### المشكلة: `cython: command not found`

```bash
pip install "cython==0.29.36"
# تحقق
cython --version
```

### المشكلة: APK أكبر من 150MB

```bash
# فحص ما يأخذ المساحة
unzip -l bin/OmniMedical-1.1.0-debug.apk | sort -rn -k1 | head -20

# عادةً السبب: assets/models/ كبيرة
python download_models.py --clean
# أعد التنزيل بإصدارات أصغر (quantized ONNX)
```

### المشكلة: التطبيق يتعطل عند الإقلاع

```bash
# سحب السجلات
adb logcat -s python | tail -50

# مشاكل شائعة:
# - "No module named 'X'" → أضفه إلى requirements في buildozer.spec
# - "libpython.so not found" → buildozer android clean ثم أعد البناء
# - "Tesseract not initialized" → تأكد أن ara.traineddata في assets/models/
```

### المشكلة: لا يظهر الهاتف في adb

```bash
# على Linux: إضافة udev rules
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="18d1", MODE="0666", GROUP="plugdev"' | \
    sudo tee /etc/udev/rules.d/51-android.rules
sudo udevadm control --reload-rules

# أعد تشغيل adb
adb kill-server
adb start-server
adb devices
```

---

## 8️⃣ التطوير المتقدّم

### تعديل الكود + اختبار سريع

```bash
# على الكمبيوتر (بدون بناء APK)
python main.py

# تعديل + اختبار
# ... عدّل main.py ...
python main.py
```

### إضافة تبويب جديد

1. في `main.py`, أضف كلاس `MyNewTab(MDBoxLayout)`.
2. في `OmniMedicalApp.build()`, أضف:
   ```python
   bottom.add_widget(self._make_nav_item("MyNew", "icon-name", MyNewTab(self)))
   ```

### CI/CD (GitHub Actions)

أنشئ `.github/workflows/android-apk.yml`:

```yaml
name: Build Android APK
on:
  push:
    tags: ['v*']
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
      - run: pip install "buildozer==1.5.0" "cython==0.29.36"
      - run: cd mobile/android && python download_models.py
      - run: cd mobile/android && buildozer -v android debug
      - uses: actions/upload-artifact@v4
        with:
          name: omnimedical-apk
          path: mobile/android/bin/*.apk
```

### توقيع Play Store

```bash
# 1. توليد upload key
keytool -genkey -v \
    -keystore play-upload.keystore \
    -alias omnimedical-upload \
    -keyalg RSA -keysize 4096 \
    -validity 25000

# 2. البناء بـ release
./build_apk.sh release

# 3. رفع على Play Console
# https://play.google.com/console
```

---

## 9️⃣ المراجع

- [Kivy Documentation](https://kivy.org/doc/stable/)
- [KivyMD Documentation](https://kivymd.readthedocs.io/)
- [Buildozer Documentation](https://buildozer.readthedocs.io/)
- [python-for-android](https://python-for-android.readthedocs.io/)
- [ONNX Runtime Mobile](https://onnxruntime.ai/docs/tutorials/mobile/)
- [Tesseract Android](https://github.com/tesseract-ocr/tesseract)

---

## 📞 الدعم

- 🐛 مشكلة في البناء؟ [افتح issue على GitHub](../../issues/new?labels=android-build)
- 💬 سؤال سريع؟ `drabdulmalek@proton.me`
- 📖 وثائق المشروع الأم: [README.md](../../README.md)

---

**تم الإعداد بـ ❤️ لخدمة الممارسين الطبيين العرب**
