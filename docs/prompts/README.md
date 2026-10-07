# docs/prompts — عقود التنفيذ والبرومبتات المؤرشفة (محادثة DeepSeek 2873vzbqibqh1ihe31)

برومبتات "Master Prompt" وعقود تدقيق أُنشئت في المحادثة لتُعطى لوكلاء
منفذين (Z.ai/genspark/Qwen). **حالتها: مؤرشفة للاستخدام عند الطلب** —
لم تُنفذ جميعها، وكل عقد يتضمن بوابات توقف خاصة به.

> **ملاحظة هامة (تدقيق 2026-10-08):** عدة عقود هنا تقترح بناء
> `omni-ocr-core` مركزي — هذا **موجود فعليًا** باسم
> [`ocr-core`](https://github.com/DrAbdulmalek/ocr-core)
> (‏`marathon-ocr-core` v0.7.0+: 34 أمرًا، محركات، ميثاق 18 قاعدة،
> كشف كلمات، jina-vlm). عند تنفيذ C-00/C-01 أو "omni-ocr-core Phase 1"
> يجب توجيهها إلى ocr-core القائم لا إنشاء مستودع موازٍ.
> وكذلك jina-ocr-v1 (JOCR-01): **مدمج مسبقًا** في ocr-core
> ‏(`engines/jina_vlm.py` + `[jina]` extra).

| العقد/البرومبت | الموضوع | الحالة |
|---|---|---|
| `AHW-01-master-prompt-v2.md` | تدريب OCR خط يدوي عربي ذاتي التعلم (omni-medical-suite) | جاهز للتنفيذ عبر وكيل |
| `JOCR-01-jina-integration-audit.md` | تدقيق دمج jina-ocr-v1 | ✅ تجاوزه التنفيذ الفعلي في ocr-core |
| `OCR-CR-opencodereview-analysis.md` | تحليل Alibaba OpenCodeReview | دراسة |
| `OCR-CR-01-executive-contract.md` | عقد اعتماد OpenCodeReview (بوابات 1-7) | جاهز — لم يُعتمد بعد |
| `opencodereview-rule.json` | قاعدة مراجعة OCR جاهزة للأداة | مرتبطة بـ OCR-CR-01 |
| `XB-01-xberg-forensic-audit.md` | تدقيق Xberg (Rust doc-intelligence) + معمارية + خطة benchmark | STUDY ONLY (قرار المحادثة) |
| `ARCH-07-final-architecture-package.md` | الحزمة المعمارية النهائية | مرجع |
| `M-00-multi-project-integration.md` | دمج 4 مشاريع خارجية (بوابات) | مرجع |
| `ATR-acceptance-criteria.md` | معايير قبول هندسية (ATR-02/05/06) | مرجع |
| `VPS-future-plan-documentation.md` | مهمة توثيق خطة VPS | → docs/future/ |
| `DOC-01-docling-forensic-audit.md` | تدقيق Docling ("ضيف لا مضيف") | STUDY ONLY |
| `C-00-ocr-consolidation-preflight.md` | توحيد OCR — pre-flight | ✅ تجاوزه ocr-core القائم |
| `C-01-inventory-conflict-formats.md` | صيغ تقارير الجرد/التعارضات | صالحة لأي توحيد مستقبلي |
| `omni-ocr-core-phase1-master-prompt.md` | Phase 1/8 لبناء omni-ocr-core | ⚠️ وجّهها إلى ocr-core القائم |
