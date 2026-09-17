# SESSION ARTIFACTS POLICY — قاعدة الحفظ الدائم لأصول كل جلسة

> Status: **MANDATORY / PERMANENT** — سارية على كل جلسة قادمة على أي فرع.
> Established: 2026-09-17, by owner directive (بعد فقد أصول بين جلستين).
> Enforcement: `scripts/verify_session_artifacts.py` + `docs/SESSION_ARTIFACTS_LEDGER.md`.

## 0. سبب وجود هذه السياسة (سجل الحوادث — أرشيفي)

بيئة العمل تُعاد ضبطها دوريًا (environment resets)، وكل ما لم يُلتزم في Git يُفقد.
الحوادث الموثقة حتى تاريخه:

| # | الحادثة | ما فُقد |
|---|---------|---------|
| 1 | Reset بعد SESSION-14/15 | عمل الجلستين (وثّقته SESSION-16) |
| 2 | فقد الـ clone المحلي وقت AHW-01-RECON-GATE | النسخة المحلية للمستودع |
| 3 | Reset #4 (قبل SESSION-21) | commits AHW-02 الأصلية الثلاثة `7319bc9` / `6e89c7b` / `05b56f2` (branch-local، لم تُرفع) + مرايا `download/ahw02/` + ملفات الإثبات داخل الجلسة |
| 4 | بعد SESSION-21 | أدلة الإثبات (`ahw02_recon_*.json`, سكربتات الفحص والمقارنة, chain smoke) كانت "run artifacts" غير مُلتزمة — أُزيلت من القرص بينما التقرير §K.2/§K.5/§K.6 يشير إليها |

الدرس: **أي أصل غير مُلتزم في Git = أصل غير موجود.**

## 1. القواعد الملزمة

1. **قاعدة الالتزام الإلزامي (Commit-or-it-didn't-happen):** كل جلسة **يجب** أن تلتزم
   (branch-local commit) جميع أصول الإثبات التي أنتجتها قبل انتهائها: التقارير،
   ملفات نتائج الفحوصات (JSON)، سكربتات الفحص/المقارنة/الـ smoke نفسها، مخرجاتها،
   وقرارات التوثيق. لا يُسمح بترك أي أصل إثبات كـ "run artifact" عابر.
2. **قاعدة السجل (Ledger):** كل أصل يُسجَّل بصف في `docs/SESSION_ARTIFACTS_LEDGER.md`
   يضم: الجلسة، المسار، **sha256 كامل**، و**SHA الكامل للـ commit الحاوي له**.
3. **قاعدة التحقق الآلي:** قبل إنهاء أي جلسة يُشغَّل
   `python scripts/verify_session_artifacts.py` ويجب أن ينتهي بـ `PASS` (exit 0).
   مخرجاته تُلصق في `worklog.md` كإثبات إغلاق.
4. **قاعدة Append-only:** السجل append-only — يُمنع حذف أو تعديل صف موجود. تصحيح
   خطأ = صف جديد يشير إلى القديم. لا `amend` / `rebase` / `force` على الفروع العاملة.
5. **قاعدة الأولوية:** النسخة الملزَمة داخل Git هي المرجع القانوني؛ مرايا
   `/home/z/my-project/download/` نسخ عرض ثانوية تُحدَّث منها.
6. **قاعدة النطاق:** الالتزام يكون على فرع العمل المرخَّص فقط — لا push ولا merge
   ولا لمس `main` إلا بترخيص صريح من المالك؛ هذه السياسة لا تعدل أي إذن.
7. **قاعدة القراءة الأولى:** كل جلسة/وكيل يقرأ `worklog.md` أولًا، ويقرأ هذه
   السياسة، ثم يحدد في أول إدخال له أنه عِلم بقاعدة الحفظ الدائم.

## 2. إجراء الإغلاق القياسي لكل جلسة (Checklist)

> **التسلسل القانوني للإغلاق (SESSION CLOSE) — ملزم حرفيًا وبالترتيب:**
>
> **TEST → ARTIFACTS → COMMIT → VERIFY → PUSH → VERIFY REMOTE → RECORD SHA → CLEAN WORKTREE**

```
[ ] 1. كل الأصول الإثباتية مكتوبة تحت مسارات مُلتزَمة داخل المستودع
        (docs/… أو scripts/… أو evidence/) وليس فقط في مجلدات عابرة.
[ ] 2. إضافة صف لكل أصل جديد في docs/SESSION_ARTIFACTS_LEDGER.md
        (المسار + sha256 الكامل + commit الحاوي).
[ ] 3. git commit محلي على فرع العمل (رسالة توضح نوع الأصل).
[ ] 4. تحديث صف الـ commit في السجل بعد معرفة الـ SHA النهائية
        (commit إغلاق أخير إذا لزم).
[ ] 5. تشغيل scripts/verify_session_artifacts.py → يجب PASS، ولصق المخرجات في worklog.md.
[ ] 6. PUSH لفرع العمل إلى remote (push عادي فقط — لا force، لا main) —
        الجلسة ليست منتهية قبل أن ينجح الـ push.
[ ] 7. VERIFY REMOTE: إثبات أن remote HEAD == local HEAD
        (git ls-remote أو GitHub API) وأن الأصول موجودة في remote tree.
[ ] 8. RECORD SHA: تسجيل SHA النهائي لرأس الفرع في worklog.md ورسالة
        الإغلاق للمالك (قاعدة §3).
[ ] 9. CLEAN WORKTREE: git status نظيف، لا uncommitted ولا untracked.
[ ] 10. تحديث مرايا download/ من الملفات الملتزَمة.
[ ] 11. إدخال worklog (Task ID + Work Log + Stage Summary) يذكر التزام الأصول والـ push.
```

## 3. ملاحظة على الـ self-reference

لا يمكن لملف أن يسجّل SHA الـ commit الحاوي له قبل إنشائه؛ لذلك يُسمح بصف مؤقت
بدون SHA يُستكمل في **commit إغلاق لاحق** (ليس amend)، أو يُسجَّل SHA الـ commit
الأخير في `worklog.md` ورسالة الإغلاق للمالك. `git log` يبقى المصدر الأعلى.

## 4. قاعدة الجدوى الدائمة (PERSISTENCE RULE)

> **«UNPUSHED WORK IS NOT PERSISTED WORK»**
> لا يوجد عمل "منجز" ما لم يصبح محفوظًا في Git remote ويمكن استعادته من fresh clone.

- commit محلي بلا push = عمل معرض للفقد عند أي إعادة ضبط للبيئة — **لا يُعتبر حفظًا**.
- إثبات الحفظ الوحيد المقبول: remote HEAD == local HEAD **و** استعادة ناجحة من
  fresh clone تعيد إنتاج نتائج الـ verifier نفسها.
- سابقة التطبيق (PERSISTENCE GATE، 2026-09-17): الفرع
  `feat/ahw-02-controlled-handwriting-ocr` رُفع بالكامل إلى remote، وHEAD =
  `4bc4ba4d43ae5bea8a535a64809a5abbc21dee2f` (+ كل commit تالٍ يحدَّث SHA في
  worklog)، وأُثبتت الاستعادة عبر fresh clone بنتيجة verifier مطابقة (14/14 PASS).
