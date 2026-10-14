<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 5 | حُفظ: 2026-10-08 -->

# Jina-OCR-v1 Integration Audit (JOCR-01)

# MASTER PROMPT — Jina-OCR-v1 Integration & Analysis Phase
## إضافة Jina-OCR-v1 كخيار OCR مساعد داخل Omni Medical Suite

> **تعليمات:** انسخ كل ما هو أسفل هذا السطر وأرسله إلى Z.ai **كما هو**. هذا البرومبت مستقل عن Master Prompt V2 السابق، لكنه يعتمد على نفس الفلسفة (Evidence-Driven، Stop-Gates، لا تعديل لـmain).

---

## 0. الهوية والسياق

أنت الآن تعمل كـ **Senior Document AI Engineer + OCR Integration Architect + License Compliance Officer**.

المستودع المستهدف:

```
/home/z/my-project/repos/omni-medical-suite
```

المستودع يحتوي بالفعل على:
- منظومة Omni OCR مركزية (Printed / Document / Handwriting).
- OLMoCR كـlayout/document engine (لا تلمسه).
- Phase-1 و AHW (Arabic Handwriting) قيد التطوير.
- فرع `main` مستقر.

**مهمتك في هذه المرحلة:** إضافة **Jina-OCR-v1** كـ **Optional OCR Engine Candidate** إلى المنظومة القائمة، مع تحليل دقيق ومُوثَّق يسمح باتخاذ قرار مبني على أدلة حول:
1. هل يُضاف فعلاً كمحرك إنتاجي؟
2. ما هي حدوده التقنية والقانونية؟
3. أين يتفوق/يتأخر مقارنة بالمحركات القائمة؟
4. ما الذي يمكن استخلاصه منه لتحسين مشروعك حتى لو لم يُستخدم مباشرة؟

---

## 1. القواعد المطلقة (Hard Constraints)

### 1.1 لا تلمس main

- لا `checkout` على main.
- لا commit على main.
- لا merge.
- لا حذف أي محرك قائم.
- لا تعديل OLMoCR أو AHW.
- لا استبدال أي dependency قائم.
- العمل فقط على فرع:

```
feature/jina-ocr-v1-integration
```

إذا كان الفرع موجودًا، أبلغ عنه قبل الاستخدام.

### 1.2 Jina-OCR-v1 ليس استبدالاً

Jina-OCR-v1 يُضاف كـ **Candidate Engine** وليس كبديل عن:
- Tesseract
- PaddleOCR
- EasyOCR
- TrOCR
- OLMoCR
- أي محرك آخر قائم.

وجوده يجب أن يكون:
- **OPTIONAL**
- **DISABLED BY DEFAULT**
- **FEATURE-FLAGGED**
- **ROLLBACK-SAFE**

### 1.3 الترخيص — قيد قانوني حرج

نموذج Jina-OCR-v1 مرخّص تحت:

```
CC BY-NC 4.0 (Creative Commons Attribution-NonCommercial 4.0)
```

هذا يعني:
- ❌ **لا يجوز استخدامه في الإنتاج التجاري** دون ترخيص تجاري من Jina AI.
- ✅ مسموح للبحث، التطوير، والتجارب غير التجارية.
- ⚠️ أي دمج في `omni-medical-suite` يجب أن يوضّح أن هذا المحرك **معطّل افتراضيًا** في أي مسار تجاري.

**يجب أن يوثّق تقريرك:**

| البند | الحالة |
|---|---|
| الترخيص | CC BY-NC 4.0 |
| الاستخدام التجاري | ❌ ممنوع بدون عقد منفصل |
| رابط التواصل التجاري | https://jina.ai/contact-sales/ |
| هل مشروعك تجاري؟ | (يسأل المستخدم) |
| إذا تجاري، ما البديل؟ | (يُذكر لاحقًا) |

إذا كان مشروع المستخدم تجاريًا، يجب وضع **Blocking Flag** قبل أي دمج إنتاجي.

---

## 2. STOP-GATE MODEL

العمل على مراحل. لا تنتقل من مرحلة إلى أخرى بدون موافقة صريحة.

كل مرحلة تُنتج:
- الملفات التي فُحصت.
- الأوامر المنفذة.
- المخرجات الخام.
- الاختبارات المنفذة.
- `git status` + `git diff --stat`.
- حالة: `PROVEN / PARTIALLY PROVEN / UNPROVEN / CONTRADICTED / BLOCKED`.
- المخاطر المتبقية.
- التوصية التالية.

---

## 3. PHASE JOCR-01 — AUDIT ONLY

### 3.1 قيود المرحلة

في هذه المرحلة **لا تفعل**:
- ❌ لا تُنزّل أوزان النموذج (3B params = ~6GB).
- ❌ لا تعدّل dependencies.
- ❌ لا تكتب كود دمج.
- ❌ لا تستدعي API خارجي.
- ❌ لا تعدّل main أو أي محرك قائم.

**الاستثناء الوحيد:** يمكنك قراءة وثائق Jina-OCR-v1 العامة (Hugging Face card، arXiv paper، Jina blog) واستخراج الأدلة.

### 3.2 التحقق من وجود المستودع (أول خطوة إلزامية)

قبل أي شيء آخر:

```bash
test -d /home/z/my-project/repos/omni-medical-suite
git -C /home/z/my-project/repos/omni-medical-suite rev-parse --is-inside-work-tree
git -C /home/z/my-project/repos/omni-medical-suite remote -v
git -C /home/z/my-project/repos/omni-medical-suite branch --show-current
git -C /home/z/my-project/repos/omni-medical-suite status
```

إذا فشل أي فحص: **توقف فورًا** واذكر الخطأ الدقيق. لا تخمّن. لا تستنسخ.

### 3.3 المطلوب في تقرير JOCR-01

أنشئ ملفًا:

```
docs/audit/JINA_OCR_V1_INTEGRATION_AUDIT.md
```

يجب أن يحتوي على الأقسام التالية:

---

#### A. Jina-OCR-v1 — بطاقة تقنية كاملة

املأ الجدول التالي بأدلة من المصادر الرسمية:

| الحقل | القيمة | المصدر (URL + مقتطف) |
|---|---|---|
| الاسم الكامل | Jina-OCR-v1 | HF card |
| المطوّر | Jina AI | HF card |
| الورقة البحثية | arXiv:2609.03181 | arXiv |
| تاريخ الإصدار | 2026-09-02 | arXiv |
| الترخيص | CC BY-NC 4.0 | HF card |
| الاستخدام التجاري | يحتاج عقد | jina.ai/contact-sales |
| البنية | DeepSeek-OCR (DeepEncoder + 3B MoE) | HF card |
| إجمالي المعاملات | ~3B | arXiv |
| المعاملات النشطة/توكن | ~570M | arXiv |
| الإدخال | صورة صفحة (1024×1024 + tiles) | HF card |
| الإخراج | Markdown (نص + جداول HTML + LaTeX) | HF card |
| OmniDocBench v1.6 | 91.14 | arXiv |
| olmOCR-Bench | 83.4 | arXiv |
| Throughput | 2.57 صفحة/ثانية | arXiv |
| GPU المستهدف | NVIDIA L4 (low-budget) | arXiv |
| Backends | Transformers, vLLM ≥0.21, SGLang | HF card |
| Serving API | OpenAI-compatible (api.jina.ai) | HF card |
| trust_remote_code | مطلوب = True | HF card |
| FastMTP | K=3 speculative decoding | arXiv |
| دعم اللغات | ~100 لغة (وراثة من DeepSeek-OCR) | Jina blog |
| دعم العربية | (يُحقَّق — غير مؤكد رسميًا) | UNPROVEN حتى إثبات |
| دعم الخط اليدوي | مذكور في الـprompt الرسمي | HF card |
| دعم الجداول | HTML tables | HF card |
| دعم المعادلات | LaTeX | HF card |
| دعم RTL | (يُحقَّق) | UNPROVEN حتى إثبات |

---

#### B. تحليل الأثر على مشروع omni-medical-suite

1. **أين سيُدمج؟**
   - هل البنية الحالية للـengines تسمح بإضافة محرك جديد بدون تعديل الـcontract؟
   - ما هو المسار المقترح: `packages/omni_ocr/engines/jina_ocr_v1/` أم موقع آخر؟
   - هل يوجد registry مركزي؟ كيف تُسجَّل المحركات؟

2. **التوافق مع الـProfiles:**
   - هل يوجد Profile مناسب (DOCUMENT / FULL / OCR_HEAVY)؟
   - هل يحتاج Profile جديد (`JINA_OCR` / `DOCUMENT_AI`)?

3. **التأثير على الـRouter:**
   - كيف يُقرر الـrouter متى يستخدم Jina-OCR-v1؟
   - هل يحتاج قواعد جديدة (حجم الملف، نوع المستند، وجود جداول)؟

4. **التوافق مع الـContract:**
   - هل `OCRResult` الحالي يستوعب Markdown output؟
   - كيف تُحفظ الجداول والمعادلات في الـprovenance؟

---

#### C. تحليل المخاطر (Risk Matrix)

| المخاطرة | الشدة | الاحتمال | التخفيف |
|---|---|---|---|
| ترخيص CC BY-NC يمنع الاستخدام التجاري | CRITICAL | مؤكد | Feature flag + توثيق + منع في production profile |
| حجم النموذج (3B / ~6GB) يتجاوز موارد الجهاز | HIGH | محتمل | تحميل عند الطلب + GPU requirement واضح |
| trust_remote_code = True (أمان) | HIGH | مؤكد | Sandbox + مراجعة كود الـsnapshot |
| توافق vLLM ≥0.21 مع النسخة الحالية | MEDIUM | محتمل | Dependency isolation |
| تعارض Transformers version | MEDIUM | محتمل | Optional extra + venv منفصل |
| دعم العربية غير مؤكد | HIGH | محتمل | Benchmark مخصص قبل الاعتماد |
| دعم الخط اليدوي غير مؤكد | HIGH | محتمل | اختبار على عينات AHW |
| Cold start 503 على الـAPI المستضاف | LOW | مؤكد | Retry logic + Local fallback |
| عدم وجود Inference Provider على HF | LOW | مؤكد | تشغيل محلي فقط |

---

#### D. تحليل الترخيص التفصيلي

| السيناريو | مسموح؟ | ملاحظات |
|---|---|---|
| بحث أكاديمي | ✅ | CC BY-NC يسمح |
| تطوير داخلي غير تجاري | ✅ | مسموح |
| إنتاج في مستشفى حكومي غير ربحي | ⚠️ | يحتاج مراجعة قانونية |
| إنتاج تجاري (SaaS / بيع) | ❌ | يحتاج عقد Jina |
| تدريب نموذج مشتق | ⚠️ | CC BY-NC يقيّد المشتقات التجارية |
| استخدام المخرجات (Markdown) | ⚠️ | المخرجات قد تكون حرة، لكن النموذج مقيّد |

**قرار مطلوب من المستخدم:** هل المشروع تجاري أم بحثي/شخصي؟

---

#### E. ما يمكن استخلاصه حتى لو لم يُستخدم النموذج

هذا قسم مهم. حتى لو قررنا عدم دمج Jina-OCR-v1 (بسبب الترخيص أو الموارد)، ما الذي يمكن تعلمه منه؟

1. **معمارية DeepEncoder:**
   - ضغط 1024×1024 إلى 256 visual tokens — تقنية قابلة للتطبيق على مشروعك.
   - دمج SAM (محلي) + CLIP (عام) — مفيد للخط اليدوي.

2. **FastMTP Speculative Decoding:**
   - تسريع 1.95× — يمكن تطبيقه على أي decoder في مشروعك.
   - فكرة "draft block واحد يُعاد استخدامه K=3 مرات" — مبتكرة.

3. **Dense Verifiable Rewards (GRPO):**
   - مكافآت قابلة للتحقق برمجيًا (جداول، معادلات) — قابلة للتطبيق في fine-tuning AHW.
   - فكرة "partial credit" بدل pass/fail — مفيدة لتدريب OCR عربي.

4. **Prompt Engineering:**
   - الـprompt الرسمي يحتوي على تعليمات دقيقة (HTML tables, LaTeX math, drop headers/footers, read handwriting).
   - يمكن استخلاص بنية prompt مشابهة لمشروعك.

5. **توزيع البيانات التدريبية:**
   - mix من corpora عامة + synthetic pages + historical degraded docs.
   - قابل للتطبيق في بناء dataset AHW.

6. **Benchmark Methodology:**
   - OmniDocBench v1.6 + olmOCR-Bench — يمكن اعتماد مقاييس مماثلة.

7. **Serving Efficiency:**
   - منهجية قياس pages/s, tok/page, tok/s — قابلة لإعادة الاستخدام.

---

#### F. خطوات التكامل المقترحة (AHW/JOCR-02 → JOCR-05)

| المرحلة | المهمة | المخرج |
|---|---|---|
| JOCR-02 | إنشاء adapter skeleton + feature flag | ملفات فارغة + config |
| JOCR-03 | تحميل النموذج محليًا + اختبار أساسي | تقرير تشغيل |
| JOCR-04 | Benchmark ضد المحركات القائمة | جدول مقارنة |
| JOCR-05 | قرار الدمج (ADOPT / ADAPT / DEFER / REJECT) | تقرير قرار |

---

#### G. Acceptance Criteria للـAudit

تقرير JOCR-01 يُعتبر مكتملاً فقط إذا:

1. ✅ كل ادعاء تقني مدعوم بمصدر URL + مقتطف.
2. ✅ كل "غير مؤكد" مُعلَّم بوضوح كـ`UNPROVEN`.
3. ✅ الترخيص موثّق مع رابط.
4. ✅ Risk Matrix مكتمل.
5. ✅ قسم "ما يمكن استخلاصه" يحتوي على 5 بنود على الأقل.
6. ✅ لا يوجد أي تعديل على كود المشروع.
7. ✅ تقرير Git status + diff مرفق.

إذا فشل أي معيار: **التقرير غير مكتمل**، ولا يُسمح بـJOCR-02.

---

## 4. ما يجب أن لا تفعله في JOCR-01

- ❌ لا تنزّل النموذج (3B = ~6GB).
- ❌ لا تثبّت vLLM أو Transformers إصدارًا جديدًا.
- ❌ لا تستدعي `api.jina.ai` (لا تملك API key، ولا داعي).
- ❌ لا تعدّل `requirements.txt` أو `pyproject.toml`.
- ❌ لا تنشئ branch جديدًا في JOCR-01 (الـAudit لا يحتاج branch).
- ❌ لا تفترض أن Jina-OCR-v1 "أفضل من OLMoCR" أو العكس.
- ❌ لا تُدخل Jina-OCR-v1 في أي Profile إنتاجي.

---

## 5. الصيغة النهائية للتقرير

```
# JINA_OCR_V1_INTEGRATION_AUDIT.md

## 1. Executive Summary (5 أسطر max)
## 2. Repository Verification (أوامر + مخرجات)
## 3. Jina-OCR-v1 Technical Card (جدول كامل)
## 4. License Analysis (جدول + قرار)
## 5. Integration Points (مسار الدمج المقترح)
## 6. Risk Matrix
## 7. Extractable Insights (حتى لو لم يُدمج)
## 8. Proposed Phases JOCR-02 → JOCR-05
## 9. Open Questions for User (3 أسئلة على الأقل)
## 10. Status Table
| Item | Status | Evidence |
## 11. Decision
ADOPT / ADAPT / DEFER / REJECT / UNPROVEN لكل مكوّن
## 12. Git Evidence
git status
git diff --stat
```

---

## 6. الأسئلة المفتوحة الإلزامية (للرد عليها من المستخدم)

يجب أن يتضمن التقرير هذه الأسئلة، ويجب أن يتوقف Z.ai بعدها:

1. **هل المشروع تجاري أم بحثي/شخصي؟**
   - إذا تجاري: هل يوجد ميزانية للترخيص التجاري من Jina AI؟
   - إذا بحثي: هل يكفي CC BY-NC 4.0؟

2. **ما هي الموارد المتاحة؟**
   - هل يوجد GPU بـVRAM ≥8GB؟
   - هل يمكن تحمّل تحميل نموذج بحجم ~6GB؟

3. **ما هو الهدف الفعلي من Jina-OCR-v1؟**
   - هل هو Document Parsing عام (جداول، معادلات)؟
   - هل هو الخط اليدوي العربي؟
   - هل هو benchmark للمقارنة فقط؟

4. **هل نقبل `trust_remote_code=True`؟**
   - هذا يعني تنفيذ كود من snapshot النموذج.
   - هل نحتاج sandbox؟

---

## 7. STOP-GATE النهائي

بعد تسليم `JINA_OCR_V1_INTEGRATION_AUDIT.md`:

```
STOP.

Do NOT:
- create branch
- download model
- modify code
- install dependencies
- commit
- push

Wait for explicit user authorization for JOCR-02.
```

---

## 8. الصيغة النهائية للرد

في نهاية التقرير:

```
JOCR-01 STATUS

Repository: /home/z/my-project/repos/omni-medical-suite
Branch: <actual>
HEAD: <actual SHA>
Production code modified: NO
Existing engines modified: NO
Dependencies modified: NO
External AI calls: NO
Model downloaded: NO
Audit report: docs/audit/JINA_OCR_V1_INTEGRATION_AUDIT.md
Commands executed: <list>
Tests executed: <list or NONE>
Critical findings: <list>
PROVEN: <list>
PARTIALLY PROVEN: <list>
UNPROVEN: <list>
CONTRADICTED: <list>
BLOCKED: <list>

Next phase: JOCR-02 (requires authorization)
Authorization required: YES
```

ثم توقف.

---

## 9. المبدأ الأساسي

```
Jina-OCR-v1 هو ضيف، وليس مضيفًا.
يُدرس أولاً، يُقيَّم ثانيًا، يُدمج ثالثًا — وقد يُرفض.
حتى لو رُفض، ما يمكن تعلمه منه يبقى في المشروع.
الترخيص ليس تفصيلاً — هو قيد معماري من الدرجة الأولى.
لا دمج بدون evidence.
لا evidence بدون أوامر خام.
```

**ابدأ الآن بـJOCR-01 فقط. ثم توقف.**
