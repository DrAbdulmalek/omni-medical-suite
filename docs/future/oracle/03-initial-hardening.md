# 03 — Initial Hardening (V-1 · PLANNED)

القالب التنفيذي: `deploy/oracle/01-initial-hardening.sh.template` (**TEMPLATE ONLY — NOT EXECUTED — TESTED: NO**).

## الخطوات (idempotent)
1. **تحديث النظام**: `apt update && apt upgrade -y`.
2. **SSH hardening**: `PasswordAuthentication no` + `PermitRootLogin no` (بعد التأكد أن مفتاحك يعمل من جلسة ثانية — **لا تغلق الجلسة الأولى**).
3. **جدار ناري ufw**: default deny incoming → allow 22,80,443 → enable. (تطابق مع Security List — 02).
4. **fail2ban**: تثبيت + تفعيل jails (sshd + nginx لاحقًا).
5. **unattended-upgrades**: تحديثات أمنية تلقائية.
6. (اختياري موصى به) تغيير منفذ SSH أو tallowlist IPs؛ تفعيل MFA عبر OCI console.

## تحقق (عند التنفيذ مستقبلًا)
- دخول بكلمة سر **يفشل**؛ دخول بالمفتاح ينجح.
- `sudo ufw status verbose` → 22/80/443 فقط.
- `fail2ban-client status sshd` → active.
- منفذ 5000 من الخارج: **مرفوض**.

**بوابة الخروج V-1 (جزئي):** البندان 1-5 موثقة النتائج → [04](04-install-dependencies.md).
**Status: PLANNED · لم يُؤمَّن أي خادم.**
