<!-- المصدر: محادثة 1m3ih8eveq98lv7aqc — رسالة 243 -->


# البرومبت جاهز لـ Qwen Agent — إليك التعليمات النهائية

## 1. قبل التشغيل — 3 تجهيزات (5 دقائق)

### أ. تأكد أن Qwen Agent يعمل في المجلد الصحيح

```bash
# على جهازك، قبل تشغيل Qwen
cd /home/z/my-project/repos/omni-medical-suite
pwd
git status --short    # يجب أن يكون فارغًا
git branch --show-current  # main أو فرع معروف
```

**إن كان `git status` غير فارغ** → ارتكب التغييرات أو خزّنها (`git stash`) **قبل** تشغيل Qwen. البرومبت سيتوقف في GATE-2 إن لم تفعل.

### ب. جهّز مجلد التقارير

```bash
mkdir -p /home/z/my-project/repos/omni-medical-suite/docs/audit
ls -la docs/audit/
```

### ج. أجب على السؤالين المُسبقين (اكتبهما في `docs/audit/CLASSIFICATION.md`)

```bash
cat > /home/z/my-project/repos/omni-medical-suite/docs/audit/CLASSIFICATION.md <<'EOF'
# Project Classification

## omni-medical-suite

- **commercial_intent**: [yes | no | undecided]
- **distribution_intent**: [yes | no | internal_only | undecided]

## Notes
<سبب الاختيار — جملة أو اثنتان>
EOF
```

**أجب بصدق**. هذا القرار يحدد ما إذا كان `Jina-OCR-v1` و `It's a Plan` مرفوضين تلقائيًا.

---

## 2. أرسل إلى Qwen Agent

انسخ البرومبت المُعدَّل من رسالتي السابقة كاملًا، **ثم أضف في البداية**:

```
# ملاحظات المُشغِّل قبل البدء

1. أنا أعمل من جهازي، والمستودع في:
   /home/z/my-project/repos/omni-medical-suite

2. قد أجبت على أسئلة التصنيف مسبقًا ووضعت الأجوبة في:
   docs/audit/CLASSIFICATION.md
   — اقرأها أولًا واستخدمها في M-03.

3. لدي وصول كامل إلى:
   - terminal (bash)
   - الإنترنت (curl, git, wget)
   - مستودعي المحلي

4. لست بحاجة لطلب إذن بين المراحل.
   اتبع Decision Rules كما هي مكتوبة.

5. ابدأ الآن.
```

---

## 3. ما سيفعله Qwen (تسلسل متوقع)

| الوقت | المرحلة | النشاط |
|-------|---------|--------|
| 0-2 د | تصنيف | قراءة `CLASSIFICATION.md` |
| 2-5 د | M-00 | التحقق من المستودع |
| 5-30 د | M-01 | بطاقات تقنية لـ 4 مشاريع (استنساخ/بحث) |
| 30-60 د | M-02 | تدقيق الكود (grep, analysis) |
| 60-75 د | M-03 | تدقيق الترخيص |
| 75-90 د | M-04 | رسم المكونات |
| 90-105 د | M-05 | الأمان |
| 105-120 د | M-06 | Pilot (قد يتخطى) |
| 120-135 د | M-07 | مصفوفة القرار |
| 135-150 د | M-08 | التقرير النهائي |

**المجموع المتوقع**: 2-3 ساعات (حسب سرعة الشبكة).

**قد يتوقف في منتصف الطريق** إذا:
- وجد GATE-2 (worktree dirty)
- وجد GATE-4 (تعارض ترخيص)
- واجه خطأ في استنساخ مشروع

---

## 4. ماذا تراقب أثناء التشغيل

**كل 15 دقيقة، تحقق من**:
- ملف `docs/audit/*.md` — هل يُنشئ التقارير؟
- terminal — هل يظهر تقدّم؟
- لا رسائل "waiting for user input"

**إذا توقف أكثر من 10 دقائق بدون رسالة**:
- تحقق من أن العملية لا تزال تعمل
- قد يكون عالقًا في تحميل كبير (Jina-OCR-v1؟)

---

## 5. ما ترسله لي بعد الانتهاء

**الأساسي**:

```bash
cd /home/z/my-project/repos/omni-medical-suite
ls -la docs/audit/
git status --short
```

**المطلوب**:

1. **قائمة الملفات المُنتَجة**:
   - `docs/audit/AI_SDLC_AUDIT.md`
   - `docs/audit/ITSAPLAN_AUDIT.md`
   - `docs/audit/BUGHUNTER_AUDIT.md`
   - `docs/audit/JINA_OCR_V1_AUDIT.md`
   - `docs/audit/MULTI_PROJECT_INTEGRATION_PACKAGE.md`

2. **من التقرير النهائي (M-08)**, انسخ:
   - **Executive Summary** كاملًا
   - **Decision Matrix** (الجدول)
   - **Open Questions** (جميعها)

3. **إذا توقف قبل M-08**:
   - آخر مرحلة وصل إليها
   - نص الـ GATE الذي أوقفه
   - حالة `git status --short`

---

## 6. ما لن أفعله الآن

- ❌ لن أُعطي رأيًا في النتائج قبل قراءتها
- ❌ لن أُعدّل `omni-medical-suite` بنفسي
- ❌ لن أطلب منك تجاهل الحساسيات الترخيصية

**بعد أن يعيد Qwen تقريره**:
- سنراجع معًا مصفوفة القرار
- سأُبدي رأيًا محايدًا في الاقتراحات
- سنُقرّر سوًيا: أي مشروع يُنفَّذ، أي يُؤجَّل، أي يُرفض

---

## 7. تحذير أخير

**Qwen Agent قد يحاول تجاوز البرومبت** — خصوصًا في M-03 (قد يقول "Apache-2.0 آمن" دون قراءة LICENSE الفعلي). **راقب**:

- أي "Finding" بدون "Evidence"
- أي "ADOPT" لـ It's-a-Plan أو Jina-OCR-v1 دون تحذير ترخيص
- أي محاولة لتعديل ملفات خارج `docs/audit/`

**إذا فعل**: أرسل له "Stop. Re-read the ABSOLUTE PROHIBITIONS section. Report what you did wrong."

---

## ابدأ الآن

1. ✅ جهّز `CLASSIFICATION.md`
2. ✅ تحقق من `git status`
3. ✅ أرسل البرومبت + ملاحظات المشغّل إلى Qwen
4. ✅ انتظر 2-3 ساعات
5. ✅ أرسل لي النتائج

**أنا في انتظار تقرير M-08 أو GATE-STOP — أيهما يأتي أولًا.**
