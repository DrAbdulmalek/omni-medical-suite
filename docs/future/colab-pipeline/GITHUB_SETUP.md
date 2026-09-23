# GITHUB SETUP (V-6 · PLANNED)

## المستودعان الخاصان
1. **`omni-ahw-datasets` (private)**:
   - `datasets/encrypted-<sha8>.tar.gz.gpg` + `manifests/<date>.json` (counts+sha256).
   - فرع واحد (main)؛ pushes من VPS فقط (PAT ضيق).
   - Retention: workflow/سكريبت يحذف ما >30 يومًا.
2. **`omni-ahw-models` (private أو public حسب قرار المالك)**:
   - **Releases** فقط (لا commits ضخمة): `trocr-arabic-v<n>.safetensors` + `metrics.json` + `SHA256SUMS`.
   - tags `v<n>`؛ لا يُحذف release قائم (immutable history) — الترقيات releases جديدة.

## Actions workflows (قوالب — لا تُفعَّل الآن)
- `trigger-training.yml.template`: `workflow_dispatch` (+ schedule اختياري) →
  يُجهز context (أحدث dataset) ويعطي تعليمات/رابط تشغيل Colab (Colab لا يُشغَّل
  من Actions مباشرة بلا self-hosted runner — التصميم: Actions = محفّز/موثّق،
  التنفيذ في Colab يدويًا أو عبر runner خاص لاحقًا — قرار V-6).
- `validate-model.yml.template`: عند release جديد → يحسب/يتحقق SHA256 + يخزن
  سجل تحقق (بدون تنزيل الأوزان في runner — حجم/تكلفة).

## Secrets المطلوبة (تُنشأ وقت V-6 فقط)
| Secret | النطاق | الصلاحية |
|---|---|---|
| `DATASETS_PAT` | VPS env (ليس GitHub) | contents:write → datasets repo |
| `MODELS_PAT` | Colab Secret | releases:write → models repo |
| `GPG_PASSPHRASE` | Colab Secret | فك التشفير بالذاكرة |

**قاعدة: لا secret في ملفات المستودع؛ التدوير سنوي/عند الشك (SECURITY.md).**
