# 09 — Automated Encrypted Backup (V-4 · PLANNED)

القوالب: `deploy/oracle/07-setup-backup.sh.template` + `automation/vps/01..02` + `automation/shared/encrypt.sh.template` + `automation/vps/crontab.template` (TEMPLATE ONLY).

## السلسلة اليومية (02:00)
1. **Export**: corrections + metadata_all → `dataset-<date>.tar.gz` + manifest (عدد الصفوف + SHA256).
2. **Encrypt**: GPG symmetric (passphrase من keyring الخادم) أو keypair (المفتاح العام فقط على VPS).
3. **Push**: `gh` إلى مستودع **datasets الخاص** (`encrypted-<hash>.tar.gz.gpg`).
4. **Retention**: 30 يومًا (حذف الأقدم آليًا).
5. **شهري**: اختبار استعادة كامل (فك تشفير + تحقق عدّ الصفوف + عينة بصرية) — **بوابة V-4**.

## قواعد
- المفتاح الخاص/passphrase **لا يُخزن على VPS ولا في Git** (خارجهما فقط + نسخة مالك).
- النسخ مشفرة **دائمًا** — حتى في المستودعات الخاصة (دفاع عميق).
- نسخة إضافية خارجية (B2/R2) اختيارية (R1).

**Status: PLANNED · لم تُنشأ أي نسخة احتياطية.**
