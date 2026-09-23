# Codespaces TROUBLESHOOTING (PLANNED)

| المشكلة | السبب الشائع | الحل |
|---|---|---|
| بطء في الفتح | بناء devcontainer أول مرة (تنزيل apt/pip) | انتظر؛ المرات التالية snapshot أسرع. تحقق من Output→devcontainer logs |
| فشل تثبيت متطلبات | حزم ثقيلة (torch) أو إصدار Python | post-create يتجاهل torch (`grep -v "^torch"`)؛ ثبّت torch CPU يدويًا عند الحاجة: `pip install torch --index-url https://download.pytorch.org/whl/cpu` |
| Port forwarding لا يعمل | المنفذ لم يُلتقط | Ports → Add 5000 يدويًا؛ تأكد أن الخادم يربط 0.0.0.0 داخل الحاوية (Codespaces يحوّل) — استخدم `--host 0.0.0.0` **داخل Codespace فقط** (بيئة معزولة) مع بقاء قاعدة عدم رفع PHI |
| انتهت الـ60 ساعة | الحصة الشهرية (120 core-hours) | انتظر التجديد الشهري، أو خفّض المواصفات (2-core)، أو انتقل لمحلي/Colab |
| Python import errors | venv غير مفعّل / مسارات | `source /workspace/.venv/bin/activate`؛ شغّل من جذر المستودع (pytest pythonpath يعتمد الجذر) |
| OOM عند تحميل أوزان | 8GB مع torch+TrOCR full | استخدم dry_run/smoke؛ التدريب الفعلي → Colab |
| الملفات اختفت بعد إعادة إنشاء | storage مؤقت | commit+push دائمًا؛ لا تعتمد على /workspace ك存储 دائم |
| devcontainer.json غير مقروء | خطأ JSON | تحقق بصلاحية JSON (ملف هذا الفرع صالح بنيويًا — مراجعة بصرية فقط) |

**قاعدة:** أي مشكلة أمنية/بيانات → أغلق الـCodespace واحذفه (Delete) — البيئة disposable.
