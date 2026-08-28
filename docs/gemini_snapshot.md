# Gemini Project Snapshot

## الغرض
أداة لتوليد ملف نصي واحد يحتوي على كود المشروع الآمن، لرفعه إلى Gemini (أو أي LLM آخر) لمراجعة الكود.

## الاستخدام

### سطر الأوامر
```bash
# الوضع الافتراضي (Git tracked فقط) — الأكثر أماناً
python tools/export_project_snapshot.py

# تصدير كامل
python tools/export_project_snapshot.py --scope full

# مراجعة PR الحالي (الملفات المتغيرة فقط)
python tools/export_project_snapshot.py --scope diff --purpose "PR #100 audit" --with-prompt

# ملفات محددة
python tools/export_project_snapshot.py --scope selected --include app/core config.py
```

## الحماية
- يتم استبعاد `.env` و `*.pem` و `credentials.json` تلقائيًا.
- يتم استبعاد الملفات الثنائية.
- يتم كشف وتحرير (Redact) الأسرار: API keys, tokens, passwords, DB URLs, private keys.
- إذا كان هناك شك، تُستبدل القيمة بـ `[REDACTED: POSSIBLE SECRET]`.

## تحذير
هذا الملف ليس نسخة احتياطية كاملة من المستودع. هو نسخة مبسّطة للمراجعة فقط.
