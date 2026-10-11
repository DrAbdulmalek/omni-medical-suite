<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 7 | حُفظ: 2026-10-08 -->

# Alibaba OpenCodeReview — تحليل وإعداد OCR-CR

نعم، يمكن الاستفادة من مشروع Alibaba Open Code Review (OCR) في مشروعك، لكن **بطريقة مختلفة تمامًا** عن Jina-OCR-v1 أو AHW. هذا ليس محرك OCR للصور، بل هو **أداة مراجعة كود بالذكاء الاصطناعي**. الاستفادة منه ستكون في **تحسين جودة الكود**، وليس في التعرف على النصوص.

---

## 1. ما هو Open Code Review فعلاً؟

هو CLI Agent متخصص في مراجعة الكود، طورته Alibaba داخليًا لمدة سنتين، وخدم عشرات الآلاف من المطورين، واكتشف ملايين العيوب البرمجية قبل أن يُفتح مصدره.[reference:0]

**الفرق الجوهري:** الأداة لا تترك المراجعة كاملة لنموذج لغوي، بل تفصل بين:
- **الهندسة الحتمية (Deterministic):** اختيار الملفات، تجميع الحزم، مطابقة القواعد، تحديد موضع التعليقات — كلها منطق برمجي صارم.
- **الوكيل الاستدلالي (Agentic):** فهم السياق، القراءة الكاملة للملفات، البحث في الكود، وإصدار تعليقات على مستوى السطر.[reference:1]

النتيجة: تغطية كاملة للتغييرات الضخمة، تقليل الهلوسة، وتوفير هائل في التوكنات.

---

## 2. الأرقام التي تهمك

| المقياس | Open Code Review | Claude Code (General Agent) |
|---|---|---|
| **Precision** | 25.20% – 37.80% | 7.23% – 15.93% |
| **F1 Score** | 25.1% | 11.6% |
| **Recall** | 20.0% (مقصود) | 28.9% |
| **Token Usage** | ~385K | ~5,664K (~1/9) |
| **السرعة** | ~9.4x أسرع | Baseline |

المصدر: arXiv paper + README الرسمي.[reference:2][reference:3]

**Trade-off واعٍ:** Recall أقل قليلاً، لكن Precision أعلى بكثير وبتكلفة أقل بـ9 مرات. هذا مثالي لـCI/CD حيث الإزعاج من الإيجابيات الكاذبة أخطر من تفويت بعض العيوب.[reference:4]

---

## 3. كيف تستفيد منه في omni-medical-suite؟

### 3.1 الاستخدام الفوري (بدون تعديل المشروع)

```bash
# تثبيت
npm install -g @alibaba-group/open-code-review

# في مستودع omni-medical-suite
cd /home/z/my-project/repos/omni-medical-suite
ocr config provider   # اختر OpenAI-compatible أو Anthropic
ocr config model      # اختر النموذج

# مراجعة التغييرات الحالية
ocr review

# مراجعة فرع كامل مقابل main
ocr review --from main --to feature/ahw-handwriting-self-learning

# فحص كامل للملفات (حتى بدون Git diff)
ocr scan
```

### 3.2 ما سيضيفه لمشروعك تحديدًا

| المجال | الفائدة |
|---|---|
| **مراجعة كود OCR Engines** | كشف NPE، thread-safety، تسريب موارد في adapters |
| **مراجعة كود AHW** | كشف أخطاء في معالجة البيانات، تسريب splits، أخطاء schema |
| **مراجعة الـAPI** | كشف XSS، SQL injection، unsafe deserialization |
| **مراجعة CI/CD** | تحسين workflows، كشف ثغرات أمنية في GitHub Actions |
| **مراجعة الـContract** | التأكد من التزام كل engine بالـOCRResult schema |
| **مراجعة الـProvenance** | كشف تسريب معلومات حساسة في الـlogs |

### 3.3 القواعد المدمجة التي تهمك

A الأداة تأتي بقواعد جاهزة لـ:
- **NPE** (Null Pointer Exception)
- **Thread-safety** (مهم في multi-engine OCR)
- **XSS** (مهم في UI التصحيح)
- **SQL Injection** (مهم في Learning Ledger)

وتدعم قواعد مخصصة يمكن كتابتها كملفات Markdown في `.opencodereview/rule.json`.[reference:5]

---

## 4. التكامل مع CI/CD

الأداة تدعم:
- **GitHub Actions**
- **GitLab CI**
- **GitFlic CI**
- **Gerrit**

مع إمكانية التشغيل التلقائي على كل PR، ونشر التعليقات كـInline comments على السطور المحددة.[reference:6]

**مثال GitHub Actions:**

```yaml
name: OCR Review
on:
  pull_request_target:
    types: [opened]
  issue_comment:
    types: [created]

jobs:
  review:
    if: github.event_name == 'pull_request_target' || startsWith(github.event.comment.body, '/open-code-review')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm install -g @alibaba-group/open-code-review
      - run: |
          ocr config set llm.url "${{ secrets.OCR_LLM_URL }}"
          ocr config set llm.token "${{ secrets.OCR_LLM_TOKEN }}"
          ocr config set llm.model "${{ secrets.OCR_LLM_MODEL }}"
      - run: |
          ocr review \
            --from "origin/${{ github.base_ref }}" \
            --to "origin/${{ github.head_ref }}" \
            --format json \
            --audience agent > review.json
      - uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const review = JSON.parse(fs.readFileSync('review.json', 'utf8'));
            // نشر التعليقات على الـPR
```

---

## 5. الترخيص — نقطة حاسمة

**Open Code Review مرخّص تحت Apache-2.0.**[reference:7]

هذا يعني:
- ✅ **الاستخدام التجاري مسموح تمامًا** — على عكس Jina-OCR-v1 (CC BY-NC 4.0).
- ✅ يمكن تعديله وإعادة توزيعه.
- ✅ يمكن دمجه في منتج تجاري دون عوائق.
- ✅ لا يحتاج ترخيصًا منفصلًا من Alibaba.

**هذا فرق جوهري عن Jina-OCR-v1:** Open Code Review يمكن أن يكون جزءًا من مشروعك التجاري مباشرة.

---

## 6. متى لا تستخدمه؟

| الحالة | التوصية |
|---|---|
| مشروعك كله Python فقط | الأداة تدعم Python، لكنها مصممة لمشاريع متعددة اللغات |
| لا يوجد Git في المشروع | الأداة تعتمد على Git diff (يمكن استخدام `ocr scan` بدون Git) |
| لا يوجد API key لنموذج LLM | لا تعمل بدون LLM backend |
| الموارد محدودة | الأداة نفسها خفيفة (Node.js)، لكن تحتاج LLM |
| تريد OCR للصور | ❌ هذه ليست أداة OCR — هذه أداة مراجعة كود |

---

## 7. التوصية النهائية

### ✅ استخدمه — لكن كأداة تطوير، وليس كمكوّن في الإنتاج

**السبب:** مشروعك omni-medical-suite يحتوي على:
- محركات OCR متعددة (Tesseract, Paddle, EasyOCR, TrOCR, OLMoCR)
- طبقة AHW قيد التطوير
- Learning Ledger + Dataset pipeline
- UI للتصحيح

كل هذه المكونات تحتاج **مراجعة كود مستمرة** لضمان:
1. عدم وجود تسريبات في الـdataset splits.
2. التزام كل engine بالـcontract.
3. أمان الـAPI والـUI.
4. جودة الكود في CI/CD.

**Open Code Review** يعطيك هذا بأقل تكلفة (1/9 من توكنات Claude Code) وبدقة أعلى.

### خطة التكامل المقترحة

| المرحلة | المهمة |
|---|---|
| **الآن** | تثبيت `ocr` محليًا وتشغيله على فرع AHW يدويًا |
| **بعد أسبوع** | إضافة GitHub Action لتشغيله على كل PR |
| **بعد شهر** | كتابة قواعد مخصصة لمشروعك (`.opencodereview/rule.json`) |
| **مستمر** | استخدامه لمراجعة كود الـengines الجديدة قبل الدمج |

### قواعد مخصصة مقترحة لمشروعك

```json
{
  "rules": [
    {
      "name": "OCR Engine Contract",
      "files": "**/engines/**/*.py",
      "rule": "Every engine must return a valid OCRResult object. Check for: raw_text, engine_name, confidence, provenance. Flag any engine that returns None or a non-OCRResult object."
    },
    {
      "name": "Dataset Split Safety",
      "files": "**/ahw/dataset/**/*.py",
      "rule": "Flag any code that adds samples to both train and test splits from the same source_page. Flag any code that modifies the fixed test set."
    },
    {
      "name": "Medical Safety",
      "files": "**/*.py",
      "rule": "Flag any code that automatically corrects medical text without human validation. Flag any code that sends medical data to external APIs without explicit user consent."
    },
    {
      "name": "Provenance Completeness",
      "files": "**/provenance/**/*.py",
      "rule": "Every OCR result must log: engine, model, version, preprocessing, timestamp, page, raw_output. Flag any missing field."
    }
  ]
}
```

---

## 8. الخلاصة في سطر واحد

**Open Code Review ليس بديلاً عن Jina-OCR-v1 أو AHW — هو طبقة جودة فوق كل ما تبنيه، بترخيص Apache-2.0 يسمح بالاستخدام التجاري، وبتكلفة 1/9 من Claude Code، ودقة أعلى في كشف العيوب الحقيقية.**

إذا أردت، أستطيع في الخطوة التالية إعداد **Master Prompt لـZ.ai** لدمج Open Code Review في `omni-medical-suite` كنظام CI/CD، مع قواعد مخصصة لمشروعك، وبنفس فلسفة Stop-Gates التي نستخدمها.
