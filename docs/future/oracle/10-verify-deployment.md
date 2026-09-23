# 10 — Deployment Verification (V-2/V-4 gate · PLANNED)

القالب: `deploy/oracle/08-verify-deployment.sh.template` (TEMPLATE ONLY).

## قائمة التحقق النهائية (عند التنفيذ مستقبلًا)
| # | الفحص | الأمر/المعيار | النتيجة المتوقعة |
|---|---|---|---|
| 1 | SSH keys-only | محاولة password → fail | refused |
| 2 | ufw | `ufw status` | 22/80/443 فقط |
| 3 | HTTPS | `curl -I https://<DOMAIN>` | 200 + HSTS (لاحقًا) |
| 4 | التحويل | `curl -I http://…` | 301→https |
| 5 | الخدمات | `systemctl is-active ahw-*` | active |
| 6 | API خلف nginx | `curl https://<DOMAIN>/api/status` (بالتوكن إن فُعل) | 200/401 صحيحان |
| 7 | 5000/5001 خارجيًا | `nc -z <IP> 5000` | **مرفوض** |
| 8 | fail2ban | `fail2ban-client status sshd` | active |
| 9 | Backup | آخر run + اختبار استعادة | نجاح موثق |
| 10 | Monitoring | UptimeRobot على /api/status | إشعار اختباري وصل |
| 11 | logs | `journalctl -u ahw-* -n 200` | بلا أسرار/PHI |
| 12 | smoke اصطناعي | `scripts/atr_smoke.py` على الخادم (بيانات اصطناعية فقط) | PASS |

**كل نتيجة تُوثَّق (PASS/FAIL + تاريخ) — FAIL واحد = لا إعلان "منشور".**
**Status: PLANNED · لم يُتحقق من أي نشر (لا نشر أصلًا).**
