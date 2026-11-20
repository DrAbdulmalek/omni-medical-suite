<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 71 -->

# MASTER PROMPT — Oracle Cloud Deployment Kit
## Omni Medical Suite — Deployment Templates for Oracle Always Free

## 0. النطاق

المهمة: إنشاء حزمة نشر كاملة (Templates + Scripts) لاستخدامها لاحقاً 
على Oracle Cloud Always Free VPS.

النمط: TEMPLATE_ONLY — كل الملفات تُنشأ، لكن لا شيء يُنفَّذ.
لا SSH، لا نسخ، لا تثبيت، لا تشغيل.

الفرع: feature/oracle-deploy-kit

## 1. القواعد المطلقة

ممنوع:
- تعديل أي ملف كود موجود
- الاتصال بأي خادم
- تشغيل أي سكربت
- تنزيل أي شيء
- ادعاء أن شيئاً "مُختبر" أو "يعمل"

مسموح:
- إنشاء ملفات في deploy/oracle/
- إنشاء ملفات README.md توضيحية
- إنشاء Templates كاملة

## 2. المخرجات

### 2.1 الهيكل
deploy/oracle/
├── README.md
├── 00-prerequisites.md
├── 01-oracle-account-setup.md
├── 02-server-provisioning.md
├── 03-initial-hardening.sh
├── 04-install-dependencies.sh
├── 05-clone-and-configure.sh
├── 06-setup-nginx.sh
├── 07-setup-ssl.sh
├── 08-setup-systemd.sh
├── 09-setup-backup.sh
├── 10-verify-deployment.sh
├── rollback.sh
├── update.sh
├── configs/
│   ├── nginx-ahw.conf.template
│   ├── ahw-correction.service
│   ├── ahw-training.service
│   └── .env.template
└── TROUBLESHOOTING.md

### 2.2 لكل سكربت .sh
- shebang: #!/bin/bash
- set -euo pipefail
- idempotent (يمكن تشغيله أكثر من مرة بأمان)
- تعليقات عربية
- تحقق قبل كل خطوة حساسة
- رسالة "SUCCESS" في النهاية
- header يشرح: المتطلبات، الوقت المتوقع، الأثر

### 2.3 README.md الرئيسي
يحتوي:
- نظرة عامة على العملية
- متطلبات Oracle Free Tier
- الجدول الزمني (أسبوع)
- خطوات التسجيل من سوريا (بالتفصيل)
- تحذير بارز: "لا تُنفّذ على بيانات حقيقية حتى تتحقق من الأمان"
- Rollback plan

### 2.4 configs/nginx-ahw.conf.template
server {
    listen 80;
    server_name {{DOMAIN}};
    
    client_max_body_size 100M;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }
    
    location /static/ {
        alias /home/ubuntu/omni-medical-suite/static/;
    }
}

### 2.5 configs/ahw-correction.service
[Unit]
Description=AHW Correction Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/omni-medical-suite
Environment="PATH=/home/ubuntu/omni-medical-suite/venv/bin"
EnvironmentFile=/home/ubuntu/omni-medical-suite/.env
ExecStart=/home/ubuntu/omni-medical-suite/venv/bin/python server.py --host 0.0.0.0 --port 5000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

### 2.6 configs/.env.template
# Omni Medical Suite — Production Environment
# ⚠️ هذا الملف لا يُرفع إلى Git
# ⚠️ PHI غير مسموح على VPS عام

FLASK_SECRET_KEY=<generate-with-openssl-rand-hex-32>
AHW_SAMPLE_ID=S001
AHW_DB_PATH=/home/ubuntu/omni-medical-suite/output/S001/corrections.db
AHW_MAX_UPLOAD_MB=100
AHW_ADMIN_EMAIL=<your-email>
BACKUP_REPO=<your-private-repo-url>
BACKUP_RETENTION_DAYS=30

### 2.7 09-setup-backup.sh
- ينشئ /home/ubuntu/backups/
- سكربت daily tar.gz لقاعدة البيانات + corrections
- cron job يومي 2 AM
- ارفع إلى GitHub Private عبر gh CLI (إن توفر)
- احتفظ بـ30 يوماً

### 2.8 rollback.sh
- إيقاف الخدمات
- استعادة آخر backup
- إعادة تشغيل النموذج السابق
- تحذير: لا يحذف البيانات

### 2.9 10-verify-deployment.sh
فحوصات:
- curl http://localhost:5000/api/health
- systemctl status ahw-correction
- df -h
- free -m
- آخر backup

### 2.10 TROUBLESHOOTING.md
- مشاكل التسجيل في Oracle
- رفض SSH
- Nginx 502
- SQLite locked
- Out of memory
- Certificate renewal fails

## 3. القيود

- كل ملف يحمل header:
  # STATUS: TEMPLATE ONLY — NOT EXECUTED
  # PHASE: V-1 through V-5 (planned)
  # LAST UPDATED: <date>
  # TESTED: NO

- لا تدّعي أن أي سكربت "يعمل" أو "تم اختباره"
- لا تشغّل أي سكربت
- لا تختبر الاتصال

## 4. الأمان

- كل سكربت يستخدم متغيرات بدل قيم صلبة
- لا API keys في أي ملف
- .env.template فقط — لا .env حقيقي
- تحذيرات PHI في كل مكان مناسب

## 5. Stop Gates

T-STOP-1: أي محاولة تنفيذ → STOP
T-STOP-2: أي اتصال بـOracle → STOP
T-STOP-3: أي credential حقيقي → STOP

## 6. التقرير النهائي

=== ORACLE DEPLOY KIT ===
Branch:          feature/oracle-deploy-kit
HEAD SHA:        <full>

FILES CREATED:   <list>
TOTAL SCRIPTS:   <count>
TOTAL LINES:     <count>

EXECUTION:       NONE (templates only)
NETWORK CALLS:   NONE
CREDENTIALS:     NONE

PROVEN:
  - <verified facts>

NOT EXECUTED:
  - Everything (by design)

NEXT STEPS FOR USER:
  1. اقرأ deploy/oracle/README.md كاملاً
  2. سجّل في Oracle Cloud (انظر 01-...)
  3. عند نجاح التسجيل، ابدأ من 02-...
  4. اختبر على VPS فارغ أولاً
  5. لا تنقل PHI حتى تضبط الأمان

PERSISTENCE:     OK
