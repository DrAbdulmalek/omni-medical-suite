# 06 — Nginx Reverse Proxy (V-2 · PLANNED)

القالب: `deploy/oracle/04-setup-nginx.sh.template` + `deploy/configs/nginx-ahw.conf.template` (TEMPLATE ONLY).

## التصميم
- nginx على 80/443 → proxy إلى **127.0.0.1:5000** (correction) و**127.0.0.1:5001** (training UI عبر location /train/ أو subdomain — يُحسم وقت التنفيذ).
- الخدمات نفسها loopback-only (نمط ATR الآمن) — لا 0.0.0.0 إلا داخل container mode الموثق.
- `client_max_body_size 100M` (PDFs السكانر).
- headers: X-Real-IP/X-Forwarded-For/X-Forwarded-Proto.
- **قبل الإنتاج**: أضف `limit_req_zone`/`limit_req` (rate limiting — بند SECURITY_CHECKLIST).
- Socket.IO (/socket.io/): يتطلب `proxy_http_version 1.1` + `Upgrade/Connection` headers — **أضفها للقالب وقت التنفيذ** (القالب الحالي يخدم HTTP؛ دعم ws موثق كخطوة V-2 اختيارية).

## تحقق مستقبلي
`nginx -t` → reload → `curl -I http://<IP>/` (200/301) → المنفذ 5000 من الخارج **مرفوض**.

**Status: PLANNED · لم يُضبط أي nginx.**
