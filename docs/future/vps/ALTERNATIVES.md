# ALTERNATIVES — خطط بديلة (PLANNED)

## إذا فشل Oracle (R3 — احتمال عالٍ)

**الخطة البديلة الأساسية: Codespaces + Colab + GitHub Actions**
- تطوير/تصحيح: Codespaces (بلا بطاقة، دقائق) — انظر [../codespaces/](../codespaces/README.md).
- تدريب: Colab (كما هو) — الخط نفسه في [../colab-pipeline/](../colab-pipeline/README.md) يعمل بلا VPS
  (التصحيح محلي/Codespaces، التصدير يدوي إلى datasets repo).
- خدمات "دائمة": GitHub Actions (scheduled workflows) للمهام الدورية بدل خادم —
  محدودة (دقائق/تشغيل) لكنها تغطي export/validate.
- بدائل VPS أخرى للتجربة: GCP e2-micro / AWS 12 شهرًا / Fly / Railway
  (قيود ذاكرة — راجع FREE_VPS_OPTIONS).

## إذا احتجت GPU

| الخيار | التكلفة التقريبية | الملاءمة |
|---|---|---|
| Colab Pro/Pro+ | ~$10-50/شهر | الأبسط؛ جلسات محدودة |
| RunPod / Vast.ai | ~$0.2-0.7/GPU-hour (UNVERIFIED) | تدريب مجدول بالدفع-بالاستخدام |
| Kaggle Notebooks | مجاني (حصص أسبوعية ~30h GPU — UNVERIFIED) | بديل Colab |
| HF AutoTrain/Spaces GPU | مدفوع | نشر+تدريب متكامل مع HF |

## إذا احتجت تخزينًا كبيرًا

- **Backblaze B2**: ~$6/TB/شهر، أول 10GB مجاني (UNVERIFIED) — rclone مشفر.
- **Cloudflare R2**: صفر egress fees، 10GB مجاني (UNVERIFIED).
- **GitHub Releases**: ملفات حتى 2GB (UNVERIFIED) — للنماذج مع SHA256.
- قاعدة: **كل تخزين سحابي = مشفر GPG قبل الرفع** (PRIVACY_COMPLIANCE).
