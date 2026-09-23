# INTEGRATION POINTS — تكامل الوثائق مع الكود القائم (PLANNED)

> ⚠️ **IMPLEMENTATION: NOT NOW — PLANNED FOR PHASE V-X** لكل بند أدناه.
> لا يُعدَّل أي كود production في هذه المرحلة التوثيقية. أسماء الملفات تتبع
> حالة المستودع على `main@39640a6` + حزمة AHW على فرع ATR (PR #136 قيد المراجعة).

| الملف الحالي | التكامل | التعديل | الأولوية | الحالة |
|---|---|---|---|---|
| `correction_server.py` (AHW) | يعمل على VPS خلف nginx | **لا تعديل** (bind loopback + nginx proxy) | CRITICAL | NOT NOW — V-2 |
| `segment_batch.py` / `ahw/segment.py` | عند الرفع على VPS | **لا تعديل** | HIGH | NOT NOW — V-2 |
| `train_server.py` | على Colab فقط — **لا يعمل تدريب على VPS** (بلا GPU/RAM كافٍ) | لا تعديل | HIGH | NOT NOW — V-6 |
| `corrections.xlsx/csv` (بيانات) | تنتقل إلى VPS | نسخ + تحقق SHA256 | CRITICAL | NOT NOW — V-3 |
| `Dockerfile.atr` / `docker-compose.atr.yml` | يُعاد استخدامها على VPS (اختياري) | جديد إن لزم (env production) | MEDIUM | NOT NOW — V-5 |
| Nginx config | reverse proxy + SSL | **جديد** (`deploy/configs/nginx-ahw.conf.template` موجود كقالب) | HIGH | NOT NOW — V-1/V-2 |
| systemd services | تشغيل الخدمات | **جديد** (قالبان في `deploy/configs/`) | HIGH | NOT NOW — V-2 |
| Backup script | نسخ مشفر يومي | **جديد** (`automation/vps/*.template`) | HIGH | NOT NOW — V-4 |
| Monitoring | UptimeRobot خارجي (مجاني) | **لا تعديل كود** | MEDIUM | NOT NOW — V-4 |

## لكل بند: الخطوات/الأوامر/الملفات/المخاطر (مختصر)

- **V-2 نشر الخدمات:** clone → venv → `pip install -r requirements-atr.txt`
  (فرع ATR) → systemd (القالب) → nginx (القالب) → تحقق `/api/status`.
  المخاطر: تعارض منافذ، صلاحيات، ذاكرة عند التقطيع بـDPI عالٍ → البدء بـ150-200.
- **V-3 نقل البيانات:** تصدير محلي → SHA256 → نقل مشفر → تحقق على VPS →
  عيّنات عشوائية بصريًا. المخاطر: فقدان صفوف/ترميز عربي → مقارنة عدّ الصفوف.
- **V-4 Backup/Monitoring:** cron + GPG + gh push؛ UptimeRobot على `/api/status`.
  المخاطر: تسريب مفتاح GPG → passphrase + تخزين المفتاح الخاص خارج VPS.
- **V-6 Colab:** انظر [../colab-pipeline/](../colab-pipeline/README.md).

**قاعدة ذهبية:** كل تكامل يُختبر أولًا على Codespaces/محليًا قبل VPS الإنتاجي.
