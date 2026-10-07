<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 3 | حُفظ: 2026-10-08 -->

# MASTER PROMPT V2 — Arabic Handwriting Self-Learning (AHW-01)

# مراجعة MASTER PROMPT V2

## الحكم السريع

البرومبت **جاهز للإرسال بعد إصلاح 5 نقاط حرجة** (موضّحة أدناه). البنية المعمارية، فلسفة Offline-First، فصل Vyce، وقواعد Medical Safety — كلها ممتازة ومتماسكة. لكن هناك ثغرات تنفيذية قد تجعل Z.ai:
- يحاول تنفيذ كل شيء دفعة واحدة.
- يتوه في تكرار قسم Vyce.
- يفترض وجود المستودع محليًا دون التحقق.

---

## 1. نقاط القوة (احتفظ بها كما هي)

| المحور | التقييم |
|---|---|
| فصل Vyce بين Dev-time وRuntime | ممتاز — يحل لبسًا كان في V1 |
| Offline-First كقاعدة معمارية | ممتاز ويحمي الخصوصية الطبية |
| منع الـSilent Medical Correction | ضروري وموضوع بوضوح |
| Learning Ledger + Provenance | ممتاز |
| منع Data Leakage بين Splits | ممتاز |
| Test Integrity Rules | ممتاز |
| STOP-GATE صريح في نهاية AHW-01 | موجود لكنه يحتاج تقوية |
| Evidence Format (PROVEN/UNPROVEN/...) | ممتاز |

---

## 2. الثغرات الحرجة (يجب إصلاحها قبل الإرسال)

### 2.1 تكرار قسم Vyce

القسم الرئيسي يحتوي **Sections 25–32** عن Vyce، ثم في النهاية قسم كامل **"VYCE AI — CORRECTED ROLE IN THE PROJECT"** يعيد نفس الأفكار. هذا سيربك Z.ai وقد يجعله يعتقد أن هناك نسختين من التعليمات.

**الإصلاح المقترح:** احذف Sections 25–32 من الجزء الرئيسي، واترك فقط قسم Vyce النهائي. أو ضع في البداية:

```
NOTE: The section "VYCE AI — CORRECTED ROLE" at the end
SUPERSEDES any earlier mention of Vyce AI in this document.
Ignore Sections 25–32 if they conflict.
```

### 2.2 غياب فحص أولي إلزامي للمستودع

البرومبت يفترض أن `/home/z/my-project/repos/omni-medical-suite` موجود. إذا لم يكن موجودًا، Z.ai قد يبدأ التخمين أو يحاول الاستنساخ من GitHub.

**أضف في القسم 3 (PHASE A) — قبل أي شيء:**

```
BEFORE ANY OTHER ACTION:

1. Verify the repository exists:
   test -d /home/z/my-project/repos/omni-medical-suite

2. Verify it is a git repository:
   git -C /home/z/my-project/repos/omni-medical-suite rev-parse --is-inside-work-tree

3. Verify remote matches "DrAbdulmalek/omni-medical-suite":
   git -C /home/z/my-project/repos/omni-medical-suite remote -v

4. Verify current branch and that main is clean:
   git -C /home/z/my-project/repos/omni-medical-suite branch --show-current
   git -C /home/z/my-project/repos/omni-medical-suite status

IF ANY CHECK FAILS:
   STOP immediately.
   Report exact error.
   Do NOT clone, do NOT guess, do NOT create directories.
```

### 2.3 لا يوجد حد لحجم تقرير الـAudit

Z.ai قد يُنتج تقريرًا من 5000 سطر. هذا يُهدر الوقت ويصعّب المراجعة.

**أضف:**

```
AUDIT REPORT SIZE CONSTRAINT:
- Maximum 4000 words.
- Maximum 15 tables.
- Use bullet lists, not paragraphs, for findings.
- If more space is needed, create APPENDIX_<topic>.md files
  and reference them, but keep the main report self-contained
  for the Decision section (Section 48.R).
```

### 2.4 لا توجد حماية ضد الأوامر المدمّرة

البرومبت يمنع تعديل `main` لكنه لا يمنع أوامر مثل:
- `git clean -fdx`
- `rm -rf`
- `pip install --upgrade` globally
- `pip install` بدون `--user` أو venv
- `git reset --hard`
- `git push --force`

**أضف قسمًا جديدًا بعنوان `FORBIDDEN COMMANDS`:**

```
The following commands are FORBIDDEN during AHW-01 and all
implementation phases unless explicitly authorized in writing:

- git clean -fdx / -fdX / -x
- git reset --hard
- git push --force / --force-with-lease
- git branch -D main
- rm -rf (outside a dedicated tmp/ created by the agent)
- pip install without virtual environment activation
- pip install --upgrade on any pre-existing dependency
- conda install / conda update
- apt install / apt remove
- sudo (any form)
- docker system prune
- Any command that modifies ~/.cache, ~/.config, ~/.local
- Any command that downloads >500MB without prior approval

If a task seems to require one of these, STOP and ask.
```

### 2.5 غياب تعريف واضح لـ"Acceptable Audit"

القسم 48 يحدد **ماذا** يجب أن يحتوي التقرير، لكن لا يحدد **كيف نعرف أنه جيد بما يكفي** للموافقة على AHW-02.

**أضف معايير قبول صريحة:**

```
AHW-01 ACCEPTANCE CRITERIA (all must be met):

1. Real command outputs are included (not described, not paraphrased).
2. Every architecture claim has a file path + line number or command.
3. Every candidate model has an evidence-based license field.
4. Every "supports Arabic" claim is backed by either:
   - official documentation URL, OR
   - explicit "UNPROVEN — no evidence found"
5. The Decision table (Section 48.R) marks every component.
6. At least 3 open questions are listed for the user.
7. The report explicitly states whether a Git branch was created
   (or not) and why.

If any of the above is missing, the report is INCOMPLETE and
AHW-02 must NOT start.
```

---

## 3. تحسينات مهمة (مستحسنة)

### 3.1 اذكر GitHub CI/CD بشكل صريح في AHW-01

القسم 0 يقول أنك "GitHub CI/CD Engineer"، لكن Section 4 (Map the Real Architecture) لا يذكر مجلد `.github/workflows/`.

**أضف إلى Section 4:**

```
Also inspect:
- .github/workflows/ (CI/CD pipelines)
- .pre-commit-config.yaml
- Makefile / justfile / task runner configs
- Dockerfile / docker-compose.yml
- Any existing deployment scripts

For each, report:
- What it does
- Whether it would be affected by adding AHW packages
- Whether it needs a new workflow for training/evaluation
```

### 3.2 Rollback Procedure كـDeliverable إلزامي

القسم 22 (Promotion Gate) و44 (Model Registry) يذكران "rollback" لكن لا يوجد تعريف إجرائي.

**أضف:**

```
The AHW-01 audit MUST propose a concrete rollback procedure
covering at least:

- How to revert to the previous model version
- How to revert to the previous dataset version
- How to invalidate a training run
- How to invalidate a promotion decision
- How to mark a sample as CONTAMINATED if leakage is discovered
- Where rollback logs are stored

This must be documented before AHW-02.
```

### 3.3 حالة BLOCKED يجب أن تكون صريحة

القسم 2 يذكر حالات الحكم (PROVEN/PARTIALLY/UNPROVEN/CONTRADICTED)، لكن لا يوجد حالة "BLOCKED".

**أضف:**

```
A fifth status is required:

BLOCKED — a required capability, dependency, resource, or
permission is unavailable, and progress cannot continue without
user intervention.

Examples:
- Repository path does not exist
- GPU required but not available
- Required model license is incompatible
- Network access needed for a critical audit step
- Missing API credentials for a required test

If AHW-01 ends with any BLOCKED item that affects the Decision
table, the report must be marked INCOMPLETE and AHW-02 must not
start.
```

### 3.4 حد أقصى لعدد Tool Calls في AHW-01

لمنع Z.ai من استهلاك ميزانية كبيرة في مرحلة الـAudit.

**أضف:**

```
AHW-01 TOOL BUDGET:
- Maximum 150 tool calls total.
- Maximum 30 minutes of wall-clock time.
- If approaching the budget, produce a partial report and
  mark remaining items as DEFERRED with reasons.

This constraint applies only to AHW-01.
```

### 3.5 ذكر مسار حفظ التقرير

**أضف:**

```
Save the audit report at:
docs/audit/ARABIC_HANDWRITING_SELF_LEARNING_AUDIT.md

If docs/audit/ does not exist, create it.
Do NOT save it in the repository root.
Do NOT save it in packages/.
```

### 3.6 قسم "قبل أن تبدأ" في رأس البرومبت

بدلًا من أن يقرأ Z.ai 700 سطر ثم يبدأ، اجعل أول 30 سطرًا ملخصًا تنفيذيًا.

**اقترح هذا الرأس:**

```
# MASTER PROMPT V2 — EXECUTIVE CONTRACT

You are about to read a long specification.
Before you act, internalize these 5 rules:

1. You will execute ONLY AHW-01 (Architecture Audit).
2. You will NOT modify any production code.
3. You will NOT install, download, or call anything external.
4. You will produce ONE file:
   docs/audit/ARABIC_HANDWRITING_SELF_LEARNING_AUDIT.md
5. You will then STOP and ask for authorization.

Read the rest of this document as constraints on those 5 rules,
not as a task list to complete in one turn.

---
[then the full prompt]
```

---

## 4. تفاصيل صغيرة لكن مهمة

| النقطة | الإصلاح |
|---|---|
| القسم 47 (Documentation) لا يذكر `CHANGELOG.md` أو `docs/adr/` | أضف: "If the repo uses ADRs, add an ADR for the AHW architecture decision in AHW-02, not AHW-01." |
| القسم 22 (Promotion Gate) يستخدم "safety threshold" بدون تعريف | أضف: "Thresholds must be derived from the AHW-08 baseline, not set arbitrarily." |
| القسم 12 (Correction States) لم يحدد من يملك سلطة الانتقال بين الحالات | أضف: "State transitions and their actors must be documented in AHW-02's schema." |
| القسم 40 (Test Integrity) لا يذكر CI | أضف: "Existing CI must remain green. Any new failures must be reported, not silenced." |
| لا يوجد ذكر لـ`.gitignore` | أضف في AHW-01: "Audit `.gitignore` for: model weights, datasets, API keys, training artifacts, user uploads. Report gaps." |
| لا يوجد ذكر لـ`LICENSE` | أضف في AHW-01: "Report the repository's current license and any license implications of adding ML models or datasets." |

---

## 5. مصفوفة القرار النهائي

| البند | الحالة |
|---|---|
| البنية المعمارية العامة | ✅ جاهز |
| فلسفة Offline-First | ✅ جاهز |
| فصل Vyce | ⚠️ يحتاج حذف Sections 25–32 |
| STOP-GATE | ⚠️ يحتاج إضافة BLOCKED + Acceptance Criteria |
| الحماية ضد الأوامر المدمّرة | ❌ مفقودة |
| التحقق من وجود المستودع | ❌ مفقود |
| حدود تقرير الـAudit | ❌ مفقودة |
| Tool Budget | ❌ مفقود |
| مسار حفظ التقرير | ❌ مفقود |
| Rollback كـDeliverable | ⚠️ مذكور بدون تعريف |
| CI/CD في الـAudit | ⚠️ مذكور في Role فقط |

---

## 6. التوصية النهائية

**لا ترسل البرومبت كما هو.**

نفّذ الإصلاحات الخمسة الحرجة (2.1 → 2.5)، ثم أرسل. هذه الإصلاحات لا تغيّر فلسفة البرومبت — فقط تمنع Z.ai من:

1. التخبّط بسبب تكرار Vyce.
2. البدء دون التحقق من المستودع.
3. إنتاج تقرير ضخم غير قابل للمراجعة.
4. تنفيذ أوامر مدمّرة.
5. المضي في AHW-02 بناءً على Audit ناقص.

بعد الإصلاح، البرومبت V2 سيكون **من أقوى البرومبتات المعمارية** التي يمكن أن تُعطى لـZ.ai في هذا النطاق.

---

## 7. الخطوة التالية المقترحة

إذا أردت، أستطيع:

**الخيار A:** إعادة كتابة البرومبت V2.1 كاملًا مع كل الإصلاحات مدمجة، جاهز للنسخ واللصق.

**الخيار B:** إرسال **Patch فقط** — قائمة الإضافات بالضبط (Sections جديدة + تعديلات محددة) لتطبيقها يدويًا على V2.

**الخيار C:** انتظر حتى يرسل لك Z.ai تقرير `ARABIC_HANDWRITING_SELF_LEARNING_AUDIT.md`، ثم أساعدك في تدقيقه قبل السماح بـAHW-02.

أخبرني أي مسار تريد.
