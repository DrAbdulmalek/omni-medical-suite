# 07 — SSL via Let's Encrypt (V-2 · PLANNED)

القالب: `deploy/oracle/05-setup-ssl.sh.template` (TEMPLATE ONLY).

## المتطلبات
نطاق (موصى به) يشير A-record إلى الـIP؛ المنفذ 80 مفتوح (Security List + ufw).

## الخطوات
```bash
# TEMPLATE — DO NOT EXECUTE
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d <DOMAIN> --redirect --agree-tos -m <EMAIL>
sudo certbot renew --dry-run   # اختبار التجديد التلقائي
```

## ملاحظات
- التجديد التلقائي: systemd timer لـcertbot (يأتي مع الحزمة) — تحقق `systemctl list-timers`.
- بلا نطاق: خيارات محدودة (شهادة self-signed = تحذيرات متصفح؛ أو tunnel مؤقت مثل cloudflared — قيّمه وقت التنفيذ).
- HSTS: فعّله بعد استقرار HTTPS بأسبوع (لا قبل — خطر قفل).
- **بوابة V-2:** HTTPS يعمل + تحويل 80→443 + dry-run تجديد ناجح.

**Status: PLANNED · لم تُستخرج أي شهادة.**
