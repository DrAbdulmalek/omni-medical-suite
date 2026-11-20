<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 83 | حُفظ: 2026-10-08 -->

# Docling Forensic Audit (DOC-01)

# MASTER PROMPT — Docling Integration & Forensic Audit
## Omni Medical Suite — Optional Document Structuring Layer

> **تعليمات:** انسخ كل ما هو أسفل هذا السطر وأرسله إلى الوكيل المنفذ (Z.ai) **كما هو**. هذا البرومبت مستقل، لكنه يعتمد على نفس فلسفة Stop-Gates والـEvidence-Driven Engineering التي استخدمناها في XB-01 و JOCR-01 و OCR-CR-01.

---

## 0. الهوية والسياق

أنت الآن تعمل كـ:

- **Senior Document AI Engineer**
- **Python Packaging Auditor**
- **License Compliance Officer**
- **Security Forensic Analyst**
- **Integration Architect**

المستودع المستهدف:

```
/home/z/my-project/repos/omni-medical-suite
```

**المهمة:** تدقيق مشروع **Docling** (IBM) وتحديد ما إذا كان يستحق الدمج في Omni Medical Suite، وأين بالضبط، وكيف. Docling **ليس محرك OCR/HTR**. هو **طبقة تحويل وتوحيد مستندات** (Document Structuring Layer) تشبه Xberg، لكن بتركيز أعمق على **فهم البنية الدلالية** (Layout, Tables, Reading Order).

**النتيجة المستهدفة:** تقرير تدقيق كامل + قرار مبني على أدلة. **لا دمج فعلي في هذه المرحلة.**

---

## 1. القواعد غير القابلة للتفاوض

### 1.1 ممنوع تماماً

- ❌ تعديل `main`.
- ❌ تعديل `packages/omni_ocr/`.
- ❌ استبدال أي محرك OCR قائم (Tesseract, Paddle, EasyOCR, TrOCR, OLMoCR, AHW).
- ❌ إدخال Docling في OCR Runtime.
- ❌ تثبيت `docling` أو أي من تبعياته في هذه المرحلة.
- ❌ تحميل نماذج Docling (~2.9GB)[reference:0].
- ❌ تعديل `requirements.txt` أو `pyproject.toml`.
- ❌ commit أو push في هذه المرحلة (التقرير فقط).
- ❌ استدعاء أي API خارجي.
- ❌ إرسال أي PHI أو صور مرضى إلى أي خدمة خارجية.
- ❌ ادعاء أن Docling "أفضل" أو "أسوأ" من أي أداة أخرى قبل إجراء الاختبارات.

### 1.2 إلزامي

- ✅ Evidence لكل ادعاء (مسار ملف + رقم سطر، أو أمر + مخرجه).
- ✅ التحقق من الترخيص من ملف `LICENSE` الرسمي (ليس README).
- ✅ تحليل دعم العربية والـRTL (نقطة حرجة).
- ✅ تحليل التكامل مع LangChain وMCP.
- ✅ مقارنة موضوعية مع Xberg (المشروع المشابه).
- ✅ تحديد نقاط التكامل مع Omni.
- ✅ أسئلة صريحة للمستخدم عند الغموض.

---

## 2. STOP-GATE MODEL

كل مرحلة تُنتج تقريراً مستقلاً بحالة واحدة من:

```
PROVEN | PARTIALLY PROVEN | UNPROVEN | CONTRADICTED | BLOCKED | NOT EXECUTED
```

كل تقرير يجب أن يحتوي:
- الملفات التي فُحصت (مع مساراتها).
- الأوامر التي نُفّذت.
- المخرجات الخام.
- `git status` + `git diff --stat`.
- المخاطر المتبقية.
- التوصية التالية.

**لا تقل "DONE" إلا إذا كانت Definition of Done محققة.**

---

## 3. المراحل (DOC-01 → DOC-05)

### 🅰️ DOC-01 — Upstream Forensic Audit

**الهدف:** فهم Docling من المصدر الرسمي، دون تعديل المستودع.

#### 3.1 التحقق من المستودع

```bash
# التحقق من الوصول
curl -s https://api.github.com/repos/docling-project/docling | jq '{name, license, stargazers_count, default_branch}'

# أحدث إصدار
git ls-remote --tags https://github.com/docling-project/docling.git | tail -5
```

**سجّل:**

| الحقل | القيمة | المصدر |
|---|---|---|
| Repository | docling-project/docling | GitHub |
| License | MIT | `pyproject.toml`[reference:1] |
| Latest Version | | GitHub Releases |
| Exact Commit SHA | | 40-char SHA |
| Stars | | GitHub |
| Runtime | Python 3.9+ | docs |
| Core Dependencies | docling-parse, docling-core, docling-ibm-models | pyproject |
| Model Size | ~2.9 GB | Xberg benchmark[reference:2] |

#### 3.2 License Audit

| البند | القيمة | ملاحظات |
|---|---|---|
| **Core License** | MIT | ✅ آمن تجاريًا[reference:3] |
| **Dependencies Licenses** | (افحص) | بعض النماذج قد تكون Apache-2.0 أو MIT |
| **Model Licenses** | (افحص) | DocLayNet, TableFormer |
| **Attribution** | مطلوب | MIT يتطلب حفظ حقوق النشر |

#### 3.3 Source Code Forensic Audit

```bash
# استنساخ للتحليل (بدون تثبيت)
git clone --depth 1 https://github.com/docling-project/docling.git /tmp/docling-audit

# فحص الاستدعاءات الخارجية
grep -r "subprocess\|exec\|spawn" /tmp/docling-audit/docling/ --include="*.py" | head -20
grep -r "requests\|http\|fetch\|urllib" /tmp/docling-audit/docling/ --include="*.py" | head -20

# فحص Telemetry
grep -r "telemetry\|analytics\|track" /tmp/docling-audit/docling/ --include="*.py" | head -20

# فحص تحميل النماذج
grep -r "from_pretrained\|hf_hub_download\|snapshot_download" /tmp/docling-audit/docling/ --include="*.py" | head -20
```

**افحص:**

| المجال | النتيجة |
|---|---|
| Command Execution | |
| Network Egress | |
| File Access | |
| Secret Handling | |
| Prompt Injection | |
| Model Download Behavior | |

#### 3.4 دعم العربية — تحليل حرج

**هذا هو أهم قسم في التقرير.**

| القدرة | الحالة | الدليل |
|---|---|---|
| **دعم العربية** | ⚠️ محدود | `lang` parameter غير مفعّل لـRapidOCR[reference:4] |
| **RTL** | ❌ غير مكتمل | "RTL text support is currently not fully implemented"[reference:5] |
| **Mixed Arabic-English** | ❌ فاشل | issue #3462[reference:6] |
| **Tesseract العربي** | ✅ ممكن | يمكن تفعيله يدويًا[reference:7] |
| **EasyOCR العربي** | ✅ ممكن | "Better with non-Latin scripts (Arabic)"[reference:8] |
| **الخط اليدوي** | ❌ غير مدعوم | "Less accurate with handwritten text"[reference:9] |

**الأسئلة الحرجة:**

1. هل يمكن تشغيل Docling على النصوص العربية **بدون RTL**؟
2. ما هو الحل المؤقت لـRTL؟ (python-bidi؟)
3. ما هي دقة Tesseract العربي مقارنة بـEasyOCR؟
4. هل يدعم Docling الخط اليدوي؟ (الجواب: لا)

#### 3.5 المخرج

```
docs/audit/DOCLING_FORENSIC_AUDIT.md
```

#### 3.6 Definition of Done — DOC-01

- [ ] Upstream SHA مسجّل.
- [ ] الترخيص من `pyproject.toml` أو `LICENSE`.
- [ ] Dependency tree مستخرج.
- [ ] Forensic grep نُفّذ.
- [ ] دعم العربية موثق بأدلة.
- [ ] مقارنة مع Xberg موثقة.
- [ ] نقاط التكامل محددة.
- [ ] أسئلة للمستخدم (≥5).

#### 3.7 STOP-GATE DOC-01

**لا تنتقل إلى DOC-02 قبل تقديم التقرير وانتظار موافقة صريحة.**

---

### 🅱️ DOC-02 — Architecture Mapping & Integration Points

**الهدف:** رسم كيف يمكن دمج Docling في Omni دون كسر أي شيء.

#### 3.1 المطلوب

1. **نقاط التكامل المحتملة:**

| المكوّن الحالي | كيف يتكامل Docling | التعديل المطلوب | الأولوية |
|---|---|---|---|
| `packages/omni_extraction/` | طبقة جديدة | `docling_backend.py` | MEDIUM |
| `server.py` | لا | لا | — |
| `segment.py` | لا | لا | — |
| `train_server.py` | لا | لا | — |
| `Docker Compose` | حاوية جديدة | `docling-serve` | LOW |

2. **الـContracts المقترحة:**

```python
# packages/omni_extraction/backends/docling_backend.py
class DoclingBackend:
    def extract(self, source: str) -> ExtractionResult:
        # يستدعي docling CLI أو Python API
        # يحول النتيجة إلى ExtractionResult الموحد
```

3. **المقارنة مع Xberg:**

| الميزة | Docling | Xberg | Omni Need |
|---|---|---|---|
| **الترخيص** | MIT | MIT | ✅ |
| **حجم النموذج** | 2.9 GB | 80 MB (core) | ⚠️ Docling ثقيل |
| **السرعة** | بطيء[reference:10] | سريع | Xberg أفضل |
| **Layout Analysis** | ✅ (ML models) | ✅ | مطلوب |
| **Table Structure** | ✅ (TableFormer) | ✅ | مطلوب |
| **دعم العربية** | ⚠️ محدود | ⚠️ محدود | مطلوب |
| **MCP** | ✅ | ✅ | للتطوير |
| **LangChain** | ✅ | ❌ | للـRAG |
| **صيغ الصوت** | ❌ | ✅ (Whisper) | Xberg أفضل |

**الخلاصة:** Docling وXberg متشابهان. Docling يتفوق في **التكامل مع LangChain**، لكنه أثقل وأبطأ. Xberg أخف وأسرع ويدعم صيغًا أكثر.

#### 3.2 المخرج

```
docs/audit/DOCLING_INTEGRATION_MAPPING.md
```

#### 3.3 STOP-GATE DOC-02

**لا تنتقل إلى DOC-03 قبل موافقة المستخدم على نقاط التكامل.**

---

### 🅲 DOC-03 — Security & Privacy Audit

**الهدف:** التأكد من أن Docling آمن للاستخدام في بيئة طبية.

#### 3.1 المطلوب

1. **Security Checklist:**
   - [ ] لا Command Execution خطير.
   - [ ] لا Network Egress غير مصرح.
   - [ ] تحميل النماذج من Hugging Face (يحتاج إنترنت).
   - [ ] تخزين مؤقت للنماذج (~2.9GB).
   - [ ] لا Telemetry.
   - [ ] لا Secrets مطلوبة.

2. **Privacy Checklist:**
   - [ ] هل يعمل Offline بعد تحميل النماذج؟ (نعم)
   - [ ] هل يرسل أي بيانات للخارج؟ (لا)
   - [ ] هل يخزن PHI؟ (يعتمد على الاستخدام)

3. **المخاطر:**

| المخاطرة | الشدة | الاحتمال | التخفيف |
|---|---|---|---|
| تحميل نماذج كبيرة (2.9GB) | MEDIUM | مؤكد | تحميل مسبق، تحكم في المساحة |
| تعارض مع تبعيات Omni | HIGH | محتمل | بيئة معزولة (venv منفصل) |
| دعم العربية غير كامل | HIGH | مؤكد | استخدام Tesseract/EasyOCR العربي |
| بطء المعالجة | MEDIUM | محتمل | استخدامه فقط للمستندات المطبوعة |

#### 3.2 المخرج

```
docs/audit/DOCLING_SECURITY_PRIVACY.md
```

#### 3.3 STOP-GATE DOC-03

**إذا وُجد خطر غير مقبول: STOP. لا تنتقل إلى DOC-04.**

---

### 🅳 DOC-04 — Pilot Plan (اختياري)

**الهدف:** خطة تجريبية إذا قرر المستخدم المضي قدمًا.

#### 3.1 المطلوب

1. **Pilot A:** تقرير طبي إنجليزي مطبوع (PDF) → Docling → Markdown.
2. **Pilot B:** نفس التقرير عبر Xberg → Markdown.
3. **Pilot C:** مقارنة الجداول والبنية والسرعة.
4. **Pilot D:** محاولة عربية (لتوثيق الفشل).

#### 3.2 المخرج

```
docs/audit/DOCLING_PILOT_PLAN.md
```

#### 3.3 STOP-GATE DOC-04

**لا تنتقل إلى DOC-05 قبل إتمام التجربة وموافقة المستخدم.**

---

### 🅴 DOC-05 — Final Decision

**الهدف:** قرار نهائي مبني على أدلة.

#### 3.1 Decision Matrix

| Capability | Evidence | Omni Need | Risk | Proposed Action |
|---|---|---|---|---|
| Document Conversion (PDF → MD) | | | | |
| Layout Analysis | | | | |
| Table Structure | | | | |
| Arabic Support | | | | |
| RTL Handling | | | | |
| LangChain Integration | | | | |
| MCP Server | | | | |
| Batch Processing | | | | |
| Performance | | | | |
| Model Size | | | | |

**القرارات المسموحة:**
```
ADOPT | ADAPT | WRAP | PILOT | STUDY ONLY | DEFER | REJECT
```

#### 3.2 المخرج

```
docs/audit/DOCLING_ADOPTION_DECISION.md
```

---

## 4. المبادئ الأساسية (تذكير دائم)

1. **Docling ليس محرك OCR.** هو طبقة تحويل مستندات.
2. **دعم العربية محدود.** RTL غير مكتمل. الخط اليدوي غير مدعوم.
3. **Docling ثقيل (2.9GB).** Xberg أخف (80MB).
4. **لا تدمج Docling في OCR Runtime.** فقط كطبقة مساعدة.
5. **Offline-First.** Docling يعمل محليًا بعد تحميل النماذج.
6. **Evidence Over Opinion.** كل ادعاء يحتاج دليلًا.
7. **Simplicity Over Popularity.** Xberg أبسط وأسرع.

---

## 5. الخطوة الأولى الآن

**ابدأ بـDOC-01 فقط.**

نفّذ التحقق من المستودع.
أنتج تقرير `DOCLING_FORENSIC_AUDIT.md`.
**ثم STOP. انتظر موافقة صريحة قبل DOC-02.**

**لا تثبّت Docling. لا تحمّل النماذج. لا تعدّل أي كود.**

---

## 6. صيغة الرد الأولى المتوقعة

```
=== DOCLING — DOC-01 ===

UPSTREAM:
VERSION:
COMMIT:
LICENSE: MIT ✅
ACCESS: OK | BLOCKED

SOURCE AUDIT: <finding>
DEPENDENCY AUDIT: <finding>
SECURITY: <finding>
ARABIC SUPPORT: <finding with evidence>
RTL SUPPORT: <finding with evidence>
HANDWRITING: <finding with evidence>
MODEL SIZE: ~2.9 GB

INTEGRATION POINTS:
  - packages/omni_extraction/backends/docling_backend.py
  - Docker Compose (docling-serve)

COMPARISON WITH XBERG:
  - <findings>

USEFUL COMPONENTS:
NON-USEFUL COMPONENTS:

PROVEN:
PARTIALLY PROVEN:
UNPROVEN:
CONTRADICTED:
BLOCKED:
NOT EXECUTED:

FILES CREATED: docs/audit/DOCLING_FORENSIC_AUDIT.md
COMMITS: NONE (DOC-01 only)
HEAD SHA: <current>
WORKTREE: <status>

NEXT: WAIT FOR EXPLICIT AUTHORIZATION FOR DOC-02
```

---

## 7. المبدأ النهائي

```
Docling هو "ضيف" — يُدرس أولاً، يُقيَّم ثانيًا، يُدمج ثالثًا — وقد يُرفض.

دعم العربية محدود.
RTL غير مكتمل.
الخط اليدوي غير مدعوم.
الحجم 2.9GB.

إذا لم يثبت أن Docling يقدم قيمة تفوق Xberg،
فالقرار الصحيح هو REJECT.

لا دمج بدون evidence.
لا evidence بدون أوامر خام.
```

**ابدأ الآن بـDOC-01. ثم توقف.**
