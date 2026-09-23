# SECURITY CHECKLIST — إلزامي قبل أي نشر (V-1 gate)

**الحالة: PLANNED.** لا يُعتبر أي خادم "منشورًا" قبل تحقق كل بند وتوثيقه.

- ☐ **SSH keys فقط** — `PasswordAuthentication no` في sshd_config (مؤكد باختبار دخول فاشل بكلمة سر).
- ☐ **جدار ناري (ufw)** — deny incoming افتراضيًا؛ allow 22/80/443 فقط؛ **لا** 5000/5001 للعالم (تبقى loopback خلف nginx).
- ☐ **HTTPS إلزامي** — Let's Encrypt + تحويل 80→443؛ HSTS مفعّل.
- ☐ **Fail2Ban** — sshd + nginx jails فعالة ومختبرة بمنع تجريبي.
- ☐ **تحديثات أمنية تلقائية** — unattended-upgrades مفعّل.
- ☐ **Backup مشفّر** — GPG (symmetric أو keypair) + passphrase غير مخزن مع النسخة.
- ☐ **لا PHI على VPS عام** — راجع [PRIVACY_COMPLIANCE.md](PRIVACY_COMPLIANCE.md)؛ الخدمات المكشوفة = واجهات بلا بيانات حقيقية إلا خلف HTTPS+مصادقة.
- ☐ **API keys/tokens في `.env` فقط** (غير مُلتزم؛ `.gitignore` يغطيه) — لا في كود/وثائق/تاريخ Git.
- ☐ **Rate limiting** — nginx `limit_req` على /api و/ (يمنع brute-force/DoS خفيف).
- ☐ **Logs بلا معلومات حساسة** — لا tokens/نصوص طبية في access/error logs (nginx لا يسجل bodies؛ راجع سجلات التطبيق).
- ☐ **مصادقة الخدمات** — نمط ATR: `ATR_ALLOW_REMOTE=1`+`ATR_API_TOKEN`+`ATR_SECRET_KEY` لأي تعريض غير loopback (fail-closed) — موثق في PR #136 remediation.
- ☐ **مستخدم غير root للخدمات** (ubuntu) + صلاحيات دنيا على المجلدات.
- ☐ **تحقق دوري**: `sudo apt audit` شهريًا + مراجعة fail2ban + اختبار استعادة backup.

**Sources (UNVERIFIED — تحقق عند V-1):** man.openbsd.org sshd_config · wiki.debian.org/UnattendedUpgrades · nginx.org limit_req · letsencrypt.org
