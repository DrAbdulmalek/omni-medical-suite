# ROADMAP.md — خارطة طريق Omni Medical Suite

> آخر تحديث: 2026-07-18

---

## الإنجازات المكتملة (v1.0.0-rc1)

### البنية التحتية
- [x] مستودع موحد omni-medical-suite (275+ commit)
- [x] فصل القواميس إلى omni-medical-dictionaries
- [x] تنظيف الاستيرادات: صفر كسر (data-prep→data_prep, omni-ocr→omni_ocr)
- [x] فروع احتياطية: backup/lost-monorepo-work, backup/current-main-dictionaries
- [x] CI/CD: GitHub Actions + Dependabot

### OCR والمعالجة
- [x] OCR Ensemble (Tesseract + EasyOCR + PaddleOCR + TrOCR)
- [x] HybridSpellChecker + Jais LLM proofreading
- [x] NER طبي عربي + حقل مستخرج
- [x] RTL fixer + Arabic field extractor
- [x] engine_router + engine_registry (runtime-aware)
- [x] DeduplicationPipeline (RTL→Field→Dedup + confidence scoring)

### scanner_fixer
- [x] pipeline: crop → deskew → rotate → enhance
- [x] normalize: full normalization + canvas fitting
- [x] dedup: phash clustering + CSV report
- [x] batch_pipeline: parallel processing + previews + manifest + quarantine
- [x] CLI: scanner-fixer command-line tool
- [x] تكامل Gradio: Before/After + Batch + PDF + ZIP + Random Preview
- [x] تكامل Desktop: deskew + crop + normalize + dedup مع fallback

### واجهات المستخدم
- [x] gradio_full_hitl.py — 10 وظائف إنتاجية
- [x] advanced_review_app.py — 6 تبويبات متكاملة مع scanner_fixer
- [x] medical_doc_gui_final.py — Desktop PySide6 (3231 سطر)
- [x] PyInstaller ELF build script
- [x] AppImage build script (Manjaro)

### التدريب والبيانات
- [x] Handwriting Trainer HF Space
- [x] Training data collection + active learning
- [x] Fine-tuning scripts (TrOCR/Qwen2-VL)
- [x] Medical OCR benchmarks + ground truth

---

## الخطوات التالية (v1.1.0)

### أولوية عالية
- [ ] **اختبار تكاملي شامل**: تشغيل advanced_review_app.py مع صور حقيقية
- [ ] **AppImage فعلي**: بناء واختبار AppImage على مانجارو حقيقي
- [ ] **أمان الرموز**: إبطال PAT المُكشوف واستبداله بـ fine-grained token
- [ ] **CI pipeline**: إضافة pytest + import audit إلى GitHub Actions

### أولوية متوسطة
- [ ] **Ollama + Llama 3.3**: أتمتة GitHub محلية (من اقتراح Kimi)
- [ ] **Manjaro PKGBUILD**: حزمة AUR لـ medical-doc-processor
- [ ] **Docker Compose production**: نشر متعدد الخدمات
- [ ] **Performance benchmarks**: قياس زمن المعالجة لكل مرحلة

### أولوية منخفضة
- [ ] **Wayland native**: دعم كامل لـ Qt6 Wayland
- [ ] **Mobile companion**: تطبيق مرافق للهاتف (تصوير → رفع → معالجة)
- [ ] **i18n**: ترجمة الواجهة لـ English + Deutsch
- [ ] **Plugin system**: بنية إضافات لـ OCR engines

---

## الإصدارات

| الإصدار | الحالة | التاريخ |
|---|---|---|
| v1.0.0-rc1 | ✅ مستقر | 2026-07-16 |
| v1.1.0 | 🔜 قادم | TBD |
