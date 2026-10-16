# Release Notes v1.0.0-rc1

**Version**: `v1.0.0-rc1`
**Date**: July 2026
**Status**: Release Candidate — stable beta for platform validation.

---

## Arabic (النسخة العربية)

### نظرة عامة
يسرنا الإعلان عن الإصدار التجريبي الأول للمنصة الموحدة **SmartTextETL v8 Ultimate**. هذا الإصدار يمثل نقلة نوعية من كونه مجرد "أداة معالجة نصوص" إلى كونه **منصة متكاملة** تجمع بين OCR، التصنيف الهجين، البحث الشعاعي (FAISS/Qdrant)، المراقبة، والمصادقة، مع واجهات تشغيل متعددة (Gradio UI، HF Space، REST API).

لقد ركزنا في هذا الإصدار على تثبيت البنية التحتية وفصل المكونات، مع الحفاظ على أعلى درجات المرونة للمطورين والمستخدمين النهائيين.

### الميزات الجديدة
- **منصة OCR موحدة**: دمج محركات متعددة (EasyOCR، Tesseract) مع آلية توجيه ذكية (`EngineRouter`) تختار المحرك الأنسب بناءً على لغة المدخلات وجودة الصورة وزمن التشغيل.
- **نظام مصادقة وصلاحيات (Auth & RBAC)**: تطبيق JWT بالكامل مع إدارة مستخدمين عبر قاعدة البيانات (PostgreSQL)، وإمكانية التحكم بالصلاحيات (Roles) للمسارات الحساسة.
- **إدارة المهام (Job Management)**: نقل نظام معالجة الدفعات من الذاكرة المؤقتة إلى Redis، مما يضمن استمرارية الحالة حتى مع تعدد العمال (Workers).
- **لوحة المراقبة (Monitoring)**: دمج كامل مع Prometheus و Grafana لتتبع أداء OCR، زمن المعالجة، ونسب النجاح.
- **واجهة المستخدم الإنتاجية**: إعادة العمل على `gradio_full_hitl.py` كواجهة رئيسية متكاملة تشمل: رفع الملفات، المعالجة المسبقة، التصحيح البشري، استخراج الكيانات (NER)، والحفظ في قاعدة البيانات.
- **التكامل مع Hugging Face Spaces**: توفير تشغيل تجريبي سريع للمنصة عبر HF Spaces.

### التحسينات التقنية
- **إعادة هيكلة الكود**: فصل واضح بين `app/` (التطبيق)، `src/` (المنطق الأساسي)، و `packages/` (المكتبات المشتركة).
- **إدارة الأسرار (Secrets)**: أصبحت جميع المفاتيح والبيانات الحساسة تُقرأ حصرًا من متغيرات البيئة، مع منع التشغيل في وضع الإنتاج حال فقدانها.
- **أمان الشبكة**: إغلاق المنافذ العامة (5432, 6379, 8000) خلف وكيل عكسي (Nginx) مع تطبيق `TrustedHostMiddleware` و `CORS` بقائمة مسموحة محددة.
- **تحسين OCR للغة العربية**: إضافة وحدة `rtl_utils.py` لمعالجة مشاكل إعادة تشكيل الحروف العربية الناتجة عن EasyOCR.
- **توحيد عقدة النص العربي**: إضافة دالة `canonicalize_arabic()` موحدة في `text_reconstructor.py` يعتمد عليها كل من `rtl_utils` و`text_reconstructor`.

### إصلاحات الأخطاء
- إزالة استخدام `eval()` الخطير واستبداله بمُفسّر شروط آمن (`safe_eval_condition`).
- إصلاح تسرب الذاكرة (Memory Leak) في رفع الملفات عبر تفعيل القراءة المتدفقة (Streaming) والتحقق الفعلي من حجم الملف.
- توحيد هيكلة قاعدة البيانات عبر Alembic وإلغاء الاعتماد على `create_all` في بدء التشغيل.
- إصلاح اختبارات Qdrant Fallback: إزالة `importorskip` من مستوى الملف، فصل اختبارات Fallback عن Integration.
- إصلاح `pyproject.toml`: استبدال self-referencing extras بقائمة مسطحة في `full`.

### المشاكل المعروفة
1. **التوحيد النهائي للنص العربي (RTL)**: تم حلها — دالة `canonicalize_arabic()` الموحدة تعمل، و 40 اختبار RTL يمرّ بنجاح.
2. **اختبارات مسار Fallback في Qdrant**: تم حلها — اختبارات Fallback تعمل بدون Qdrant (4/4 يمرّ).
3. **حالة Hugging Face Space**: النسخة العامة على الرابط المعلن في حالة Beta. تم تحديث الشارة من "Live" إلى "Beta" في README.

---

## English Version

### Overview
We are excited to announce the first Release Candidate of **SmartTextETL v8 Ultimate**. This release marks the transition from a "script-based tool" to a **unified platform** combining OCR, hybrid classification, FAISS/Qdrant search, monitoring, and authentication, with multiple runtime interfaces (Gradio UI, HF Space, REST API).

This RC focuses on infrastructure hardening, component decoupling, and developer experience.

### New Features
- **Unified OCR Platform**: Integrated multiple engines (EasyOCR, Tesseract) with an intelligent `EngineRouter` that selects the best engine based on language, image quality, and runtime health.
- **Authentication & RBAC**: Full JWT implementation with database-backed user management (PostgreSQL) and role-based access control for sensitive endpoints.
- **Job Management**: Migrated batch processing from in-memory to Redis-backed jobs, ensuring state persistence across multiple workers.
- **Monitoring Stack**: Fully integrated Prometheus & Grafana dashboards for OCR performance, latency tracking, and success rates.
- **Production UI**: Enhanced `gradio_full_hitl.py` as the primary interface, featuring upload, preprocessing, human correction, NER, and data persistence.
- **HuggingFace Integration**: Provided a lightweight deployment path for quick demos.

### Technical Improvements
- **Code Restructuring**: Clear separation between `app/` (application), `src/` (core logic), and `packages/` (shared libraries).
- **Secrets Management**: All sensitive keys are now strictly read from environment variables, with runtime guards preventing production startup if missing.
- **Network Hardening**: Closed public ports behind an Nginx reverse proxy, with `TrustedHostMiddleware` and strict `CORS` policies.
- **Arabic Language Support**: Added `rtl_utils.py` and unified `canonicalize_arabic()` contract for Arabic text normalization across the entire codebase.
- **Service Layer**: Extracted `OCRService`, `ReviewService`, `SearchService`, `ExportService`, and `HFDatasetService` from monolithic Gradio app.

### Bug Fixes
- Removed dangerous `eval()` and replaced it with a secure AST-based condition parser.
- Fixed memory leaks in file uploads by enforcing streaming reads and actual size validation.
- Standardized database migrations via Alembic, removing `create_all` from production startup.
- Fixed Qdrant fallback tests: removed module-level `importorskip`, separated fallback from integration tests.
- Fixed `pyproject.toml`: replaced self-referencing extras with flat list in `full` group.

### Known Issues
1. **Arabic RTL Normalization**: Resolved — unified `canonicalize_arabic()` contract is active, 40 RTL tests pass.
2. **Qdrant Fallback Tests**: Resolved — fallback tests run without Qdrant installed (4/4 pass).
3. **HF Space Status**: Public demo is in Beta. README badge updated from "Live" to "Beta".

---

### Quick Start
```bash
git clone --recursive https://github.com/DrAbdulmalek/omni-medical-suite.git
cd omni-medical-suite
cp .env.example .env
# Fill in required variables (DB_PASSWORD, JWT_SECRET_KEY)
pip install -r requirements/gradio.txt
python app/gradio_full_hitl.py
```

### Next Steps
This RC is the launch point. The next cycle will focus on the remaining items in OPEN_ISSUES.md, followed by `v1.0.0-rc2` and the final `v1.0.0` release.