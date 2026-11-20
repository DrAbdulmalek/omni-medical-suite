# Scanner Fixer Pro v2.0 - Docker Deployment Guide

## نظرة عامة

نظام Docker متكامل لـ Scanner Fixer Pro مع إصلاحات معروفة لمشاكل التوافقية:

| المشكلة | السبب | الحل |
|---------|-------|------|
| `ImportError: HfFolder` | `huggingface_hub>=1.0` حذف `HfFolder` | تثبيت `huggingface_hub<1.0.0` |
| `TypeError: bool is not iterable` | `pydantic>=2.11` يضع `additionalProperties: true` | تثبيت `pydantic<2.11.0` |
| `gradio_client` crash | عدم توافق مع الإصدارات الجديدة | تثبيت `gradio-client<1.0.0` |

## الملفات

```
.
├── Dockerfile.final              # ملف Docker الرئيسي (multi-stage)
├── docker-compose.final.yml      # Docker Compose للإنتاج
├── build-and-push.sh             # سكريبت بناء ورفع
├── run.sh                        # runner لـ Linux/macOS
├── run.bat                       # runner لـ Windows
└── .dockerignore                 # تجاهل الملفات غير الضرورية
```

## التشغيل السريع

### 1. Web Mode (Gradio) - موصى به للسيرفرات

```bash
# Linux/macOS
./run.sh -m web -t hf_xxxxxxxx

# أو Docker Compose
docker-compose -f docker-compose.final.yml up -d scanner-fixer-web

# Windows
run.bat -m web -t hf_xxxxxxxx
```

**الوصول:** http://localhost:7860

### 2. Desktop Mode (Tkinter)

**Linux:**
```bash
xhost +local:docker
./run.sh -m desktop
```

**macOS:**
```bash
# 1. تثبيت XQuartz: https://www.xquartz.org/
# 2. XQuartz > Preferences > Security > ✅ Allow connections
# 3. إعادة تشغيل XQuartz
xhost +
./run.sh -m desktop
```

**Windows:**
```bash
# 1. تثبيت VcXsrv: https://sourceforge.net/projects/vcxsrv/
# 2. تشغيل XLaunch > Multiple windows > Display 0
# 3. ✅ Disable access control
set DISPLAY=host.docker.internal:0.0
run.bat -m desktop
```

### 3. Development Shell

```bash
./run.sh -m shell
# أو
docker-compose -f docker-compose.final.yml --profile shell run --rm scanner-fixer-shell
```

## البناء والرفع

```bash
chmod +x build-and-push.sh

# بناء فقط
./build-and-push.sh

# بناء + رفع إلى Docker Hub
./build-and-push.sh --push-dockerhub

# بناء + رفع إلى GitHub Container Registry
./build-and-push.sh --push-ghcr

# بناء + رفع للجميع
./build-and-push.sh --push-all --version 2.0.1
```

## الإعدادات

### متغيرات البيئة

| المتغير | الوصف | الافتراضي |
|---------|-------|----------|
| `HF_TOKEN` | توكن Hugging Face | (فارغ) |
| `HF_USERNAME` | اسم المستخدم | `DrAbdulmalek` |
| `GRADIO_SERVER_NAME` | عنوان الخادم | `0.0.0.0` |
| `GRADIO_SERVER_PORT` | المنفذ | `7860` |
| `DISPLAY` | عنوان X11 | `:0` |

### Docker Compose Volumes

| Volume | الوصف |
|--------|-------|
| `scanner-data` | بيانات الإدخال |
| `scanner-output` | النتائج |
| `scanner-backups` | النسخ الاحتياطية المحلية |
| `scanner-logs` | السجلات |

## التحقق من الصحة

```bash
# فحص الحالة
docker ps

# سجلات التطبيق
docker logs -f scanner-fixer-web

# اختبار الـhealth check
curl http://localhost:7860/

# دخول للحاوية
docker exec -it scanner-fixer-web /bin/bash
```

## استكشاف الأخطاء

### المشكلة: `cannot connect to X server`
**الحل:** تأكد من تشغيل X11 وتفعيل `xhost +`

### المشكلة: `ImportError: libGL.so.1`
**الحل:** تم إصلاحه في Dockerfile (libgl1-mesa-glx مثبت)

### المشكلة: Arabic text not displaying
**الحل:** تم تثبيت fonts-noto وfonts-arabeyes في Dockerfile

## الترخيص

MIT License - جزء من Omni Medical Suite
