# 05 — Clone & Configure (V-2 · PLANNED)

القالب: `deploy/oracle/03-clone-and-configure.sh.template` (TEMPLATE ONLY).

## الخطوات
1. **Clone** (مستودع خاص → deploy key read-only أو fine-grained PAT ضيق النطاق — يُولَّد **وقتها** بيد المالك، لا في هذه المرحلة):
   ```bash
   # TEMPLATE — DO NOT EXECUTE
   git clone https://github.com/DrAbdulmalek/omni-medical-suite ~/omni-medical-suite
   cd ~/omni-medical-suite && git checkout <release-branch-or-main>
   ```
2. **venv + متطلبات** (فرع ATR بعد دمجه):
   ```bash
   python3.10 -m venv venv && ./venv/bin/pip install -r requirements-atr.txt
   ```
3. **.env من القالب** `deploy/configs/.env.template` → `cp` ثم **توليد قيم حقيقية وقت التنفيذ فقط**:
   - `FLASK_SECRET_KEY` / `ATR_SECRET_KEY`: `openssl rand -hex 32` (على الخادم، لا يُسجل في محضر).
   - `ATR_API_TOKEN`: عشوائي مماثل.
   - `.env` يبقى 0600 وغير مُلتزم (مغطى بـ.gitignore).
4. **مجلدات**: `mkdir -p output models` (مغطاة بـ.gitignore).
5. **اختبار دخاني محلي (loopback فقط)** قبل nginx:
   `./venv/bin/python correction_server.py --port 5000` ثم `curl 127.0.0.1:5000/api/...`

## مخاطر
- فرع غير مدموج (ATR على PR #136) → النشر من `main` قبل الدمج يعني غياب خدمات AHW؛ التسلسل الصحيح: دمج PR (بعد بواباته) ثم V-2.
- wheels aarch64 (R11) → `pip install --dry-run` أولًا.

**Status: PLANNED · لم يُستنسخ/يُهيأ أي خادم.**
