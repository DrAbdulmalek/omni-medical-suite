<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 25 | حُفظ: 2026-10-08 -->

# ARCH-07 — Final Architecture Package

# MASTER PROMPT — AI Architecture Audit & Smart System Transformation
## Omni Medical Suite — From Tools Collection to Intelligent System

> **تعليمات:** انسخ كل ما هو أسفل هذا السطر وأرسله إلى Z.ai كما هو. البرومبت مصمم ليكون مستقلاً عن البرومبتات السابقة، لكنه يشاركها نفس الفلسفة (Evidence-Driven، Stop-Gates، لا تعديل لـmain).

---

## 0. الهوية والسياق

أنت الآن تعمل كـ:

- **AI Systems Architect**
- **Production ML Engineer**
- **Distributed Systems Designer**
- **Observability Engineer**
- **Reliability Engineer**
- **Repository Archaeologist**

المستودع المستهدف:

```
/home/z/my-project/repos/omni-medical-suite
```

المستودع يحتوي بالفعل على:
- محركات OCR متعددة (Tesseract, PaddleOCR, EasyOCR, TrOCR)
- OLMoCR (Document/Layout OCR)
- AHW (Arabic Handwriting Recognition) — قيد التطوير
- Jina-OCR-v1 — قيد الدراسة
- Xberg — قيد الدراسة
- OpenCodeReview — قيد الدراسة
- Learning Ledger / Dataset pipeline — قيد التصميم

**المشكلة الأساسية التي تحلها هذه المهمة:**

المشروع يمتلك **أدوات** (Tools) لكنه يفتقد **نظاماً معمارياً** (System Architecture) يربطها. الهدف ليس إضافة framework جديد، بل **تصميم Architecture كاملة** تجيب على الأسئلة التالية لكل مكوّن:

1. **What?** — ماذا يفعل؟
2. **Why?** — لماذا نحتاجه؟
3. **Where?** — أين يوضع في النظام؟
4. **How?** — كيف يتواصل مع باقي المكونات؟
5. **What if it fails?** — ماذا يحدث عند الفشل؟

---

## 1. الفلسفة الأساسية

```
FRAMEWORKS تتغير.
MODELS تتغير.
LIBRARIES تتغير.

لكن ARCHITECTURE + DATA FLOW + STATE + TOOLS +
RELIABILITY + EVALUATION + TRADE-OFFS — تبقى.
```

**القاعدة الذهبية:**

> **ARCHITECTURE FIRST → THEN TOOLS.**

لا تبدأ بالـframework. ابدأ بالرسم. ابدأ بالسؤال "لماذا هذا المكوّن موجود؟".

---

## 2. القواعد غير القابلة للتفاوض

### 2.1 ممنوع تماماً

- ❌ تعديل `main`.
- ❌ merge بدون تفويض.
- ❌ حذف أي محرك أو مكوّن قائم.
- ❌ إضافة framework جديد (`LangGraph`, `LlamaIndex`, `CrewAI`...) في هذه المرحلة.
- ❌ تثبيت أي حزمة.
- ❌ كتابة كود production.
- ❌ ادعاء أن مكوّناً "مفقود" أو "مطلوب" قبل إثبات ذلك بأدلة.
- ❌ اقتباس Architecture من مشروع آخر ونقلها كما هي.
- ❌ تجاهل المكونات الموجودة فعلاً في المستودع.
- ❌ اعتبار "الشعبية" أو "الحداثة" دليلاً معمارياً.

### 2.2 إلزامي

- ✅ Evidence لكل ادعاء (مسار ملف + رقم سطر، أو أمر + مخرجه).
- ✅ التحقق من وجود كل مكوّن فعلاً في الكود، لا في التوثيق فقط.
- ✅ رسم Architecture Diagram فعلي (Mermaid في تقرير Markdown).
- ✅ تحديد Failure Modes لكل مكوّن.
- ✅ اقتراح Trade-offs، ليس قرارات مطلقة.
- ✅ أسئلة صريحة للمستخدم عند الغموض.

---

## 3. STOP-GATE MODEL

كل مرحلة تُنتج تقريراً مستقلاً بحالة واحدة من:

```
PROVEN | PARTIALLY PROVEN | UNPROVEN | CONTRADICTED | BLOCKED | NOT EXECUTED
```

كل تقرير يجب أن يحتوي:
- الملفات التي فُحصت (مع مساراتها).
- الأوامر التي نُفّذت.
- المخرجات الخام ذات الصلة.
- `git status` + `git diff --stat`.
- المخاطر المتبقية.
- التوصية التالية.

**لا تقل "DONE" إلا إذا كانت Definition of Done محققة.**

---

## 4. المراحل (ARCH-00 → ARCH-07)

### 🅰️ ARCH-00 — Pre-Flight Verification

**الهدف:** التحقق من أن المستودع جاهز للتفتيش قبل أي شيء.

**الأوامر:**

```bash
test -d /home/z/my-project/repos/omni-medical-suite
git -C /home/z/my-project/repos/omni-medical-suite rev-parse --is-inside-work-tree
git -C /home/z/my-project/repos/omni-medical-suite remote -v
git -C /home/z/my-project/repos/omni-medical-suite branch --show-current
git -C /home/z/my-project/repos/omni-medical-suite status --short
git -C /home/z/my-project/repos/omni-medical-suite log -n 5 --oneline
```

**إذا فشل أي فحص:** STOP. أبلغ المستخدم. لا تخمّن. لا تستنسخ.

**المخرج:** تقرير قصير بحالة المستودع.

**STOP-GATE 0:** لا تبدأ ARCH-01 قبل اجتياز ARCH-00.

---

### 🅱️ ARCH-01 — Current Architecture Inventory

**الهدف:** رسم كامل لمعمارية المشروع **كما هي الآن** — لا كما نتمناها.

#### المطلوب

1. **شجرة المستودع الكاملة:**
```bash
tree -L 4 -I 'node_modules|__pycache__|.git|*.pyc|venv|.venv'
```

2. **جرد المكونات الفعلية:**

| المكوّن | موجود؟ | المسار | الوصف | يدخل في runtime؟ |
|---|---|---|---|---|
| OCR Engine 1 (Tesseract) | | | | |
| OCR Engine 2 (Paddle) | | | | |
| OCR Engine 3 (EasyOCR) | | | | |
| OCR Engine 4 (TrOCR) | | | | |
| OLMoCR | | | | |
| AHW | | | | |
| Router | | | | |
| Normalization | | | | |
| Provenance | | | | |
| Dataset Pipeline | | | | |
| UI | | | | |
| CLI | | | | |
| API | | | | |
| Config System | | | | |
| Logging | | | | |
| Testing | | | | |
| CI/CD | | | | |

**لا تفترض وجود أي مكوّن.** افحص الكود فعلاً.

3. **Data Flow الحالي:**

رسم Mermaid يصف: من يدخل → ماذا يحدث → من يخرج.

```mermaid
graph LR
    A[Input] --> B[?]
    B --> C[?]
    C --> D[Output]
```

4. **Failure Modes الحالية:**

| المكوّن | ماذا يحدث عند الفشل؟ | هل يوجد fallback؟ | هل يُسجَّل الخطأ؟ |
|---|---|---|---|
| | | | |

5. **الـContracts الحالية:**

- ما هي الـinterfaces الرسمية؟
- هل هي موثقة؟
- هل كل مكوّن يلتزم بها؟

#### المخرج

```
docs/audit/ARCH-01_CURRENT_ARCHITECTURE.md
```

#### Definition of Done

- [ ] شجرة المستودع مرفقة.
- [ ] جدول المكونات مكتمل (لا فراغات).
- [ ] Data Flow Diagram موجود.
- [ ] Failure Modes موثقة.
- [ ] الـContracts مُحددة.
- [ ] كل ادعاء يحمل Evidence.

#### STOP-GATE 1

لا تبدأ ARCH-02 قبل أن يؤكد المستخدم دقة الجرد.

---

### 🅲 ARCH-02 — Gap Analysis

**الهدف:** تحديد **ما هو مفقود** في المعمارية، بناءً على ARCH-01.

#### المطلوب

لكل مكوّن من المكونات المعمارية المعيارية التالية، حدد:

| المكوّن المعياري | موجود في Omni؟ | الحالة | الأولوية | Evidence |
|---|---|---|---|---|
| **Router / Orchestrator** | | | | |
| **Validation Layer** | | | | |
| **Observability / Tracing** | | | | |
| **Metrics Collection** | | | | |
| **Evaluation Pipeline** | | | | |
| **State Management** | | | | |
| **Long-term Memory / Learning Ledger** | | | | |
| **Retry / Fallback Logic** | | | | |
| **Rate Limiting / Resource Control** | | | | |
| **Caching Layer** | | | | |
| **Health Checks** | | | | |
| **Error Taxonomy** | | | | |
| **A/B Testing / Model Versioning** | | | | |
| **Feature Flags** | | | | |
| **Documentation / ADRs** | | | | |

#### القواعد

- **لا تفترض أن كل مكوّن "مطلوب"**. بعضها قد يكون غير ضروري لمشروعك.
- لكل مكوّن مفقود، اسأل: **هل نحتاجه فعلاً؟** أم أنه Over-engineering؟
- رتّب حسب **الأولوية الفعلية** لمشروع طبي:
  - **CRITICAL:** الأمان، التحقق الطبي، الـtracing.
  - **HIGH:** Router، Fallback، Evaluation.
  - **MEDIUM:** Caching، Rate Limiting.
  - **LOW:** A/B Testing، Feature Flags (قد تكون لاحقاً).

#### المخرج

```
docs/audit/ARCH-02_GAP_ANALYSIS.md
```

#### Definition of Done

- [ ] جدول Gap كامل.
- [ ] كل Gap له مبرر (لماذا نحتاجه؟).
- [ ] كل Gap له أولوية.
- [ ] تمييز واضح بين "ضروري" و"لاحقاً" و"غير ضروري".

#### STOP-GATE 2

لا تبدأ ARCH-03 قبل موافقة المستخدم على قائمة الفجوات.

---

### 🅳 ARCH-03 — Target Architecture Design

**الهدف:** رسم Architecture **المستهدفة** — النظام الذكي الذي نريد الوصول إليه.

#### المطلوب

1. **Target Architecture Diagram:**

```mermaid
graph TB
    User[User / API]
    Router[Router / Orchestrator]
    Tools[Tools Layer]
    Agents[Agent Layer]
    State[State / Memory]
    LLM[LLM / Reasoning]
    Validation[Validation Layer]
    Eval[Evaluation]
    Obs[Observability]
    DB[(Database)]
    RAG[RAG / Retrieval]

    User --> Router
    Router --> Agents
    Agents --> Tools
    Agents --> LLM
    Agents --> RAG
    Tools --> DB
    LLM --> Validation
    Validation --> Eval
    Eval --> Obs
    Router --> State
    State --> DB
```

2. **Data Flow (Step-by-Step):**

لكل مرحلة، وثّق:
- المدخلات.
- المعالجة.
- المخرجات.
- الحالة (State).
- الأخطاء المحتملة.

3. **Component Specifications:**

لكل مكوّن جديد، أجب على الأسئلة الخمسة:

| السؤال | الإجابة |
|---|---|
| **What?** | |
| **Why?** | |
| **Where?** | |
| **How?** | |
| **What if it fails?** | |

4. **Trade-offs:**

- ما الذي **نكسبه** من كل مكوّن؟
- ما الذي **نخسره** (تعقيد، latency، تكلفة)؟
- هل هناك بديل أبسط؟

5. **Reliability Plan:**

- ماذا يحدث إذا فشل كل مكوّن؟
- ما هي خطة الـfallback؟
- كيف نتعافى؟

6. **Security & Privacy:**

- أين توجد البيانات الحساسة؟
- هل تخرج من النظام؟
- كيف نحميها؟

#### المخرج

```
docs/audit/ARCH-03_TARGET_ARCHITECTURE.md
```

#### Definition of Done

- [ ] Target Diagram موجود.
- [ ] كل مكوّن جديد له الإجابات الخمس.
- [ ] Trade-offs موثقة.
- [ ] Failure Modes مُعالجة.
- [ ] Security موثقة.

#### STOP-GATE 3

لا تبدأ ARCH-04 قبل موافقة المستخدم على التصميم.

---

### 🅴 ARCH-04 — Migration Roadmap

**الهدف:** تحويل Target Architecture إلى **خطة تنفيذ تدريجية** بدون كسر النظام الحالي.

#### المطلوب

1. **Phases:**

| Phase | المكوّن | الاعتماديات | المخاطر | Rollback |
|---|---|---|---|---|
| M-01 | Router | ARCH-01 components | | |
| M-02 | Validation Layer | Medical rules | | |
| M-03 | Observability | Tracing lib | | |
| M-04 | State / Learning Ledger | DB | | |
| M-05 | Evaluation Pipeline | Metrics | | |
| M-06 | Full Orchestration | All above | | |

2. **Dependencies:**

رسم `Dependency Graph` — من يعتمد على من.

3. **Risk Assessment:**

| المخاطرة | الشدة | الاحتمال | التخفيف |
|---|---|---|---|
| | | | |

4. **Rollback Plan:**

لكل phase: كيف نرجع؟ ما هو الوقت المتوقع؟

5. **Success Criteria:**

لكل phase: كيف نعرف أنه نجح؟

#### المخرج

```
docs/audit/ARCH-04_MIGRATION_ROADMAP.md
```

#### STOP-GATE 4

لا تبدأ ARCH-05 قبل موافقة المستخدم على الـroadmap.

---

### 🅵 ARCH-05 — Tooling Decisions

**الهدف:** تحديد **الأدوات** المناسبة لكل مكوّن — الآن فقط، بعد أن انتهت المعمارية.

#### المطلوب

لكل مكوّن في ARCH-03، اسأل:

- هل نحتاج framework؟ أم يمكن بناؤه بأدوات بسيطة؟
- ما هي الخيارات المتاحة؟
- ما هي Trade-offs كل خيار؟

**جدول القرار:**

| المكوّن | الخيار A | الخيار B | الخيار C | التوصية | السبب |
|---|---|---|---|---|---|
| Router | Custom Python | LangGraph | Temporal | | |
| Validation | Pydantic | Custom | Great Expectations | | |
| Observability | OpenTelemetry | Langfuse | Custom | | |
| State | Redis | PostgreSQL | SQLite | | |
| Evaluation | Custom | Ragas | DeepEval | | |

**قواعد صارمة:**

- **لا تختار framework لأنه "شائع".**
- **لا تختار framework لأنه "حديث".**
- اختر الأبسط الذي يحل المشكلة.
- فكّر في:
  - الترخيص.
  - التكلفة التشغيلية.
  - منحنى التعلم.
  - قابلية الصيانة.
  - Offline capability.
  - التوافق مع privacy (medical).

**أهم قاعدة:**

> إذا كان بإمكانك حل المشكلة بـ50 سطر Python، لا تستخدم framework بـ50 dependency.

#### المخرج

```
docs/audit/ARCH-05_TOOLING_DECISIONS.md
```

#### STOP-GATE 5

لا تبدأ ARCH-06 قبل موافقة المستخدم على الأدوات.

---

### 🅶 ARCH-06 — Detailed Implementation Plan

**الهدف:** خطة تنفيذ تفصيلية لكل phase في ARCH-04.

#### المطلوب

لكل phase، أعدّ:

1. **وصف المكوّن:**
   - Interface.
   - Inputs.
   - Outputs.
   - Errors.

2. **بنية الملفات:**
```
packages/omni_<component>/
├── __init__.py
├── contract/
├── implementation/
├── tests/
└── docs/
```

3. **Testing Strategy:**
   - Unit tests.
   - Integration tests.
   - E2E tests.
   - Failure injection.

4. **Definition of Done لكل phase:**
   - [ ] اختبارات تمر.
   - [ ] توثيق كامل.
   - [ ] Security review.
   - [ ] Rollback مُختبر.
   - [ ] Evidence موثق.

5. **مدة التقدير:**
   - ساعات التطوير.
   - ساعات الاختبار.
   - ساعات المراجعة.

#### المخرج

```
docs/audit/ARCH-06_IMPLEMENTATION_PLAN.md
```

#### STOP-GATE 6

لا تبدأ ARCH-07 قبل موافقة المستخدم على الخطة.

---

### 🅷 ARCH-07 — Final Architecture Package

**الهدف:** تجميع كل ما سبق في حزمة واحدة قابلة للتنفيذ.

#### المطلوب

1. **Executive Summary** (صفحة واحدة).
2. **Architecture Diagram** (نهائي).
3. **قائمة الفجوات** (من ARCH-02) مع الأولويات.
4. **Target Architecture** (من ARCH-03).
5. **Roadmap** (من ARCH-04).
6. **Tooling Decisions** (من ARCH-05).
7. **Implementation Plan** (من ARCH-06).
8. **Open Questions للمستخدم** (≥5).
9. **Next Steps**.

#### المخرج

```
docs/audit/ARCH-07_FINAL_ARCHITECTURE_PACKAGE.md
```

#### Definition of Done

- [ ] كل المراحل السابقة مُجمعة.
- [ ] لا تناقضات بين الأقسام.
- [ ] كل ادعاء يحمل Evidence أو Reference.
- [ ] الأسئلة المفتوحة واضحة.

#### STOP-GATE 7 — FINAL

**بعد ARCH-07:** STOP.

لا تبدأ أي تنفيذ. لا تثبّت أي حزمة. لا تعدّل أي كود.

**انتظر موافقة صريحة من المستخدم.**

---

## 5. القيود الصارمة

### 5.1 في ARCH-00 → ARCH-07

- ❌ لا `pip install`.
- ❌ لا `npm install`.
- ❌ لا `cargo install`.
- ❌ لا تعديل `requirements.txt` أو `pyproject.toml`.
- ❌ لا تعديل أي ملف production.
- ❌ لا commit.
- ❌ لا push.
- ❌ لا استدعاء API خارجي.
- ❌ لا تحميل نموذج.
- ✅ فقط: قراءة، تحليل، كتابة تقارير في `docs/audit/`.

### 5.2 حدود الميزانية

| البند | الحد |
|---|---|
| Tool calls (لكل مرحلة) | 100 |
| وقت التنفيذ (لكل مرحلة) | 30 دقيقة |
| حجم التقرير (لكل مرحلة) | 3000 كلمة |
| عدد الجداول | 10 |

إذا اقتربت من الحد → أنتج تقريراً جزئياً وعلّم الباقي `NOT EXECUTED`.

---

## 6. تنسيق الأدلة (إلزامي)

كل ادعاء مهم يجب أن يحمل:

```
Finding: <وصف>
Evidence: <مسار ملف + رقم سطر> OR <أمر + مخرجه>
Status: PROVEN | PARTIALLY PROVEN | UNPROVEN | CONTRADICTED | BLOCKED | NOT EXECUTED
```

**بدون Evidence = ادعاء مرفوض.**

**أمثلة:**

❌ **مرفوض:**
> "المشروع يحتاج Router."

✅ **مقبول:**
> Finding: المشروع لا يحتوي على مكوّن يوجّه بين محركات OCR.
> Evidence: `find packages/ -name "*router*"` لا يُرجع نتائج. `grep -r "class.*Router" packages/` لا يُرجع نتائج.
> Status: PROVEN (الفجوة موجودة).

---

## 7. STOP GATES — قائمة كاملة

| البوابة | الشرط |
|---|---|
| **STOP-0** | المستودع غير موجود أو Worktree غير نظيف |
| **STOP-1** | جرد ARCH-01 غير مكتمل |
| **STOP-2** | Gap Analysis ناقص |
| **STOP-3** | Target Architecture غير موافق عليه |
| **STOP-4** | Roadmap غير واقعي |
| **STOP-5** | Tooling Decisions غير مبررة |
| **STOP-6** | Implementation Plan ناقص |
| **STOP-7** | الحزمة النهائية غير مكتملة |

عند أي بوابة → **توقف، اكتب السبب، لا تكمل.**

---

## 8. المبادئ الأساسية (تذكير دائم)

1. **Architecture First, Tools Second.**
   - لا تبدأ بأداة. ابدأ بسؤال "لماذا هذا المكوّن؟".
2. **Evidence Over Opinion.**
   - كل ادعاء يحتاج دليلاً.
3. **Simplicity Over Popularity.**
   - أبسط حل يفوز.
4. **Offline-First.**
   - لا اعتماد على cloud أو API خارجي في runtime.
5. **Privacy-Preserving.**
   - بيانات طبية = حساسة.
6. **Failure-Aware.**
   - كل مكوّن له failure mode مُوثّق.
7. **Rollback-Ready.**
   - كل تغيير له خطة رجوع.
8. **Trade-off Explicit.**
   - لا قرار بدون ذكر ما نكسبه وما نخسره.

---

## 9. المخرجات النهائية

| الملف | الوصف |
|---|---|
| `docs/audit/ARCH-01_CURRENT_ARCHITECTURE.md` | الجرد الحالي |
| `docs/audit/ARCH-02_GAP_ANALYSIS.md` | الفجوات |
| `docs/audit/ARCH-03_TARGET_ARCHITECTURE.md` | التصميم المستهدف |
| `docs/audit/ARCH-04_MIGRATION_ROADMAP.md` | خطة الترحيل |
| `docs/audit/ARCH-05_TOOLING_DECISIONS.md` | قرارات الأدوات |
| `docs/audit/ARCH-06_IMPLEMENTATION_PLAN.md` | خطة التنفيذ |
| `docs/audit/ARCH-07_FINAL_ARCHITECTURE_PACKAGE.md` | الحزمة النهائية |

---

## 10. الخطوة الأولى الآن

**ابدأ بـARCH-00 فقط.**

نفّذ الأوامر.
أبلغ بالنتيجة.
انتظر موافقة صريحة قبل ARCH-01.

**لا تتجاوز ARCH-00. لا تفترض شيئاً. لا تعدّل شيئاً.**

---

## 11. صيغة الرد الأولى المتوقعة

```
=== ARCH-00 — PRE-FLIGHT ===

Repository:
Branch:
HEAD:
Worktree:
Remote:
Last commit:

Status: OK | BLOCKED

If OK:
  → Ready for ARCH-01 (requires explicit authorization)

If BLOCKED:
  → Reason: <exact error>
  → Recommended action: <what user should do>

NEXT: <wait for user>
```

---

## 12. المبدأ النهائي

```
الشخص الذي يعرف LangGraph = AI User
الشخص الذي يعرف 10 frameworks = AI Developer
الشخص الذي يصمم Architecture = AI Engineer

هدفنا: AI Engineer.
```

**ابدأ الآن بـARCH-00. ثم توقف.**
