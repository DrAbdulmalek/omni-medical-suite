# MERGE_TRACKING — جدول تتبع عمليات الدمج المتبقية

**تاريخ الجرد:** 2026-09-28 | **الأساس:** main @ `3631335f` (استنساخ حي + فحص فعلي)
**المنهجية:** `find` + `md5sum` + `cmp` على الشجرة الحالية لـ omni-medical-suite — لا أرقام مستعارة من تقارير وكلاء.
**السياق المعماري:** يخدم A2/A3/A5 (توحيد السطح، قياس منضبط، بلا انقسام مسارات) — القرارات الحاكمة في `QWEN_EXCHANGE_REVIEW.md`.

---

## 1) المكتمل (على main الآن — تحقق هذا اليوم)

| # | العنقود | الحالة على main @ 3631335 | الدليل (أمر منفذ) | PR | الحكم |
|---|---|---|---|---|---|
| C-1 | `ai_corrector.py` (5 نسخ → كنسية + 3 shims) | الكنسية `packages/nlp/ai_corrector.py` md5=`2f53a5ea` بلا تغيير؛ 3 شيمات تعيد التصدير فقط | `md5sum` + `grep 'Consolidation shim'` على الاستنساخ الحي | #129 (CLOSED؛ المحتوى على main — commit squash `0f1630b7` سلف لـ main وفق `compare main...0f1630b7 = behind`) | PROVEN |
| C-2 | إزالة كلمة مرور PostgreSQL المضمّنة (SEC-1) | grep المستودع كاملاً لا يجد `omni_dev_****` (استثناء `.git/`) | `grep -rn` على الاستنساخ الحي | #128 (MERGED، mergeCommit `60112cfb`) | PROVEN |
| C-3 | بوابة السحابة P0 + عزل الثقة المخترعة + provenance | main HEAD = `3631335f` (عنوان الـcommit يطابق موضوع #137) | `git log` + `gh pr view` | #137 (CLOSED؛ commit على main) | commit PROVEN — **التحقق التفصيلي لبنوده الثمانية (R1) لم يُنفذ بعد → UNPROVEN حتى مراجعة R1** |

> **ملاحظة حجب (‏`omni_dev_****`):** القيمة مكتوبة مُجزَّأة عمداً.
> `tests/security/test_no_embedded_default_credentials.py` يمسح **كل** ملف متتبَّع بحثاً عن
> `KNOWN_FORBIDDEN_DEFAULTS` ويستثني نفسه فقط (`DECLARED_FIXTURES`) — فكتابة الكلمة كاملةً
> في هذا الجدول، وهو السجل الذي يوثّق إزالتها، كانت تُبطل ادعاءه وتُشعل الحارس
> (‏`Production security regression gate` و`Unit Tests`).
> **القاعدة: لا تُكتب قيمة سرّ محظور حرفياً في أي وثيقة، ولا حتى لنفي وجودها.**

## 2) المتبقي — عناقيد التكرار المرشحة للدمج (جرد 2026-09-28 على main)

| # | الملف | النسخ على main (المسار + md5) | الهدف المقترح | المهمة/الفرع المخطط | العوائق | الحالة |
|---|---|---|---|---|---|---|
| R-1 | `arabic_rtl.py` | 5 نسخ متطابقة (`05b28e6b`): المرجع الحاكم `packages/nlp/arabic_rtl.py` (الفعلي على main — دليل الاستيراد الحي: `packages/vision/text_reconstructor.py:33` و`src/ocr/rtl_utils.py:15`) + `packages/omnifile/modules/nlp/` + `packages/handwriting/modules/nlp/` + `packages/file_processor/modules/nlp/` + `hf-space/packages/nlp/` (لقطة مولّدة) | المرجع T3 + shims موسومة `DeprecationWarning` | **T3** — `gs/t3-canonical-arabic-rtl` | فحص أنماط الاستيراد الفعلية قبل كتابة الشيمات (§5.T3)؛ lqta hf-space تتجدد بـ`sync-hf-space.sh` | مخططة (P1) |
| R-2 | `correction_dict.json` | 10 نسخ بمجموعتين: `e6eb3df8` ×6 (modules/nlp عبر الحزم + hf-space + apps variant) و`3347a55b` ×4 (artifacts: handwriting، file_processor، file_processor/legacy، apps variant) | مرجع واحد (T4: `packages/config/correction_dict.json` أو مسار التحميل المثبت) | **T4** — `gs/t4-canonical-corrections` | diff مفاتيح JSON بين المجموعتين أولاً → اندماج شامل → إثبات مسار التحميل الحي | مخططة (P1) |
| R-3 | `text_reconstructor.py` | 5 نسخ بمجموعتين منحرفتين: `06adc5f8` (packages/vision + hf-space لقطة) و`b7441a8b` (handwriting/file_processor/omnifile modules/vision) | يُحدد بعد مقارنة المجموعتين | غير مُسندة (نمط T2/T3) | **انحراف مثبت بين المجموعتين** — ممنوع الدمج الأعمى قبل diff وظيفي | بانتظار مقارنة |
| R-4 | `mixed_text.py` | 5 نسخ متطابقة (`c4637d74`) — نفس نمط R-1 | `packages/nlp/mixed_text.py` (أو المرجع المثبت وقت التنفيذ) | غير مُسندة (يُقترح ضمّها لفرع T3 أو PR بنفس النمط) | لا يوجد جوهري | جاهزة للجدولة |
| R-5 | `api_server.py` | 4 نسخ: `c3747888` ×2 (packages/core + hf-space لقطة) و`7af3357d` (legacy/) و`8d5f14dc` (apps/ocr-pipeline/) | `packages/core/api_server.py` | غير مُسندة (P3) | النسختان المنحرفتان قد تحملان قدرات فريدة — مقارنة محتوى إلزامية؛ قرار legacy (shim/أرشفة) | بانتظار مقارنة |
| R-6 | `surya_ocr.py` | نسختان متطابقتان (`44b76ce8`): packages/vision + hf-space لقطة | `packages/vision/surya_ocr.py` | غير مُسندة (نمط T2) | لا يوجد جوهري | جاهزة للجدولة |
| R-7 | `engine_registry.py` | نسختان متطابقتان (`58201f33`): packages/core + hf-space لقطة | `packages/core/engine_registry.py` | غير مُسندة (نمط T2) | لا يوجد جوهري | جاهزة للجدولة |
| R-8 | `deploy_space.py` | نسختان منحرفتان داخل المستودع: hf-space (`5ad0e2b7`) وapps/ocr-demo (`7923e2a4`) | يُحدد بعد المقارنة | غير مُسندة (P3) | انحراف مثبت؛ نسخة مطابقة لنسخة hf-space موجودة في مستودع `medical-ocr-demo` المستقل (خارج نطاق هذا المستودع) | بانتظار مقارنة |
| R-9 | `rtl_utils.py` | نسختان متطابقتان (`6f3a951b`): src/ocr + hf-space/src/ocr لقطة | `src/ocr/rtl_utils.py` | غير مُسندة (نمط بسيط) | لا يوجد جوهري | جاهزة للجدولة |

## 3) تدقيق أرقام المرجع الخارجي (R4)

| الملف | ادعاء Z.ai (محلي) | جرد 2026-09-28 | الحكم |
|---|---|---|---|
| `arabic_rtl.py` | 5 | 5 | PROVEN (مطابق) |
| `correction_dict.json` | 10 | 10 | PROVEN (مطابق) |
| `text_reconstructor.py` | 5 | 5 | PROVEN (مطابق) — **لكن بإنحراف محتوى بين مجموعتين لم يذكره المرجع** |
| `mixed_text.py` | 5 | 5 | PROVEN (مطابق) |
| `rtl_utils.py` | 2 | 2 | PROVEN (مطابق) |

## 4) ترتيب التنفيذ المقترح (أولوية)

1. **T1** (`gs/t1-fixed-arabic-testset`) — مجموعة الاختبار العربية + harness المعيار الذهبي — أولوية P1، تسبق أي دمج لاحق لأنها البوابة القياسية (A3/A5).
2. **T3** (R-1) و**T4** (R-2) — العنقودان المخططان في البرومبت الحاكم.
3. R-3 (مقارنة المجموعتين) ثم R-5/R-8 (مقارنات المحتوى) — لا shim قبل الحسم.
4. R-4/R-6/R-7/R-9 — النمط البسيط (نسخ متطابقة) — PRs صغيرة منفصلة.
5. **T2** — توحيد السطح على `packages/omni_ocr` بعد استقرار العناقيد أعلاه.

## 5) قواعد ثابتة لكل صف يُنفذ

- فرع `gs/<task-id>-<slug>` + PR واحد < 300 سطر، Conventional Commits.
- الكنسية لا تُمس أثناء كتابة الشيمات؛ اختبار استيراد يغطي كل shim.
- فحص أسرار §3.6 قبل كل commit؛ `hf-space/` لقطة تتجدد — لا تعديل يدوي دائم فيها.
- وسم كل صف بعد التنفيذ: `PROVEN` (اختبارات منفذة + remote HEAD مطابق) في هذا الملف نفسه.
