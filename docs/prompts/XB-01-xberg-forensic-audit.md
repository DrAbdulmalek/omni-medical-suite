<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 15 | حُفظ: 2026-10-08 -->

# Xberg Forensic Audit (XB-01) + Architecture + Benchmark Plan

سأقوم بإعداد الوثائق الثلاث المطلوبة. سأبدأ بمراجعة المصادر التي جمعتها حول Xberg، ثم أُعدّ كل وثيقة على حدة.

---

# 📄 الوثيقة الأولى: XB-01_AUDIT_PROMPT.md

```markdown
# MASTER PROMPT — Xberg Forensic Audit (XB-01)
## Document Intelligence Engine — Selective Adoption for Omni Medical Suite

أنت الآن تعمل كـ Senior Document AI Architect + Rust Systems Auditor + License Compliance Engineer + Security Forensic Analyst على مشروع:

DrAbdulmalek/omni-medical-suite

الهدف ليس تثبيت Xberg، بل:

تدقيق Xberg كطبقة Document Intelligence محتملة، ثم تحديد ما يمكن استخلاصه أو دمجه داخل Omni Medical Suite، دون نسخ أعمى، ودون إدخاله في Runtime الخاص بـ OCR/HTR إلا بعد إثبات القيمة.

---

## 0 — القرار المعماري الأساسي

Xberg هو:

Document Intelligence / Extraction Layer

وليس:

OCR Engine متخصص
وليس بديلاً عن AHW
وليس بديلاً عن Jina-OCR-v1
وليس بديلاً عن OLMoCR

المكان المقترح للدراسة:

tools/xberg/
أو:
packages/omni_extraction/

اختر الحل الأقل تدخلاً والأكثر قابلية للـ rollback، وسجّل سبب الاختيار.

---

## 1 — قواعد غير قابلة للتفاوض

ممنوع:
- تعديل main مباشرة
- merge بدون تفويض
- حذف أي OCR engine قائم
- تعديل packages/omni_ocr/ بهدف إدخال Xberg
- استبدال OLMoCR أو AHW
- تغيير OCRResult
- تغيير router
- تشغيل auto-fix على كود المشروع
- إرسال PHI أو صور مرضى أو أسرار إلى أي خدمة خارجية
- وضع أي credential داخل Git
- ادعاء أن Xberg "أفضل" قبل إجراء الاختبارات
- اعتبار benchmarks Xberg الخارجية دليلاً على الأداء داخل Omni

قاعدة أساسية:

AUDIT FIRST → ISOLATE → INSTALL/SNAPSHOT → SECURITY REVIEW → ARCHITECTURE MAPPING → PILOT → CUSTOM RULES → TEST → DECISION → ADOPTION

---

## 2 — Persistence First

UNPUSHED WORK IS NOT PERSISTED WORK.

يجب تطبيق التسلسل التالي:

TEST → ARTIFACTS → COMMIT → VERIFY COMMIT → PUSH → VERIFY REMOTE → RECORD SHA → CLEAN WORKTREE

إذا كانت credentials غير متاحة:
PUSH = BLOCKED
ولا تعتبر العمل محفوظاً على GitHub.

أنشئ handoff bundle محلياً قبل إنهاء أي مرحلة.

---

## 3 — الهدف الحقيقي

أريد منك دراسة Xberg بهدف استخراج ما قد يفيد:

Omni Medical Suite

خصوصاً:
- unified output layer
- 100+ document format support
- layout & table reconstruction
- audio/video transcription
- code intelligence (371 languages)
- MCP server
- REST API
- OCR fallback chains
- confidence scoring
- language auto-detection
- chunking for RAG
- embeddings & search
- structured extraction via LLMs

---

## 4 — Upstream Discovery

ابدأ بدون تعديل Omni.

تحقق من:
- official GitHub repository: https://github.com/xberg-io/xberg
- latest release
- exact commit SHA
- license (MIT)
- README
- architecture (Rust core + 15 bindings)
- CLI
- REST API
- MCP server
- OCR backends
- layout models
- table models
- VLM support
- dependency tree
- release notes

سجّل:
UPSTREAM_REPOSITORY=https://github.com/xberg-io/xberg
UPSTREAM_TAG=
UPSTREAM_COMMIT=
LICENSE=MIT
RELEASE_DATE=
LANGUAGES=
RUNTIME=
DEPENDENCIES=
INTEGRATION_SURFACES=

---

## 5 — Pin Exact Version

اختر release/commit محدداً، وسجله.

مثلاً:
Xberg version = <exact>
commit = <40-char SHA>

إذا تغير الإصدار أثناء التنفيذ، لا تستخدم النسخة الجديدة بصمت.

---

## 6 — لا تبدأ بـ global installation

قبل التثبيت تحقق من:
- package provenance
- install scripts
- postinstall behavior
- binaries
- shell execution
- network calls
- telemetry
- update mechanisms
- MCP
- subprocesses
- filesystem access

أنماط التثبيت المسموحة:

Pattern A — Isolated node_modules in tools/xberg/
Pattern B — pip install in dedicated venv
Pattern C — Docker/Podman
Pattern D — Separate clone outside Omni

الممنوع:
- npm install -g
- pip install globally
- أي install يعدل global environment

---

## 7 — Forensic Source Audit

افحص الكود الفعلي لـ Xberg.

ابحث تحديداً عن:
subprocess exec spawn shell child_process os.system Popen requests http https fetch curl wget telemetry analytics MCP filesystem writes credential access environment variables git commands docker network sockets

وافحص:
A. Command execution
B. Network egress
C. File access
D. Secret exposure
E. Prompt injection
F. Malicious document handling (zip bombs, malformed PDFs)

---

## 8 — GitHub Action Security Audit

إذا كان المشروع يوفر GitHub Action:
افحص workflow فعلياً.

خصوصاً:
pull_request pull_request_target permissions secrets checkout untrusted code workflow commands comment permissions write permissions token exposure

صنّف النتيجة:
PROVEN / PARTIALLY PROVEN / UNPROVEN / CONTRADICTED / BLOCKED

---

## 9 — License Audit

تحقق من license الرسمي: MIT

افحص:
LICENSE
NOTICE
package manifests
lock files
direct dependencies
important transitive dependencies

الهدف:
Commercial compatibility
Attribution requirements
Redistribution requirements
Modification requirements
Copyleft contamination
Model/license restrictions

Xberg نفسه MIT، لكن لا تفترض أن جميع dependencies لها نفس الترخيص.

---

## 10 — Omni Repository Forensics

افحص DrAbdulmalek/omni-medical-suite:

git status
git branch --show-current
git rev-parse HEAD
git remote -v
git log -n 10 --oneline

ثم افحص:
packages/omni_ocr/
packages/core/
tests/
.github/
scripts/
docs/
tools/

وابحث عن:
existing extraction
existing document processing
lint
static analysis
security scan
pytest
CI gates
PR automation
quality gates

---

## 11 — Current Omni Baseline

سجّل exact baseline:

BASE_SHA =
BRANCH =
WORKTREE =
PYTHON =
PYTEST =
OS =
GIT =

ثم:
pytest ...

إذا كان baseline يحتوي failures:
سجّلها كـ KNOWN BASELINE FAILURE
ولا تنسبها إلى Xberg.

---

## 12 — Study Architecture

أنشئ تقريراً:

docs/audit/XBERG_FORENSIC_AUDIT.md

يحتوي:
1. Executive Summary
2. Exact Upstream Version
3. License
4. Architecture (Rust core, bindings, crates)
5. CLI
6. REST API
7. MCP Server
8. OCR Backends
9. Layout Models
10. Table Models
11. VLM Support
12. Audio/Video Transcription
13. Code Intelligence
14. Embeddings & Search
15. Structured Extraction
16. Security
17. Data Flow
18. Secret Handling
19. Prompt Injection
20. Dependency Risks
21. Useful Components
22. Components NOT suitable for Omni
23. Proposed Adaptations
24. Risks
25. Decision

---

## 13 — Component-by-Component Extraction

لا تقل: Xberg is useful.

بدلاً من ذلك أنشئ جدولاً:

| Component | Exists in Omni? | Upstream quality | Reuse? | Adapt? | Wrap? | Copy? | Reason |
|---|---|---|---|---|---|---|---|
| Unified output | | | | | | | |
| Format detection | | | | | | | |
| OCR backends | | | | | | | |
| Layout models | | | | | | | |
| Table models | | | | | | | |
| Audio transcription | | | | | | | |
| Code intelligence | | | | | | | |
| MCP server | | | | | | | |
| REST API | | | | | | | |
| Chunking | | | | | | | |
| Embeddings | | | | | | | |
| Structured extraction | | | | | | | |

---

## 14 — REUSE > ADAPT > WRAP > EXTEND > MERGE > BUILD NEW

طبّق هذه القاعدة حرفياً.

لكل capability:
- REUSE: إذا أمكن استخدام Xberg كما هو خارج runtime
- ADAPT: إذا كان تعديل صغير كافياً
- WRAP: إذا كان الأفضل وضع adapter حوله
- EXTEND: إذا كان النظام مفيداً لكن يحتاج extension
- MERGE: فقط إذا كانت هناك قيمة واضحة وlicense/security يسمحان
- BUILD NEW: آخر خيار فقط

---

## 15 — What should NOT enter Omni OCR

ضع قائمة explicit بما لا ينبغي إدخاله إلى packages/omni_ocr/:

- Xberg core library
- Xberg CLI
- Xberg REST API server
- Xberg MCP server
- Xberg embeddings
- Xberg structured extraction
- أي شيء يضيف dependency إلى OCR runtime

هذه تبقى developer tooling أو extraction layer منفصلة.

---

## 16 — Proposed Omni Integration

إذا أثبت التدقيق أن هناك قيمة:
اقترح architecture مثل:

Input (PDF/Image/DOCX/...)
        ↓
Xberg Extraction Layer (optional)
        ↓
Unified Output (text + tables + metadata)
        ↓
Omni OCR Pipeline
        ↓
OCRResult (existing contract)

ولا تجعل Xberg جزءاً من OCR runtime.

---

## 17 — Omni-Specific Review Rules

صمم draft rules، لكن لا تفرضها على CI قبل الموافقة.

القواعد المقترحة يجب أن تغطي:
- OCR Contract compatibility
- Dataset Safety
- Medical Safety
- Privacy
- Security
- Engineering

---

## 18 — Independent Review Principle

أنشئ درجات استقلال:

LEVEL 0 Same agent self-review
LEVEL 1 Separate review invocation
LEVEL 2 Different model
LEVEL 3 Different provider/model + deterministic rules
LEVEL 4 Deterministic + independent AI + tests/security

الحد الأدنى لـ XB-01: LEVEL 2

---

## 19 — Pilot

بعد اكتمال audit فقط:

أنشئ branch منفصل:
feat/xberg-pilot

Pilot A: مستند PDF بسيط (نص مطبوع)
Pilot B: صورة ممسوحة ضوئياً (عربية)
Pilot C: خط يد عربي (من dataset AHW)
Pilot D: ملف DOCX مع جداول
Pilot E: ملف صوتي (اختبار Whisper)

---

## 20 — Compare Review Results

لكل pilot سجّل:
Files processed
Formats handled
Text extracted
Tables extracted
Layout preserved
Arabic support
RTL preserved
Mixed Arabic/English
Medical terminology accuracy
Processing time
RAM/VRAM peak
Errors

---

## 21 — False Positive / False Negative Study

خذ عينة صغيرة من مستندات معروفة.

لكل finding:
TRUE POSITIVE
FALSE POSITIVE
DUPLICATE
NOT ACTIONABLE
MISSED
UNPROVEN

ووثّق الدليل.

---

## 22 — Security Gate

قبل أي real integration:

نفّذ:
credential scan
secret scan
dependency audit
network/egress inspection
filesystem access review
command execution review
GitHub Action review
MCP review
prompt-injection review

يجب ألا ينتقل النظام إلى CI production إذا بقي خطر غير مفهوم في:
credentials PHI untrusted input command execution network egress

---

## 23 — Offline-First

Omni Medical Suite: Offline-first.

لذلك:
- لا external LLM افتراضياً
- لا automatic upload
- لا PHI cloud
- لا API key داخل repo
- لا telemetry غير مفهومة
- external provider يجب أن يكون explicit opt-in
- cloud execution يجب أن يكون auditable
- يجب أن توجد طريقة لتعطيله

---

## 24 — Evidence Labels

كل claim مهم يجب أن يحمل:

PROVEN
PARTIALLY PROVEN
UNPROVEN
CONTRADICTED
BLOCKED
NOT EXECUTED

مثال:
Arabic support = PROVEN (via PaddleOCR script family)

إذا لم تُختبر فعلياً.

---

## 25 — No Benchmark Marketing Claims

إذا ذكر upstream:
benchmark accuracy F1 token reduction senior-engineer evaluation superiority over another model

سجّلها كـ:
UPSTREAM CLAIM

ولا تحولها إلى:
PROVEN FOR OMNI

إلا إذا اختبرتها محلياً بنفسك.

---

## 26 — Rollback

أي integration يجب أن يكون قابلاً للرجوع.

قبل كل تغيير:
BASE SHA

وبعد كل commit:
git rev-parse HEAD
git rev-parse HEAD^
git diff HEAD^ HEAD --stat
git status --short

إذا تم push:
git ls-remote origin <branch>

يجب أن يطابق SHA.

احتفظ بتقرير rollback.

---

## 27 — Handoff Bundle After EVERY Commit

بعد كل commit أنشئ:
download/OMNI-EXECUTION/handovers/<commit-sha>/

يحتوي على:
COMMIT_SHA.txt PARENT_SHA.txt BRANCH.txt STATUS.txt CHANGED_FILES.txt DIFF.patch DIFF_STAT.txt NEW_FILES_MANIFEST.txt TEST_RESULTS.txt SECURITY_RESULTS.txt ARTIFACT_MANIFEST.sha256 ENVIRONMENT.txt RECONSTRUCTION.md REMOTE_STATE.txt TIMESTAMP.txt

ثم احسب SHA256 للـ artifacts.

---

## 28 — Recovery Simulation

قبل إعلان integration complete:

اختبر persistence protocol نفسه.

السيناريو:
clone → create temporary commit → create handoff bundle → record SHA → delete local repo → fresh clone → reconstruct from handoff → verify exact commit SHA

إذا فشل:
PERSISTENCE = BLOCKED

---

## 29 — Suggested Files

docs/audit/XBERG_FORENSIC_AUDIT.md
docs/audit/XBERG_SECURITY.md
docs/audit/XBERG_LICENSE.md
docs/audit/XBERG_DATAFLOW.md
docs/audit/XBERG_OMNI_MAPPING.md
docs/audit/XBERG_PILOT.md
docs/audit/XBERG_ADOPTION_DECISION.md

لا تنشئ هذه الملفات إذا لم تكن ضرورية؛ تجنب documentation bloat.

---

## 30 — Decision Matrix

في النهاية أعطني decision-by-capability:

| Capability | Evidence | Omni Need | Risk | Proposed Action |
|---|---|---|---|---|
| Unified output | | | | |
| Format detection | | | | |
| OCR backends | | | | |
| Layout models | | | | |
| Table models | | | | |
| Audio transcription | | | | |
| Code intelligence | | | | |
| MCP server | | | | |
| REST API | | | | |
| Chunking | | | | |
| Embeddings | | | | |
| Structured extraction | | | | |

القرارات المسموحة:
ADOPT / ADAPT / WRAP / PILOT / STUDY ONLY / DEFER / REJECT

---

## 31 — STOP GATES

STOP GATE 1: إذا لم تستطع الوصول إلى upstream → STOP
STOP GATE 2: إذا وجدت license conflict → STOP ADOPTION
STOP GATE 3: إذا وجدت uncontrolled secret/PHI egress → STOP
STOP GATE 4: إذا كان GitHub Action يعرض untrusted PR إلى secrets → STOP CI ADOPTION
STOP GATE 5: إذا فشل baseline unexpectedly → STOP
STOP GATE 6: إذا لم يمكن حفظ commit/handoff → PERSISTENCE = BLOCKED
STOP GATE 7: إذا احتاجت adoption إلى تعديل OCR runtime → STOP AND REASSESS

---

## 32 — Phase Boundaries

PHASE XB-01 Upstream Forensic Audit
PHASE XB-02 Isolated Installation / Snapshot
PHASE XB-03 Security + License + Dataflow Audit
PHASE XB-04 Omni Mapping
PHASE XB-05 Controlled Pilot
PHASE XB-06 Omni-specific Rules
PHASE XB-07 CI Pilot
PHASE XB-08 Adoption Decision

لا تبدأ XB-05 قبل إغلاق XB-03.
لا تبدأ XB-07 قبل نجاح XB-05.
ولا تعتبر XB-08 مكتملة قبل persistence + rollback verification.

---

## 33 — Initial Scope

ابدأ الآن فقط بـ XB-01.

ولا تعدّل production.

أنجز:
upstream discovery
exact version pin
architecture audit
source-code forensic audit
license audit
dependency audit
GitHub Action security audit
data-flow map
Omni integration mapping
preliminary extraction list

ثم:
COMMIT → HANDOFF BUNDLE → VERIFY

ولا تعمل merge.

---

## 34 — Required Final Report

=== XBERG — XB-01 ===
UPSTREAM:
VERSION:
COMMIT:
LICENSE:
ACCESS:
SOURCE AUDIT:
DEPENDENCY AUDIT:
SECURITY:
DATAFLOW:
GITHUB ACTION:
MCP:
PLUGIN SYSTEM:
OMNI COMPATIBILITY:
RUNTIME INTRUSION:
PHI RISK:
SECRET RISK:
PROMPT INJECTION RISK:
USEFUL COMPONENTS:
NON-USEFUL COMPONENTS:
CANDIDATE ADAPTATIONS:
STATUS:

ثم:
PROVEN:
PARTIALLY PROVEN:
UNPROVEN:
CONTRADICTED:
BLOCKED:
NOT EXECUTED:

ثم:
FILES CREATED:
COMMITS:
HEAD SHA:
REMOTE SHA:
WORKTREE:
PERSISTENCE:
ROLLBACK STATUS:

---

## 35 — Final Rule

لا أريد منك أن تثبت أن Xberg "ممتاز".
ولا أريد منك أن تثبت أنه "سيئ".

أريد:
أدلة تسمح بتحديد أي أجزاء منه تستحق الاستفادة داخل Omni Medical Suite، وأي أجزاء يجب إبقاؤها خارج المشروع.

المعيار النهائي:
SOURCE CODE > TESTS > RUNTIME EVIDENCE > SECURITY EVIDENCE > LICENSE EVIDENCE > GIT HISTORY > DOCUMENTATION > MODEL OPINION

ابدأ الآن بـ XB-01 فقط.
```

---

# 📄 الوثيقة الثانية: XB_INTEGRATION_ARCHITECTURE.md

```markdown
# Xberg Integration Architecture
## Document Intelligence Layer for Omni Medical Suite

**Version:** 1.0
**Date:** 2026-09-18
**Status:** DRAFT — يتطلب مراجعة بعد XB-01
**License:** MIT (Xberg) — متوافق مع الاستخدام التجاري

---

## 1. الملخص التنفيذي

Xberg ليس OCR engine، بل هو **طبقة استخراج وتوحيد مستندات**. هذه الوثيقة تصف كيف يمكن دمجه كطبقة اختيارية داخل Omni Medical Suite، دون كسر العقد القائم، ودون استبدال أي محرك OCR موجود.

**القرار المعماري:** Xberg يُدمج كـ **Optional Extraction Layer** — منفصل تمامًا عن OCR runtime، ويُستدعى فقط عند الحاجة.

---

## 2. المبادئ المعمارية

### 2.1 الفصل التام

```
┌─────────────────────────────────────────────────────────┐
│                   Omni Medical Suite                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │              OCR Runtime (Core)                  │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐            │   │
│  │  │Tesseract│ │PaddleOCR│ │ EasyOCR │            │   │
│  │  └─────────┘ └─────────┘ └─────────┘            │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐            │   │
│  │  │  TrOCR  │ │ OLMoCR  │ │   AHW   │            │   │
│  │  └─────────┘ └─────────┘ └─────────┘            │   │
│  │                                                 │   │
│  │         OCRResult (Canonical Contract)          │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │          Extraction Layer (NEW)                  │   │
│  │                                                 │   │
│  │              Xberg (Optional)                    │   │
│  │  ┌─────────────────────────────────────────┐    │   │
│  │  │ • Format Detection (106 formats)        │    │   │
│  │  │ • Unified Output (text/tables/metadata) │    │   │
│  │  │ • Layout Reconstruction                 │    │   │
│  │  │ • Table Extraction                      │    │   │
│  │  │ • Audio Transcription                   │    │   │
│  │  │ • Code Intelligence                     │    │   │
│  │  └─────────────────────────────────────────┘    │   │
│  │                                                 │   │
│  │         ExtractionResult (Xberg Contract)        │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │          Bridge Layer (NEW)                      │   │
│  │                                                 │   │
│  │     XbergResult → OCRResult Adapter              │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 2.2 القواعد غير القابلة للتفاوض

1. **Xberg لا يدخل `packages/omni_ocr/`** — يبقى في `packages/omni_extraction/` أو `tools/xberg/`.
2. **Xberg لا يستبدل أي محرك** — يُضاف كخيار إضافي.
3. **Xberg لا يعمل في الـ default profile** — يجب تفعيله صراحةً.
4. **Xberg لا يرسل بيانات للخارج** — يعمل محليًا بالكامل.
5. **Xberg لا يعدل OCRResult** — يُنتج ExtractionResult ويُحوَّل عبر Bridge.

---

## 3. البنية المقترحة

### 3.1 هيكل المجلدات

```
packages/
├── omni_ocr/                          # موجود — لا يُعدّل
│   ├── contract/
│   ├── engines/
│   ├── routing/
│   ├── normalization/
│   └── provenance/
│
├── omni_extraction/                   # جديد
│   ├── __init__.py
│   ├── contract/
│   │   ├── __init__.py
│   │   ├── extraction_result.py       # ExtractionResult dataclass
│   │   └── extraction_metadata.py
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── xberg_backend.py           # Xberg adapter
│   │   └── base_backend.py            # Base interface
│   ├── bridge/
│   │   ├── __init__.py
│   │   ├── xberg_to_ocr.py            # Xberg → OCRResult
│   │   └── ocr_to_extraction.py       # OCRResult → ExtractionResult
│   ├── profiles/
│   │   ├── __init__.py
│   │   └── extraction_profiles.py     # LITE/STANDARD/FULL
│   └── config/
│       ├── __init__.py
│       └── xberg_config.py
│
└── tests/
    ├── test_xberg_adapter.py
    ├── test_xberg_bridge.py
    └── test_xberg_profiles.py

tools/
└── xberg/                             # للـpilot فقط
    ├── requirements.txt
    └── pilot_scripts/
```

### 3.2 العقود (Contracts)

#### 3.2.1 ExtractionResult (جديد)

```python
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class ExtractionFormat(Enum):
    TEXT = "text"
    MARKDOWN = "markdown"
    DJOT = "djot"
    HTML = "html"
    JSON_TREE = "json_tree"
    STRUCTURED = "structured"

@dataclass
class ExtractionResult:
    """نتيجة استخراج موحدة من Xberg."""
    # المحتوى
    text: str
    markdown: str
    structured: dict

    # التنسيق
    format: ExtractionFormat
    mime_type: str

    # البيانات الوصفية
    metadata: dict = field(default_factory=dict)
    tables: list = field(default_factory=list)
    images: list = field(default_factory=list)

    # المصدر
    source_path: str = ""
    source_format: str = ""
    page_count: int = 0

    # التتبع
    backend: str = "xberg"
    backend_version: str = ""
    extraction_time_ms: float = 0.0

    # الجودة
    confidence: Optional[float] = None
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
```

#### 3.2.2 Bridge Contract

```python
class XbergToOCRAdapter:
    """يحوّل ExtractionResult إلى OCRResult."""

    def __init__(self, ocr_contract_version: str):
        self.contract_version = ocr_contract_version

    def convert(self, extraction: ExtractionResult) -> "OCRResult":
        """
        يحوّل نتيجة Xberg إلى OCRResult القياسي.
        يحافظ على:
        - raw_text (من extraction.text)
        - engine_name = "xberg"
        - provenance (مصدر Xberg)
        - confidence (إذا توفرت)
        """
        from omni_ocr.contract import OCRResult

        return OCRResult(
            raw_text=extraction.text,
            engine_name="xberg",
            engine_version=extraction.backend_version,
            confidence=extraction.confidence,
            provenance={
                "source": "xberg",
                "format": extraction.format.value,
                "backend": extraction.backend,
                "extraction_time_ms": extraction.extraction_time_ms,
                "warnings": extraction.warnings,
            },
            metadata={
                "tables": extraction.tables,
                "images": extraction.images,
                "page_count": extraction.page_count,
                **extraction.metadata,
            }
        )
```

### 3.3 الـBackend

```python
# packages/omni_extraction/backends/base_backend.py

from abc import ABC, abstractmethod
from ..contract.extraction_result import ExtractionResult

class ExtractionBackend(ABC):
    """واجهة أساسية لأي backend استخراج."""

    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def version(self) -> str: ...

    @abstractmethod
    def supports_format(self, mime_type: str) -> bool: ...

    @abstractmethod
    def extract(self, source: str, **kwargs) -> ExtractionResult: ...

    @abstractmethod
    def is_available(self) -> bool: ...
```

```python
# packages/omni_extraction/backends/xberg_backend.py

import subprocess
import json
from pathlib import Path
from .base_backend import ExtractionBackend
from ..contract.extraction_result import ExtractionResult, ExtractionFormat

class XbergBackend(ExtractionBackend):
    """
    Adapter لـ Xberg.
    يستدعي Xberg CLI أو Python binding.
    """

    # الصيغ المدعومة
    SUPPORTED_FORMATS = {
        "application/pdf",
        "image/png", "image/jpeg", "image/tiff", "image/webp",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/html", "text/markdown", "text/plain",
        "message/rfc822",
        "application/epub+zip",
        "audio/mpeg", "audio/wav", "audio/mp4",
    }

    def __init__(self, config: dict = None):
        self.config = config or {}
        self._version = None
        self._available = None

    def name(self) -> str:
        return "xberg"

    def version(self) -> str:
        if self._version is None:
            self._version = self._detect_version()
        return self._version

    def _detect_version(self) -> str:
        try:
            result = subprocess.run(
                ["xberg", "--version"],
                capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return "unknown"

    def is_available(self) -> bool:
        if self._available is None:
            try:
                subprocess.run(
                    ["xberg", "--version"],
                    capture_output=True, timeout=5
                )
                self._available = True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                self._available = False
        return self._available

    def supports_format(self, mime_type: str) -> bool:
        return mime_type in self.SUPPORTED_FORMATS

    def extract(self, source: str, **kwargs) -> ExtractionResult:
        """
        يستدعي Xberg CLI ويحوّل النتيجة.

        kwargs:
        - output_format: "markdown" | "text" | "json" | "structured"
        - ocr_backend: "tesseract" | "paddle-ocr" | "easyocr" | "vlm"
        - ocr_language: "ara" | "eng" | "ara+eng"
        - layout: bool (default True)
        - tables: bool (default True)
        - timeout: int (default 300)
        """
        if not self.is_available():
            raise RuntimeError("Xberg is not installed or not in PATH")

        output_format = kwargs.get("output_format", "markdown")
        timeout = kwargs.get("timeout", 300)

        cmd = [
            "xberg", "extract",
            source,
            "--format", output_format,
            "--output", "-",  # stdout
        ]

        # OCR options
        if ocr_backend := kwargs.get("ocr_backend"):
            cmd.extend(["--ocr-backend", ocr_backend])

        if ocr_language := kwargs.get("ocr_language"):
            cmd.extend(["--ocr-language", ocr_language])

        if kwargs.get("layout", True):
            cmd.append("--layout")

        if kwargs.get("tables", True):
            cmd.append("--tables")

        import time
        start = time.time()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            elapsed = (time.time() - start) * 1000

            if result.returncode != 0:
                return ExtractionResult(
                    text="",
                    markdown="",
                    structured={},
                    format=ExtractionFormat(output_format),
                    mime_type="",
                    source_path=source,
                    errors=[result.stderr],
                    extraction_time_ms=elapsed,
                )

            return self._parse_output(result.stdout, source, elapsed, output_format)

        except subprocess.TimeoutExpired:
            return ExtractionResult(
                text="",
                markdown="",
                structured={},
                format=ExtractionFormat(output_format),
                mime_type="",
                source_path=source,
                errors=[f"Xberg timeout after {timeout}s"],
                extraction_time_ms=timeout * 1000,
            )

    def _parse_output(self, output: str, source: str,
                      elapsed: float, fmt: str) -> ExtractionResult:
        """يحوّل مخرجات Xberg إلى ExtractionResult."""
        if fmt == "json":
            try:
                data = json.loads(output)
                return ExtractionResult(
                    text=data.get("text", ""),
                    markdown=data.get("markdown", ""),
                    structured=data.get("structured", {}),
                    format=ExtractionFormat.JSON_TREE,
                    mime_type=data.get("mime_type", ""),
                    metadata=data.get("metadata", {}),
                    tables=data.get("tables", []),
                    images=data.get("images", []),
                    source_path=source,
                    page_count=data.get("page_count", 0),
                    backend="xberg",
                    backend_version=self.version(),
                    extraction_time_ms=elapsed,
                )
            except json.JSONDecodeError as e:
                return ExtractionResult(
                    text=output,
                    markdown=output,
                    structured={},
                    format=ExtractionFormat.TEXT,
                    mime_type="",
                    source_path=source,
                    errors=[f"JSON parse error: {e}"],
                    extraction_time_ms=elapsed,
                )

        # markdown / text / djot / html
        format_map = {
            "markdown": ExtractionFormat.MARKDOWN,
            "text": ExtractionFormat.TEXT,
            "djot": ExtractionFormat.DJOT,
            "html": ExtractionFormat.HTML,
        }

        return ExtractionResult(
            text=output,
            markdown=output if fmt == "markdown" else "",
            structured={},
            format=format_map.get(fmt, ExtractionFormat.TEXT),
            mime_type="",
            source_path=source,
            backend="xberg",
            backend_version=self.version(),
            extraction_time_ms=elapsed,
        )
```

---

## 4. الـProfiles

### 4.1 تعريف الـProfiles

```python
# packages/omni_extraction/profiles/extraction_profiles.py

from enum import Enum
from dataclasses import dataclass

class ExtractionProfile(Enum):
    LITE = "lite"           # استخراج أساسي، بدون OCR
    STANDARD = "standard"   # استخراج + OCR أساسي
    ADVANCED = "advanced"   # استخراج + OCR + layout + tables
    FULL = "full"           # كل شيء (بما في ذلك audio + code)
    ARABIC_FOCUSED = "arabic"  # تحسين للعربية
    MEDICAL = "medical"     # للوثائق الطبية

@dataclass
class ProfileConfig:
    """تكوين كل profile."""
    name: ExtractionProfile
    ocr_enabled: bool
    ocr_backend: str
    ocr_language: str
    layout: bool
    tables: bool
    audio: bool
    code: bool
    embeddings: bool
    structured: bool
    max_pages: int = 0  # 0 = لا حد
    timeout: int = 300

PROFILES = {
    ExtractionProfile.LITE: ProfileConfig(
        name=ExtractionProfile.LITE,
        ocr_enabled=False,
        ocr_backend="",
        ocr_language="",
        layout=False,
        tables=False,
        audio=False,
        code=False,
        embeddings=False,
        structured=False,
    ),
    ExtractionProfile.STANDARD: ProfileConfig(
        name=ExtractionProfile.STANDARD,
        ocr_enabled=True,
        ocr_backend="tesseract",
        ocr_language="ara+eng",
        layout=False,
        tables=False,
        audio=False,
        code=False,
        embeddings=False,
        structured=False,
    ),
    ExtractionProfile.ADVANCED: ProfileConfig(
        name=ExtractionProfile.ADVANCED,
        ocr_enabled=True,
        ocr_backend="paddle-ocr",
        ocr_language="ara",
        layout=True,
        tables=True,
        audio=False,
        code=False,
        embeddings=False,
        structured=False,
    ),
    ExtractionProfile.FULL: ProfileConfig(
        name=ExtractionProfile.FULL,
        ocr_enabled=True,
        ocr_backend="paddle-ocr",
        ocr_language="ara+eng",
        layout=True,
        tables=True,
        audio=True,
        code=True,
        embeddings=True,
        structured=True,
    ),
    ExtractionProfile.ARABIC_FOCUSED: ProfileConfig(
        name=ExtractionProfile.ARABIC_FOCUSED,
        ocr_enabled=True,
        ocr_backend="paddle-ocr",
        ocr_language="ara",
        layout=True,
        tables=True,
        audio=False,
        code=False,
        embeddings=False,
        structured=False,
    ),
    ExtractionProfile.MEDICAL: ProfileConfig(
        name=ExtractionProfile.MEDICAL,
        ocr_enabled=True,
        ocr_backend="paddle-ocr",
        ocr_language="ara+eng",
        layout=True,
        tables=True,
        audio=True,
        code=False,
        embeddings=True,
        structured=True,
    ),
}
```

---

## 5. طبقة الجسر (Bridge Layer)

### 5.1 Xberg → OCRResult

```python
# packages/omni_extraction/bridge/xberg_to_ocr.py

from typing import Optional
from ..contract.extraction_result import ExtractionResult

class XbergToOCRBridge:
    """
    يحوّل ExtractionResult إلى OCRResult القياسي.
    يحافظ على provenance الكامل.
    """

    BRIDGE_VERSION = "1.0.0"

    def __init__(self, ocr_contract):
        """
        Args:
            ocr_contract: وحدة OCRResult من packages/omni_ocr/contract
        """
        self.ocr_contract = ocr_contract

    def convert(self, extraction: ExtractionResult,
                page_number: int = 0) -> "OCRResult":
        """يحوّل نتيجة Xberg إلى OCRResult."""

        provenance = {
            "source": "xberg",
            "bridge_version": self.BRIDGE_VERSION,
            "xberg_version": extraction.backend_version,
            "extraction_format": extraction.format.value,
            "extraction_time_ms": extraction.extraction_time_ms,
            "source_path": extraction.source_path,
            "source_format": extraction.source_format,
            "page_count": extraction.page_count,
            "page_number": page_number,
            "warnings": extraction.warnings,
            "errors": extraction.errors,
        }

        metadata = {
            "tables_count": len(extraction.tables),
            "images_count": len(extraction.images),
            "has_structured_data": bool(extraction.structured),
            **extraction.metadata,
        }

        # اختيار النص الأنسب
        raw_text = extraction.text
        if not raw_text and extraction.markdown:
            raw_text = extraction.markdown

        return self.ocr_contract.OCRResult(
            raw_text=raw_text,
            engine_name="xberg",
            engine_version=extraction.backend_version,
            confidence=extraction.confidence,
            provenance=provenance,
            metadata=metadata,
            alternatives=[],  # Xberg لا ينتج alternatives بنفس الطريقة
        )

    def convert_with_alternatives(
        self,
        extraction: ExtractionResult,
        alternative_engines: list = None
    ) -> "OCRResult":
        """
        يحوّل ExtractionResult مع إضافة alternatives من محركات أخرى.
        يُستخدم في الـensembles.
        """
        result = self.convert(extraction)

        if alternative_engines:
            for engine_name, engine_text, confidence in alternative_engines:
                result.alternatives.append({
                    "engine": engine_name,
                    "text": engine_text,
                    "confidence": confidence,
                })

        return result
```

---

## 6. التكامل مع الـRouter

### 6.1 Routing Logic

```python
# packages/omni_extraction/routing/extraction_router.py

from pathlib import Path
from ..profiles.extraction_profiles import ExtractionProfile, PROFILES
from ..backends.xberg_backend import XbergBackend

class ExtractionRouter:
    """
    يقرر متى يستخدم Xberg ومتى يستخدم OCR runtime العادي.
    """

    # الصيغ التي يحتاجها Xberg
    XBERG_REQUIRED_FORMATS = {
        # صيغ لا يدعمها OCR runtime
        ".docx", ".xlsx", ".pptx",
        ".html", ".htm",
        ".eml", ".msg",
        ".epub",
        ".mp3", ".wav", ".mp4", ".m4a",
        ".zip", ".tar", ".gz", ".7z",
    }

    # الصيغ التي يمكن لكليهما معالجتها
    SHARED_FORMATS = {
        ".pdf", ".png", ".jpg", ".jpeg",
        ".tiff", ".tif", ".webp",
    }

    def __init__(self, xberg_backend: XbergBackend = None):
        self.xberg = xberg_backend or XbergBackend()

    def route(self, source_path: str,
              profile: ExtractionProfile = ExtractionProfile.STANDARD,
              prefer_xberg: bool = False) -> dict:
        """
        يقرر المحرك المناسب.

        Returns:
            dict مع:
            - engine: "xberg" | "ocr_runtime"
            - reason: سبب الاختيار
            - profile: الـprofile المستخدم
        """
        path = Path(source_path)
        suffix = path.suffix.lower()

        # 1. صيغ تحتاج Xberg حتماً
        if suffix in self.XBERG_REQUIRED_FORMATS:
            if self.xberg.is_available():
                return {
                    "engine": "xberg",
                    "reason": f"Format {suffix} requires Xberg",
                    "profile": profile,
                }
            else:
                return {
                    "engine": "unsupported",
                    "reason": f"Format {suffix} requires Xberg, but Xberg is not available",
                    "profile": profile,
                }

        # 2. صيغ مشتركة
        if suffix in self.SHARED_FORMATS:
            if prefer_xberg and self.xberg.is_available():
                return {
                    "engine": "xberg",
                    "reason": "User prefers Xberg for shared format",
                    "profile": profile,
                }
            return {
                "engine": "ocr_runtime",
                "reason": "Shared format, default to OCR runtime",
                "profile": profile,
            }

        # 3. صيغ غير معروفة
        return {
            "engine": "unsupported",
            "reason": f"Unknown format: {suffix}",
            "profile": profile,
        }
```

---

## 7. التكامل مع الـConfig

```python
# packages/omni_extraction/config/xberg_config.py

from dataclasses import dataclass
from pathlib import Path

@dataclass
class XbergConfig:
    """تكوين Xberg."""
    enabled: bool = False
    binary_path: str = "xberg"  # أو مسار مطلق
    default_profile: str = "standard"
    ocr_backend: str = "paddle-ocr"
    ocr_language: str = "ara+eng"
    timeout: int = 300
    max_file_size_mb: int = 500
    cache_dir: Path = Path.home() / ".cache" / "xberg"
    allow_network: bool = False  # للتحديثات فقط
    telemetry: bool = False  # معطل افتراضياً

    @classmethod
    def from_env(cls) -> "XbergConfig":
        """يقرأ من environment variables."""
        import os
        return cls(
            enabled=os.getenv("OMNI_XBERG_ENABLED", "false").lower() == "true",
            binary_path=os.getenv("OMNI_XBERG_PATH", "xberg"),
            default_profile=os.getenv("OMNI_XBERG_PROFILE", "standard"),
            ocr_backend=os.getenv("OMNI_XBERG_OCR_BACKEND", "paddle-ocr"),
            ocr_language=os.getenv("OMNI_XBERG_OCR_LANG", "ara+eng"),
            timeout=int(os.getenv("OMNI_XBERG_TIMEOUT", "300")),
            max_file_size_mb=int(os.getenv("OMNI_XBERG_MAX_SIZE_MB", "500")),
            allow_network=os.getenv("OMNI_XBERG_ALLOW_NETWORK", "false").lower() == "true",
            telemetry=False,  # دائماً false
        )
```

---

## 8. خطة التنفيذ

| المرحلة | المهمة | المخرج |
|---|---|---|
| **XB-01** | Audit شامل | `XBERG_FORENSIC_AUDIT.md` |
| **XB-02** | Isolated install | `tools/xberg/` + requirements |
| **XB-03** | Security + License | `XBERG_SECURITY.md` |
| **XB-04** | Omni Mapping | `XBERG_OMNI_MAPPING.md` |
| **XB-05** | Pilot (5 سيناريوهات) | `XBERG_PILOT.md` |
| **XB-06** | Custom Rules | `.xberg/rules/` |
| **XB-07** | CI Pilot | GitHub Action |
| **XB-08** | Adoption Decision | `XBERG_ADOPTION_DECISION.md` |

---

## 9. المخاطر والتخفيف

| المخاطرة | الشدة | التخفيف |
|---|---|---|
| Xberg يضيف dependency ثقيل | MEDIUM | Isolated venv + optional install |
| PaddleOCR لا يدعم العربية جيداً | HIGH | Benchmark قبل الاعتماد |
| TrOCR line-level only | MEDIUM | استخدامه فقط للأسطر |
| VLM يحتاج GPU | MEDIUM | Fallback إلى Tesseract |
| trust_remote_code | HIGH | Sandbox + مراجعة |
| تعارض مع OCR runtime | LOW | فصل تام في packages/ |
| عدم دعم RTL | HIGH | Benchmark مخصص |

---

## 10. الخلاصة

Xberg يُدمج كـ **طبقة استخراج اختيارية**، وليس كمحرك OCR. الفوائد الرئيسية:

1. **دعم 106 صيغ** — بدلاً من بناء extractors من الصفر.
2. **توحيد المخرجات** — طبقة تنسيق لمحركات OCR المتعددة.
3. **Audio/Video** — قدرة جديدة كلياً.
4. **Code Intelligence** — لمشروعك نفسه.
5. **MCP Server** — لتطوير المشروع.

**القرار:** `ADOPT` — لكن فقط بعد اجتياز XB-01 → XB-08.
```

---

# 📄 الوثيقة الثالثة: XB_BENCHMARK_PLAN.md

```markdown
# Xberg Benchmark Plan
## Evaluating Xberg for Arabic Handwriting & Medical Documents

**Version:** 1.0
**Date:** 2026-09-18
**Status:** DRAFT — يتطلب XB-01 قبل التنفيذ

---

## 1. الهدف

قياس أداء Xberg (بـbackends مختلفة) على:
1. الخط اليدوي العربي
2. النص العربي المطبوع
3. النص الطبي (عربي + إنجليزي مختلط)
4. RTL
5. الجداول
6. الوثائق متعددة الصفحات

**المقارنة:** ضد المحركات القائمة في Omni:
- Tesseract
- PaddleOCR
- EasyOCR
- TrOCR
- OLMoCR
- AHW (بعد التطوير)

---

## 2. مجموعة الاختبار

### 2.1 التصنيفات

| # | الفئة | عدد العينات | المصدر |
|---|---|---|---|
| 1 | خط يد عربي | 50 | dataset AHW |
| 2 | عربي مطبوع | 50 | PDFs عربية |
| 3 | عربي + إنجليزي مختلط | 30 | ملاحظات طبية |
| 4 | جداول طبية | 20 | تقارير |
| 5 | أرقام وجرعات | 20 | وصفات طبية |
| 6 | RTL كامل | 30 | صفحات |
| 7 | خط يد صعب | 20 | عينات متحدية |
| 8 | مسح ضوئي منخفض الجودة | 20 | صور قديمة |
| 9 | متعدد الصفحات | 10 | مستندات 5+ صفحات |
| 10 | عربي + كود | 10 | ملفات تقنية |

**الإجمالي:** 260 عينة

### 2.2 معايير الاختيار

- ✅ تنوع الكتابة (رجالية/نسائية، أعمار مختلفة)
- ✅ تنوع الجودة (مسح ضوئي، هاتف، ماسح)
- ✅ تنوع المحتوى (طبي، تقني، عام)
- ✅ وجود Ground Truth موثّق
- ❌ لا PHI حقيقي (بيانات اصطناعية أو مجهولة)

---

## 3. المقاييس

### 3.1 مقاييس عامة

| المقياس | الوصف | الصيغة |
|---|---|---|
| **CER** | Character Error Rate | `(S+D+I)/N` |
| **WER** | Word Error Rate | `(S+D+I)/N_words` |
| **Character Accuracy** | `1 - CER` | |
| **Word Accuracy** | `1 - WER` | |
| **Precision** | TP/(TP+FP) | |
| **Recall** | TP/(TP+FN) | |
| **F1** | 2·P·R/(P+R) | |

### 3.2 مقاييس عربية

| المقياس | الوصف |
|---|---|
| **Diacritic Error Rate** | أخطاء التشكيل |
| **Dot Error Rate** | أخطاء النقاط (ب/ت/ث) |
| **RTL Preservation** | نسبة النصوص التي حافظت على RTL |
| **Arabic Character Accuracy** | دقة الحروف العربية فقط |
| **Mixed-script Accuracy** | دقة العربي + الإنجليزي المختلط |

### 3.3 مقاييس طبية

| المقياس | الوصف |
|---|---|
| **Medical Critical Error Rate (MCER)** | أخطاء تغير المعنى الطبي |
| **Critical Token Accuracy** | دقة الرموز الحرجة (L4/L5، جرعات) |
| **Medication Name Accuracy** | دقة أسماء الأدوية |
| **Dosage Accuracy** | دقة الجرعات |
| **Unit Accuracy** | دقة الوحدات (mg, mL) |

### 3.4 مقاييس تشغيلية

| المقياس | الوصف |
|---|---|
| **Inference Time** | ms/صفحة |
| **RAM Peak** | MB |
| **VRAM Peak** | MB (إذا GPU) |
| **CPU Usage** | % |
| **Model Size** | MB |
| **Startup Time** | ms |
| **Throughput** | صفحات/ثانية |

---

## 4. الإعدادات

### 4.1 Xberg Configurations

| Config | OCR Backend | Layout | Tables | Language |
|---|---|---|---|---|
| **X-T** | Tesseract | ❌ | ❌ | ara+eng |
| **X-P** | PaddleOCR | ❌ | ❌ | ara |
| **X-PL** | PaddleOCR | ✅ | ❌ | ara |
| **X-PLT** | PaddleOCR | ✅ | ✅ | ara |
| **X-E** | EasyOCR | ❌ | ❌ | ara+eng |
| **X-V** | VLM | ❌ | ❌ | ara+eng |
| **X-C** | Candle | ❌ | ❌ | ara |

### 4.2 Baselines

| Baseline | المحرك |
|---|---|
| **B-T** | Tesseract (مباشر) |
| **B-P** | PaddleOCR (مباشر) |
| **B-E** | EasyOCR (مباشر) |
| **B-TR** | TrOCR (line-level) |
| **B-OL** | OLMoCR |
| **B-AH** | AHW (بعد XB-05) |

---

## 5. منهجية التنفيذ

### 5.1 خطوات Benchmark

```bash
# 1. تحضير مجموعة الاختبار
mkdir -p benchmarks/xberg/{images,ground_truth,results}

# 2. تشغيل كل config
for config in X-T X-P X-PL X-PLT X-E X-V X-C; do
    for img in benchmarks/xberg/images/*; do
        xberg extract "$img" \
            --config "$config" \
            --format json \
            --output "benchmarks/xberg/results/${config}/$(basename $img).json"
    done
done

# 3. حساب المقاييس
python benchmarks/xberg/evaluate.py \
    --results benchmarks/xberg/results/ \
    --ground-truth benchmarks/xberg/ground_truth/ \
    --output benchmarks/xberg/report.json
```

### 5.2 سكربت التقييم

```python
# benchmarks/xberg/evaluate.py

import json
import jiwer
from pathlib import Path
from collections import defaultdict

def compute_cer(reference: str, hypothesis: str) -> float:
    """Character Error Rate."""
    return jiwer.cer(reference, hypothesis)

def compute_wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate."""
    return jiwer.wer(reference, hypothesis)

def compute_medical_cer(reference: str, hypothesis: str,
                        critical_tokens: set) -> float:
    """
    Medical Critical Error Rate.
    يقيس الأخطاء في الرموز الحرجة فقط.
    """
    ref_tokens = set(reference.split())
    hyp_tokens = set(hypothesis.split())

    critical_ref = ref_tokens & critical_tokens
    critical_hyp = hyp_tokens & critical_tokens

    if not critical_ref:
        return 0.0

    errors = len(critical_ref - critical_hyp)
    return errors / len(critical_ref)

def evaluate(results_dir: Path, ground_truth_dir: Path) -> dict:
    """يقيّم كل النتائج."""
    metrics = defaultdict(lambda: defaultdict(list))

    for result_file in results_dir.rglob("*.json"):
        config = result_file.parent.name
        sample_id = result_file.stem

        gt_file = ground_truth_dir / f"{sample_id}.txt"
        if not gt_file.exists():
            continue

        reference = gt_file.read_text(encoding="utf-8")
        result = json.loads(result_file.read_text(encoding="utf-8"))
        hypothesis = result.get("text", "")

        # مقاييس عامة
        metrics[config]["cer"].append(compute_cer(reference, hypothesis))
        metrics[config]["wer"].append(compute_wer(reference, hypothesis))

        # مقاييس عربية
        metrics[config]["arabic_cer"].append(
            compute_cer(
                extract_arabic(reference),
                extract_arabic(hypothesis)
            )
        )

        # مقاييس طبية
        metrics[config]["medical_cer"].append(
            compute_medical_cer(reference, hypothesis, CRITICAL_TOKENS)
        )

    # تجميع
    summary = {}
    for config, config_metrics in metrics.items():
        summary[config] = {
            metric: {
                "mean": sum(values) / len(values),
                "median": sorted(values)[len(values) // 2],
                "min": min(values),
                "max": max(values),
                "count": len(values),
            }
            for metric, values in config_metrics.items()
        }

    return summary
```

---

## 6. جدول النتائج (نموذج)

### 6.1 CER حسب الفئة

| Config | خط يد | مطبوع | مختلط | جداول | أرقام | RTL | متوسط |
|---|---|---|---|---|---|---|---|
| X-T | | | | | | | |
| X-P | | | | | | | |
| X-PL | | | | | | | |
| X-PLT | | | | | | | |
| X-E | | | | | | | |
| X-V | | | | | | | |
| X-C | | | | | | | |
| **B-T** | | | | | | | |
| **B-P** | | | | | | | |
| **B-E** | | | | | | | |
| **B-TR** | | | | | | | |
| **B-OL** | | | | | | | |

### 6.2 MCER حسب الفئة

| Config | أسماء أدوية | جرعات | وحدات | تشريح | تشخيص | متوسط |
|---|---|---|---|---|---|---|
| X-T | | | | | | |
| X-P | | | | | | |
| X-PLT | | | | | | |
| X-V | | | | | | |
| **B-AH** | | | | | | |

### 6.3 الأداء التشغيلي

| Config | Inference (ms) | RAM (MB) | VRAM (MB) | Startup (ms) | Throughput (pg/s) |
|---|---|---|---|---|---|
| X-T | | | | | |
| X-P | | | | | |
| X-PLT | | | | | |
| X-V | | | | | |
| **B-OL** | | | | | |

---

## 7. معايير القبول

### 7.1 للاعتماد الكامل (ADOPT)

- ✅ CER على الخط اليدوي ≤ 15%
- ✅ MCER ≤ 5%
- ✅ RTL Preservation ≥ 95%
- ✅ Mixed-script Accuracy ≥ 85%
- ✅ Inference ≤ 5s/صفحة
- ✅ RAM ≤ 4GB

### 7.2 للاعتماد المشروط (ADAPT)

- ⚠️ CER ≤ 25%
- ⚠️ MCER ≤ 10%
- ⚠️ RTL ≥ 85%

### 7.3 للرفض (REJECT)

- ❌ CER > 30%
- ❌ MCER > 15%
- ❌ RTL < 80%
- ❌ Inference > 30s/صفحة
- ❌ RAM > 16GB

---

## 8. تحليل الأخطاء

### 8.1 تصنيف الأخطاء

| النوع | الوصف | المثال |
|---|---|---|
| **Dot Error** | خطأ في النقاط | ب → ت |
| **Shape Error** | خطأ في الشكل | ع → غ |
| **Connection Error** | خطأ في الاتصال | ـبـ → بـ |
| **Diacritic Error** | خطأ في التشكيل | َ → ُ |
| **Segmentation Error** | خطأ في التقطيع | كلمة واحدة → كلمتين |
| **Script Error** | خطأ في الكتابة | عربي → إنجليزي |
| **RTL Error** | خطأ في الاتجاه | انعكاس |
| **Medical Error** | خطأ طبي | L4 → L5 |
| **Digit Error** | خطأ في الأرقام | ٥ → ٥ |
| **Unit Error** | خطأ في الوحدات | mg → g |

### 8.2 تحليل الجذور

لكل خطأ، حدد:
- **Root Cause:** preprocessing؟ model؟ postprocessing؟
- **Severity:** CRITICAL / HIGH / MEDIUM / LOW
- **Frequency:** كم مرة يتكرر؟
- **Fixable:** هل يمكن إصلاحه؟

---

## 9. الجدول الزمني

| الأسبوع | المهمة |
|---|---|
| 1 | تحضير مجموعة الاختبار (260 عينة) |
| 2 | تشغيل Xberg configs (7 configs) |
| 3 | تشغيل Baselines (5 baselines) |
| 4 | حساب المقاييس + تحليل |
| 5 | كتابة التقرير النهائي |

---

## 10. المخرجات

| الملف | الوصف |
|---|---|
| `XB_BENCHMARK_PLAN.md` | هذه الوثيقة |
| `benchmarks/xberg/images/` | 260 صورة |
| `benchmarks/xberg/ground_truth/` | 260 نص مرجعي |
| `benchmarks/xberg/results/` | نتائج كل config |
| `benchmarks/xberg/report.json` | التقرير المُهيكل |
| `benchmarks/xberg/report.md` | التقرير النهائي |
| `benchmarks/xberg/error_analysis.md` | تحليل الأخطاء |

---

## 11. القيود

1. **لا PHI حقيقي** — كل العينات مجهولة أو اصطناعية.
2. **لا مقارنة غير عادلة** — نفس الأجهزة، نفس الإعدادات.
3. **لا نتائج marketing** — كل رقم مدعوم بـevidence.
4. **لا اعتماد على benchmarks Xberg الخارجية** — يجب اختبارها محلياً.
5. **الشفافية الكاملة** — كل سكربت وكل config موثق.

---

## 12. الخلاصة

هذه الخطة تهدف إلى إنتاج **أدلة قابلة لإعادة الإنتاج** حول أداء Xberg على اللغة العربية والخط اليدوي والمحتوى الطبي. النتيجة ستكون:

1. **قرار مبني على أدلة:** ADOPT / ADAPT / REJECT
2. **فهم عميق للحدود:** ما يفيد، ما لا يفيد
3. **توصيات محددة:** كيف يُدمج، كيف لا يُدمج
4. **مقارنة عادلة:** Xberg vs Baselines
```

---

## 📊 ملخص الوثائق الثلاث

| الوثيقة | الغرض | الحالة |
|---|---|---|
| **XB-01_AUDIT_PROMPT.md** | برومبت شامل لـZ.ai لتدقيق Xberg | ✅ جاهز |
| **XB_INTEGRATION_ARCHITECTURE.md** | تصميم معماري مفصل للدمج | ✅ جاهز |
| **XB_BENCHMARK_PLAN.md** | خطة benchmark تفصيلية | ✅ جاهز |

---

## 🎯 الخطوة التالية

**أرسل XB-01_AUDIT_PROMPT.md إلى Z.ai أولاً.** بعد أن يُنتج تقرير `XBERG_FORENSIC_AUDIT.md`، أرسله لي لأراجعه قبل السماح بـXB-02.

الوثيقتان الأخريان (Architecture + Benchmark) هما **مرجعيتان** — لا تُرسلان إلى Z.ai الآن، بل تُستخدمان في XB-02 وXB-05.

هل تريد أن أُعدّ أيضاً **Pre-Flight Checklist** قصير (صفحة واحدة) يُرفق مع XB-01 لضمان عدم تفويت أي فحص أساسي؟
