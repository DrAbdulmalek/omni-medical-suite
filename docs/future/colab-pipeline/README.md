# VPS ↔ Colab Training Pipeline (PLANNED — NOT IMPLEMENTED)

**الحالة: PLANNED.** لم يُنشأ مستودع datasets، لم يُولَّد مفتاح GPG، لم يُشغَّل notebook.

## لماذا pipeline؟
التدريب الحقيقي (TrOCR+AraBERT بأوزان كاملة) يحتاج GPU وذاكرة تفوق VPS المجاني
(تجربة ATR أثبتت OOM حتى بـ1GB sandbox؛ وVPS ARM بلا GPU). الحل: **VPS للبيانات
والخدمة، Colab للتدريب، GitHub وسيطًا مشفرًا** — بلا تكلفة وبلا خادم GPU.

## التحديات التي يصمم الخط لها
1. **بيانات كبيرة** → ضغط + تشفير + دفعات (datasets صغيرة النمو).
2. **GPU محدود/متقطع** (Colab) → checkpoints + استئناف + تدريب مجدول.
3. **تكلفة $0** → GitHub Private وسيطًا (بدل S3).
4. **أمن/خصوصية** → GPG إلزامي، SHA256، secrets معزولة — [SECURITY.md](SECURITY.md).
5. **الثقة** → validate_model + promote/rollback آلي بقرار موثق — لا ترقية عمياء.

## الملفات
[ARCHITECTURE.md](ARCHITECTURE.md) · [SECURITY.md](SECURITY.md) · [VPS_SETUP.md](VPS_SETUP.md) ·
[COLAB_SETUP.md](COLAB_SETUP.md) · [GITHUB_SETUP.md](GITHUB_SETUP.md) · [WORKFLOW.md](WORKFLOW.md)

القوالب: `automation/**` (vps/colab/github/shared) — كلها TEMPLATE ONLY.

## الحد الأدنى للتفعيل (V-6 gates)
☐ VPS منشور ومستقر (V-2..V-4) ☐ مستودعا datasets/models الخاصان ☐ GPG keypair
☐ notebook جُرِّب على **بيانات اصطناعية** أولًا ☐ عتبة CER للترقية محددة من المالك.
