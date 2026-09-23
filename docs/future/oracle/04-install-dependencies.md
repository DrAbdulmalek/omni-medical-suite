# 04 — Install Dependencies (V-1 · PLANNED)

القالب: `deploy/oracle/02-install-dependencies.sh.template` (TEMPLATE ONLY).

## الحزم
```bash
# TEMPLATE — DO NOT EXECUTE
sudo apt install -y python3.10 python3.10-venv python3-pip git nginx \
    libgl1 libglib2.0-0 poppler-utils tesseract-ocr tesseract-ocr-ara
# Docker اختياري (V-5):
# curl -fsSL https://get.docker.com | sh   ← راجع السكربت قبل أي تنفيذ
```

## ملاحظات ARM
- `python3.10` متوفر في Ubuntu 22.04 رسميًّا ✓.
- torch CPU: `pip install torch --index-url https://download.pytorch.org/whl/cpu` (wheels aarch64 متوفرة — UNVERIFIED لحظيًا).
- الذاكرة: 24GB تكفي venv + خدمات؛ 1GB (micro) لا تكفي torch — للخدمات الخفيفة فقط.

## تحقق مستقبلي
`python3.10 --version · nginx -v · git --version · tesseract --version`
→ [05-clone-and-configure.md](05-clone-and-configure.md)

**Status: PLANNED · لم تُثبَّت أي حزمة (قاعدة DOCUMENTATION_ONLY).**
