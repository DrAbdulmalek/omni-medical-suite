# Oracle Cloud Deployment Kit (PLANNED — NOT IMPLEMENTED)

> ## ⚠️ تحذير بارز
> **لا تُنفّذ أي خطوة على بيانات حقيقية حتى تكتمل بوابات الأمان
> ([../vps/SECURITY_CHECKLIST.md](../vps/SECURITY_CHECKLIST.md)) ومراجعة
> [../vps/PRIVACY_COMPLIANCE.md](../vps/PRIVACY_COMPLIANCE.md).**
> كل القوالب المرتبطة: `TEMPLATE ONLY — NOT EXECUTED — TESTED: NO`.

## الملخص
حزمة نشر كاملة لخادم Oracle Always Free (Ampere ARM 4c/24GB تقريبي — UNVERIFIED):
12 خطوة مرقمة (00→11) + خطة تراجع. الزمن الكلي المقترح: أسبوع (V-0..V-2).

## المتطلبات المسبقة (باختصار — التفصيل في 00)
حساب Oracle (بطاقة تحقق)، نطاق أو IP ثابت، معرفة ssh أساسية، مفاتيح GPG للـbackup (V-4).

## الفهرس
| الخطوة | الملف | المرحلة |
|---|---|---|
| المتطلبات | [00-prerequisites.md](00-prerequisites.md) | V-0 |
| تسجيل Oracle (incl. مشاكل التسجيل من سوريا) | [01-oracle-account-setup.md](01-oracle-account-setup.md) | V-0 |
| إنشاء VM (Ampere/Ubuntu 22.04) | [02-server-provisioning.md](02-server-provisioning.md) | V-0/V-1 |
| تأمين أولي (SSH/ufw/fail2ban) | [03-initial-hardening.md](03-initial-hardening.md) | V-1 |
| تثبيت التبعيات (Python/Nginx/Git/Docker) | [04-install-dependencies.md](04-install-dependencies.md) | V-1 |
| استنساخ وإعداد المشروع | [05-clone-and-configure.md](05-clone-and-configure.md) | V-2 |
| Nginx reverse proxy | [06-setup-nginx.md](06-setup-nginx.md) | V-2 |
| SSL (Let's Encrypt) | [07-setup-ssl.md](07-setup-ssl.md) | V-2 |
| systemd services | [08-setup-systemd.md](08-setup-systemd.md) | V-2 |
| Backup تلقائي مشفر | [09-setup-backup.md](09-setup-backup.md) | V-4 |
| التحقق من النشر | [10-verify-deployment.md](10-verify-deployment.md) | V-2/V-4 |
| حل المشاكل | [11-troubleshooting.md](11-troubleshooting.md) | — |
| خطة التراجع | [ROLLBACK_PLAN.md](ROLLBACK_PLAN.md) | — |

القوالب التنفيذية: `deploy/oracle/*.sh.template` + `deploy/configs/*.template` (لا تُنفَّذ في هذه المرحلة).
