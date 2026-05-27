# المساهمة في OmniMedical Suite

شكراً لرغبتك في المساهمة! نرحب بطلبات السحب (Pull Requests) والتقارير عن المشكلات.

## متطلبات البيئة

- Node.js 20+ و pnpm (للواجهة الأمامية)
- Python 3.11+ و Poetry (للخادم الخلفي)
- Docker و Docker Compose (للتشغيل المحلي للحاويات المساعدة)
- Redis, PostgreSQL, Qdrant

## إعداد بيئة التطوير

### 1. استنساخ المستودع
```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
```

### 2. تشغيل الخدمات المساعدة (Redis, PostgreSQL, Qdrant)
```bash
docker-compose -f docker-compose.dev.yml up -d
```

### 3. إعداد الخادم الخلفي (FastAPI)
```bash
cd services/api
poetry install
cp .env.example .env  # ثم عدّل المتغيرات
poetry run python -m alembic upgrade head
poetry run uvicorn app.main:app --reload --port 8000
```

### 4. إدارة المهام (Celery)
في نافذة أخرى:
```bash
cd services/api
poetry run celery -A worker.celery_app worker --loglevel=info
```

### 5. إعداد الواجهة الأمامية (Next.js)
```bash
cd frontend
pnpm install
pnpm run dev
```

## تشغيل الاختبارات
```bash
# اختبارات Python
cd services/api
poetry run pytest

# اختبارات الواجهة
cd frontend
pnpm run test
```

## بناء التوثيق محلياً
```bash
cd docs
pnpm install
pnpm run start
```

## معايير كتابة الكود
- استخدم Black و isort لتنسيق Python
- استخدم ESLint و Prettier للواجهة الأمامية
- أضف اختبارات وحدة لأي ميزة جديدة
- حدّث ملفات Swagger/OpenAPI تلقائياً

## عملية طلب السحب (PR)
1. أنشئ فرعاً جديداً من `main` باسم وصفي (`feature/medical-validator`)
2. نفذ تغييراتك مع اختبارات
3. تأكد من اجتياز جميع الاختبارات وفحوصات lint
4. اشرح تغييراتك بوضوح في وصف طلب السحب
