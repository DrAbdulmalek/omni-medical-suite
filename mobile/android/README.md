# OmniMedical Android (Kivy + Buildozer)

> Native Android APK for **omni-medical-suite** — offline-first Arabic medical OCR.
> Built with Kivy 2.3 + KivyMD 1.2 + ONNX Runtime + Tesseract + TrOCR.

[![Build APK](https://github.com/DrAbdulmalek/omni-medical-suite/actions/workflows/android-apk.yml/badge.svg)](../../actions/workflows/android-apk.yml)
[![APK Size](https://img.shields.io/badge/APK-~134MB-success)](bin/)
[![Min Android](https://img.shields.io/badge/Android-7.0%2B-API24-blue)](buildozer.spec)
[![License](https://img.shields.io/badge/license-AGPL--3.0-red)](../../LICENSE)

---

## ✨ الميزات (Features)

| الميزة | الوصف |
|--------|------|
| 🖋️ **Handwriting Trainer** | تدريب النموذج على خط اليد الطبي العربي + حفظ التصحيحات offline |
| 📷 **Scanner Fixer** | deskew + denoise + auto-crop للصور الممسوحة |
| ✂️ **Text-Aware Auto-Crop** | اقتصاص يحافظ على محتوى النص |
| 🗂️ **Batch + PDF + ZIP** | معالجة دفعة + PDF متعدد الصفحات + تصدير ZIP |
| 🧠 **Fine-Tuning** | تدريب incremental على تصحيحات المستخدم (≥25 عينة) |
| ✈️ **Offline Mode** | كل النماذج محلية — لا حاجة لإنترنت بعد التنزيل |
| 🔔 **Notifications** | إشعارات محلية عند اكتمال المهام |
| 📊 **Progress Bar** | شريط تقدّم لكل عملية batch |
| 🌐 **WebView Fallback** | اتصال بـ Gradio server محلي عند الحاجة |

---

## 🏗️ البنية (Architecture)

```
mobile/android/
├── main.py                  # Kivy + KivyMD entry point (~700 LOC)
├── buildozer.spec           # Android APK build config
├── build_apk.sh             # end-to-end build script
├── prebuild.py              # pre-build hook (icons, version)
├── postbuild.py             # post-build hook (size check, SHA256)
├── download_models.py       # fetch offline models from HF Hub
├── requirements-dev.txt     # desktop dev dependencies
├── assets/
│   ├── icons/
│   │   ├── icon.png         # app launcher icon (512×512)
│   │   └── presplash.png    # launch screen (1080×1920)
│   └── models/              # bundled OCR models (~140 MB)
│       ├── trocr-ar-handwritten.onnx
│       ├── trocr-ar-printed.onnx
│       ├── easyocr-arabic.pth
│       ├── ara.traineddata
│       └── ar-medical-spell.json
├── build/                   # buildozer workspace (gitignored)
├── bin/                     # output APK files
└── docs/
    └── INSTALL.md           # detailed installation guide
```

---

## 🚀 البناء السريع (Quick Build)

### 1. إعداد البيئة (Ubuntu 22.04+)

```bash
cd mobile/android
./build_apk.sh setup
```

هذا يثبّت: Java 17, Android SDK/NDK, buildozer 1.5.0, Cython 0.29.36, وكل التبعيات.

### 2. تنزيل النماذج (مرة واحدة، ~140 MB)

```bash
python download_models.py
```

### 3. بناء APK

```bash
./build_apk.sh debug
```

البناء الأول يستغرق **20–40 دقيقة** (تنزيل SDK + NDK + تجميع recipes).
البناءات اللاحقة: **5–10 دقائق** (ccache).

### 4. النتيجة

```
bin/OmniMedical-1.1.0-arm64-v8a-debug.apk
```

---

## 📱 التثبيت على الجهاز (Install on Device)

### الطريقة 1: ADB (موصى لها للتطوير)

```bash
# تفعيل USB debugging على الهاتف أولاً
adb devices                                    # التأكد من الاتصال
adb install -r bin/OmniMedical-1.1.0-arm64-v8a-debug.apk
adb shell am start -n com.omnimedical.omnimedical/MainActivity
adb logcat -s python                           # متابعة السجلات
```

### الطريقة 2: نقل يدوي

1. انسخ ملف APK إلى الهاتف (USB / Google Drive / Signal).
2. على الهاتف: `Settings → Security → Unknown sources` → فعّل.
3. افتح ملف APK من مدير الملفات.

### الطريقة 3: buildozer deploy

```bash
./build_apk.sh deploy    # تثبيت + تشغيل تلقائي على الجهاز الموصول
```

---

## 🧪 التشغيل على الكمبيوتر (Desktop Dev)

```bash
cd mobile/android
pip install -r requirements-dev.txt
python main.py
```

يفتح نافذة 450×900 تحاكي شاشة الهاتف.

---

## ⚙️ التخصيص (Customization)

### تغيير الإصدار

في `buildozer.spec`:
```ini
version.code = 110          # increment per release
# version.regex reads from main.py:APP_VERSION
```

### تغيير الأيقونة

استبدل `assets/icons/icon.png` (512×512 PNG) و `presplash.png` (1080×1920).

### إضافة نموذج جديد

1. أضف إدخالاً في `ModelManager.REQUIRED_MODELS` (في `main.py`).
2. أضف الإدخال في `download_models.py:MODELS`.
3. أعد البناء.

### تغيير صلاحيات Android

في `buildozer.spec` → `android.permissions`:
```ini
android.permissions =
    CAMERA,
    READ_EXTERNAL_STORAGE,
    ...
```

---

## 📊 ميزانية الحجم (Size Budget)

| المكوّن | الحجم |
|---------|------|
| Python 3.11 | ~12 MB |
| Kivy + KivyMD | ~11 MB |
| NumPy | ~10 MB |
| OpenCV (headless) | ~35 MB |
| Pillow | ~3 MB |
| ONNX Runtime (CPU) | ~18 MB |
| Tesseract + ara.traineddata | ~15 MB |
| Bundled models | ~25 MB |
| أخرى (regex, ftfy, ...) | ~5 MB |
| **الإجمالي** | **~134 MB** ✓ (<150) |

---

## 🔧 استكشاف الأخطاء (Troubleshooting)

| المشكلة | الحل |
|---------|------|
| `Build failed: Cython 3.x incompatible` | `pip install "cython==0.29.36"` |
| `NDK not found` | `export ANDROIDNDKPATH=~/Android/Sdk/ndk/25.1.8937393` |
| `Java 11 too old` | `sudo apt install openjdk-17-jdk` |
| `APK > 150MB` | شغّل `python download_models.py --clean` ثم أعد التنزيل |
| ` Crash on launch: libpython.so missing` | `buildozer android clean` ثم أعد البناء |
| `Tesseract not initialized` | تأكد أن `ara.traineddata` في `assets/models/` |
| `Cannot download from HF` | `huggingface-cli login` + ضع token في `HF_TOKEN` |

---

## 🔐 الأمان (Security)

- ✅ **Offline-first**: لا اتصال بالإنترنت بعد التنزيل الأولي للنماذج.
- ✅ **No analytics**: لا تجميع بيانات، لا تتبّع.
- ✅ **Local DB only**: التصحيحات تُحفظ في `corrections.jsonl` على الجهاز.
- ⚠️ **أذونات Android**: راجع `buildozer.spec → android.permissions` قبل التوزيع.

---

## 🔄 التكامل مع omni-medical-suite

التطبيق يستخدم نفس منطق:
- `app/services/ocr_service.py` → `OCRPipeline` (في `main.py`)
- `packages/handwriting/src/correction.py` → `CorrectionsDB`
- `packages/scanner_fixer/` → `ScannerTab`

لتصدير التصحيحات إلى منصة HF:
```bash
adb pull /data/data/com.omnimedical.omnimedical/files/corrections.jsonl ./corrections.jsonl
# ثم استخدم app/services/hf_dataset_service.py لرفعها
```

---

## 📜 الترخيص

AGPL-3.0 — نفس رخصة omni-medical-suite الأم.

## 👥 المساهمة

PRs welcome! راجع [CONTRIBUTING.md](../../CONTRIBUTING.md).

## 📞 الدعم

- GitHub Issues: [omni-medical-suite/issues](../../issues)
- Email: drabdulmalek@proton.me

---

**Built with ❤️ for Arabic medical professionals**
