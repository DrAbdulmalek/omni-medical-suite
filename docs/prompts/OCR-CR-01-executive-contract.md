<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 9 | حُفظ: 2026-10-08 -->

# OCR-CR-01 — Executive Contract (OpenCodeReview)

# مراجعة MASTER PROMPT — Alibaba OpenCodeReview Integration

## الحكم السريع

البرومبت **من أقوى ما رأيته في هذا النطاق** — فلسفة "Zero Blind Adoption"، Persistence-First، فصل Dev-tooling عن OCR runtime، وIndependent Review Levels كلها ممتازة. لكن هناك **8 ثغرات حرجة** يجب إصلاحها قبل الإرسال، وإلا Z.ai قد:

- يتوه لأنه لا يوجد حد أقصى للنطاق.
- يتعامل مع غياب المستودع كأنه "خطأ مؤقت".
- يخلط بين OpenCodeReview وOpenCode.
- لا يعرف كيف يجري الـPilot بدون LLM backend.
- يعتبر تقرير OCR-CR-01 مكتملاً وهو ناقص.

---

## 1. نقاط القوة (احتفظ بها حرفيًا)

| المحور | التقييم |
|---|---|
| الفصل الحاسم بين Dev-tooling وOCR runtime | ⭐⭐⭐ ممتاز |
| قاعدة REUSE > ADAPT > WRAP > EXTEND > MERGE > BUILD NEW | ممتاز |
| Independent Review Levels (0–4) | مبتكر ومهم |
| Persistence-First + Handoff Bundle | ضروري بعد فقدان العمل سابقًا |
| Evidence Labels (PROVEN/UNPROVEN/BLOCKED/...) | ممتاز |
| Stop Gates (7 بوابات) | قوية |
| "SOURCE CODE > TESTS > RUNTIME EVIDENCE > ... > MODEL OPINION" | القاعدة الذهبية |
| لا تنسخ code لمجرد أنه جميل | مبدأ صحيح |
| Recory Simulation كـDeliverable | نادر وممتاز |

---

## 2. الثغرات الحرجة (يجب إصلاحها)

### 2.1 غياب التحقق الأولي من وجود الـUpstream

القسم 4 يقول "تحقق من official GitHub repository" لكن لا يوجد فحص صريح + Stop Gate إن لم يوجد.

**أضف في بداية القسم 4:**

```
BEFORE ANY FURTHER AUDIT:

1. Verify the upstream repository is reachable:
   - URL: https://github.com/alibaba/open-code-review
   - Verify last commit SHA
   - Verify latest release tag
   - Verify LICENSE file presence

2. Verify the npm package exists (if referenced):
   npm view @alibaba-group/open-code-review

3. If ANY of the above fails:
   - Report exact error
   - Mark OCR-CR-01 as BLOCKED
   - STOP

Do NOT substitute an alternative repository.
Do NOT use a fork without explicit user approval.
Do NOT assume the repository name from social media.
```

### 2.2 لا يوجد تمييز بين "OpenCodeReview" و"OpenCode"

القسم 4 يذكر "OpenCode integration" كواجهة تكامل — لكن **OpenCode** هو مشروع مختلف عن **OpenCodeReview**. هذا سيُربك Z.ai.

**أضف:**

```
NAMING CLARIFICATION — MANDATORY

The following are DIFFERENT projects:

- Alibaba OpenCodeReview (alibaba/open-code-review) — TARGET
- OpenCode (opencode.ai / sst/opencode) — NOT the target
- Claude Code — NOT the target
- Codex — NOT the target
- Cursor — NOT the target

When the upstream README mentions "OpenCode integration",
verify from the SOURCE CODE which OpenCode is meant.

Report the exact integration surface with file path + line.
```

### 2.3 لا يوجد حد أقصى للـTool Budget

البرومبت قد يستمر لأيام. لا يوجد Budget.

**أضف:**

```
OCR-CR-01 TOOL BUDGET:
- Maximum 200 tool calls.
- Maximum 45 minutes wall-clock.
- If approaching budget: produce partial report
  and mark remaining items as NOT EXECUTED.
```

### 2.4 غياب تحديد مستوى الاستقلال المطلوب للـAudit نفسه

القسم 18 يعرّف Levels 0–4 لكنه **لا يحدد الحد الأدنى المقبول** لاعتماد OCR-CR-01.

**أضف:**

```
MINIMUM INDEPENDENCE REQUIREMENT:

OCR-CR-01 (Audit)      → Level 2 minimum (different model)
OCR-CR-03 (Security)   → Level 3 minimum (different provider + deterministic rules)
OCR-CR-05 (Pilot)      → Level 3 minimum
OCR-CR-07 (CI Pilot)   → Level 4 required

A report that does not disclose its independence level
is INCOMPLETE.
```

### 2.5 مسار الـHandoff Bundle لم يُتحقق منه

القسم 28 يقول احفظ في `download/OMNI-EXECUTION/handovers/` لكن لا يتحقق من وجود هذا المسار أو ملاءمته.

**أضف في القسم 28:**

```
BEFORE creating the first handoff bundle:

1. Verify download/OMNI-EXECUTION/ exists.
   find /home/z -maxdepth 4 -type d -name "OMNI-EXECUTION"

2. If it does not exist:
   - Report absence
   - ASK user for preferred path
   - Do NOT create directories outside the repository
     without explicit approval

3. Document the actual path in ENVIRONMENT.txt
```

### 2.6 لا يوجد تعريف لـ"DoD" (Definition of Done) لـOCR-CR-01

التقرير النهائي محدد، لكن **معايير القبول** غير موجودة.

**أضف:**

```
OCR-CR-01 DEFINITION OF DONE:

All must be TRUE:

[ ] Upstream SHA recorded (40 chars)
[ ] License verified from LICENSE file (not README)
[ ] Dependency tree extracted (npm ls --all or equivalent)
[ ] Source-code forensic grep executed
    (subprocess, exec, spawn, fetch, telemetry)
[ ] GitHub Action workflow(s) fetched and analyzed
[ ] Data-flow diagram produced
[ ] Omni baseline SHA recorded
[ ] Omni baseline pytest executed (pass/fail counts)
[ ] Integration mapping table produced
[ ] Component extraction table produced
[ ] Decision Matrix produced (Section 31)
[ ] Handoff bundle created
[ ] Handoff bundle SHA256 verified
[ ] Recovery simulation attempted (even partially)
[ ] Independence Level disclosed
[ ] Open Questions listed (≥5)

If any is FALSE:
  OCR-CR-01 = INCOMPLETE
  OCR-CR-02 = NOT AUTHORIZED
```

### 2.7 لا يوجد مسار للـPilot بدون LLM Provider

OpenCodeReview يحتاج LLM backend. البرومبت يقول "لا API key في prompt" لكنه لا يوضح كيف يجري الـPilot.

**أضف قسمًا جديدًا:**

```
PILOT PROVIDER PROTOCOL

The audit (OCR-CR-01) does NOT require an LLM.
The pilot (OCR-CR-05) DOES require an LLM backend.

If user wants to proceed to OCR-CR-05:

1. ASK user which provider to use:
   [ ] Local (Ollama / llama.cpp / vLLM)
   [ ] OpenAI-compatible endpoint (URL only, key via env)
   [ ] Anthropic
   [ ] Vyce (development-time only)
   [ ] None → OCR-CR-05 = BLOCKED

2. Credentials MUST be provided via:
   export OCR_LLM_TOKEN="..."
   (never in prompt, never in commit, never in logs)

3. Before pilot, verify:
   - .env is in .gitignore
   - No token appears in git history
   - Provider endpoint is HTTPS or localhost

4. If user cannot provide a provider:
   - OCR-CR-05 = BLOCKED
   - OCR-CR-06 and later = NOT AUTHORIZED
   - Produce final report with this status
```

### 2.8 Stop Gate 7 (Reassess Architecture) غامضة

**أضف:**

```
STOP GATE 7 — REASSESS ARCHITECTURE means:

1. STOP all implementation.
2. Produce a new document:
   docs/audit/OCR_RUNTIME_MODIFICATION_REQUEST.md
   containing:
   - Exact runtime change requested
   - Why it is unavoidable
   - Impact on existing OCR engines
   - Impact on AHW, OLMoCR, Phase-1
   - Rollback plan
   - Alternative designs that avoid the change
3. WAIT for explicit user approval.
4. Do NOT proceed on assumption.
```

---

## 3. تحسينات مهمة

### 3.1 قرار موقع الأدوات يجب أن يكون حاسمًا

القسم 0 يعطي خيارين (`tools/open-code-review/` أو `tools/code-review/`) ويطلب من Z.ai "اختر". لكن هذا القرار معماري، ويجب أن يُبنى على بنية المستودع.

**عدّل:**

```
Tool location decision MUST be based on:

1. Does tools/ exist in the repo?
2. If yes, what naming convention is used?
3. Is there an existing dev-tools folder?
4. Is there a monorepo layout (packages/, apps/, tools/)?

Decision rule:
- If tools/ exists with a naming convention → FOLLOW IT
- If tools/ does not exist → DEFER decision to user
- Do NOT create tools/ without evidence it fits the repo

Report the decision with evidence (existing dir listing).
```

### 3.2 .gitignore كـDeliverable إلزامي

إذا سيثبّت npm package محليًا، يجب تحديث `.gitignore`.

**أضف في Section 30 (Suggested Files):**

```
MANDATORY .gitignore AUDIT:

Before any npm install inside the repo:

1. Verify node_modules/ is in .gitignore
2. Verify package-lock.json handling
3. Verify any tools/*/node_modules is ignored
4. If not, PROPOSE the addition (do not commit without approval)
5. Report in docs/audit/OPENCODEREVIEW_GITIGNORE.md (short)
```

### 3.3 Cross-reference مع Audits السابقة

هذا البرومبت منفصل عن Jina-OCR-v1 وAHW. يجب الربط.

**أضف في القسم 0:**

```
RELATIONSHIP TO OTHER AUDITS:

- AHW-01 (Arabic Handwriting) — separate, independent
- JOCR-01 (Jina-OCR-v1) — separate, independent
- OCR-CR-01 (this) — SEPARATE, but:
  - Shares the same persistence protocol
  - Shares the same handoff bundle structure
  - Shares the same evidence labeling

Do NOT merge reports.
Do NOT let one audit's findings leak into another's scope.
```

### 3.4 Independent Review Levels — مثال تطبيقي

القسم 18 نظري. أضف مثالاً:

```
EXAMPLE for OCR-CR-01:

Level 0: Z.ai reviews its own audit
Level 1: Z.ai re-runs with fresh context
Level 2: A different model (e.g., Claude via Vyce) reviews Z.ai's findings
Level 3: Level 2 + deterministic security scanners
         (semgrep, gitleaks, npm audit)
Level 4: Level 3 + independent human review

For OCR-CR-01, MINIMUM = Level 2.
Attach the review evidence as:
docs/audit/OPENCODEREVIEW_INDEPENDENT_REVIEW.md
```

### 3.5 نمط الاستدعاء يجب أن يكون صريحًا

القسم 6 يمنع global install لكن لا يوضح البديل.

**أضف:**

```
ALLOWED INSTALLATION PATTERNS (choose one, document it):

Pattern A — Isolated node_modules in tools/
  cd tools/open-code-review
  npm init -y
  npm install @alibaba-group/open-code-review
  → Uses local node_modules
  → Reproducible via package-lock.json

Pattern B — npx without install
  npx @alibaba-group/open-code-review@<exact-version> --help
  → Does not persist
  → Acceptable only for reconnaissance

Pattern C — Docker / Podman
  → Highest isolation
  → Requires Dockerfile or upstream image

Pattern D — Separate clone outside Omni
  /home/z/tools-sandbox/open-code-review/
  → Zero impact on Omni repo

FORBIDDEN:
- npm install -g
- npm link without rollback plan
- Any install that modifies global node_modules
```

### 3.6 تعريف "Uncontrolled Secret Egress"

Stop Gate 3 يستخدم هذا المصطلح دون تعريف.

**أضف:**

```
UNCONTROLLED SECRET/PHI EGRESS means:

- The tool reads .env, .git/config, SSH keys, or env vars
  containing secrets, AND
- Sends them to a network endpoint, AND
- Without explicit per-call user consent, AND
- Without clear logging.

If the tool only reads env vars for its OWN configuration:
  → CONTROLLED, acceptable
If it sends repo contents to a network:
  → REQUIRES explicit user opt-in
If it sends repo contents WITHOUT logging:
  → UNCONTROLLED = STOP
```

---

## 4. تفاصيل صغيرة لكن مهمة

| النقطة | الإصلاح |
|---|---|
| Section 22 (Security Gate) لا يذكر `gitleaks` أو `semgrep` أو `npm audit` بالاسم | أضفها كأدوات مقترحة |
| Section 28 (Handoff Bundle) لا يذكر حجم الـDiff | أضف: "If DIFF.patch >5MB, store stat only + full diff path" |
| Section 29 (Recovery Simulation) يحتاج وقتًا | أضف: "May be partial in OCR-CR-01, mandatory by OCR-CR-08" |
| Section 31 (Decision Matrix) لا يحدد شكل الجدول بدقة | أضف مثال Markdown concrete |
| Section 34 (Initial Scope) لا يذكر DoD | أضف: "OCR-CR-01 is COMPLETE only when Section 2.6 DoD is fully satisfied" |
| Section 35 (Final Report) طويل | أضف: "Max 3000 words for the main report, rest in appendices" |
| Section 12 (Study Architecture) لا يذكر ADR | أضف: "If the repo uses ADRs, note where the OCR-CR decision will be recorded" |

---

## 5. مصفوفة القرار النهائي

| البند | الحالة |
|---|---|
| فلسفة Zero Blind Adoption | ✅ جاهز |
| فصل Dev-tooling عن Runtime | ✅ جاهز |
| Persistence Protocol | ✅ جاهز |
| Independent Review Levels | ⚠️ يحتاج مثالًا تطبيقيًا |
| Stop Gates (7) | ⚠️ Gate 7 غامضة |
| Upstream Verification | ❌ مفقود |
| OpenCode/OpenCodeReview Disambiguation | ❌ مفقود |
| Tool Budget | ❌ مفقود |
| Minimum Independence Level | ❌ مفقود |
| Handoff Path Verification | ❌ مفقود |
| Definition of Done | ❌ مفقود |
| Pilot Provider Protocol | ❌ مفقود |
| .gitignore as Deliverable | ❌ مفقود |
| Allowed Installation Patterns | ⚠️ ضمني فقط |
| Cross-reference with AHW/JOCR | ❌ مفقود |

---

## 6. التوصية النهائية

**نفّذ الإصلاحات الثمانية الحرجة (2.1 → 2.8) قبل الإرسال.**

هذه الإصلاحات لا تغيّر فلسفة البرومبت — بل تمنع:

1. التخبّط بسبب عدم وجود المستودع.
2. الالتباس بين OpenCode وOpenCodeReview.
3. تقرير ضخم غير قابل للمراجعة.
4. المضي في Pilot بدون LLM provider واضح.
5. اعتبار Audit ناقصًا مكتملاً.
6. تنفيذ تغييرات runtime تحت ضغط الوقت.

بعد الإصلاح، هذا البرومبت سيكون **الأقوى في سلسلة البرومبتات الثلاثة (AHW، JOCR، OCR-CR)**، وسيعطيك إطارًا يمكن إعادة استخدامه لأي أداة خارجية تريد تقييمها مستقبلاً.

---

## 7. الخطوة التالية — اختر مسارًا

**الخيار A:** إعادة كتابة البرومبت كاملًا مع كل الإصلاحات (V2 جاهز للنسخ).

**الخيار B:** Patch فقط — قائمة الإضافات بالضبط (Sections جديدة + تعديلات محددة).

**الخيار C:** كتابة `OCR_CR-01_STARTUP_CHECKLIST.md` مختصر (صفحة واحدة) يُرفق مع البرومبت كـPre-Flight Check يقرأه Z.ai قبل أي خطوة.

**الخيار D:** انتظر حتى يرد Z.ai بتقرير `OPENCODEREVIEW_FORENSIC_AUDIT.md`، ثم أساعدك في تدقيقه قبل السماح بـOCR-CR-02.

أخبرني أي مسار تريد.
