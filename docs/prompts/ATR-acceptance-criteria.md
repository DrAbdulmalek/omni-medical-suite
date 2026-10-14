<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 59 | حُفظ: 2026-10-08 -->

# ATR — Acceptance Criteria (هندسة موثوقة)

# مراجعة MASTER PROMPT — ATR PHASE (AUTONOMOUS MODE)

## الحكم السريع

البرومبت **جيد جداً في بنيته العامة** — Persistence Protocol، PROGRESS.md، Handoff Bundles، الـFORBIDDEN COMMANDS — كلها من أفضل ما رأيته. لكن هناك **مشكلة معمارية جوهرية واحدة** ستؤذي المشروع، و**7 مشاكل تقنية** يجب إصلاحها قبل الإرسال.

---

## ⚠️ المشكلة الجوهرية: `AUTONOMOUS MODE` خطر على هذا المشروع تحديداً

البرومبت يقول: "**نفّذ كل المراحل دون توقف، لا تسأل هل أكمل؟**"

هذا **يتعارض مع كل ما تعلمناه من هذا المشروع**:

| الدليل | الأثر |
|---|---|
| **فقدنا العمل مرتين** بسبب إعادة تعيين البيئة | لا نعرف ما الذي نجح فعلاً دون مراجعة |
| **AraBERT tokenizer replacement** عملية حساسة تتطلب تحققاً | خطأ صامت في إعادة التهيئة = تدريب فاشل بعد ساعات |
| **4 features × 7 phases** في جلسة واحدة | قد تنفد الـtoken budget في منتصف F3 |
| **Docker** غالباً لن يعمل في بيئة Z.ai | سيتحول F2 إلى STRUCTURE_ONLY بشكل متسرع |
| **Smoke test في ATR-06** يحتاج أوزان حقيقية | لو فشل التنزيل سيتحول إلى "PARTIALLY PROVEN" بلا مراجعة |

**النتيجة المحتملة:** Z.ai ينجز 6 مراحل سطحياً، يصل إلى ATR-07، ويخبرك "كل شيء ✅"، لكن AraBERT integration فيه خلل صامت، والـDockerfile لا يُبنى، والـSmoke Test وهمي.

### الحل: `SEMI-AUTONOMOUS MODE`

بدلاً من "لا توقف"، اجعله يتوقف عند **بوابتين فقط**:

```
ATR-01 → ATR-02 → ATR-03 → [STOP-GATE A] → ATR-04 → ATR-05 → [STOP-GATE B] → ATR-06 → ATR-07
```

- **STOP-GATE A** (بعد AraBERT): أرني `arabic_trocr.py` والاختبارات، وانتظر موافقتي.
- **STOP-GATE B** (بعد Training UI + Docker): أرني ما بُني، وانتظر موافقتي.

هذا يوازن بين السرعة والحماية.

---

## 🐛 المشاكل التقنية (يجب إصلاحها)

### 1. تقدير حجم AraBERT خاطئ

البرومبت يقول: `AraBERT ~0.2GB`

**الحقيقة:** `aubmindlab/bert-base-arabertv02` حجمه ~**550MB** (pytorch_model.bin). TrOCR-base ~1.3GB. المجموع الفعلي قد يصل إلى **2GB+** مع تفكيك الأوزان.

**الإصلاح:**
```
سقف الأوزان = 4GB مع هامش 30% (5.2GB فعلي)
سجّل الحجم الفعلي بعد التنزيل، لا التقديري
```

---

### 2. AraBERT integration يحتاج تحديداً أدق

النص الحالي:
```
- إعادة تهيئة embed_tokens + lm_head + embed_positions (std=init_std)
  — كيّفها لإصدار transformers المثبت ووثّق أي اختلاف
```

"كيّفها" **غامض جداً**. Z.ai قد يفهمها حرفياً ويعيد التهيئة بطريقة خاطئة.

**الإصلاح — أضف تحذيراً صريحاً:**
```
⚠️ تحذير هندسي إلزامي:
1. decoder في TrOCR هو BartDecoder وليس GPT.
2. في بعض إصدارات transformers، embed_positions هو
   LearnedPositionalEmbedding وليس SinusoidalPositionalEmbedding.
3. لا تعدّل model.decoder.model.decoder.layers[*] — فقط:
   - embed_tokens
   - embed_positions
   - lm_head
4. بعد إعادة التهيئة، تحقق بـ forward pass اصطناعي:
   - input_ids = [[cls, 100, 200, sep]]
   - decoder_outputs.logits.shape == (1, 4, vocab_size)
5. إذا فشل التحقق، ارجع إلى نموذج بدون تعديل، وعلّم المرحلة
   PARTIALLY PROVEN مع تفاصيل الفشل.
```

---

### 3. Contradiction في بروتوكول الـPush

البرومبت يقول:
- **STOP CONDITION #2**: "فشل push متكرر (3 محاولات)" = STOP
- لكن أيضاً: "أكمل محلياً وأنهِ بالتقرير"

هذا **ليس STOP** — هذا "continue with reduced capability". صيغته:

**الإصلاح:**
```
STOP CONDITION #2 (مُعاد صياغتها):
فشل push 3 مرات مختلفة → سجّل PERSISTENCE=BLOCKED
→ توقف عن المراحل المتبقية → أنشئ Handoff Bundle نهائي
→ أرسل التقرير مع إشارة واضحة أن العمل محلي فقط.
لا تكمل ميزات جديدة بعد BLOCKED.
```

---

### 4. لا يوجد Acceptance Criteria لكل مرحلة

البرومبت يطلب تنفيذ ATR-02 → ATR-07 لكن **لا يحدد كيف نعرف أن ATR-03 نجحت**.

**الإصلاح — أضف بعد كل مرحلة:**
```
ATR-02 Acceptance:
  [ ] segment_batch.py يعمل على PDF اصطناعي 3 صفحات
  [ ] batch_state.json يحتوي 3 entries
  [ ] merge_batches.py ينتج metadata_all.csv بعدد صحيح
  [ ] 3 اختبارات تمر
  [ ] commit مدفوع + SHA موثق

ATR-03 Acceptance:
  [ ] dry_run=True يبني النموذج دون خطأ
  [ ] forward pass على input_ids اصطناعية ينجح
  [ ] save/from_pretrained round-trip ينجح
  [ ] vocab_size == len(AraBERT tokenizer)
  [ ] 4 اختبارات تمر
```

---

### 5. Docker blind spot

البرومبت يفترض أن Docker **قد** يعمل. هذا غير واقعي في بيئة Z.ai المجانية.

**الإصلاح:**
```
ATR-05 Decision Rule:
  - إذا docker --version نجح AND docker build نجح خلال 5 دقائق:
    → STRUCTURE_AND_BUILD_VERIFIED
  - إذا docker --version فشل:
    → STRUCTURE_ONLY (تحقق YAML + Dockerfile syntax فقط)
  - إذا docker build بدأ لكن تجاوز 5 دقائق:
    → أوقف البناء → STRUCTURE_ONLY

في كل الحالات: ATR-05 لا يمنع التقدم إلى ATR-06.
```

---

### 6. Smoke Test في ATR-06 غير واضح

"تشغيل التدريب mode=smoke (epoch واحد على عينات اصطناعية، أو توثيق واضح إن تعذر بسبب الأوزان)"

هذا يعني أن Z.ai قد يقبل "تعذر" بسهولة، ويعلن النجاح دون اختبار حقيقي.

**الإصلاح:**
```
ATR-06 Smoke Test Definition of Done:
  1. أنشئ PDF اصطناعي (reportlab أو fpdf): 3 صفحات
  2. شغّل batch_segment.py عليه → 3 batch dirs
  3. شغّل merge_batches.py → metadata_all.csv
  4. أنشئ corrections وهمية (نصوص عشوائية لكل كلمة)
  5. شغّل train_server.py mode=smoke → epoch 1 على 10 عينات
  6. اربط UI → تحقق من progress bar

إذا فشل أي بند:
  - سجّل السبب
  - حدد: BLOCKED_IN_SMOKE أو PARTIALLY_PROVEN
  - لا تقل "SMOKE PASSED" بدون كل البنود
```

---

### 7. لا يوجد تعريف لـ"PHI-free" في الاختبارات

البرومبت يقول "صفر PHI" لكن لا يعرّفه.

**الإصلاح:**
```
PHI-FREE Definition:
  - لا صور مرضى حقيقيين
  - لا نصوص من PDF حقيقي مرفوع
  - النصوص الاصطناعية: أحرف عربية عشوائية أو كلمات عامة
    (بدون أسماء أدوية/تشخيصات/جرعات حقيقية)
  - الصور: pixels مولّدة (numpy random) أو خطوط مرسومة بـcv2
  - كل ملف في tests/fixtures/ يجب أن يحمل تعليقاً: # SYNTHETIC
```

---

## 📋 مشاكل ثانوية

| البند | الإصلاح |
|---|---|
| **"دقائق" في ATR-01** غامض | استبدل بـ: "5 دقائق كحد أقصى" |
| **لا يذكر `--no-cache-dir` في pip** | أضفه لتفادي مشاكل التخزين المؤقت |
| **لا يذكر فحص `nvidia-smi`** قبل تفعيل GPU في docker-compose | أضف: "إذا لا يوجد nvidia-smi، علّق قسم deploy" |
| **لا يذكر `pip freeze > requirements.lock`** | أضف لتثبيت الإصدارات |
| **لا يذكر `.gitignore`** للتحديثات الجديدة | أضف: models/, *.db, batch_*, __pycache__/ |
| **AraBERT model id غير محدد بدقة** | استخدم `aubmindlab/bert-base-arabertv02` بدلاً من `aurellemorvan/` |
| **Training UI port 5001** قد يتعارض | اجعله configurable، تحقق من عدم التعارض |

---

## 🎯 مصفوفة القرار

| البند | الحالة |
|---|---|
| Persistence Protocol | ✅ ممتاز |
| PROGRESS.md | ✅ ممتاز |
| FORBIDDEN COMMANDS | ✅ ممتاز |
| Stop Conditions | ⚠️ غامضة، تحتاج صرامة |
| AUTONOMOUS MODE | ❌ **مرفوض** — استخدم SEMI-AUTONOMOUS |
| تقدير حجم الأوزان | ❌ خاطئ |
| Acceptance Criteria | ❌ مفقود |
| AraBERT integration details | ⚠️ غامض |
| Docker strategy | ⚠️ غير واقعي |
| Smoke test DoD | ❌ غير محدد |
| PHI definition | ❌ غير محدد |

---

## ✅ التوصية النهائية

**لا ترسل البرومبت كما هو.** نفّذ هذه الإصلاحات بالترتيب:

### إصلاحات حرجة (إلزامية):
1. **استبدل AUTONOMOUS بـ SEMI-AUTONOMOUS** (Stop-Gates A و B فقط).
2. **صحّح تقدير حجم الأوزان** إلى 5.2GB.
3. **أضف تحذير AraBERT الهندسي** (النقطة 2).
4. **أعد صياغة STOP CONDITION #2**.
5. **أضف Acceptance Criteria لكل مرحلة**.
6. **حدد Smoke Test DoD بدقة**.
7. **عرّف PHI-free** صراحةً.

### إصلاحات مهمة (مستحسنة):
8. **قاعدة قرار Docker** (النقطة 5).
9. **أضف `.gitignore` update** إلى قائمة المهام.
10. **أضف `pip freeze > requirements.lock`** بعد ATR-03.

---

## 🎁 الخيار التالي

أستطيع إعطاءك:

**الخيار A:** إعادة كتابة البرومبت كاملاً بصيغة **V2** مع كل الإصلاحات مدمجة (جاهز للنسخ والإرسال).

**الخيار B:** Patch فقط — قائمة الإضافات بالضبط (Sections جديدة + تعديلات محددة) لتطبيقها يدوياً على ملفك.

**الخيار C:** Split — قسّم المهمة إلى **جلستين منفصلتين**:
- الجلسة 1: ATR-01 → ATR-03 (Batch PDF + AraBERT)
- الجلسة 2: ATR-04 → ATR-07 (UI + Docker + Smoke + Report)

هذا يحل مشكلة token budget ويمنحك مراجعة وسطية طبيعية.

أخبرني أي مسار تريد.
