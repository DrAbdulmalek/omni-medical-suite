# OLMoCR + Xberg — تقرير التحقق الرسمي (VERIFICATION ONLY)

| الحقل | القيمة |
|---|---|
| التاريخ | 2026-09-22 |
| النوع | **8.1 مرحلة تحقق بلا أي تنفيذ** (ZAI_MASTER_PROMPT §8) |
| المصدر 1 | `github.com/allenai/olmocr` — HEAD `f7cfe4c22098` (2026-03-25)، نسخة استنساخ ضحلة وقت التنفيذ |
| المصدر 2 | `github.com/xberg-io/xberg` — HEAD `588401cec14e` (2026-09-21)، نسخة استنساخ ضحلة وقت التنفيذ |
| المصدر 3 | PyPI JSON API (`pypi.org/pypi/xberg/1.2.6`) + HuggingFace API (model cards) |
| المصدر 4 | كود المستودع الحالي على `origin/main` = `39640a6dbba7` (فرع العمل: `docs/olmocr-xberg-verification`) |
| تقرير Gemini | **ADVISORY فقط** — كل claim حُكم عليه منفرداً في القسم 5 أدناه |
| التنفيذ | **لم يُنفَّذ شيء** — لا adapter، لا تعديل `OCRResult`، لا registry، لا تبعيات، لا vllm/transformers |

> المنهجية: كل claim أدناه مُتحقق منه مباشرة من الكود المصدري الرسمي المستنسخ وقت التنفيذ أو من API رسمي (GitHub/PyPI/HF)، مع مرجع `ملف:سطر`. ما لم يكن له دليل مباشر حُكم عليه `UNPROVEN` أو `UNKNOWN` — لا تخمين.

---

## 1 — جدول المطالبات الرئيسي

| # | Claim | Evidence | Status | Source | Decision |
|---|---|---|---|---|---|
| 1 | OLMoCR الإصدار الحالي = **0.4.27** (آخر release `v0.4.27` بتاريخ 2026-03-12) | `olmocr/version.py`: `_MAJOR="0" _MINOR="4" _PATCH="27"`؛ `CHANGELOG.md` سطر 9؛ GitHub Releases API | **PROVEN** | repo clone + releases API | استخدام رقم الإصدار كما هو عند الربط |
| 2 | OLMoCR النموذج الحالي = **`allenai/olmOCR-2-7B-1025-FP8`** (افتراضي مضمّن في الكود) | `olmocr/pipeline.py:1213-1214` — `default="allenai/olmOCR-2-7B-1025-FP8"` | **PROVEN** | repo clone | اعتماد الاسم الحرفي، لا أسماء قديمة من تقارير سابقة |
| 3 | OLMoCR ترخيص الكود = **Apache-2.0** | `LICENSE` (نص Apache 2.0)؛ classifier في `pyproject.toml`؛ GitHub API `license.key=apache-2.0` | **PROVEN** | repo clone + GitHub API | مسموح للاستخدام والتوزيع التجاري |
| 4 | OLMoCR ترخيص النموذج = **Apache-2.0** (سلسلة كاملة: FP8 وbf16 والنموذج الأساسي Qwen) | HF API: `allenai/olmOCR-2-7B-1025-FP8` → `license:apache-2.0`، base `Qwen/Qwen2.5-VL-7B-Instruct` → `license:apache-2.0`؛ و`allenai/olmOCR-2-7B-1025` → `license:apache-2.0` | **PROVEN** (مع توقيع قانوني نهائي للمالك) | HF model cards API | لا `LEGAL_REVIEW_NEEDED` مانع؛ الموافقة القانونية النهائية = HUMAN ACTION |
| 5 | OLMoCR متطلبات GPU = **NVIDIA حديثة بذاكرة ≥ 12GB** (مُختبَر على RTX 4090/L40S/A100/H100) + 30GB قرص؛ «based on a 7B parameter VLM, so it requires a GPU» | `README.md` قسم Installation → Option 2: "at least 12 GB of GPU RAM"، "30GB of free disk space"؛ سطر 35 في الترويسة | **PROVEN** (كما هو موثق) — الأداء الفعلي على عتادنا | repo clone | لا يعمل محلياً على CPU؛ remote mode هو البديل |
| 6 | OLMoCR local inference = محلي عبر vLLM مُدار داخلياً (CLI `olmocr <workspace> --markdown --pdfs ...`) | `pyproject.toml` `[project.scripts] olmocr = "olmocr.pipeline:cli_main"`؛ `[gpu]` extras: `torch>=2.7.0, transformers==4.57.3, vllm==0.11.2` | **PROVEN** | repo clone | محرك اختياري فقط، تبعياته معزولة في extras |
| 7 | OLMoCR remote inference = **مدعوم رسمياً** عبر `--server` (OpenAI-compatible) + `--api_key`؛ مُختبَر على Cirrascale/DeepInfra/Parasail بأسعار معلنة | `README.md` "Using an Inference Provider or External Server" + جدول المزودين (0.07–0.10$/1M input)؛ مثال `vllm serve allenai/olmOCR-2-7B-1025-FP8` | **PROVEN** | repo clone | remote **معطّل افتراضياً** في أي تكامل مستقبلي (§8.3) |
| 8 | OLMoCR الإخراج = Markdown + Dolma JSONL لكل workspace؛ مستوى الصفحة: `{primary_language, is_rotation_valid, rotation_correction, is_table, is_diagram, natural_text}`؛ معادلات→LaTeX؛ جداول→HTML (prompt v3)؛ تسمية الأشكال بصيغة `![alt](page_startx_starty_width_height.png)`؛ **لا bounding boxes حقيقية في الإخراج** | `olmocr/prompts/prompts.py:50-60`؛ dataclass `PageResponse` في `prompts.py:74-84`؛ README "Viewing Results"؛ `olmocr/prompts/anchor.py:99` `BoundingBox` = داخلي للتثبيت (anchoring) لا للإخراج | **PROVEN** | repo clone | يُمثَّل داخل `OCRResult` عبر `text` + `raw_result` (Q6) |
| 9 | OLMoCR handwriting = **قدرة موثقة**: «Support for equations, tables, handwriting…» + التعليمات «Read any natural handwriting.» في كل prompt variants | `README.md:32`؛ `olmocr/prompts/prompts.py:12,26,41,57`؛ `olmocr/bench/prompts.py:10` | **PROVEN** (موثق) / **UNPROVEN** (فعلي لعربي سريري) | repo clone | خط اليد العربي السريري يبقى UNPROVEN حتى قياس (Wave 3) |
| 10 | OLMoCR Arabic suitability = **غير مثبت**: بطاقة النموذج تُدرج لغة `en` فقط، وolmOCR-Bench فئاته: ArXiv/Old scans math/Tables/Old scans/Headers&footers/Multi column/Long tiny text/Base — **لا فئة عربية ولا handwriting** | HF API tags للنموذجين؛ `olmocr/bench/README.md` جدول النتائج | **UNPROVEN** | HF API + repo clone | لا ادعاء جودة عربية قبل قياس على الحزمة (§8.3) |
| 11 | OLMoCR offline behavior = تثبيت يتطلب شبكة؛ تنزيل النموذج مرة واحدة عبر HF hub (أو مسار محلي/Docker بنموذج مضمّن)؛ **لا telemetry في مسار الاستدلال** (wandb في كود التدريب فقط)؛ وضع remote يخرّج الوثائق من الجهاز بالتصميم | `olmocr/pipeline.py:27` (`from huggingface_hub import snapshot_download`)؛ `pipeline.py:1213` ("can be local, s3, or hugging face")؛ wandb فقط في `olmocr/train/config.py:255-299` و`grpo_train.py`؛ Docker `latest-with-model` (~30GB) | **PROVEN** (تصنيف كامل في §2-J) | repo clone | local-only ممكن بعد تخزين النموذج؛ remote يحتاج بوابة صريحة |
| 12 | Xberg الإصدار الحالي = **1.2.6** (release `v1.2.6` 2026-09-20؛ HEAD `588401cec14e` 2026-09-21؛ PyPI `xberg==1.2.6`؛ Cargo workspace `version = "1.2.6"`) | `Cargo.toml:29`؛ `packages/python/pyproject.toml` (`version = "1.2.6"`)؛ PyPI JSON؛ GitHub Releases API | **PROVEN** | repo clone + PyPI + Releases API | تثبيت `>=1.2.6,<1.3` عند الربط |
| 13 | Xberg الترخيص = **MIT** (Copyright 2025-2026 Kreuzberg, Inc.) على كل workspace (Rust + bindings) | `LICENSE`؛ `Cargo.toml` `license = "MIT"`؛ `packages/python/pyproject.toml` `license = "MIT"` | **PROVEN** | repo clone | مسموح تجاري؛ فحص سُمعة/استمرارية الكيان = HUMAN ACTION |
| 14 | Xberg الصيغ المدعومة = **107 صيغ / 141 امتداداً** + 371 لغة برمجة (PDF، Office، HTML، بريد، أرشيفات، SQLite، iWork، HWP، صور/HEIC، صوت…) | `README.md` («107 formats · 141 file extensions · 371 code languages»)؛ وصف crate في `crates/xberg/Cargo.toml:11`؛ features: `office/excel/email/archives/heic/hwp/iwork/sqlite…` | **PROVEN** (تعداد رسمي) — مخرجات كل صيغة على وثائقنا | repo clone | يُفعَّل تدريجياً حسب الحاجة |
| 15 | Xberg OCR capability = **مدعوم فعلياً** كخلفيات قابلة للتبديل: Tesseract (حزمة نظام)، PaddleOCR (مضمّن)، Candle (TrOCR/PaddleOCR-VL/GLM-OCR/DeepSeek-OCR بـRust)، Sceptre، VLM عبر liter-llm (مفتاح API) — مع سلاسل fallback ودرجات ثقة | `crates/xberg/Cargo.toml` features `ocr/paddle-ocr*/candle-*/sceptre-*/liter-llm`؛ `docs-site/.../guides/ocr.mdx` جدول الباك-إندات؛ `packages/python/README.md:94-100` | **PROVEN** — إجابة السؤال المعماري = **C** (انظر §3) | repo clone + docs | نستخدمه كطبقة استيعاب؛ باك-إندات OCR الخاصة به **لا** تُفعَّل في المسار الطبي مبدئياً |
| 16 | Xberg الإخراج = 6 صيغ (Text/Markdown/Djot/HTML/JSON tree/Docling DocTags) + renderers مخصصة؛ `ExtractionResult{results[], errors[], summary}` و`ExtractedDocument` يحوي `content/metadata/tables/pages/ocr_elements(geometry+confidence)/chunks/images/quality_score/processing_warnings/entities/formulas…` — **bounding boxes حقيقية** (`BBox x1y1x2y2`، `OcrBoundingGeometry`) | `packages/python/xberg/_xberg.pyi` (فئات `ExtractionResult/ExtractedDocument/PageContent/OcrElement/BBox`)؛ README جدول «6 output formats» | **PROVEN** | repo clone | تغطية غلاف إضافي فقط عند الحاجة؛ لا تعديل على `OCRResult` |
| 17 | Xberg offline = **النواة لا تُصدر أي طلب شبكة إطلاقاً** («xberg never makes outbound network requests» — SECURITY.md)؛ features الافتراضية = `tokio-runtime, simd-utf8` فقط بلا أي عميل HTTP | `SECURITY.md` قسم "Out of scope → Network requests"؛ `crates/xberg/Cargo.toml:44` `default = ["tokio-runtime", "simd-utf8"]` | **PROVEN** (للنواة) | repo clone | مناسب لوثائق سريرية على جهاز معزول |
| 18 | Xberg network behavior = تنزيل نماذج ML (OCR/التخطيط/embeddings) من HF hub **مفعّل افتراضياً** (`allow_network=true`) مع وضع air-gap (`allow_network=false` + `xberg warm`)؛ tessdata يُنزَّل وقتياً إلا إذا حُزم (`bundle-tessdata-eng`) أو ثبتت بيانات النظام؛ URL ingestion وcrawlberg = features اختيارية | `docs-site/.../reference/configuration.md:931` و`api-typescript.md:6470` (`allow_network` default `true`)؛ `crates/xberg/Cargo.toml:631` `url-ingestion = [...]`؛ `Cargo.toml:165-176` (tessdata)؛ `src/ocr/tessdata_download.rs:94` | **PROVEN** — تصنيف كامل في §3-G | repo clone + docs | التكوين الطبي: `allow_network=false` + warm مسبق؛ URL ingestion ممنوع |
| 19 | Xberg security implications = نموذج تهديد موثق ومطبق في الكود: ZipBombValidator (نسبة 100×، أرشيف 500MiB)، embedded files 50MiB، عمق أرشفة ≤3، timeout 60s، SecurityBudget 100MiB، حماية billion-laughs وXML depth (1024)، حد خلايا جداول 100k، path traversal بمحلل Components، DDE/formula تحذيرات، تخطي OLE، لا تنفيذ ماكرو | `SECURITY.md` جدول "Protected attack surfaces" كاملاً؛ `unsafe_code = "deny"` في `Cargo.toml:36` | **PROVEN** (إعلان + مرجع تنفيذي) — يُعاد التحقق بالاختبارات عند التكامل | repo clone | يتوافق مع سياسة §8.3 (حدود حجم/مسارات/أرشيفات) |
| 20 | معمارية omni_ocr الحالية = `OCRResult` dataclass واحد (`text, confidence: float = 0.0, engine, word_count, processing_time, words[{text,confidence,x,y,w,h}], raw_result, error`) + `UnifiedOCR` + `OCREngineID{mixed_engine,tesseract,mistral,easyocr}` + `EngineAdapter`/`EngineRegistry` (توفر صحي/ذاكرة/مهام) + `EngineRouter` (profiles low/balanced/high) — **لا يوجد `BaseOCREngine` ولا `OCRPageResult` ولا `EngineProvenance`** في المستودع | `packages/omni_ocr/adapter.py:56-99`؛ `packages/core/engine_registry.py:38-47,66-230`؛ `packages/core/engine_router.py:29-52`؛ بحث grep سلبي موثق | **PROVEN** | هذا المستودع @ `39640a6dbba7` | أساس قرار الموقع المعماري (§4) |
| 21 | حد التكامل الموصى به = **Xberg طبقة استيعاب/استخراج وثائق جديدة معزولة (default OFF)**؛ **OLMoCR محرك اختياري خلف واجهة المحركات الحالية (EngineAdapter + extras)** | اشتقاق من الأدلة في §3 و§4 — القرار المفصل في §6 | **INFERRED** (مدعوم بالأدلة) | هذا التقرير | قرار المالك بعد المراجعة |
| 22 | أثر التبعيات = xberg: عجلة native واحدة 33–59MB **بصفر تبعيات Python** (`requires_dist=None`)، لا torch/transformers؛ olmocr: أساس خفيف (~20 تبعية) لكن `[gpu]` يسحب `torch>=2.7 + transformers==4.57.3 + vllm==0.11.2` — **تعارض محتمل مع extras الحالية** (`nlp` تتطلب `transformers>=4.36`, `training` `>=4.40` بلا سقف) | PyPI xberg 1.2.6 (8 wheels abi3) + `requires_dist: null`؛ extras في `pyproject.toml` (olmocr)؛ extras في `pyproject.toml` (suite) أسطر 73-111 و131+ | **PROVEN** (وجود التعارض المحتمل) — الحسم بيئة منفصلة/remote أولاً | PyPI + المستودعان | olmocr عبر extras معزولة أو remote mode أولاً |
| 23 | أثر provenance = الحالي يغطي **engine + processing_time فقط**؛ مطلوب توسيع additive: المحرك المطلوب/الفعلي، النموذج وإصداره، المزود، موقع التنفيذ (محلي/بعيد)، هل خرجت البيانات، fallback وسببه، زمن التنفيذ | `packages/omni_ocr/adapter.py:56-99` (حقول موجودة) مقابل متطلبات §7.2 من Master Prompt | **PROVEN** (الفجوة مثبتة) | هذا المستودع | توسيع additive بحقول جديدة ذات قيم افتراضية (غير كاسر) |
| 24 | أثر fallback = `EngineRouter` مبني على سلاسل fallback ضمنية بprofile؛ سياسة §7.2 تتطلب `strict_engine_selection=True` افتراضياً و`allow_fallback` صريحاً ولا fallback صامت | `packages/core/engine_router.py:55-90` (profiles/سلاسل) مقابل `ZAI_MASTER_PROMPT.md` §7.2 | **PROVEN** (الفجوة مثبتة) | المستودع + Master Prompt | أي محرك جديد يُضاف بوضع strict صريح، فشل واضح لا تحويل صامت |

---

## 2 — OLMoCR: التحقق التفصيلي (A–J)

### A. Version
- **PROVEN**: الإصدار الحالي `0.4.27` (`olmocr/version.py`)، مطابق لآخر GitHub release `v0.4.27` (2026-03-12) وCHANGELOG.
- ملاحظة نشاط: آخر commit على main = `f7cfe4c22098` (2026-03-25) — أي **~6 أشهر صمت** حتى تاريخ التحقق (2026-09-22). المشروع غير مؤرشف (`archived: false`)، ~19.6k نجمة. لا يغيّر الحكم لكنه يستوجب إعادة فحص إصدار أحدث قبل التنفيذ.

### B. Model
- **PROVEN**: الافتراضي المضمّن في الكود = `allenai/olmOCR-2-7B-1025-FP8` (`pipeline.py:1214`). نُشر 2025-10-21 (README News)؛ بنية `qwen2_5_vl`؛ أساسه `Qwen/Qwen2.5-VL-7B-Instruct`. توجد نسخة bf16 غير مضغوطة `allenai/olmOCR-2-7B-1025`.
- تقييم olmOCR-bench المعلن لـv0.4.0: **82.4±1.1** إجمالاً (جدول README).

### C. License
- كود: Apache-2.0 (`LICENSE` + GitHub API) — **PROVEN**.
- نموذج: Apache-2.0 على `olmOCR-2-7B-1025-FP8` و`olmOCR-2-7B-1025` (HF tags) — **PROVEN**.
- checkpoint base: `Qwen/Qwen2.5-VL-7B-Instruct` Apache-2.0 (HF tags) — **PROVEN**.
- إعادة التوزيع/الاستخدام التجاري: مسموحة نصاً في Apache-2.0 — لا نقطة قانونية غامضة اكتُشفت ⇒ **لا `LEGAL_REVIEW_NEEDED` مانع**، مع بقاء توقيع قانوني نهائي بقرار المالك (HUMAN ACTION).

### D. Runtime
- **PROVEN**: `requires-python >= 3.11`؛ أساس خفيف بلا torch؛ extras `[gpu]` = `torch>=2.7.0, transformers==4.57.3, vllm==0.11.2` (فهرس cu128)؛ flashinfer اختياري؛ تبعيات نظام: `poppler-utils` + خطوط (mscorefonts/caladea/carlito/gsfonts/lcdf-typetools).

### E. Hardware
- **PROVEN** (موثق): NVIDIA حديثة ≥12GB VRAM (RTX 4090/L40S/A100/H100)، 30GB قرص (أو صورة Docker `latest-with-model` ~30GB). **CPU**: غير مدعوم للاستدلال المحلي (نموذج 7B VLM) — البديل الموثق هو remote `--server`. **quantization**: FP8 هو الافتراضي (compressed-tensors)، وbf16 متاح — لا أرقام VRAM موثقة لغير حد 12GB ⇒ أي رقم آخر = UNPROVEN.

### F. Inference
- محلي: CLI يدير vLLM داخلياً — **PROVEN**.
- بعيد: `--server <OpenAI-compatible>` + `--api_key` — **PROVEN** مع مزودين موثقين (Cirrascale/DeepInfra/Parasail) وأسعار معلنة.
- REST مباشر: أي خادم vLLM متوافق OpenAI API يكفي (مثال موثق `vllm serve ... --max-model-len 16384`). معالجة دفعات: `--pdfs`/S3/Beaker — **PROVEN**.

### G. Input
- **PROVEN** (`pipeline.py:1349-1370`): PDF (فحص magic `%PDF`)، PNG، JPEG (فحص magic)، أرشيفات tar.gz من PDFs، ملفات .txt كقوائم مسارات. **لا DOCX ولا TIFF** (يتطلبان تحويلاً مسبقاً — وهذا بالضبط موقع قيمة Xberg كطبقة استيعاب).
- multi-page: نعم — معالجة صفحة-صفحة مع تعليمات صريحة للحفاظ على الجُمل العابرة للصفحات — **PROVEN**.

### H. Output
- **PROVEN**: Markdown (`--markdown`) + Dolma JSONL؛ هيكل الصفحة `PageResponse` (لغة أساسية، صلاحية الدوران وتصحيحه، is_table/is_diagram، النص الطبيعي)؛ معادلات→LaTeX، جداول→HTML، أشكال بتسمية تحمل إحداثيات تقريبية في الاسم؛ **لا bounding boxes حقيقية** ولا إخراج بكسلي؛ ترتيب قراءة طبيعي من VLM (يشمل multi-column).

### I. Handwriting
- موثق: «Read any natural handwriting» في كل prompts + README feature — **PROVEN كقدرة معلنة**.
- **validated Arabic clinical handwriting = UNPROVEN** — لا يوجد benchmark عربي أو فئة handwriting داخل olmOCR-Bench، ولا داخل المشروع حتى الآن. الحكم النهائي مؤجل لقياس Wave 3 على حزمة ذهبية.

### J. Network (تصنيف إلزامي)
| المكوّن | التصنيف |
|---|---|
| التثبيت (pip + فهرس PyTorch cu128 للنسخة المحلية) | **REQUIRED** (مرة واحدة) |
| تنزيل النموذج (HF hub) | **REQUIRED أولاً** ثم يُخزَّن — يتحول **OPTIONAL** مع مسار محلي أو Docker with-model |
| التشغيل المحلي بعد التخزين | **OPTIONAL/بلا شبكة** (لا استدعاء خارجي في مسار الاستدلال — فحص كود) |
| وضع remote `--server` | **REQUIRED** شبكة — ويخرّج الوثيقة من الجهاز ⇒ معطّل افتراضياً في أي تكامل |
| Telemetry في الاستدلال | **DISABLED (بغياب)**: لا analytics في `olmocr/` الاستدلالي؛ wandb فقط في `olmocr/train/` |
| S3/Beaker | **OPTIONAL** (بنية تحتية اختيارية) |

---

## 3 — Xberg: التحقق التفصيلي

### 3-A الهوية والنسخة
- **PROVEN**: «The fast, precise document-intelligence engine» — 107 صيغ/141 امتداداً/371 لغة برمجة/15 binding/6 صيغ إخراج (README). «Xberg is the next iteration of Kreuzberg» (README).
- الإصدار `1.2.6` متسق عبر: Cargo workspace، pyproject بايثون، PyPI، GitHub release (2026-09-20). نشاط يومي (HEAD قبل ساعة من الاستنساخ).

### 3-B الترخيص
- **PROVEN**: MIT — `LICENSE` (Kreuzberg, Inc. 2025-2026)، على Rust core وكل bindings. `unsafe_code = "deny"` في workspace.
- ملاحظة توثيقية بسيطة: جدول "Supported Versions" في `SECURITY.md` يذكر «5.x» — بقايا جدول قديم من عهد Kreuzberg لا يطابق سطر الإصدار 1.2.6 (تناقض توثيقي لا قانوني).

### 3-C الصيغ والقدرات
- **PROVEN**: PDF (pdf-native افتراضياً + pdfium اختياري)، Office/Excel/Email/Archives/SQLite/iWork/HWP/HEIC (features)، HTML/XML، صوت عبر Whisper ONNX (feature `transcription`)، code intelligence عبر tree-sitter.
- Layout/Tables: PP-DocLayout-V3 وRT-DETR (feature `layout-detection`)، TATR وSLANet للجداول (README) — **PROVEN** كقدرات معلنة في الكود.

### 3-D السؤال المعماري الأساسي: A أم B أم C؟
- الأدلة: Xberg يستهلك ملفات خام (PDF/DOCX/صور…) ويكتشف الصيغة ويستخرج ويوحّد الإخراج (طبقة استيعاب/استخراج = A)، **وفي الوقت نفسه** يضمّن باك-إندات OCR حقيقية قابلة للتبديل (Tesseract/PaddleOCR/Candle/VLM = قدرة محرك OCR داخل نفس الأداة).
- **الحكم: C — الاثنان معاً حسب input/backend.** لكن في معمارية هذا المشروع يُستخدَم **كسطح A فقط**: استيعاب الوثائق غير-PDF وتوحيد الاستخراج، بينما تبقى محركات OCR القائمة (ومنها OLMoCR مستقبلاً) في طبقة المحركات. مبدأ Master Prompt §8.2 «Xberg طبقة استيعاب/استخراج وليس محرك OCR» = **PARTIALLY_PROVEN**: صحيح كقرار معماري لحدود التكامل، غير صحيح كوصف مطلق للأداة (هي تحوي OCR فعلياً).

### 3-E OCR في Xberg — التفاصيل
- Tesseract: يتطلب **حزمة نظام** (`apt install tesseract-ocr`) + بيانات لغة منفصلة (`tesseract-ocr-ara` للعربية) أو تضمين `eng` وقت البناء (`bundle-tessdata-eng`) — `guides/ocr.mdx:89-133`.
- PaddleOCR: مضمّن native في العجلة (لا حزمة نظام) — `packages/python/README.md:109` «The wheel bundles the feature set for your platform — OCR (including PaddleOCR), layout detection, embeddings…».
- Candle (Rust خالص): TrOCR / PaddleOCR-VL / GLM-OCR / DeepSeek-OCR — ملاحظة توثيقية سابقة في تقرير Gemini عن TrOCR «line-level only، إخراج ضعيف على صفحات كاملة» لم تُتحقق مصدرها في هذه الجولة ⇒ تبقى **UNPROVEN** كادعاء.
- VLM: عبر liter-llm (مفتاح API) = استدلال بعيد اختياري.
- درجات ثقة: `OcrElement.confidence` + `PageContent.ocr_confidence` — **PROVEN** (بخلاف OLMoCR الذي لا يوفر ثقة قابلة للمقارنة).

### 3-F الإخراج
- **PROVEN**: 6 صيغ (text/markdown/djot/html/json tree/Docling DocTags) + renderers مخصصة. `ExtractedDocument` يوفر: content، metadata، tables، pages (PageContent مع layout_regions وocr_confidence)، ocr_elements بـgeometry وconfidence وrotation وpage_number، chunks، images، entities، formulas، form_fields، quality_score، processing_warnings. **bounding boxes حقيقية** — نقيض OLMoCR الذي لا يوفرها.

### 3-G الشبكة (تصنيف إلزامي)
| المكوّن | التصنيف |
|---|---|
| الاستخراج الأساسي (PDF/Office/HTML/بريد…) | **DISABLED** — «never makes outbound network requests» (SECURITY.md) + لا عميل HTTP في features الافتراضية |
| نماذج ML (OCR/تخطيط/embeddings/NER) | **OPTIONAL→REQUIRED عند التفعيل**: افتراضياً `allow_network=true` (تنزيل من HF)؛ air-gap: `allow_network=false` + `xberg warm`/`cache warm` مسبقاً |
| tessdata للـTesseract | **OPTIONAL**: بيانات النظام أو `bundle-tessdata-eng`؛ وإلا يُنزَّل وقتياً (`tessdata_download.rs`) |
| URL ingestion / crawl | **OPTIONAL** feature صريح (`url-ingestion`) — يُمنع في التكوين الطبي |
| VLM/LLM backends | **OPTIONAL** — remote بمفتاح API (يخرّج الوثيقة ⇒ معطّل افتراضياً) |
| Telemetry | **DISABLED**: وحدة telemetry = tracing/OTel/Prometheus محلية اختيارية (`otel`/`prometheus` features) — لا phone-home |

### 3-H الأمان
- **PROVEN** كنموذج تهديد موثق ومطبق: ZipBombValidator (100×/500MiB)، حد الملفات المضمّنة 50MiB، عمق أرشفة ≤3، timeout 60s، SecurityBudget (نمو نص 100MiB)، EntityValidator/DepthValidator (billion-laughs/1024)، حد خلايا 100k، حل مسارات ZIP عبر `std::path::Component` (لا substring)، تحذيرات DDE/`WEBSERVICE`، تخطي OLE التنفيذي، لا تنفيذ ماكرو، لا كسر تشفير المحمية (تُرجع خطأ).

---

## 4 — معمارية omni-medical-suite الحالية (من المستودع نفسه)

### 4-A ما هو موجود فعلاً
| المكوّن | الموقع | الحالة |
|---|---|---|
| `OCRResult` | `packages/omni_ocr/adapter.py:56-99` | موجود — dataclass صورة-أحادية: `text, confidence: float = 0.0, engine, word_count, processing_time, words[{text,confidence,x,y,w,h}], raw_result, error` |
| `UnifiedOCR` + `OCREngineID` | `packages/omni_ocr/adapter.py` | موجود — سلسلة fallback قابلة للتهيئة بـ`OCR_ENGINE_ORDER` + cache LRU(50)؛ المحركات: `mixed_engine, tesseract, mistral, easyocr` |
| `MixedLanguageOCR` | `packages/omni_ocr/mixed_engine.py` | موجود — TrOCR (`microsoft/trocr-base-handwritten`) + EasyOCR fallback + PatternDB؛ `WordResult` مع bbox ولغة |
| `EngineAdapter` + `EngineRegistry` | `packages/core/engine_registry.py:66-333` | موجود — عقد توفر صحي: `is_available()/healthcheck()/probe()` + adapters (EasyOCR/Tesseract/TrOCR/PaddleOCR/Qwen-handwritten/QARI/Nougat) |
| `EngineRouter` | `packages/core/engine_router.py:29-90` | موجود — profiles (low/balanced/high) + RAM + فلترة بالتوفر الفعلي |
| **`BaseOCREngine`** | — | **غير موجود** (grep سلبي على كامل `packages/`) |
| **`OCRPageResult`** | — | **غير موجود** |
| **`EngineProvenance`** | — | **غير موجود** |
| طبقة document-ingestion موحّدة | — | **غير موجودة** — ثلاثة مسارات متوازية: `file_processor` (تطبيق Streamlit)، `hf-space/app_core.py`، `doc_processor` (مهارات مُغلَّفة)؛ `omniparse` = كrawler مُغلَّف لويب/جداول |
| آلية تبعيات اختيارية | `pyproject.toml:43-111+` | **موجودة** — extras: `[core]/[ocr]/[nlp]/[search]/[ai]/[training]` + حراسة `try/except ImportError` و`_can_import()` وقت التشغيل |

### 4-B ملاحظات إضافية مثبتة
- `UnifiedOCR` غير مستهلك خارج `packages/omni_ocr` نفسها (grep: لا مستوردون) — أي أن الـadapter الموحّد لم يُوصَّل بعد بالتطبيقات.
- `EngineRouter` مستهلك فعلياً في `app/advanced_review_app.py` و`packages/scanner_fixer/.../pdf_ocr_processor.py`؛ وتوجد نسخة مكررة في `packages/file_processor/modules/core/engine_router.py` ومرآة `hf-space/packages/core` (نزاع تكرار معروف من Wave 1).
- `mistral` محرك cloud موجود في `OCREngineID` — سابقة لمزود بعيد داخل الواجهة، تُبرر إضافة مزود OLMoCR-remote بنفس النمط لاحقاً.

### 4-C إجابات Q1–Q7

**Q1 — أين يجب أن يعيش Xberg فعلياً؟**
حزمة جديدة معزولة `packages/omni_extraction/` (اسم مقترح؛ بدائل: `xberg_bridge`) — adapter اختياري حول عجلة `xberg`، **معطّل افتراضياً**، بلا دخول إلى `packages/omni_ocr/` ولا إلى registry المحركات (لأنه ليس محرك OCR في دورنا له). مساره: ملف ← `ExtractedDocument` (نص/markdown/جداول/صفحات) ← تغذية خط OCR أو خط ما بعد-OCR. يقرأ/يعدّل فقط ملفاته، ويظهر في provenance كطبقة استيعاب. (موقع Gemini المقترح `tools/xberg/ أو packages/omni_extraction/` = متوافق — اخترنا الباقي الثاني لأنه حزمة قابلة للاختبار في بنية packages القائمة).

**Q2 — أين يجب أن يعيش OLMoCR؟**
كمحرك خلف واجهة المحركات الحالية: adapter جديد (`OlmocrEngineAdapter`) يطبّق عقد `EngineAdapter` (`name/estimated_ram_gb/supported_tasks/is_available/healthcheck`) — يوضع في حزمة المحركات الاختيارية (مثل `packages/omni_ocr/olmocr_engine.py` أو حزمة `olmocr_engine` مستقلة) ويسجَّل في `EngineRegistry` عبر `register()` الموجودة أصلاً. يُنتج `OCRResult` (`text` = markdown/النص الطبيعي، `raw_result` = JSON الصفحة). وضعان: remote `--server` (خفيف — الأساس فقط) افتراضياً معطّل، وlocal GPU عبر extras مستقلة.

**Q3 — هل يوجد document-ingestion layer قابل لإعادة الاستخدام؟**
**لا** — مثبت بالبحث (§4-A). Xberg-adapter سيصبح أول طبقة استيعاب فعلية، ويجب ألا يُعاد بناؤها داخل `omni_ocr`.

**Q4 — هل يوجد provider abstraction؟**
جزئي: `EngineAdapter`/`EngineRegistry` = عقد توفر/صحة (يكفي لـOLMoCR)؛ `UnifiedOCR` = سلسلة fallback؛ `mistral` = سابقة cloud provider. لا يوجد abstraction موحّد لـ«provider» بمفهوم الموقع (محلي/بعيد) أو المفاتيح — توسيع additive مطلوب (Q7).

**Q5 — هل توجد آلية optional dependency؟**
**نعم** — pattern مثبت في المستودع: extras في `pyproject.toml` + `_can_import()`/try-except عند التشغيل (`engine_registry.py:232`) — يُطبَّق نفس النمط على `xberg` و`olmocr` (استيراد حرِس، فشل واضح عند الغياب لا سقوط صامت).

**Q6 — هل يستطيع `OCRResult` تمثيل إخراج OLMoCR دون breaking change؟**
**نعم مع نقطة واحدة**: `text` (النص/markdown)، `engine="olmocr"`، `word_count`، `processing_time`، `raw_result` (JSON `PageResponse` كامل) — كلها كافية دون كسر. النقطة: `confidence` حالياً `float = 0.0` و`0.0` تُفسَّر كفشل، بينما OLMoCR لا يوفر ثقة قابلة للمقارنة (و§7.2 يمنع اختراعها ⇒ يجب `None`). يتطلب توسعاً additive واحداً: `Optional[float]` أو حقلاً منفصلاً `confidence_provided: bool` — قرار تنفيذي مؤجل بعد موافقة المالك. boxes الكلمات: OLMoCR لا يوفرها ⇒ `words=[]` صحيح كما هو.

**Q7 — هل provenance الحالي يكفي أم يحتاج additive extension؟**
**يحتاج additive extension** — الحالي يغطي فقط «المحرك الفعلي» + زمن المعالجة. ينقص (مطلوب في §7.2): المحرك المطلوب، النموذج وإصداره، المزود، موقع التنفيذ (محلي/بعيد)، هل خرجت البيانات من الجهاز، هل دخلت dataset، fallback وسببه. كلها حقول جديدة بقيم افتراضية = غير كاسر للتوافق.

---

## 5 — تقرير Gemini: حكم على كل claim (ADVISORY)

| Claim في تقرير Gemini | الحكم | الأساس |
|---|---|---|
| Xberg ترخيص MIT، تجاري ✅ | **PROVEN** | LICENSE + Cargo/pyproject |
| «Xberg ليس محرك OCR بل طبقة استخراج وتوحيد» | **PARTIALLY_PROVEN** | صحيح كقرار حدود تكامل لنا؛ غير صحيح كوصف مطلق — الكود يحوي باك-إندات OCR فعلية (features `ocr/paddle/candle/sceptre/vlm`) ⇒ إجابة السؤال = C |
| 100+ صيغة | **PROVEN** | 107/141 موثقة في README ووصف crate |
| OCR عبر Tesseract/Paddle/Candle/VLM + fallback + confidence | **PROVEN** | features + docs + `.pyi` types |
| Layout: PP-DocLayout-V3, RT-DETR, TATR, SLANet | **PROVEN** | README + feature `layout-detection` |
| Whisper ONNX transcription | **PROVEN** (feature اختيارية) | README + Cargo features |
| 15 binding + library/CLI/REST/MCP | **PROVEN** | شارات PyPI/crates/npm/Maven… + أوامر CLI (extract/batch/serve/mcp/api/chunk/embed/doctor…) |
| Xberg offline ✅ | **PARTIALLY_PROVEN** | النواة offline حرفياً؛ لكن نماذج ML تُنزَّل افتراضياً (`allow_network=true`) — الـoffline الكامل يحتاج warm مسبق + `allow_network=false` + tessdata نظام/مضمن |
| «حجم النموذج صفر (محرك Rust)» | **PARTIALLY_PROVEN** | النواة native بلا نموذج، لكن OCR/التخطيط يستخدمون نماذج تنزَّل وقتياً؛ «CPU by default, no GPU required» = PROVEN |
| العربية عبر Paddle ⚠️/✅ | **UNPROVEN** (لمجالنا) | قدرة معلنة ≠ جودة مثبتة على وثائق طبية عربية — يحتاج قياس Wave 3 |
| الخط اليدوي عبر VLM ⚠️ | **PARTIALLY_PROVEN** (معلنة) / UNPROVEN (فعلياً) | TrOCR line-level ادعاء Gemini لم يُتحقق مصدره في هذه الجولة |
| Xberg يوحّد مخرجات محركات OCR: «OCR Engines → Xberg Extraction API → Unified JSON» | **CONTRADICTED** كنمط أساسي | إخراج Xberg الموحّد مشتق من استخراجه هو للملف الخام؛ استخدامه كمنسّق لمخرجات محركات خارجية ليس النمط الموثق ولا يستفيد من قيمته الأساسية. حد التكامل الصحيح: استيعاب قبل-OCR (Q1) |
| OLMoCR: جودة عربية «مخصصة (يتحقق)» | **UNPROVEN** | بطاقة النموذج `en` فقط؛ لا فئة عربية في bench |
| OLMoCR: ترخيص/تجاري «يتحقق» | **PROVEN** الآن | Apache-2.0 كامل السلسلة (كود+FP8+bf16+Qwen base) |
| OLMoCR layout/tables ✅ | **PROVEN** (معلنة) | prompts: جداول→HTML، معادلات→LaTeX؛ لا أرقام عربية |

---

## 6 — الخلاصة الرباعية + القرار

### VERIFIED FACTS (من المصدر الرسمي فقط)
1. olmocr v0.4.27 (2026-03-12)، نموذجه `allenai/olmOCR-2-7B-1025-FP8` (7B، Qwen2.5-VL base)، Apache-2.0 كامل السلسلة، GPU ≥12GB، vLLM محلي أو remote OpenAI-compatible، إخراج Markdown/JSONL بلا boxes، عربي/خط-يد غير مثبتين، لا telemetry استدلالي.
2. xberg 1.2.6 (2026-09-20)، MIT، Rust core (`unsafe deny`)، 107 صيغ، OCR اختياري متعدد الباك-إندات، إخراج 6 صيغ بboxes وconfidence، نواة بلا أي شبكة، أمان موثق (zip-bomb/traversal/timeout…)، عجلة بايثون بلا تبعيات.

### INFERENCES (من معمارية الكود)
- Xberg = طبقة استيعاب/استخراج في حدود مشروعنا (حزمة جديدة معزولة، default OFF).
- OLMoCR = محرك خلف `EngineAdapter`/`EngineRegistry` مع extras معزولة.
- `OCRResult` يكفي لتمثيل إخراج OLMoCR بتوسيع confidence فقط؛ provenance يحتاج توسيع additive واضح.

### UNPROVEN (يحتاج قياساً على الحزمة — Wave 3)
- جودة عربية مطبوعة (OLMoCR، xberg-Paddle، أي باك-إند).
- خط اليد العربي السريري (أي أداة).
- أداء Xberg/OLMoCR على وثائقنا الفعلية وأزمنة المعالجة على عتادنا.
- TrOCR-inside-Xberg «line-level only» (ادعاء Gemini غير مصدّر).

### CONTRADICTED
- نمط «OCR Engines → Xberg → Unified JSON» كتوصيف أساسي للتكامل (§5).
- أي رقم VRAM لـOLMoCR غير «≥12GB موثقة» (لا مصدر آخر).
- وصف Xberg كـ«محرك OCR متخصص» أو بديل عن محركات القائمة — والأوصاف المعاكسة المطلقة («ليس OCR إطلاقاً») كلاهما غير دقيق.

### DECISION (قرار معماري واحد)
- **Xberg boundary =** طبقة استيعاب/استخراج وثائق جديدة معزولة `packages/omni_extraction/` (عجلة `xberg>=1.2.6,<1.3`، default OFF، `allow_network=false` في التكوين الطبي، لا URL ingestion، SecurityLimits مضبوطة، ظهور في provenance chain) — لا يدخل `packages/omni_ocr/` ولا registry المحركات.
- **OLMoCR boundary =** محرك OCR اختياري خلف عقد `EngineAdapter` الموجود (adapter جديد + تسجيل في `EngineRegistry`، extras `[olmocr]` خفيف و`[olmocr-gpu]` معزولة، remote `--server` معطّل افتراضياً ببوابة صريحة، إخراج كـ`OCRResult` مع `raw_result`، strict selection بلا fallback صامت).
- الحالة: **بانتظار مراجعة المالك المعمارية قبل أي تنفيذ** — إن اعترض المالك على أي حد، يُسجَّل `DECISION REQUIRED` ويُعاد النقاش دون تنفيذ.

---

## 7 — المخاطر الخمسة الأعلى

| # | الخطر | الشدة | التخفيف |
|---|---|---|---|
| 1 | تعارض تبعيات olmocr[gpu] (`transformers==4.57.3` مثبّتة + vllm) مع extras القائمة (`nlp>=4.36`, `training>=4.40` بلا سقف) — قد يكسر تثبيتات حالية | عالية | ابدأ بوضع remote (أساس خفيف)؛ extras مستقلة تماماً؛ حسم بيئة/دقة النطاقات قبل أي تنفيذ |
| 2 | خروج وثائق سريرية من الجهاز (OLMoCR remote، xberg VLM/URL) | عالية جداً لو حدث | default OFF مزدوج + بوابة صريحة + حقل provenance `data_left_device` + سياسة §10 |
| 3 | ادعاء جودة عربية/خط-يد قبل القياس | عالية | كل القدرات تبقى UNPROVEN؛ لا routing إنتاجي حتى Wave 3 (CER/WER على حزمة ذهبية) |
| 4 | تنزيل نماذج xberg/OLMoCR من الشبكة افتراضياً في بيئة طبية | متوسطة | `allow_network=false` + `xberg warm` مسبق + نموذج olmocr محلي/Docker معزول |
| 5 | نشاط olmocr شبه متوقف (~6 أشهر) وتثبيت صارم لتبعياته | متوسطة | تثبيت نسخة كاملة في lockfile؛ مراقبة fork/إصدار أحدث قبل التنفيذ؛ عدم الربط بـHEAD متحرك |

## 8 — HUMAN ACTIONS (لا يوقف العمل الروتيني)
1. مراجعة هذا التقرير واعتماد/تعديل DECISION (§6) — شرط لأي Implementation Prompt لاحق.
2. توقيع قانوني نهائي على Apache-2.0 (olmOCR كود+نموذج) وMIT (xberg) — لا مانع مكتشف، لكن القرار للمالك.
3. بنود الموجات السابقة كما هي: تدوير التوكن الواسع (مؤجل بقرارك)، مراجعة/دمج PRs: suite #128→#129→#132→#133 و#130/#131/#131، وbot #2، وقرار sync-github وmalek_data.
4. عند الموافقة على التنفيذ: تحديد ترتيب Xberg-first ثم OLMoCR (وفق §8.3) وبيئة GPU المتاحة أو اعتماد remote.

## 9 — ما لم يُنفَّذ عمداً (DO NOT IMPLEMENT — محفوظ في هذا الفرع)
لا adapter لـXberg، لا `olmocr_engine.py`، لا تعديل `OCRResult`/`orchestrator`/`engine_registry`/`pyproject.toml`/`tests/`، لا إضافة `vllm`/`transformers`/`xberg` لأي تبعية، لا أي PR تنفيذية. هذا الفرع يضيف هذا الملف التوثيقي فقط.
