# استوديو الأنماط — قناة تيليجرام وقصاصات التدريب

مقابل مفتوح لتدريب أنماط المستخدم، بدون نسخ أي منتج تجاري.
ABBYY FineReader وReadiris علامتان مسجلتان؛ هذا المسار لا يتضمّن شيفرتهما ولا نصوص مساعدتهما.

## ماذا يفعل

1. **صندوق قناة.** `POST /api/pattern-studio/telegram/file` يجلب ملفاً وصل إلى البوت عبر `file_id`. الرمز `TELEGRAM_BOT_TOKEN` يبقى على الخادم ولا يُرسل من المتصفح. بلا الرمز يرجع `409` والحالة `needs_token`.
2. **قصاصة.** كل سجل إمّا `glyph` (حرف) أو `word` (كلمة) مع النص الصحيح واللغة.
3. **بوابة التأكيد على الخادم.** إنشاء القصاصة عبر `POST /api/pattern-studio/snippets` يحفظها `open` دائماً. حقل `review` المرسل من العميل يُتجاهل ولا يستطيع التأكيد. التأكيد والرفض مساران منفصلان `POST /snippets/{id}/confirm` و`POST /snippets/{id}/reject`، محميان بصلاحية RBAC `training.manage`. التصدير يقرأ من قاعدة الخادم فقط، ويضم السجلات المؤكدة في قاعدة البيانات؛ لا يستخدم سجلات يرسلها العميل مصدراً للتدريب.
4. **تصحيح معروف.** `POST /api/pattern-studio/confusions/suggest` يعيد اقتراحاً من `packages/learning/confusions_ar.py` مع `review: open` و`auto_apply: false`. الاقتراح يُعرض للمراجع ولا يُعتمد وحده.
5. **أرشيف GitHub.** الصيغة `oms.pattern.v1` سطر JSON لكل قصاصة في `training-data/patterns/`.

## الصيغة

```json
{
  "schema": "oms.pattern.v1",
  "kind": "word",
  "role": "drug",
  "text": "هيموغلوبين",
  "language": "ar",
  "review": "confirmed",
  "image_sha256": "…",
  "image_png_base64": "…",
  "ocr_guess": "هيموعلوبين",
  "source": {"channel": "@channel", "file": "page.png", "bbox": [0, 0, 10, 10]}
}
```

`role` اختياري: `title` أو `drug` أو `dose` أو `note` أو `other`.

`POST /api/pattern-studio/dataset/export` يتطلب مصادقة وصلاحية `training.manage`، ويصدر فقط السجلات المؤكدة الموجودة في قاعدة الخادم. أي `records` أو `review` يرسله العميل لا يُستخدم مصدرًا للتصدير. لا يكتب الملف إلى GitHub تلقائياً. يجب أن تستدعي الواجهة مسار التأكيد الصريح بعد مراجعة بشرية؛ لا يجوز لها ضبط حالة المراجعة داخل سجل الحفظ.

## ما لا يُنسخ

مجلد المراقبة، مقارنة PDF، أرقام Bates، وحذف البيانات الحساسة تبقى خارج هذا المسار.

## اختبار

```bash
python -m pytest tests/test_snippet_dataset.py -q
```
