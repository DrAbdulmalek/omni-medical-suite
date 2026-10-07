# استوديو الأنماط — قناة تيليجرام وقصاصات التدريب

مقابل مفتوح لتدريب أنماط المستخدم، بدون نسخ أي منتج تجاري.
ABBYY FineReader وReadiris علامتان مسجلتان؛ هذا المسار لا يتضمّن شيفرتهما ولا نصوص مساعدتهما.

## ماذا يفعل

1. **صندوق قناة.** `POST /api/pattern-studio/telegram/file` يجلب ملفاً وصل إلى البوت عبر `file_id`. الرمز `TELEGRAM_BOT_TOKEN` يبقى على الخادم ولا يُرسل من المتصفح. بلا الرمز يرجع `409` والحالة `needs_token`.
2. **قصاصة.** كل سجل إمّا `glyph` (حرف) أو `word` (كلمة) مع النص الصحيح واللغة.
3. **أرشيف GitHub.** الصيغة `oms.pattern.v1` سطر JSON لكل قصاصة في `training-data/patterns/`.

## الصيغة

```json
{
  "schema": "oms.pattern.v1",
  "kind": "word",
  "text": "هيموغلوبين",
  "language": "ar",
  "image_sha256": "…",
  "image_png_base64": "…",
  "ocr_guess": "هيموعلوبين",
  "source": {"channel": "@channel", "file": "page.png", "bbox": [0, 0, 10, 10]}
}
```

`POST /api/pattern-studio/dataset/export` يطبّع قائمة سجلات ويرجع `jsonl`.

## ما لا يُنسخ

مجلد المراقبة، مقارنة PDF، أرقام Bates، وحذف البيانات الحساسة تبقى خارج هذا المسار.

## اختبار

```bash
python -m pytest tests/test_snippet_dataset.py -q
```
