# omni_preprocess — حزمة المعالجة المسبقة للمستندات (Stirling PDF backend)

> **المصدر:** محادثة DeepSeek `2873vzbqibqh1ihe31` (رسائل 42-47) — خطة دمج
> Stirling PDF التي أعدها المالك للتنفيذ. الحزمة **إضافية ومعزولة**:
> لا تعدل أي كود قائم، ولا تُستهلك من أي مسار إنتاجي حتى يُربطها
> المستهلكون صراحةً (انظر "التكامل" أدناه).

## ما هذا

معالج مستندات 50+ أداة (Stirling PDF — AGPL-3.0 كخدمة **منفصلة** عبر
Docker) خلف واجهة موحدة:

```
PDF/صورة → PreprocessRouter → StirlingPDFClient → PreprocessingResult
                              (deskew + clean + OCR-skip-text)
```

| الوحدة | الوظيفة |
|---|---|
| `contract/preprocessing_result.py` | عقد النتيجة (dataclass + عمليات Enum) |
| `backends/stirling_client.py` | عميل REST ‏(httpx) — ocr_preprocess/split_pdf/merge_pdfs… |
| `routing/preprocess_router.py` | قرار "هل يحتاج المستند معالجة؟" + التنفيذ |
| `config/stirling_config.py` | تكوين من env ‏(OMNI_STIRLING_*) — `enabled=False` افتراضيًا |
| `tests/` | اختبارات وحدة (mock) + تكامل **تُتخطى تلقائيًا** بلا خادم حي |

## التشغيل

```bash
# 1) خادم Stirling (منفصل — AGPL-3.0 لا يلمس ترخيص هذا المستودع)
docker compose -f tools/stirling-pdf/docker-compose.yml up -d

# 2) العميل
pip install httpx
python -c "
from omni_preprocess.routing.preprocess_router import PreprocessRouter
r = PreprocessRouter()
print(r.should_preprocess('scan.pdf'))
"
```

## التكامل (مثال — لم يُربط بعد بأي مستهلك)

مثال الربط المقترح في المحادثة مع `packages/omni_ocr`:

```python
# في نقطة دخول OCR (adapter/mixed_engine) — اختياري بالكامل:
from omni_preprocess.config.stirling_config import StirlingConfig
from omni_preprocess.routing.preprocess_router import PreprocessRouter

cfg = StirlingConfig.from_env()
if cfg.enabled:
    router = PreprocessRouter(stirling_url=cfg.base_url)
    if router.should_preprocess(pdf_path)["preprocess"]:
        out = router.preprocess(pdf_path, "/tmp/prepared.pdf")
        if out["success"]:
            pdf_path = out["output_path"]
# ... تابع مسار OCR الموجود كما هو
```

## ملاحظات تدقيق (أمانة)

1. **الاعتماد على httpx**: غير مثبت افتراضيًا — العميل يفشل بوضوح عند
   الغياب (ImportError). أُضيف كتابع اختياري مقترح، لا إلزامي.
2. **ترميز `languages`**: تُرسل كقائمة multipart (مفاتيح مكررة) — مقبولة
   في Stirling (Spring) لكنها **لم تُختبر ضد خادم حي** في بيئة التدقيق؛
   إن رفضها خادمك استخدم `"ara+eng"` كنص واحد.
3. **الترخيص**: Stirling PDF ‏AGPL-3.0 يعمل كخدمة شبكة منفصلة (Docker) —
   لا ربط مكتبي، فلا عدوى ترخيصية لكود المستودع (MIT).
4. **الاختبارات الحية تتخطى ذاتيًا** (`is_available()` false → skip) —
   آمنة في CI بلا خادم.
5. **fixture الصور الممسوحة** (`tests/fixtures/scanned_arabic.pdf`) غير
   مضمّنة — اختبارات التكامل تتخطى عند غيابها.
