<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 27 | حُفظ: 2026-10-08 -->

# M-00 — Multi-Project Integration Package

# MASTER PROMPT — Multi-Project Integration & Analysis Phase
## AI-SDLC + It's a Plan + Agentic Bug Hunter + Jina-OCR-v1
### Omni Medical Suite — Evidence-Driven, Zero Blind Adoption

> **تعليمات:** انسخ كل ما هو أسفل هذا السطر وأرسله إلى Z.ai كما هو. البرومبت مستقل عن البرومبتات السابقة، لكنه يعتمد على نفس الفلسفة (Evidence-Driven، Stop-Gates، لا تعديل لـmain).

---

## 0. الهوية والسياق

أنت الآن تعمل كـ:

- **Senior Systems Architect**
- **AI Governance Engineer**
- **Security & Compliance Auditor**
- **License Compliance Officer**
- **Repository Forensic Analyst**
- **MLOps / DevSecOps Engineer**

المستودع المستهدف:

```
/home/z/my-project/repos/omni-medical-suite
```

**المهمة:** دراسة أربعة مشاريع خارجية وتحديد ما يمكن استخلاصه أو دمجه داخل Omni Medical Suite، دون نسخ أعمى، ودون إدخالها في Runtime الخاص بـ OCR/HTR إلا بعد إثبات القيمة.

**المشاريع الأربعة:**

| # | المشروع | الرابط | الترخيص | الغرض الأساسي |
|---|---|---|---|---|
| 1 | **AI-SDLC Framework** | github.com/ai-sdlc-framework/ai-sdlc | Apache 2.0 | Declarative governance for AI agents in SDLC |
| 2 | **It's a Plan** | github.com/croffasia/itsaplan | AGPL-3.0 | Self-hosted project management with AI agents |
| 3 | **Agentic Bug Hunter** | github.com/Awarexone/Agentic-Bug-Hunter | MIT | AI-powered bug bounty hunting toolkit |
| 4 | **Jina-OCR-v1** | huggingface.co/jinaai/jina-ocr-v1 | CC BY-NC 4.0 | Document parsing model (DeepSeek-OCR based) |

---

## 1. القرار المعماري الأساسي

**هذه المشاريع الأربعة ليست متساوية في العلاقة بـOmni:**

```
┌─────────────────────────────────────────────────────────┐
│                   Omni Medical Suite                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │              OCR Runtime (Core)                  │   │
│  │  Tesseract | Paddle | EasyOCR | TrOCR | OLMoCR  │   │
│  │  AHW (Arabic Handwriting) — قيد التطوير         │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │          AI Governance Layer (NEW)                │   │
│  │  AI-SDLC Framework — Declarative Governance      │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │          Project Management Layer (NEW)          │   │
│  │  It's a Plan — Issue Tracker + AI Agents         │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │          Security Layer (NEW)                    │   │
│  │  Agentic Bug Hunter — Security Testing           │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │          OCR Engine Candidate (NEW)              │   │
│  │  Jina-OCR-v1 — Document Parsing                  │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 1.1 الفصل الحاسم

| المشروع | العلاقة بـOmni | مكان الدمج |
|---|---|---|
| **AI-SDLC** | Governance / Orchestration | Developer Tooling / CI |
| **It's a Plan** | Project Management | Developer Tooling (اختياري) |
| **Agentic Bug Hunter** | Security Testing | Developer Tooling / CI |
| **Jina-OCR-v1** | OCR Engine | Extraction Layer (اختياري) |

**القاعدة:** لا يدخل أي منها إلى `packages/omni_ocr/` (Runtime).

---

## 2. القواعد غير القابلة للتفاوض

### 2.1 ممنوع تماماً

- ❌ تعديل `main`.
- ❌ merge بدون تفويض.
- ❌ حذف أي محرك أو مكوّن قائم.
- ❌ إدخال أي من المشاريع الأربعة في OCR Runtime.
- ❌ تثبيت أي حزمة (`npm`, `pip`, `cargo`, `apt`).
- ❌ تحميل أي نموذج (Jina-OCR-v1 = ~6GB).
- ❌ استدعاء أي API خارجي.
- ❌ وضع أي credential داخل Git.
- ❌ إرسال PHI أو صور مرضى إلى أي خدمة خارجية.
- ❌ ادعاء أن أي مشروع "مفيد" أو "سيء" قبل إجراء الاختبارات.
- ❌ اعتبار benchmarks خارجية دليلاً على الأداء داخل Omni.

### 2.2 إلزامي

- ✅ Evidence لكل ادعاء (مسار ملف + رقم سطر، أو أمر + مخرجه).
- ✅ التحقق من الترخيص من ملف LICENSE (ليس README).
- ✅ تحليل الأمان (subprocess, egress, secrets).
- ✅ تحليل Data Flow.
- ✅ تحديد Integration Points.
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
- المخرجات الخام.
- `git status` + `git diff --stat`.
- المخاطر المتبقية.
- التوصية التالية.

**لا تقل "DONE" إلا إذا كانت Definition of Done محققة.**

---

## 4. المراحل

### 🅰️ Phase M-00 — Pre-Flight Verification

**الأوامر:**

```bash
test -d /home/z/my-project/repos/omni-medical-suite
git -C /home/z/my-project/repos/omni-medical-suite rev-parse --is-inside-work-tree
git -C /home/z/my-project/repos/omni-medical-suite remote -v
git -C /home/z/my-project/repos/omni-medical-suite branch --show-current
git -C /home/z/my-project/repos/omni-medical-suite status --short
```

**إذا فشل أي فحص:** STOP. أبلغ المستخدم.

---

### 🅱️ Phase M-01 — Upstream Discovery لكل مشروع

**لكل مشروع من الأربعة، أنشئ بطاقة تقنية:**

#### M-01.1 — AI-SDLC Framework

| الحقل | القيمة | المصدر |
|---|---|---|
| Repository | github.com/ai-sdlc-framework/ai-sdlc | GitHub |
| License | Apache 2.0 | LICENSE file |
| Latest Release | | `git ls-remote --tags` |
| Exact Commit SHA | | 40-char SHA |
| Runtime | Node.js ≥ 20, pnpm ≥ 9 | Docs |
| Core Concepts | Pipeline, AgentRole, QualityGate, AutonomyPolicy, AdapterBinding | Docs |
| Autonomy Levels | Intern (0), Junior (1), Senior (2), Principal (3) | Docs |
| Enforcement Levels | advisory, soft-mandatory, hard-mandatory | Docs |
| SDK Languages | TypeScript, Python, Go | Docs |
| CI/CD | GitHub Actions (ci.yml) | Repo |
| Audit Logging | Tamper-evident | README |
| DSSE Attestations | ✅ | README |
| Cross-harness Review | Claude × Codex × … | README |

**الأسئلة الحرجة:**
- هل يحتاج AI-SDLC إلى تعديل كود Omni؟
- هل يمكن دمجه كـCI layer فقط؟
- ما هو الأثر على security؟
- هل يتوافق مع فلسفة Offline-First؟

#### M-01.2 — It's a Plan

| الحقل | القيمة | المصدر |
|---|---|---|
| Repository | github.com/croffasia/itsaplan | GitHub |
| License | AGPL-3.0 | LICENSE file |
| ⚠️ تحذير AGPL | Copyleft قوي — يؤثر على التوزيع | Legal |
| Latest Release | | GitHub Releases |
| Exact Commit SHA | | 40-char SHA |
| Runtime | Docker, PostgreSQL, Bun | README |
| Features | Kanban, Table, Timeline, Calendar | README |
| AI Agents | Role, Permissions, @Mentions, Scheduled Tasks | README |
| Integrations | REST API, OpenAPI, MCP, Webhooks | README |
| Coding CLI | Claude Code, Cursor, Codex | README |
| Self-hosted | ✅ | README |

**⚠️ تحذير AGPL-3.0:**
- إذا استخدمت It's a Plan **كأداة داخلية فقط** (self-hosted، لا توزيع)، AGPL لا يؤثر على كودك.
- إذا **وزّعت** Omni مع It's a Plan، قد يُطلب منك نشر كود Omni تحت AGPL.
- **قرار مطلوب:** هل ستستخدمه داخلياً أم ستوزعه؟

#### M-01.3 — Agentic Bug Hunter

| الحقل | القيمة | المصدر |
|---|---|---|
| Repository | github.com/Awarexone/Agentic-Bug-Hunter | GitHub |
| License | MIT | GitHub |
| Latest Release | | GitHub |
| Exact Commit SHA | | 40-char SHA |
| Runtime | Python | GitHub |
| Features | Recon, Hunt, Validate, Report | README |
| AI Providers | Ollama (free, local), OpenAI, Anthropic, etc. | README |
| Standalone Mode | ✅ (no subscription) | README |
| Claude Code Plugin | ✅ | README |
| Sessions | Persistent across runs | README |
| 7-Question Gate | ✅ | README |

**الأسئلة الحرجة:**
- هل نحتاج Bug Hunter لمشروع طبي؟
- هل يمكن استخدامه لاختبار أمان Omni نفسه؟
- ما هي حدود الاستخدام الأخلاقي والقانوني؟
- هل يعمل Offline (Ollama)؟

#### M-01.4 — Jina-OCR-v1

| الحقل | القيمة | المصدر |
|---|---|---|
| Model | jinaai/jina-ocr-v1 | HuggingFace |
| License | CC BY-NC 4.0 | HF Card |
| ⚠️ تحذير | Non-Commercial — لا يجوز للاستخدام التجاري | Legal |
| Paper | arXiv:2609.03181 | arXiv |
| Architecture | DeepSeek-OCR (3B MoE, 570M active) | Paper |
| FastMTP | K=3 speculative decoding | Paper |
| OmniDocBench | 91.14 | Paper |
| olmOCR-Bench | 83.4 | Paper |
| Throughput | 2.57 pages/sec | Paper |
| GPU | NVIDIA L4 (low-budget) | Paper |
| Trust Remote Code | Required | HF Card |
| Backends | Transformers, vLLM, SGLang | HF Card |

**الأسئلة الحرجة:**
- هل مشروعنا تجاري؟ (إذا نعم → BLOCKED بسبب CC BY-NC)
- هل لدينا GPU بـVRAM ≥8GB؟
- هل نقبل `trust_remote_code=True`؟

---

### 🅲 Phase M-02 — Forensic Source Audit

لكل مشروع، افحص الكود الفعلي:

**ابحث عن:**
```
subprocess | exec | spawn | shell | child_process | os.system
Popen | requests | http | https | fetch | curl | wget
telemetry | analytics | MCP | filesystem writes
credential access | environment variables | git commands
docker | network sockets
```

**افحص:**
- A. Command execution
- B. Network egress
- C. File access
- D. Secret exposure
- E. Prompt injection
- F. Malicious input handling

---

### 🅳 Phase M-03 — License Audit

لكل مشروع:

| المشروع | الترخيص | الاستخدام التجاري | التوزيع | Copyleft | المخاطر |
|---|---|---|---|---|---|
| AI-SDLC | Apache 2.0 | ✅ | ✅ | ❌ | منخفض |
| It's a Plan | AGPL-3.0 | ⚠️ | ⚠️ | ✅ | متوسط-عالي |
| Agentic Bug Hunter | MIT | ✅ | ✅ | ❌ | منخفض |
| Jina-OCR-v1 | CC BY-NC 4.0 | ❌ | ⚠️ | ❌ | **CRITICAL** |

**قرار مطلوب:** هل المشروع تجاري أم بحثي/شخصي؟

---

### 🅴 Phase M-04 — Omni Mapping

لكل مشروع، حدد:

1. **Integration Points:**
   - أين سيُدمج؟
   - هل يحتاج تعديل كود قائم؟

2. **Component Extraction:**

| Component | Exists in Omni? | Upstream Quality | Reuse? | Adapt? | Wrap? | Reason |
|---|---|---|---|---|---|---|
| AI-SDLC Governance | ❌ | | | | | |
| Quality Gates | ❌ | | | | | |
| Autonomy Policies | ❌ | | | | | |
| DSSE Attestations | ❌ | | | | | |
| It's a Plan Tracker | ❌ | | | | | |
| It's a Plan MCP | ❌ | | | | | |
| Bug Hunter Recon | ❌ | | | | | |
| Bug Hunter Validate | ❌ | | | | | |
| Jina-OCR Parsing | ❌ | | | | | |

3. **REUSE > ADAPT > WRAP > EXTEND > MERGE > BUILD NEW**

---

### 🅵 Phase M-05 — Security & Privacy Gate

**قبل أي integration:**

```bash
# Credential scan
grep -r "api_key\|password\|token\|secret" --include="*.py" --include="*.ts" --include="*.js"

# Secret scan
grep -r "sk-\|ghp_\|AKIA" .

# Egress inspection
grep -r "requests\|fetch\|http" --include="*.py" --include="*.ts"

# Subprocess inspection
grep -r "subprocess\|exec\|spawn" --include="*.py" --include="*.ts"
```

**يجب ألا ينتقل أي مشروع إلى CI production إذا بقي خطر غير مفهوم في:**
- credentials
- PHI
- untrusted input
- command execution
- network egress

---

### 🅶 Phase M-06 — Pilot (اختياري)

**فقط بعد اجتياز M-03 و M-05:**

- **Pilot A (AI-SDLC):** إنشاء pipeline تجريبي لمهمة صغيرة.
- **Pilot B (It's a Plan):** تشغيل Docker محلي + اختبار API.
- **Pilot C (Bug Hunter):** تشغيل `bughunter recon` على target وهمي (localhost).
- **Pilot D (Jina-OCR):** اختبار النموذج على عينة واحدة (إذا وافق المستخدم على الموارد).

---

### 🅷 Phase M-07 — Decision Matrix

| Capability | Evidence | Omni Need | Risk | Proposed Action |
|---|---|---|---|---|
| AI-SDLC Governance | | | | |
| Quality Gates | | | | |
| Autonomy Policies | | | | |
| DSSE Attestations | | | | |
| Cross-harness Review | | | | |
| It's a Plan Tracker | | | | |
| It's a Plan MCP | | | | |
| Bug Hunter Recon | | | | |
| Bug Hunter Validate | | | | |
| Jina-OCR Parsing | | | | |
| Jina-OCR Tables | | | | |

**القرارات المسموحة:**
```
ADOPT | ADAPT | WRAP | PILOT | STUDY ONLY | DEFER | REJECT
```

---

### 🅸 Phase M-08 — Final Package

أنشئ:

```
docs/audit/MULTI_PROJECT_INTEGRATION_PACKAGE.md
```

يحتوي:
1. Executive Summary
2. لكل مشروع: بطاقة تقنية + Forensic Audit + License + Risks + Decision
3. Component Extraction Table
4. Decision Matrix
5. Open Questions (≥5)
6. Next Steps

---

## 5. القيود الصارمة

### 5.1 في كل المراحل

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
| Tool calls (لكل مرحلة) | 150 |
| وقت التنفيذ (لكل مرحلة) | 30 دقيقة |
| حجم التقرير (لكل مرحلة) | 4000 كلمة |
| عدد الجداول | 15 |

---

## 6. تنسيق الأدلة (إلزامي)

كل ادعاء مهم يجب أن يحمل:

```
Finding: <وصف>
Evidence: <مسار ملف + رقم سطر> OR <أمر + مخرجه>
Status: PROVEN | PARTIALLY PROVEN | UNPROVEN | CONTRADICTED | BLOCKED | NOT EXECUTED
```

**بدون Evidence = ادعاء مرفوض.**

---

## 7. STOP GATES — قائمة كاملة

| البوابة | الشرط |
|---|---|
| **M-STOP-0** | المستودع غير موجود أو Worktree غير نظيف |
| **M-STOP-1** | Upstream غير قابل للوصول |
| **M-STOP-2** | License Conflict (خاصة AGPL + CC BY-NC) |
| **M-STOP-3** | Uncontrolled Secret/PHI Egress |
| **M-STOP-4** | GitHub Action يعرض untrusted PR لـsecrets |
| **M-STOP-5** | baseline يفشل بشكل غير متوقع |
| **M-STOP-6** | لا يمكن حفظ commit/handoff |
| **M-STOP-7** | Integration يحتاج تعديل OCR runtime |

---

## 8. المبادئ الأساسية

1. **Evidence Over Opinion.**
2. **Simplicity Over Popularity.**
3. **Offline-First.**
4. **Privacy-Preserving.**
5. **Failure-Aware.**
6. **Rollback-Ready.**
7. **Trade-off Explicit.**
8. **License Compliance First.**

**المعيار النهائي:**
```
SOURCE CODE > TESTS > RUNTIME EVIDENCE >
SECURITY EVIDENCE > LICENSE EVIDENCE >
GIT HISTORY > DOCUMENTATION > MODEL OPINION
```

---

## 9. المخرجات النهائية

| الملف | الوصف |
|---|---|
| `docs/audit/AI_SDLC_AUDIT.md` | تدقيق AI-SDLC |
| `docs/audit/ITSAPLAN_AUDIT.md` | تدقيق It's a Plan |
| `docs/audit/BUGHUNTER_AUDIT.md` | تدقيق Bug Hunter |
| `docs/audit/JINA_OCR_V1_AUDIT.md` | تدقيق Jina-OCR-v1 |
| `docs/audit/MULTI_PROJECT_INTEGRATION_PACKAGE.md` | الحزمة النهائية |

---

## 10. الخطوة الأولى الآن

**ابدأ بـM-00 فقط.**

نفّذ الأوامر.
أبلغ بالنتيجة.
انتظر موافقة صريحة قبل M-01.

**لا تتجاوز M-00. لا تفترض شيئاً. لا تعدّل شيئاً.**

---

## 11. صيغة الرد الأولى المتوقعة

```
=== M-00 — PRE-FLIGHT ===

Repository:
Branch:
HEAD:
Worktree:
Remote:
Last commit:

Status: OK | BLOCKED

If OK:
  → Ready for M-01 (requires explicit authorization)

If BLOCKED:
  → Reason: <exact error>
  → Recommended action: <what user should do>

NEXT: <wait for user>
```

---

## 12. المبدأ النهائي

```
هذه المشاريع الأربعة ليست "إضافات لمشروعك".
هي "مرشحون" — بعضهم قد يُقبل، بعضهم قد يُرفض.

الترخيص ليس تفصيلاً — هو قيد معماري من الدرجة الأولى.
AGPL-3.0 قد يلوّث مشروعك.
CC BY-NC 4.0 يمنع الاستخدام التجاري.

لا دمج بدون evidence.
لا evidence بدون أوامر خام.
```

**ابدأ الآن بـM-00. ثم توقف.**
