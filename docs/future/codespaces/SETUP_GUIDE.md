# Codespaces SETUP GUIDE (PLANNED — خطوات مستقبلية)

> STATUS: TEMPLATE ONLY — DO NOT EXECUTE (لم يُفتح Codespace في جلسة التوثيق)
> PHASE: متاح فورًا عند الحاجة (لا يرتبط بمراحل V)

## الخطوات

1. **افتح المستودع على GitHub** → `DrAbdulmalek/omni-medical-suite`.
2. **Code → Codespaces → "Create codespace on …"** (اختر فرع العمل — للـAHW:
   فرع ATR بعد دمجه، وإلا `main`).
3. **انتظر ~3-5 دقائق**: إنشاء الحاوية ثم تشغيل `.devcontainer/post-create.sh`
   (venv + متطلبات أساسية). *(وصف كتابي بديل عن screenshots: سترى terminal
   يسجّل "🚀 Setting up Omni Medical Suite..." ثم "✅ Setup complete")*
4. **شغّل الخدمة** (Terminal):
   ```bash
   # مثال مستقبلي — لا يُنفذ الآن
   python correction_server.py --sample S001 --data-root output --port 5000
   ```
5. **Ports → Forwarded Ports**: افتح 5000 (و5001 لخادم التدريب) — GitHub يعطيك
   رابط `*.app.github.dev` خاصًا بجلسة المتصفح.
6. **ابدأ التصحيح من أي جهاز** — العمل يُحفظ بـcommit/push قبل الإغلاق.

## ملاحظات
- الحصة: راقب الاستهلاك في Settings → Billing (120 core-hours — UNVERIFIED).
- الإيقاف التلقائي بعد خمول (30 دقيقة افتراضيًا) — طبيعي.
- للتدريب الحقيقي: استخدم مسار [../colab-pipeline/](../colab-pipeline/README.md) لا Codespaces.
- إن لم يوجد `.devcontainer` على الفرع المختار: افتح ببيئة Python الافتراضية وثبّت
  `requirements-atr.txt` يدويًا (فرع ATR).
