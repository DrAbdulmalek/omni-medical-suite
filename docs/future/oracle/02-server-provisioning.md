# 02 — Server Provisioning (V-0/V-1 · PLANNED)

## إنشاء VM (Always Free)
1. Console → Compute → Instances → **Create instance**.
2. Image: **Ubuntu 22.04 (aarch64)** لـAmpere، أو x86_64 لـmicro AMD.
3. Shape:
   - **VM.Standard.A1.Flex** — 4 OCPU / 24GB RAM (Always Free ceiling — UNVERIFIED) ← المرشح
   - VM.Standard.E2.1.Micro — 1GB RAM (بديل محدود)
4. VCN: افتراضية جديدة + **subnet عام** + IPv4 عام.
5. SSH: **الصق مفتاحك العام** (من 00) — لا تعتمد على المفتاح المولَّد مؤقتًا.
6. Create → انتظر RUNNING → سجّل الـPublic IP (ثابت في Free — UNVERIFIED).

## ملاحظات ARM (مهمة لمشروعنا — R11)
- معظم الحزم لها wheels aarch64 (torch/opencv/pymupdf/numpy ✓ عادة) — لكن **تحقق قبل V-2** بـ:
  ```bash
  # TEMPLATE — DO NOT EXECUTE
  pip install --dry-run -r requirements-atr.txt
  ```
- Python 3.10+ متوفر عبر deadsnakes أو build (الخطوة 04).

## Security List / Ingress (قبل أي خدمة)
- الافتراضي يفتح 22 فقط (جيد). عند V-2: افتح 80/443 في **Security List + ufw معًا** (طبقتان).
- لا تفتح 5000/5001 للعالم أبدًا.

## بعد الإقلاع
```bash
# TEMPLATE — DO NOT EXECUTE
ssh -i ~/.ssh/id_ed25519 ubuntu@<PUBLIC_IP>
```
→ انتقل إلى [03-initial-hardening.md](03-initial-hardening.md) **فورًا** (قبل أي تثبيت).

**Status: PLANNED · لم تُنشأ أي VM.**
