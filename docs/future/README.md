# docs/future — خطط البنية التحتية المستقبلية (قوالب — لم تُنفذ)

> **الحالة: TEMPLATES ONLY — NOT EXECUTED** (كما نصت المحادثة الأصلية
> `2873vzbqibqh1ihe31` رسائل 60-73). هذه خطط وقوالب جاهزة لليوم الذي
> يتوفر فيه VPS/Oracle Free Tier — لا شيء هنا يعمل الآن ولا يجب تشغيله
> دون مراجعة.

| الوثيقة | المحتوى |
|---|---|
| `VPS_INFRASTRUCTURE_PLAN.md` | الخطة الكاملة: VPS مجاني (Oracle/غيره)، معمارية النشر، قوالب nginx/systemd/devcontainer، سكريبتات تقوية أولية، مصفوفة الأسرار، شجرة docs/future المقترحة |
| `CODESPACES_MASTER_PROMPT.md` | Master Prompt لإعداد GitHub Codespaces لتشغيل المشروع فورًا |
| `ORACLE_DEPLOYMENT_KIT.md` | Master Prompt + سكربت نشر كامل لـ Oracle Cloud Free Tier |
| `VPS_COLAB_TRAINING_PIPELINE.md` | Master Prompt لخط تدريب تلقائي VPS ↔ Colab (GPU مجاني) |

## قرارات ذات صلة

- التدريب الثقيل (TrOCR/AraBERT): Colab GPU مجاني أولًا — انظر
  `tools/ahw-dataset-builder/docker-compose.train.yml` للتشغيل المحلي عند
  توفر GPU.
- النشر المجاني المستدام: Oracle Free Tier ‏(ARM 4×CPU/24GB) — السيناريو
  الموثق في VPS_INFRASTRUCTURE_PLAN.md.
- المستودع يبقى قابلًا للعمل **بلا أي VPS** — كل شيء محلي/Docker أولًا.
