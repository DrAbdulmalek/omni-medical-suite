# 🚀 Deployment Guide — Omni Medical Suite v1.0.0

**تاريخ النشر:** 9 يوليو 2026
**الغرض:** دليل خطوة بخطوة لنشر Omni Medical Suite في بيئات مختلفة.

---

## 📋 جدول المحتويات

1. [نشر محلي (Local Development)](#1-نشر-محلي-local-development)
2. [نشر باستخدام Docker](#2-نشر-باستخدام-docker)
3. [نشر على Hugging Face Spaces](#3-نشر-على-hugging-face-spaces)
4. [نشر على خادم إنتاج (Production Server)](#4-نشر-على-خادم-إنتاج-production-server)
5. [النسخ الاحتياطي والاستعادة](#5-النسخ-الاحتياطي-والاستعادة)
6. [استكشاف الأخطاء وإصلاحها](#6-استكشاف-الأخطاء-وإصلاحها)

---

## 1. نشر محلي (Local Development)

### 1.1 المتطلبات المسبقة

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv git

# Manjaro/Arch
sudo pacman -S python python-pip git
```

### 1.2 استنساخ المستودع

```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
```

### 1.3 إعداد البيئة الافتراضية

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows
```

### 1.4 تثبيت الاعتماديات

```bash
# التثبيت الأساسي
pip install -e .

# مع خيارات إضافية
pip install -e .[api,ml,dev,ops]  # الكل
```

### 1.5 إعداد متغيرات البيئة

```bash
cp .env.example .env
nano .env
```

أدخل القيم التالية على الأقل:

```env
APP_ENV=development
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_key_here
DB_USER=postgres
DB_PASSWORD=your_db_password
REDIS_PASSWORD=your_redis_password
```

### 1.6 تهيئة قاعدة البيانات

```bash
# تشغيل PostgreSQL محلياً (اختياري)
docker run -d --name postgres-dev \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=omni \
  -p 5432:5432 postgres:16

# تهيئة الجداول
alembic upgrade head
```

### 1.7 تشغيل التطبيقات

#### Gradio (HITL)
```bash
python app/gradio_full_hitl.py
# → http://localhost:7860
```

#### FastAPI (Backend)
```bash
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs
```

#### Next.js (Frontend)
```bash
cd apps/web && npm install && npm run dev
# → http://localhost:3000
```

### 1.8 تشغيل الاختبارات

```bash
pytest -v                                    # الكل
pytest packages/scanner_fixer/ -v           # حزمة معينة
pytest --cov=packages/ --cov-report=html    # مع تغطية
```

---

## 2. نشر باستخدام Docker

### 2.1 المتطلبات المسبقة

```bash
# Ubuntu/Debian
sudo apt install docker.io docker-compose

# التحقق
docker --version
docker-compose --version
```

### 2.2 بناء الصورة

```bash
# بناء صورة Gradio
docker build -f Dockerfile.gradio -t omni-ocr .

# بناء الصورة الكاملة
docker build -t omni-suite .
```

### 2.3 تشغيل Gradio فقط (خفيف)

```bash
docker-compose up gradio
# → http://localhost:7860
```

### 2.4 تشغيل جميع الخدمات

```bash
# التطبيقات + البنية التحتية
docker-compose --profile infra up -d
```

### 2.5 تشغيل المراقبة

```bash
docker-compose -f docker-compose.yml -f infra/monitoring/docker-compose.monitoring.yml up -d
```

### 2.6 الخدمات المتاحة

| الخدمة | المنفذ | الوصف |
|--------|--------|-------|
| **Gradio** | 7860 | واجهة HITL للتصحيح |
| **FastAPI** | 8000 | واجهة برمجة التطبيقات |
| **PostgreSQL** | 5432 | قاعدة البيانات (داخلي) |
| **Redis** | 6379 | التخزين المؤقت (داخلي) |
| **Qdrant** | 6333 | متجهات (داخلي) |
| **Prometheus** | 9090 | المقاييس (monitoring) |
| **Grafana** | 3000 | لوحات المراقبة (monitoring) |

### 2.7 أوامر Docker مفيدة

```bash
docker-compose ps                              # حالة الخدمات
docker-compose logs -f gradio                  # سجلات Gradio
docker-compose restart api                     # إعادة تشغيل
docker-compose down                            # إيقاف الكل
docker-compose down -v                         # إيقاف + حذف وحدات التخزين
```

---

## 3. نشر على Hugging Face Spaces

### 3.1 المتطلبات

- حساب Hugging Face مع Access Token (صلاحيات `write`)

### 3.2 إعداد Auto-deploy

1. في GitHub: `Settings` > `Secrets and variables` > `Actions`
2. أضف سر: `HF_TOKEN` = توكن Hugging Face
3. ادفع أي تغيير إلى `hf-space/` — سيُنشغل الـ workflow تلقائياً

### 3.3 ملفات HF Space

| الملف | الوصف |
|-------|-------|
| `hf-space/app.py` | تطبيق Gradio (460 سطر) |
| `hf-space/Dockerfile` | Multi-stage مع PaddleOCR pre-cache |
| `hf-space/requirements.txt` | الاعتماديات المحسّنة |
| `hf-space/README.md` | YAML header |

### 3.4 النشر اليدوي

```bash
git clone https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr
cp -r hf-space/* omni-medical-ocr/
cd omni-medical-ocr
git add . && git commit -m "deploy" && git push
```

### 3.5 الرابط

```
https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr
```

---

## 4. نشر على خادم إنتاج (Production Server)

### 4.1 إعداد الخادم

```bash
# تحديث النظام
sudo apt update && sudo apt upgrade -y

# تثبيت Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# إضافة المستخدم إلى مجموعة docker
sudo usermod -aG docker $USER
```

### 4.2 استنساخ وإعداد

```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite

# إعداد متغيرات الإنتاج
cat > .env.production << EOF
APP_ENV=production
DEBUG=False
LOG_LEVEL=INFO
ALLOWED_HOSTS=your-domain.com
SECRET_KEY=$(openssl rand -base64 32)
JWT_SECRET_KEY=$(openssl rand -base64 32)
DB_HOST=postgres
DB_PASSWORD=$(openssl rand -base64 24)
REDIS_PASSWORD=$(openssl rand -base64 24)
GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 24)
EOF
```

### 4.3 تشغيل الإنتاج

```bash
docker-compose --env-file .env.production --profile infra up -d
```

### 4.4 Nginx Reverse Proxy

```bash
sudo apt install nginx

sudo tee /etc/nginx/sites-available/omni-medical << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:7860;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /metrics {
        allow 127.0.0.1;
        deny all;
        proxy_pass http://localhost:9090;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/omni-medical /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx
```

### 4.5 SSL (Let's Encrypt)

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 5. النسخ الاحتياطي والاستعادة

### 5.1 النسخ الاحتياطي التلقائي

```bash
# تشغيل يدوي
python scripts/backup.py

# النسخ الاحتياطي يحفظ في /app/backups/:
#   database/  — pg_dump (SQL)
#   redis/     — RDB snapshot
#   files/     — app/, packages/, src/, config/
```

### 5.2 استعادة

```bash
# قاعدة البيانات
docker exec -i postgres psql -U omni_user -d omni < backups/database/omni_medical_YYYYMMDD.sql

# Redis
docker exec -i redis redis-cli --rdb backups/redis/redis_YYYYMMDD.rdb
```

### 5.3 جدولة يومية (cron)

```bash
0 2 * * * cd /opt/omni-medical-suite && python scripts/backup.py
```

---

## 6. استكشاف الأخطاء وإصلاحها

### 6.1 Gradio لا يعمل

```bash
docker-compose logs gradio        # فحص السجلات
docker-compose restart gradio     # إعادة التشغيل
sudo netstat -tulpn | grep 7860  # فحص المنفذ
```

### 6.2 قاعدة البيانات غير متصلة

```bash
docker-compose ps postgres        # فحص الحالة
docker-compose restart postgres   # إعادة التشغيل
docker-compose exec api python -c "import asyncpg; print('ok')"  # فحص الاتصال
```

### 6.3 OCR لا يعمل

```bash
# تثبيت لغة Tesseract العربية
docker-compose exec api apt-get install -y tesseract-ocr-ara

# التحقق من PaddleOCR
docker-compose exec api python -c "import paddleocr; print('OK')"

# إعادة التشغيل
docker-compose restart gradio
```

### 6.4 HF Space بناء فاشل

1. تحقق من سجل البناء في صفحة Space
2. تأكد من `Dockerfile` و `requirements.txt`
3. قلل حجم الصورة باستخدام `python:3.11-slim`
4. تأكد من `.dockerignore` يمنع الملفات الكبيرة

### 6.5 فحص الصحة

```bash
curl http://localhost:8000/health           # فحص شامل
curl http://localhost:8000/health/liveness   # لiveness
curl http://localhost:8000/health/readiness  # readiness
```

---

## 📞 الدعم

- **GitHub Issues**: https://github.com/DrAbdulmalek/omni-medical-suite/issues
- **Hugging Face Space**: https://huggingface.co/spaces/DrAbdulmalek/omni-medical-ocr

---

## 📊 ملخص طرق النشر

| الطريقة | المستوى | الوقت |
|---------|---------|-------|
| محلي (Local) | تطويري | 5 دقائق |
| Docker | تطويري/إنتاجي | 10 دقائق |
| HF Spaces | تجريبي/إنتاجي | 15 دقيقة |
| خادم إنتاج (VPS) | إنتاجي | 30 دقيقة |

**ابدأ بـ HF Spaces أو Docker للحصول على أسرع تجربة!**