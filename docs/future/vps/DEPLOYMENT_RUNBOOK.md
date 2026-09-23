# DEPLOYMENT RUNBOOK — قوالب التنفيذ (PLANNED)

> كل قالب أدناه:
> ```
> STATUS: TEMPLATE ONLY — DO NOT EXECUTE
> PHASE: V-X (planned)
> ```
> القوالب الكاملة القابلة للنسخ في `deploy/` و`automation/` (رؤوس TEMPLATE إلزامية).

## 1) Oracle Cloud Setup (V-0/V-1 — خطوات)
1. إنشاء حساب (بريد/هاتف/بطاقة تحقق) → Home Region قريب (Frankfurt/Amsterdam).
2. إنشاء VM: **VM.Standard.A1.Flex (ARM Ampere) 4 OCPU/24GB** أو micro AMD —
   Ubuntu 22.04، VCN افتراضية + subnet عام، مفتاح SSH **تولّده أنت** (لا تعتمد على المفتاح المؤقت).
3. بعد الإقلاع: `ssh ubuntu@IP` → نفّذ `deploy/oracle/01-initial-hardening.sh` (بعد مراجعته).
   STATUS: TEMPLATE ONLY — DO NOT EXECUTE · PHASE: V-1

## 2) Nginx Config (V-2)
القالب: `deploy/configs/nginx-ahw.conf.template` (proxy → 127.0.0.1:5000، client_max_body_size 100M للسكانر، headers أساسية؛ أضف `limit_req` قبل الإنتاج).
STATUS: TEMPLATE ONLY — DO NOT EXECUTE · PHASE: V-2

## 3) SSL Setup (V-1/V-2)
certbot + nginx plugin → شهادة للنطاق → اختبار تجديد تلقائي. (القالب: `deploy/oracle/05-setup-ssl.sh.template`)
STATUS: TEMPLATE ONLY — DO NOT EXECUTE · PHASE: V-2

## 4) Systemd Service (V-2)
القالبان: `ahw-correction.service.template` / `ahw-training.service.template`
(EnvironmentFile=.env · Restart=always · مستخدم ubuntu · **ملاحظة أمن**: القالب
يستخدم `--host 0.0.0.0` خلف nginx فقط إن كان ufw يحجب 5000/5001؛ وإلا فاستخدم
127.0.0.1 — الأفضل أمنيًا).
STATUS: TEMPLATE ONLY — DO NOT EXECUTE · PHASE: V-2

## 5) Backup Script (V-4)
`automation/vps/01..02` + `automation/shared/encrypt.sh.template`:
export → tar.gz → gpg --symmetric (أو keypair) → sha256 → gh push لمستودع datasets الخاص → retention 30 يوم.
STATUS: TEMPLATE ONLY — DO NOT EXECUTE · PHASE: V-4

## 6) Cron Jobs (V-4/V-6)
`automation/vps/crontab.template`: يومي 02:00 تصدير+تشفير+رفع؛ أسبوعي سحب نموذج+تحقق+ترقية؛ شهري اختبار استعادة.
STATUS: TEMPLATE ONLY — DO NOT EXECUTE · PHASE: V-4

## 7) Colab Integration (V-6)
انظر [../colab-pipeline/](../colab-pipeline/README.md) — notebook template + workflows.
STATUS: TEMPLATE ONLY — DO NOT EXECUTE · PHASE: V-6

## ترتيب التنفيذ عند الإذن (للمستقبل)
`01-hardening → 02-deps → 03-clone → 04-nginx → 05-ssl → 06-systemd → 07-backup → 08-verify`
— كل خطوة: مراجعة → تنفيذ → تحقق → توثيق نتيجة. الإخفاق → `rollback.sh.template` + [../oracle/ROLLBACK_PLAN.md](../oracle/ROLLBACK_PLAN.md).
