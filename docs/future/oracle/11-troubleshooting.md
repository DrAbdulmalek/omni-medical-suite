# 11 — Troubleshooting (PLANNED)

| العَرَض | التشخيص | العلاج |
|---|---|---|
| ssh مرفوض بعد hardening | أغلقت على نفسك (PasswordAuth off بلا مفتاح يعمل) | Oracle Console → VNC/serial connection → أعد `PasswordAuthentication yes` مؤقتًا |
| 80/443 لا تصل | Security List (OCI) ≠ ufw — طبقتان | افتح في كليهما |
| Ampere "Out of capacity" | Home region مزدحم | ساعات UTC مبكرة؛ أو micro AMD مؤقتًا؛ أو upgrade-to-payg ثم رجوع (بحذر) |
| pip يفشل على aarch64 | wheel غير متوفر لحزمة | `--dry-run` كشفًا؛ build deps (gcc/python3-dev)؛ أو بديل x86 |
| OOM عند التقطيع DPI عالٍ | RAM/swap | قلل DPI (150-200)؛ أضف swapfile 4GB |
| nginx 502 | الخدمة ميتة أو منفذ خاطئ | `systemctl status` + `journalctl -u` + تأكد 127.0.0.1:5000 يستجيب محليًا |
| certbot فشل | DNS غير منتشر/80 محجوب | انتظر DNS؛ تحقق الطبقتين؛ `--dry-run` |
| الخدمة تنهض ثم تموت | EnvironmentFile ناقص/مسار خاطئ | `journalctl` → صحح `.env`/WorkingDirectory |
| disk امتلأ | output/batches غير منظفة | retention policy على batch_* + logs rotation |
| GitHub push يفشل (cron) | gh auth expired | PAT fine-grained بصلاحية contents:write على datasets repo فقط + تدوير موثق |
| أي حادث أمني | — | [ROLLBACK_PLAN.md](ROLLBACK_PLAN.md) + عزل فوري (ufw deny) + تدوير كل الأسرار |
