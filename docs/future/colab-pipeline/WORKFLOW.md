# WORKFLOW — سير العمل (PLANNED)

## يومي (تلقائي — VPS)
1. المالك يصحح قصاصات عبر الواجهة (HTTPS).
2. 02:00 — export + encrypt + push (cron) → dataset اليومي في GitHub.
3. 02:30 — تحقق manifest (count/sha) + log.
*(الجهد البشري: دقائق تصحيح؛ الباقي آلي.)*

## أسبوعي (تدريب — V-6)
1. السبت 04:00 — VPS يفحص: هل نماDataset ≥ عتبة (مثلًا +500 قصاصة مصححة)؟
2. نعم → Mالك/مشغّل يفتح Colab notebook (رابط/إشعار) → تدريب (~4-6h تقدير UNVERIFIED).
3. Release `v<n>` + metrics → VPS يسحب → SHA256 → validate (50 عينة).
4. PROMOTE (symlink current يتبدل atomically) أو REJECT (يبقى السابق + توثيق).

## شهري
- اختبار استعادة backup كامل (V-4 gate مستمر).
- مراجعة logs/metrics + قرار عتبات CER.
- تدقيق secrets/مفاتيح (تواريخ تدوير).

## طارئ (rollback)
1. اكتشاف تراجع/حادث → `04-promote-or-rollback.sh.template --rollback` (يعيد previous).
2. حادث أمني → [../oracle/ROLLBACK_PLAN.md](../oracle/ROLLBACK_PLAN.md) + تدوير أسرار + عزل.
3. انقطاع Colab أثناء تدريب → استئناف من آخر checkpoint مرفوع (notebook idempotent).

## مصفوفة RACI مبسطة
| مهمة | المالك | VPS (cron) | Colab |
|---|---|---|---|
| تصحيح | ✅ | يستضيف | — |
| تصدير/تشفير/رفع | — | ✅ | — |
| تدريب/تقييم | إطلاق | — | ✅ |
| ترقية/تراجع | قرار العتبة | تنفيذ+توثيق | — |
