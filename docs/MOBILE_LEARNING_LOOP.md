# Mobile Learning Loop — حلقة التعلّم من اختيارات المستخدم على الجوال

> **الهدف**: كل تصحيح يحفظه المستخدم عبر واجهة الجوال (PWA) يُحسِّن تلقائياً
> دقة `HybridSpellChecker` في التشغيلة التالية، دون تدخّل يدوي.

## المخطط الكامل لتدفق البيانات

```
                       ┌───────────────────────────────────┐
                       │   المستخدم على الجوال (PWA)         │
                       │   packages/core/mobile/ocr-review  │
                       │   .html                            │
                       └────────────────┬──────────────────┘
                                        │
                                        │ 1) POST /process
                                        │    (رفع صورة طبية)
                                        ▼
                       ┌───────────────────────────────────┐
                       │  Flask: packages/core/mobile/      │
                       │  server.py                         │
                       │  ─────────────────────────────     │
                       │  • /process يستدعي مباشرة:         │
                       │    app.services.ocr_service.*      │
                       │    app.services.review_service.*   │
                       │  (نفس مسار Gradio الحي بالضبط)      │
                       └────────────────┬──────────────────┘
                                        │
                                        │ 2) النتيجة تُعرض للمستخدم
                                        │    (نص + كيانات + ثقة)
                                        ▼
                       ┌───────────────────────────────────┐
                       │   المستخدم يصحّح الكلمات الخاطئة    │
                       │   عبر واجهة المراجعة                │
                       └────────────────┬──────────────────┘
                                        │
                                        │ 3) POST /save
                                        │    (JSON: predicted + corrected)
                                        ▼
        ┌───────────────────────────────┴───────────────────────────────┐
        │  POST /save in packages/core/mobile/server.py                 │
        │  يوجّه كل تصحيح إلى THREE مخازن متزامنة:                         │
        └──────┬──────────────────────────┬─────────────────────────────┘
               │                          │
               ▼                          ▼                          ▼
   ┌───────────────────────┐  ┌──────────────────────┐  ┌─────────────────────┐
   │ 1. CorrectionsDict    │  │ 2. WordCorrectionDB  │  │ 3. ActiveLearner    │
   │    Manager            │  │    (SQLite)          │  │    (SQLite)         │
   │    ─────────────      │  │    ───────────       │  │    ──────────      │
   │ artifacts/            │  │ artifacts/           │  │ artifacts/          │
   │   correction_dict.json│  │   corrections.db     │  │   active_learning   │
   │                       │  │                      │  │   .db               │
   │ CorrectionsDict       │  │ WordCorrectionDB     │  │ ActiveLearningDB   │
   │   Manager.add(        │  │   .save_batch(       │  │   .save_correction( │
   │     wrong, correct)   │  │     [{predicted,     │  │     original,       │
   │                       │  │       corrected,     │  │     corrected,      │
   │                       │  │       lang, ...}])   │  │     lang, conf)    │
   │                       │  │                      │  │                     │
   │                       │  │ ⚡ يحدّث              │  │ ⚡ يفحص             │
   │                       │  │ arabic_fixes.json    │  │ correction_threshold│
   │                       │  │ تلقائياً بعد كل دفعة  │  │ → يطلق retrain عند │
   │                       │  │                      │  │ الوصول للعتبة       │
   └───────────────────────┘  └──────────┬───────────┘  └──────────┬──────────┘
                                          │                         │
                                          ▼                         ▼
                            ┌──────────────────────────┐  ┌─────────────────────┐
                            │ HybridSpellChecker       │  │ ActiveLearner       │
                            │ (packages/core/          │  │ ._retrain_model()   │
                            │  spell_checker.py)       │  │ → يستدعي            │
                            │                          │  │   TrOCRFineTuner    │
                            │ • يحمل arabic_fixes.json  │  │   .train() (lazy)   │
                            │   في كل استدعاء           │  │                     │
                            │ • يستعلم WordCorrectionDB│  │ النتيجة: نموذج      │
                            │   لكل كلمة               │  │ trocr_ar_vYYYYMMDD_ │
                            │                          │  │ HHMMSS محفوظ في     │
                            │ → يصحّح الكلمات بناءً     │  │ artifacts/models/   │
                            │   على تصحيحات المستخدم   │  │                     │
   ┌────────────────────────┴──────────────────────────┘  └─────────────────────┘
   │
   │ 4) في التشغيلة التالية (next process_image call):
   │    HybridSpellChecker.correct_text("السللام")
   │    → يُرجع "السلام" تلقائياً
   │
   ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ GET /stats → لوحة معلومات للمستخدم والإدارة                 │
   │                                                             │
   │ {                                                           │
   │   corrections_dict: {total, arabic_count, english_count},  │
   │   word_trainer:     {total_corrections, accuracy_pct,      │
   │                       sessions, by_language, top_words},   │
   │   active_learning:  {training_stats_ar: {                  │
   │                       total_corrections, total_models,     │
   │                       used_corrections,                    │
   │                       total_training_data}},               │
   │   retrain_threshold: "see packages.ai.active_learning"     │
   │ }                                                           │
   └─────────────────────────────────────────────────────────────┘
```

## نقاط التكامل الرئيسية

### 1. التكامل الفوري (Per-correction)
كل استدعاء `POST /save` يُحدِّث فوراً:
- `artifacts/correction_dict.json` (قاموس JSON قابل للمشاركة)
- `artifacts/corrections.db` (قاعدة بيانات SQLite للتصحيحات)
- `artifacts/active_learning.db` (قاعدة بيانات SQLite للتعلّم النشط)
- `data/arabic_fixes.json` (يُحدَّث تلقائياً بواسطة `WordCorrectionDB.save_batch()`
  بعد كل دفعة تحوي كلمات عربية — يستدعي `update_arabic_fixes()` داخلياً)

**النتيجة المباشرة**: في الطلب التالي على `process_image()`، يجد
`HybridSpellChecker` التصحيح الجديد ويطبّقه تلقائياً — لا حاجة لإعادة تشغيل
الخادم.

### 2. التكامل الدفعي (Batch training)
عند بلوغ عدد التصحيحات لعتبة `correction_threshold` (الافتراضي 2، قابل
للتعديل عبر `ActiveLearningDB.set_setting()`), يستدعي `ActiveLearner` تلقائياً:
- `_retrain_model(language)`
- يجمع بيانات التدريب من SQLite
- يستدعي `packages.ai.finetuning.TrOCRFineTuner.train()` (lazy import)
- يحفظ النموذج الجديد باسم `trocr_{lang}_v{timestamp}`
- يسجّل إصدار النموذج في `model_versions` table

### 3. التدريب اليدوي عبر active_learning_pipeline.py
```
python packages/training-framework/scripts/active_learning_pipeline.py \
    --retrain \
    --new-data data/ocr_corrected.json
```
يقرأ ملف `ocr_corrected.json` الذي يحفظه `/save`، يحوّله إلى JSONL،
ويُطلق دورة تدريب كاملة يدوياً.

## التحقق الحي المُجرى (Live Verification)

في `feat/mobile-server-wire-app-services` (المهمة 2):

```python
# 1. POST /save
client.post('/save', json={
    'items': [
        {'predicted': 'السللام', 'corrected': 'السلام',
         'lang': 'ar', 'confidence': 0.85}
    ],
    'source': 'mobile-pwa-test',
})

# 2. GET /stats — يُظهر نموّ العدّادات
corrections_dict.total:           54 (+1)
word_trainer.total_corrections:    3 (+1)
active_learning.total_corrections: 2 (+1)

# 3. التحقق المباشر من إغلاق الحلقة
from packages.core.spell_checker import HybridSpellChecker
sc = HybridSpellChecker()
sc.get_suggestions('السللام', lang='ar', n=5)
# → ['السلام']   ← التصحيح تعلّمه النظام تلقائياً
```

## ملاحظات تشغيلية

### أين تُحفظ البيانات؟
- **افتراضياً**: `<monorepo_root>/data/` (يُنشأ تلقائياً)
- **عبر env**: `OMNI_MOBILE_DB_DIR=/path/to/dir python -m packages.core.mobile.server`

### ماذا يحدث إذا فشل أحد المكونات؟
كل مكون من المكونات الثلاثة معزول بـ `try/except`. فشل أحدها لا يكسر الآخرين:
- فشل `corrections_mgr` → يُسجّل في `errors` field بالاستجابة
- فشل `word_trainer` → نفسه
- فشل `active_learner` → نفسه
- فشل الجميع → الاستجابة تُرجع `200 OK` مع `errors` list، والـ JSON الخام
  لا يزال يُحفظ في `ocr_corrected.json` كـ fallback

### ماذا عن التدريب على GPU؟
- `TrOCRFineTuner` يتطلب GPU (في الإعداد الافتراضي)
- على خوادم CPU-only (مثل HuggingFace Spaces free tier)، يُعطّل التدريب
  تلقائياً ويُسجّل تحذير، لكن التصحيحات تستمر في التراكم في SQLite
- يمكن تشغيل التدريب لاحقاً على جهاز GPU منفصل عبر `active_learning_pipeline.py`

## ملفات مرتبطة

| الملف | الدور |
|------|------|
| `packages/core/mobile/server.py` | خادم Flask الموحَّد (يستدعي app.services.*) |
| `packages/core/corrections_manager.py` | قاموس JSON القابل للمشاركة |
| `packages/core/word_trainer.py` | SQLite للتصحيحات (يُحدّث arabic_fixes.json) |
| `packages/core/spell_checker.py` | HybridSpellChecker (يقرأ من الكل) |
| `packages/ai/active_learning.py` | ActiveLearner (يُطلق retrain تلقائياً) |
| `packages/training-framework/scripts/active_learning_pipeline.py` | سكربت batch training |
| `app/services/ocr_service.py` | طبقة OCR الموحّدة (Gradio + Mobile) |
| `app/services/review_service.py` | NER + LLM proofreading |

## روابط داخلية ذات صلة
- `STATE_OF_TRUTH.md` — الوضع الراهن للمشروع
- `ROADMAP.md` — خارطة الطريق (تراكم التصحيحات = تحسّن تلقائي)
- `packages/core/mobile/README.md` — تشغيل الخادم
