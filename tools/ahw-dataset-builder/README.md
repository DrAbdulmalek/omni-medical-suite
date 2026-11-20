# ahw-dataset-builder — بناء مجموعة بيانات الخط اليدوي العربي

أدوات من محادثة DeepSeek `2873vzbqibqh1ihe31` (رسائل 52-58): تحويل كتب
PDF ممسوحة إلى **قصاصات كلمات** قابلة للتصحيح البشري، ثم إلى مجموعة
تدريب TrOCR (AraBERT tokenizer اختياريًا).

> **العلاقة بالأدوات الموجودة:** المستودع يملك مسبقًا
> `packages/gt_core/ocr_snippet_trainer.py` + `snippet_cli.py` +
> `snippet_review_ui.py` (قصاصات/مراجعة) و`apps/handwriting-demo/training/finetune_trocr.py`
> (تدريب). هذه الأدوات **مكملة** وليست بديلة: تركّز على *التقطيع الآلي
> من PDF* و*التعليق الجماعي عبر جدول HTML* و*التدريب بواجهة ويب* —
> قارن الميزات قبل الاختيار (انظر WARNINGS.md).

## الأدوات

| الملف | الوظيفة | المصدر |
|---|---|---|
| `segment.py` | المقطّع الرئيسي v2: PDF ← إزالة حواف/تسطير ← أعمدة ← سطور ← كلمات (Arabic-aware) ← crops + HTML + Excel | رسالة 55 |
| `standalone_pdf_to_snippets.py` | النسخة أحادية الملف الأصلية (بلا خادم) — جدول HTML للتصحيح | رسالة 53 |
| `postprocess.py` | تحسين القصاصات (enhance_crop + دمج المكونات المكسورة) | رسالة 55 |
| `server.py` | Flask + SQLite لمراجعة القصاصات جماعيًا | رسالة 55 |
| `templates/viewer.html` + `templates/embed.py` | عارض التصحيح (ويب / HTML مضمّن مستقل) | رسالة 55 |
| `pdf_batch.py` + `pdf_batch_merge.py` | تقطيع PDF كبير على دفعات + دمج النتائج | رسالة 57 |
| `train_trocr.py` | fine-tuning ‏TrOCR (إنجليزي ← عربي) | رسالة 55 |
| `patches/arabert_tokenizer_patch.py` | استبدال tokenizer بـ AraBERT لتحسين العربية | رسالة 57 |
| `train_webui.py` + `templates/train_dashboard.html` | واجهة تدريب تفاعلية (Flask + SocketIO) | رسالة 57 |
| `docker-compose.train.yml` + `Dockerfile.train` | تشغيل التدريب بنقرة (GPU) | رسالة 57 |

## التشغيل السريع

```bash
pip install -r requirements.txt

# تقطيع كتاب (عيّنات صفحات أولًا — لا تقطّع 400 صفحة دفعة واحدة)
python segment.py scan.pdf --sample S001 --pages 4 7 8 10 12 13 15

# PDF كبير على دفعات ثم دمج
python pdf_batch.py scan.pdf --batch-size 20
python pdf_batch_merge.py output/batches/

# التصحيح عبر الويب
python server.py            # ثم افتح http://localhost:5000

# التدريب (بعد اكتمال التصحيح)
python train_trocr.py --data output/S001/labels.csv
# أو بالواجهة:
python train_webui.py
```

## حالة التدقيق (أمانة — 2026-10-08)

- ✅ كل ملفات Python **تُصرف بنجاح** (py_compile) وسلامتها البنيوية مفحوصة
- ✅ استيرادات بينية متسقة (`pdf_batch` ← `segment`، `segment` ← `templates.embed`،
  `server` ← `templates/viewer.html`، `train_webui` ← `templates/train_dashboard.html`)
- ⚠️ **لم تُشغَّل end-to-end** في بيئة التدقيق (تحتاج PDF عربي حقيقي +
  تبعيات ثقيلة) — أول تشغيل يجب أن يكون على عينة صفحات صغيرة
- ⚠️ `train_trocr.py` الأصلي مبني على TrOCR إنجليزي — دقة العربية غير
  مضمونة قبل تطبيق `patches/arabert_tokenizer_patch.py` (موثق في WARNINGS.md)
- ⚠️ حدود التقطيع للخط اليدوي العربي المتصل معروفة (projection يفشل مع
  الاتصال الشديد) — التحرير البشري عبر viewer جزء أساسي من سير العمل،
  وليس اختياريًا

## الترخيص

الكود MIT (كود المالك المولّد بالمساعدة). النماذج المستهلكة:
TrOCR ‏(MIT) — AraBERT ‏(Apache-2.0) — راجع WARNINGS.md.
