<!-- المصدر: محادثة DeepSeek 2873vzbqibqh1ihe31 — رسالة 69 | حُفظ: 2026-10-08 -->

# VPS Future Plan — Documentation Task

# MASTER PROMPT — VPS Future Development Plan (Documentation Only)
## Omni Medical Suite — خطة مستقبلية للتشغيل على VPS بدون تنفيذ

> **تعليمات:** انسخ ما أسفل هذا السطر وأرسله إلى الوكيل المنفذ (Z.ai) كما هو. هذا البرومبت للتوثيق فقط — **لا تنفيذ، لا تعديل كود، لا تثبيت، لا تشغيل**.

---

## 0. الهوية والسياق

أنت الآن تعمل كـ:

- **Documentation Engineer**
- **DevOps Architect (Planning Only)**
- **Cloud Cost Analyst**
- **Security & Privacy Auditor**

المستودع المستهدف:

```
/home/z/my-project/repos/omni-medical-suite
```

**المهمة:** إضافة حزمة توثيق مستقبلية كاملة عن **نشر المشروع على VPS**، تشمل:

- الخيارات المجانية المتاحة (Oracle, GCP, AWS, Codespaces, Colab).
- المعمارية الهجينة (Local + VPS + Colab).
- نقاط التكامل مع المشروع الحالي.
- خطة ترحيل تدريجية.
- تحليل التكلفة والمخاطر.
- قائمة أمان وخصوصية.

**نمط التنفيذ:** `DOCUMENTATION_ONLY` — لا كود، لا تنفيذ، لا تعديل.

---

## 1. القواعد المطلقة

### 1.1 ممنوع تماماً

- ❌ تعديل أي ملف كود (`*.py`, `*.html`, `Dockerfile`, `docker-compose.yml`).
- ❌ تثبيت أي حزمة (`pip`, `npm`, `apt`, `docker`).
- ❌ تشغيل أي خدمة (`server.py`, `train_server.py`).
- ❌ تعديل `main` أو أي فرع.
- ❌ commit أو push أي كود إنتاجي.
- ❌ تحميل أوزان أو نماذج.
- ❌ ادعاء أن شيئاً "مُنفَّذ" أو "تم" — كل شيء **مُوثَّق فقط**.

### 1.2 مسموح

- ✅ إنشاء ملفات Markdown في `docs/future/vps/`.
- ✅ قراءة المشروع الحالي لفهم نقاط التكامل.
- ✅ كتابة Templates (سكربتات مستقبلية) داخل ملفات Markdown كـ code blocks.
- ✅ commit التوثيق فقط (في فرع منفصل).
- ✅ push إلى GitHub (لحفظ الوثائق).

### 1.3 الفرع

```
feature/vps-future-planning
```

إذا كان موجوداً، أبلغ عنه ثم استخدمه. لا تلمس `main`.

---

## 2. Pre-Flight (إلزامي)

```bash
git -C /home/z/my-project/repos/omni-medical-suite status
git -C /home/z/my-project/repos/omni-medical-suite branch --show-current
git -C /home/z/my-project/repos/omni-medical-suite log -n 3 --oneline
ls /home/z/my-project/repos/omni-medical-suite/docs/ 2>/dev/null
find /home/z/my-project/repos/omni-medical-suite -maxdepth 2 -name "*.py" | head -20
```

**إذا لم يوجد المستودع:** STOP. أبلغ. لا تخمّن.

**إذا كان Worktree غير نظيف:** أبلغ فقط. لا تنظّف. أنشئ فرعاً جديداً من HEAD الحالي.

---

## 3. المخرجات المطلوبة (5 ملفات)

أنشئ المجلد `docs/future/vps/` وأنتج الملفات التالية:

### 📄 الملف 1: `README.md` (نظرة عامة)

يحتوي:

- **الملخص التنفيذي:** لماذا VPS؟ ما الذي يقدمه؟
- **جدول المحتويات:** روابط للملفات الأخرى.
- **الحالة الحالية:** `PLANNED — NOT IMPLEMENTED`.
- **المتطلبات المسبقة:** حساب، بطاقة، بيئة.
- **الجدول الزمني المقترح:** مراحل بأسبوع/شهر.
- **تحذير بارز:** "هذه وثائق تخطيط فقط، لا شيء منها منفَّذ".

---

### 📄 الملف 2: `FREE_VPS_OPTIONS.md` (الخيارات المجانية)

يحتوي **جدولاً تفصيلياً** لكل مزود:

| المزود | المواصفات | المدة | بطاقة؟ | قابلية التسجيل من سوريا | ملاحظات |
|---|---|---|---|---|---|
| Oracle Cloud Always Free | 4 ARM cores, 24GB RAM, 200GB | دائم | نعم (للتحقق) | صعب | الأفضل تقنياً |
| Google Cloud e2-micro | 1 vCPU, 1GB RAM, 30GB | دائم | نعم | متوسط | مناطق أمريكية فقط |
| AWS Free Tier | t2.micro/t3.micro | 12 شهر | نعم | سهل | ينتهي بعد سنة |
| GitHub Codespaces | 2 vCPU, 8GB, 32GB | 60 ساعة/شهر | لا | سهل جداً | الأفضل للبدء |
| Google Colab | GPU T4 | محدود يومياً | لا | سهل | للتدريب فقط |
| Hugging Face Spaces | متغير | دائم | لا | سهل | للنماذج فقط |
| Oracle Free (ARM) | 4 cores | دائم | نعم | صعب | ممتاز لكن التسجيل صعب |
| Fly.io | مشترك | محدود | لا | متوسط | بديل جيد |
| Railway | محدود | محدود | لا | متوسط | للتجارب |
| Render | محدود | محدود | لا | متوسط | للتجارب |

**لكل مزود، أضف:**

- رابط الموقع الرسمي.
- الخطوات التفصيلية للتسجيل.
- التحديات المتوقعة.
- الحلول البديلة.
- ما يصلح له (خادم دائم، تطوير، تدريب).
- **متوافق مع سوريا؟** (نعم / لا / بشروط).

**قسم خاص: طرق تجاوز مشكلة الدفع من سوريا**
- عناوين بديلة.
- بطاقات prepaid.
- USDT/كربتو.
- أصدقاء في الخارج.

---

### 📄 الملف 3: `HYBRID_ARCHITECTURE.md` (المعمارية الهجينة)

يحتوي:

#### 3.1 Diagram (Mermaid)

```
┌──────────────┐      HTTPS      ┌─────────────────┐
│  المستخدم    │ ──────────────► │  VPS (Oracle)   │
│  (سوريا)     │                 │  ─────────────  │
└──────────────┘                 │  Flask Server   │
                                 │  SQLite/Postgres│
                                 │  Nginx + SSL    │
                                 │  Docker (Stirling│
                                 │  Xberg)         │
                                 └────────┬────────┘
                                          │
                          ┌───────────────┼───────────────┐
                          │               │               │
                          ▼               ▼               ▼
                    ┌──────────┐   ┌──────────┐   ┌──────────┐
                    │ Colab    │   │ GitHub   │   │ Backup   │
                    │ (GPU)    │   │ Private  │   │ Storage  │
                    │ Training │   │ Repo     │   │          │
                    └──────────┘   └──────────┘   └──────────┘
```

#### 3.2 مكونات المعمارية

لكل مكوّن (Local, VPS, Colab, GitHub, Backup):

- **الدور:** ماذا يفعل؟
- **المسؤوليات:** ما الموكول إليه؟
- **الموارد:** CPU/RAM/GPU/Storage.
- **التكلفة:** مجاني / مدفوع.
- **التواصل:** كيف يتصل بالآخرين؟
- **حالة الفشل:** ماذا يحدث إذا فشل؟
- **النسخ الاحتياطي:** كيف نستعيده؟

#### 3.3 تدفق البيانات (Data Flow)

سير عمل تفصيلي لحالتين:

**الحالة 1: تصحيح يومي**
```
المستخدم يرفع صورة → VPS يستقبل → يقطّع → يخزّن في SQLite
→ المستخدم يصحح من المتصفح → الحفظ على VPS → نسخة احتياطية على GitHub
```

**الحالة 2: تدريب دوري**
```
VPS يجمع 500+ تصحيح → يصدّر dataset → يرسل إلى Colab
→ Colab يدرّب → يحمّل النموذج إلى VPS → VPS يستبدل النموذج
→ إشعار للمستخدم بالبريد
```

---

### 📄 الملف 4: `INTEGRATION_POINTS.md` (نقاط التكامل مع المشروع الحالي)

يحتوي جدولاً شاملاً لكل ملف/مكوّن في المشروع الحالي:

| الملف/المكوّن الحالي | كيف يتكامل مع VPS | التعديل المطلوب | الأولوية | المخاطر |
|---|---|---|---|---|
| `server.py` | يعمل على VPS مباشرة | لا تعديل — فقط تشغيل | CRITICAL | منخفضة |
| `segment.py` | يعمل عند الرفع | لا تعديل | HIGH | منخفضة |
| `segment_batch.py` | يعمل في cron | إضافة cron job | MEDIUM | منخفضة |
| `train_server.py` | لا يعمل على VPS مجاني | تشغيل على Colab | HIGH | منخفضة |
| `train_trocr.py` | على Colab فقط | لا يعمل على VPS | CRITICAL | عالية |
| `corrections.db` (SQLite) | ينتقل إلى VPS | نسخ + تحقق | CRITICAL | متوسطة |
| `output/S001/` (crops) | تبقى على VPS | تخزين + نسخ احتياطي | HIGH | متوسطة |
| `metadata.xlsx` | يبقى على VPS | لا تعديل | MEDIUM | منخفضة |
| `models/` | تُنقل إلى VPS بعد التدريب | نسخ بعد التدريب | HIGH | منخفضة |
| `Dockerfile` | جديد (مستقبلي) | إنشاؤه لاحقاً | MEDIUM | منخفضة |
| `docker-compose.yml` | جديد (مستقبلي) | Stirling PDF + Xberg | MEDIUM | منخفضة |
| `requirements.txt` | يُثبّت على VPS | لا تعديل | CRITICAL | منخفضة |
| `.env` | جديد | متغيرات البيئة | HIGH | عالية |
| Nginx config | جديد (مستقبلي) | reverse proxy | HIGH | متوسطة |
| systemd service | جديد (مستقبلي) | تشغيل تلقائي | HIGH | منخفضة |
| Backup script | جديد (مستقبلي) | cron + rsync | HIGH | منخفضة |
| Monitoring | Uptime Robot | خارجي | MEDIUM | منخفضة |

**لكل بند، أضف:**
- الخطوات التفصيلية.
- الأوامر (code blocks).
- الملفات المتوقعة.
- المخاطر والتحذيرات.
- **هل يحتاج تنفيذاً الآن؟** (نعم/لا)

**⚠️ تأكيد مهم:** لكل بند، اكتب بوضوح: **`IMPLEMENTATION: NOT NOW — PLANNED FOR PHASE V-X`**.

---

### 📄 الملف 5: `DEPLOYMENT_RUNBOOK.md` (قالب تنفيذ مستقبلي)

يحتوي **Templates** جاهزة للاستخدام المستقبلي — كلها داخل code blocks (لا تُنشئ ملفات فعلية):

#### 5.1 Oracle Cloud Setup

```bash
# خطوات SSH الأولى
ssh ubuntu@<oracle-ip>
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv nginx git curl
# ... (تفاصيل كاملة)
```

#### 5.2 Nginx Config

```nginx
server {
    listen 80;
    server_name ahw.example.com;
    location / {
        proxy_pass http://127.0.0.1:5000;
        # ...
    }
}
```

#### 5.3 SSL Setup

```bash
sudo certbot --nginx -d ahw.example.com
```

#### 5.4 Systemd Service

```ini
[Unit]
Description=AHW Correction Server
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/omni-medical-suite
ExecStart=/home/ubuntu/omni-medical-suite/venv/bin/python server.py --host 0.0.0.0
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 5.5 Backup Script

```bash
#!/bin/bash
# backup.sh
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf /backup/corrections_$DATE.tar.gz ~/omni-medical-suite/output/
# ارفع إلى GitHub Private
# ...
```

#### 5.6 Cron Jobs

```cron
# نسخ احتياطي يومي
0 2 * * * /home/ubuntu/backup.sh

# تنظيف مؤقت أسبوعي
0 3 * * 0 find /tmp -type f -mtime +7 -delete
```

#### 5.7 Colab Integration Script

```python
# في Colab
from google.colab import drive
drive.mount('/content/drive')
!scp user@vps:/path/to/data.zip ./
# ... تدريب
!scp -r ./trocr-model/ user@vps:/path/to/models/
```

**⚠️ في نهاية كل Template، اكتب:**

```
STATUS: TEMPLATE ONLY — DO NOT EXECUTE
PHASE: V-X (planned)
```

---

## 4. الأقسام الإضافية المطلوبة

### 4.1 Cost Analysis (تحليل التكلفة)

جدول شهري/سنوي لكل خيار:

| السيناريو | VPS | Colab | التخزين | الإجمالي/شهر |
|---|---|---|---|---|
| **مجاني بالكامل** | Oracle Free | Colab Free | GitHub | $0 |
| **مختلط** | Oracle Free | Colab Pro | GitHub Pro | ~$20 |
| **متقدم** | VPS GPU | Colab Pro+ | S3 | ~$150 |

### 4.2 Risk Register (سجل المخاطر)

| المخاطرة | الشدة | الاحتمال | التخفيف |
|---|---|---|---|
| فقدان بيانات VPS | HIGH | متوسطة | نسخ يومية |
| اختراق VPS | CRITICAL | منخفضة | SSH keys + SSL + Fail2Ban |
| Oracle يرفض حسابك | MEDIUM | عالية | بديل: Codespaces |
| انقطاع كهرباء/إنترنت VPS | LOW | منخفضة | Uptime Robot |
| PHI leak عبر الشبكة | CRITICAL | منخفضة | HTTPS + تشفير محلي |
| تكلفة خفية | MEDIUM | متوسطة | تنبيهات الفاتورة |

### 4.3 Security Checklist (قائمة الأمان)

- [ ] SSH keys فقط (لا كلمات مرور).
- [ ] جدار ناري (ufw/firewalld).
- [ ] HTTPS إلزامي (Let's Encrypt).
- [ ] Fail2Ban.
- [ ] تحديثات أمنية تلقائية.
- [ ] Backup مشفّر.
- [ ] لا PHI على VPS عام.
- [ ] API Key في `.env` (ليس في الكود).
- [ ] Rate limiting على endpoints.
- [ ] Logs بدون معلومات حساسة.

### 4.4 Privacy & Compliance (الخصوصية والامتثال)

- **مسموح على VPS:** بيانات اصطناعية، Demo، كود مفتوح.
- **ممنوع على VPS عام:** PHI، بيانات مرضى، صور حقيقية.
- **إذا لا مفر:** VPS خاص + تشفير at-rest + GDPR compliance.

### 4.5 Rollout Roadmap (خطة الترحيل)

| المرحلة | المدة | المخرج | شرط الانتقال |
|---|---|---|---|
| **V-0** | أسبوع | تسجيل Oracle | نجاح التسجيل |
| **V-1** | أسبوع | SSH + Nginx + SSL | اتصال آمن |
| **V-2** | أسبوع | نشر server.py | يعمل 24/7 |
| **V-3** | أسبوع | Migration of DB | البيانات كاملة |
| **V-4** | أسبوع | Backup + Monitoring | إشعارات تعمل |
| **V-5** | أسبوع | Docker (Stirling/Xberg) | حاويات تعمل |
| **V-6** | أسبوع | Colab integration | تدريب تلقائي |
| **V-7** | أسبوع | Full production | كل شيء مستقر |

### 4.6 Alternatives (البدائل)

- **إذا فشل Oracle:** GitHub Codespaces + Colab + GitHub Actions.
- **إذا احتجت GPU:** Colab Pro، RunPod، Vast.ai.
- **إذا احتجت تخزين كبير:** Backblaze B2، Cloudflare R2.

### 4.7 FAQ (أسئلة شائعة)

10 أسئلة على الأقل، منها:

- هل VPS آمن لبيانات المرضى؟
- ماذا لو فقدت الـVPS؟
- كيف أنقل البيانات من جهازي إلى VPS؟
- كيف أدرّب على Colab من VPS؟
- كم تكلفة سنوية فعلية؟
- هل أحتاج خبرة Linux؟
- ماذا لو رُفض طلب Oracle؟
- هل VPS أسرع من جهازي؟
- هل يمكن تشغيل كل شيء على VPS؟
- كيف أستعيد العمل بعد إعادة تعيين البيئة؟

---

## 5. القواعد التوثيقية

### 5.1 الأدلة

كل ادعاء تقني يجب أن يحمل:

```
Source: <رابط رسمي أو مصدر>
Verified: <تاريخ التحقق>
Status: PROVEN | PARTIALLY PROVEN | UNVERIFIED
```

**ممنوع** الادعاء بأرقام دون مصدر.

### 5.2 اللغة

- **العناوين:** إنجليزية (للسهولة التقنية).
- **المحتوى:** عربي + إنجليزي (bilingual حيث مناسب).
- **الأوامر:** إنجليزية (code blocks).

### 5.3 الحجم

- كل ملف: **≤ 4000 كلمة**.
- إجمالي الحزمة: **≤ 20000 كلمة**.
- إذا احتجت أكثر، قسّم إلى ملفات فرعية.

---

## 6. STOP GATES

| البوابة | الشرط |
|---|---|
| **V-STOP-0** | المستودع غير موجود → STOP |
| **V-STOP-1** | Worktree غير نظيف → أبلغ، أكمل فقط بإنشاء فرع جديد |
| **V-STOP-2** | أي محاولة تنفيذ فعلية → STOP فوراً |
| **V-STOP-3** | أي تعديل كود → STOP فوراً |
| **V-STOP-4** | عدم وجود مصدر لأي ادعاء → رفض البند |
| **V-STOP-5** | PHI أو بيانات حقيقية في الوثائق → STOP |

---

## 7. خطوات التنفيذ

1. **Pre-Flight** (أعلاه).
2. **إنشاء فرع** `feature/vps-future-planning`.
3. **قراءة المشروع** لفهم نقاط التكامل (لا تعديل).
4. **إنشاء المجلد** `docs/future/vps/`.
5. **كتابة الملفات الخمسة** بالترتيب.
6. **commit** كل ملف (أو commit واحد نهائي).
7. **push** إلى GitHub.
8. **تحقق من البعيد** (`git ls-remote`).
9. **إنشاء Handoff Bundle**.
10. **إنتاج التقرير النهائي** (أدناه).

---

## 8. صيغة التقرير النهائي

```
=== VPS FUTURE PLAN — DOCUMENTATION ===

Branch:              feature/vps-future-planning
HEAD SHA:            <full SHA>
Remote SHA:          <verified>

FILES CREATED:
  - docs/future/vps/README.md
  - docs/future/vps/FREE_VPS_OPTIONS.md
  - docs/future/vps/HYBRID_ARCHITECTURE.md
  - docs/future/vps/INTEGRATION_POINTS.md
  - docs/future/vps/DEPLOYMENT_RUNBOOK.md

TOTAL WORDS:         <count>
SECTIONS COMPLETED:  <X / 7>

IMPLEMENTATION STATUS: NOT IMPLEMENTED (documentation only)

CODE MODIFIED:       NONE
PACKAGES INSTALLED:  NONE
SERVICES STARTED:    NONE
FILES TOUCHED:       <list only new docs files>

PROVEN:
  - <list of verified facts with sources>

PARTIALLY PROVEN:
  - <list of claims with partial sources>

UNVERIFIED:
  - <list of claims needing verification>

BLOCKED:
  - <list>

NEXT STEPS FOR USER:
  1. <action>
  2. <action>

PERSISTENCE:         OK | BLOCKED
HANDOFF BUNDLE:      <path>

FINAL REMINDER:      "هذا توثيق فقط. لا شيء من VPS مُنفَّذ.
                     كل الخطوات تنتظر موافقة صريحة من المالك."
```

---

## 9. المبدأ النهائي

```
هذه المهمة توثيقية بحتة.

الهدف: تحضير خطة VPS كاملة، مدروسة، مُوثَّقة، وقابلة للتنفيذ لاحقاً.
ليس الهدف: تنفيذ أي شيء منها الآن.

لا كود.
لا تثبيت.
لا تشغيل.
لا التزام.

فقط حبر على ورق — ليُقرأ عند الحاجة.
```

**ابدأ الآن بـPre-Flight. ثم أنشئ الفرع. ثم اكتب الوثائق. ثم أرسل التقرير النهائي.**

**لا تنفّذ أي شيء من محتوى الوثائق. لا تختبر. لا تشغّل. فقط وثّق.**
