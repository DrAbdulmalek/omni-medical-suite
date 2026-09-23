# ARCHITECTURE — خط التدريب الهجين (PLANNED)

```
VPS (SQLite/xlsx corrections)
    │
    │ 1. Export daily/weekly (cron)
    │ 2. Encrypt (GPG) + push to GitHub Private
    ▼
GitHub Private Repo (datasets/encrypted-<hash>.tar.gz.gpg + manifest)
    │
    │ 3. Trigger via GitHub Actions (workflow_dispatch/schedule)
    │ 4. Colab pulls via gh CLI
    ▼
Colab (Train TrOCR+AraBERT, 4-6h تقديريًا — UNVERIFIED)
    │
    │ 5. Push trained model → GitHub Releases (trocr-arabic-v<n>.safetensors)
    ▼
GitHub Releases (+ metrics.json + SHA256SUMS)
    │
    │ 6. VPS pulls via cron (weekly)
    │ 7. Validate (CER/WER على 50 عينة — اصطناعية أو مصححة معتمدة)
    │ 8. Promote أو Reject (موثق)
    ▼
VPS (models/trocr-arabic-v<n>/) ← rollback متاح دائمًا
```

## أدوار ومسؤوليات
| العقدة | تفعل | لا تفعل |
|---|---|---|
| VPS | تصحيح/تقطيع، تصدير+تشفير، سحب+تحقق+ترقية، خدمة | تدريب، فك تشفير datasets للعالم |
| GitHub | وسيط تخزين/إطلاق/تشغيل | تخزين明文 (كله مشفر)، أسرار في ملفات |
| Colab | فك تشفير بالذاكرة، تدريب، تقييم، رفع Release | تخزين دائم، مفاتيح خاصة على القرص |

## حالات الفشل
- Colab انقطع → checkpoint أخير مرفوع → استئناف (notebook idempotent).
- نموذج فاسد → SHA256 mismatch → رفض سحب.
- CER أسوأ → reject + إبقاء السابق (لا promote).
- dataset فاسد → manifest count mismatch → إيقاف الدورة وإشعار.

## حدود التصميم
- GitHub limits (repo size/API rate) — datasets مضغوطة ونمو تدريجي.
- Colab T4 ≈ يكفي base model دفعات صغيرة (large model → Pro+/RunPod — ALTERNATIVES).
- التأخير مقبول (تدريب أسبوعي لا لحظي).
