# 08 — Systemd Services (V-2 · PLANNED)

القالبان: `deploy/oracle/06-setup-systemd.sh.template` + `deploy/configs/ahw-correction.service.template` + `ahw-training.service.template` (TEMPLATE ONLY).

## النقاط الجوهرية في القوالب
- `User=ubuntu` (غير root) · `Restart=always` + `RestartSec=10`.
- `EnvironmentFile=/home/ubuntu/omni-medical-suite/.env` (الأسرار خارجه — لا inline).
- `WorkingDirectory` = جذر المستودع (pytest/pythonpath يعتمدانه).
- **أمن الربط**: القالب الحالي يشغّل `--host 0.0.0.0` (تصميم قديم) — **عند التنفيذ استخدم `--host 127.0.0.1` خلف nginx** (أصرم؛ ufw يحجب 5000/5001 أصلًا) أو نمط ATR:
  `ATR_ALLOW_REMOTE=1 + ATR_API_TOKEN + ATR_SECRET_KEY` إن لزم تعريض مباشر (fail-closed).
- خدمة التدريب على VPS: **اختيارية ومعطلة افتراضيًا** (بلا GPU — التدريب Colab).

## التفعيل (وقت التنفيذ)
```bash
# TEMPLATE — DO NOT EXECUTE
sudo systemctl daemon-reload
sudo systemctl enable --now ahw-correction
systemctl status ahw-correction   # active (running)
journalctl -u ahw-correction -f   # logs بلا أسرار
```

**Status: PLANNED · لم تُنشأ أي خدمة.**
