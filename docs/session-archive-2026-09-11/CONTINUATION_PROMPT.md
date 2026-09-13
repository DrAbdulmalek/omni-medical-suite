# CONTINUATION PROMPT — For Next Z.ai Session

Copy and paste the text below the line into the new session.

---

## PERSISTENT WORKSPACE RULE

لا تعتمد على الملفات المحلية أو الذاكرة المحلية للجلسة. قبل بدء أي عمل:

1. استخدم GitHub API للتحقق من حالة PRs المفتوحة على `DrAbdulmalek/omni-medical-suite`.
2. اعتبر آخر commit مؤكد على GitHub هو مصدر الحقيقة.
3. لا تقل إن ملفًا أو commit أو branch موجود إلا بعد التحقق الفعلي منه.
4. Agent memory is NEVER evidence.

---

## CONTEXT — Session 2026-09-11 Summary

Repository: DrAbdulmalek/omni-medical-suite
origin/main: 39640a6dbba741eaf13e078dad64719e147ea79b

### 6 Open PRs (verified via GitHub API):

| PR | Branch | HEAD | CI | Status |
|---|---|---|---|---|
| #123 | fix/p0-phi-egress-and-ocr-observability | 0e4294a | 24 green, 1 skip | 🟢 MERGE CANDIDATE |
| #122 | fix/security-production-dependencies-task02d | e5dd783 | 26 green, 1 skip | 🟢 MERGE CANDIDATE |
| #121 | feat/medical-terminology-enrichment | 518d853 | 21/21 green | 🟢 OPEN |
| #120 | feat/p0-public-api-integrations | ee68739 | varies | 🟡 SUPERSEDED |
| #119 | fix/security-pickle-remediation-task02b-phase1 | 6a15213 | 25/26 green | 🟡 1 expected failure |
| #118 | fix/security-remove-os-system | 8455dac | green | 🟢 OPEN |

### What Was Done:
1. TASK-01 (PR #118): os.system → subprocess.run in 5 files
2. TASK-02A: Forensic pickle audit (report only)
3. TASK-02B (PR #119): pickle → JSON+base64 in G1/G2/G3
4. TASK-02C (in PR #119): pip-audit scope fix (requirements files, not installed env)
5. TASK-02D-A: Forensic dependency audit (58 vulns in gradio/pillow/transformers)
6. WHO ICD-11 (PR #121): Offline enrichment script for Arabic+English medical terminology
7. Public API audit (superseded — WHO ICD-11 chosen over openFDA/RxNorm/PubMed)

### What Was NOT Done:
- No PRs merged — all OPEN
- No direct main push
- P0 (PHI egress + OCR observability) done in parallel session → PR #123

### Key Decisions:
- External APIs = offline enrichment only (NOT runtime dependencies)
- Translation pipeline works without internet (local KB authoritative)
- WHO ICD-11 chosen over openFDA/RxNorm/PubMed (Arabic-first + medical authority)
- `f69e31a` was a FABRICATION — never existed
- Scanner env separated from audit target (pip-audit uses `-r` requirements files)

### Security Alert:
- GitHub token `[REDACTED-TOKEN-2]` may be exposed in workspace repo Git history
- **REVOKE THIS TOKEN** before starting new session
- Create a new token for the new session

### Branch Protection on main:
- 8 required status checks (OCR Core Gate, Unit Tests, Code Quality, etc.)
- 1 required PR review (approval needed before merge)

### First Steps for New Session:
```bash
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
git fetch --all
# Read full session archive:
cat docs/session-archive-2026-09-11/SESSION_SUMMARY.md
# Verify PR states via GitHub API
```

---

## ANTI-FABRICATION RULES

- Never claim a commit exists without `git rev-parse` or `git ls-remote` verification
- Never claim a PR exists without GitHub API verification
- Never claim "pushed" without verifying remote SHA matches local
- Never claim "tests passed" without actual test output
- Never reference a SHA that cannot be resolved
- Agent memory is NEVER evidence

## SOURCE OF TRUTH HIERARCHY

1. Actual GitHub repository state
2. Verified Git commit
3. Verified CI result
4. Session archive document
5. Local filesystem (disposable)
6. Agent memory (never evidence)
