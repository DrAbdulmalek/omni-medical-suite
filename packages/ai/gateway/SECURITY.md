# Gateway Security Guide | دليل أمان بوابة الذكاء الاصطناعي

> **AI Gateway Security Documentation** — OmniMedical Suite
> Comprehensive guide for securing multi-provider API keys across 8+ AI providers
> (NVIDIA NIM, OpenRouter, DeepSeek, Kimi, Wafer, LMStudio, LlamaCpp, Ollama).

> **دليل أمان بوابة الذكاء الاصطناعي** — OmniMedical Suite
> دليل شامل لتأمين مفاتيح API لمزودي الذكاء الاصطناعي المتعددين عبر أكثر من 8 مزودين
> (NVIDIA NIM، OpenRouter، DeepSeek، Kimi، Wafer، LMStudio، LlamaCpp، Ollama).

---

## Table of Contents | جدول المحتويات

1. [Key Management Best Practices | أفضل ممارسات إدارة المفاتيح](#1-key-management-best-practices--أفضل-ممارسات-إدارة-المفاتيح)
2. [Per-Provider Key Configuration | تهيئة المفاتيح لكل مزود](#2-per-provider-key-configuration--تهيئة-المفاتيح-لكل-مزود)
3. [Key Rotation Strategy | استراتيجية تدوير المفاتيح](#3-key-rotation-strategy--استراتيجية-تدوير-المفاتيح)
4. [Rate Limiting & Cost Control | تقييد المعدل والتحكم في التكاليف](#4-rate-limiting--cost-control--تقييد-المعدل-والتحكم-في-التكاليف)
5. [Audit Logging | سجل التدقيق](#5-audit-logging--سجل-التدقيق)
6. [.env.example Template | قالب ملف .env](#6-envexample-template--قالب-ملف-env)

---

## 1. Key Management Best Practices | أفضل ممارسات إدارة المفاتيح

### 1.1 Never Hardcode Keys | عدم تضمين المفاتيح في الكود

> **WARNING:** API keys must **never** appear in source code, config files committed to
> version control, or Docker images. The gateway's `logging_config.py` already redacts
> Bearer tokens and Telegram bot tokens from log output — but this is a last-resort
> defense. Prevent leakage at the source.

> **تحذير:** يجب ألا تظهر مفاتيح API **أبدًا** في الكود المصدري أو ملفات التهيئة
> المُرسَلة إلى التحكم بالإصدارات أو صور Docker. ملف `logging_config.py` في البوابة
> يحجب بالفعل رموز Bearer ورموز Telegram Bot من إخراج السجلات — لكن هذا دفاع أخير.
> امنع التسريب من المصدر.

```bash
# BAD | خاطئ — will be committed to git
nvidia_nim_api_key = "nvapi-xxxx-my-secret-key"

# GOOD | صحيح — loaded from environment
from config.settings import get_settings
settings = get_settings()
key = settings.nvidia_nim_api_key  # reads NVIDIA_NIM_API_KEY from .env
```

### 1.2 Use .env Files in Development | استخدام ملفات .env في بيئة التطوير

The gateway uses `pydantic-settings` and loads environment variables from these files
(in priority order, later overrides earlier):

تستخدم البوابة `pydantic-settings` وتحمّل متغيرات البيئة من هذه الملفات
(بترتيب الأولوية، الملفات اللاحقة تتجاوز السابقة):

1. `~/.config/omnifile-ai-gateway/.env` (user-global config)
2. `.env` (project-local config)
3. File specified by `OAG_ENV_FILE` environment variable

```bash
# Setup | التهيئة
cp packages/ai/gateway/.env.example packages/ai/gateway/.env
# Edit .env and fill in your keys | عدّل .env وأدخل مفاتيحك
```

> **IMPORTANT:** Add `.env` to your `.gitignore` immediately.
> **مهم:** أضف `.env` إلى ملف `.gitignore` فورًا.

```gitignore
# .gitignore
.env
.env.local
.env.production
*.key
*.pem
```

### 1.3 Use a Vault in Production | استخدام خزنة (Vault) في بيئة الإنتاج

For production deployments, environment variables from `.env` are **not sufficient**.
Use a dedicated secrets manager:

للنشر في بيئة الإنتاج، متغيرات البيئة من `.env` **غير كافية**.
استخدم مدير أسرار مخصصًا:

| Solution | Integration | Recommended For |
|:---------|:-----------|:----------------|
| **HashiCorp Vault** | `vault kv get secret/gateway/nvidia_nim_api_key` | Enterprise, multi-team |
| **AWS Secrets Manager** | `aws secretsmanager get-secret-value --secret-id gateway-keys` | AWS deployments |
| **AWS SSM Parameter Store** | `aws ssm get-parameter --name /gateway/nvidia_nim_api_key` | AWS, cost-effective |
| **Azure Key Vault** | `az keyvault secret show --name nvidia-nim-key --vault-name myvault` | Azure deployments |
| **Kubernetes Secrets** | Mounted as files in `/var/run/secrets/` | K8s deployments |
| **Docker Secrets** | `docker secret create nvidia_key -` | Docker Swarm |
| **1Password / Doppler** | CLI injects into environment | Small teams, developer-friendly |

**Recommended pattern:** Use an init container or entrypoint script that fetches secrets
from the vault and writes them to a `.env` file with strict permissions before the
gateway starts.

**النمط الموصى به:** استخدم حاوية تهيئة (init container) أو سكريبت بدء التشغيل الذي
يجلب الأسرار من الخزينة ويكتبها إلى ملف `.env` بصلاحيات صارمة قبل بدء تشغيل البوابة.

```bash
#!/bin/bash
# entrypoint.sh — fetch secrets and start gateway
vault kv get -format=json secret/gateway | jq -r '.data.data | to_entries | .[] | "\(.key)=\(.value)"' > /app/.env
chmod 600 /app/.env
exec python -m gateway.server
```

### 1.4 File Permissions | صلاحيات الملفات

```bash
# Restrict .env to owner read/write only
chmod 600 packages/ai/gateway/.env

# Verify | التحقق
ls -la packages/ai/gateway/.env
# -rw------- 1 user user ... packages/ai/gateway/.env
```

### 1.5 Pre-Commit Hooks for Secret Detection | خطافات ما قبل الإرسال لكشف الأسرار

Add a pre-commit hook to scan for accidentally committed secrets:

أضف خطافًا ما قبل الإرسال لمسح الأسرار المُرسَلة بالخطأ:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.18.0
    hooks:
      - id: gitleaks
  - repo: https://github.com/trufflesecurity/trufflehog
    rev: v3.63.0
    hooks:
      - id: trufflehog
```

---

## 2. Per-Provider Key Configuration | تهيئة المفاتيح لكل مزود

### 2.1 Cloud Providers (API Keys Required) | مزودو السحابة (مفاتيح API مطلوبة)

| Provider | Env Variable | Where to Get Key | Base URL (default) | Transport |
|:---------|:-------------|:-----------------|:--------------------|:----------|
| **NVIDIA NIM** | `NVIDIA_NIM_API_KEY` | [build.nvidia.com/settings/api-keys](https://build.nvidia.com/settings/api-keys) | `https://integrate.api.nvidia.com/v1` | OpenAI Chat |
| **OpenRouter** | `OPENROUTER_API_KEY` | [openrouter.ai/keys](https://openrouter.ai/keys) | `https://openrouter.ai/api/v1` | Anthropic Messages |
| **DeepSeek** | `DEEPSEEK_API_KEY` | [platform.deepseek.com/api_keys](https://platform.deepseek.com/api_keys) | `https://api.deepseek.com/anthropic` | Anthropic Messages |
| **Kimi (Moonshot)** | `KIMI_API_KEY` | [platform.moonshot.cn/console/api-keys](https://platform.moonshot.cn/console/api-keys) | `https://api.moonshot.ai/v1` | OpenAI Chat |
| **Wafer** | `WAFER_API_KEY` | [wafer.ai/pass](https://www.wafer.ai/pass) | `https://pass.wafer.ai/v1` | Anthropic Messages |

### 2.2 Local Providers (No API Key Required) | المزودون المحليون (لا حاجة لمفتاح API)

| Provider | Env Variable | Default URL | Notes | ملاحظات |
|:---------|:-------------|:-------------|:------|:--------|
| **LMStudio** | `LM_STUDIO_BASE_URL` | `http://localhost:1234/v1` | Static credential: `lm-studio` | مفتاح ثابت: `lm-studio` |
| **LlamaCpp** | `LLAMACPP_BASE_URL` | `http://localhost:8080/v1` | Static credential: `llamacpp` | مفتاح ثابت: `llamacpp` |
| **Ollama** | `OLLAMA_BASE_URL` | `http://localhost:11434` | Static credential: `ollama` | مفتاح ثابت: `ollama` |

> **Note:** Local providers use hardcoded static credentials. They are safe for local
> development but should be **firewalled** in production — never expose `localhost`
> ports to the network.

> **ملاحظة:** المزودون المحليون يستخدمون مفاتيح ثابتة مُبرمجة. هم آمنون للتطوير
> المحلي لكن يجب **جدارتهم بجدار حماية** في الإنتاج — لا تعرّض منافذ `localhost`
> للشبكة.

### 2.3 Additional Authentication Keys | مفاتيح المصادقة الإضافية

| Variable | Purpose | Required? |
|:---------|:--------|:----------|
| `ANTHROPIC_AUTH_TOKEN` | Protects gateway endpoints (Anthropic-style `x-api-key` header) | Optional — when set, all clients must send `x-api-key: <token>` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot integration for messaging | Only if `MESSAGING_PLATFORM=telegram` |
| `DISCORD_BOT_TOKEN` | Discord bot integration for messaging | Only if `MESSAGING_PLATFORM=discord` |
| `HF_TOKEN` | HuggingFace token for faster Whisper model downloads | Optional |
| `ALLOWED_TELEGRAM_USER_ID` | Restricts Telegram bot to one user | Recommended with Telegram |
| `ALLOWED_DISCORD_CHANNELS` | Restricts Discord bot to specific channels | Recommended with Discord |

### 2.4 Proxy Configuration | تهيئة البروكسي

The gateway supports per-provider HTTP/SOCKS proxies for tunneling requests:

تدعم البوابة بروكسي HTTP/SOCKS لكل مزود لتوجيه الطلبات عبر أنفاق:

| Variable | Provider |
|:---------|:---------|
| `NVIDIA_NIM_PROXY` | NVIDIA NIM |
| `OPENROUTER_PROXY` | OpenRouter |
| `LMSTUDIO_PROXY` | LMStudio |
| `LLAMACPP_PROXY` | LlamaCpp |
| `KIMI_PROXY` | Kimi |
| `WAFER_PROXY` | Wafer |

> **Security Note:** Proxies can intercept API traffic. Use only trusted proxies
> (corporate MITM proxies, your own SOCKS tunnel). Never route through public/untrusted proxies.

> **ملاحظة أمنية:** البروكسي يمكنه اعتراض حركة مرور API. استخدم فقط بروكسي موثوق
> به (بروكسي MITM للشركات، نفق SOCKS خاص بك). لا توجّه عبر بروكسي عام/غير موثوق.

### 2.5 Model Routing | توجيه النماذج

```bash
# Default model (fallback for all requests)
MODEL=nvidia_nim/z-ai/glm4.7

# Per-Claude-model overrides (optional)
MODEL_OPUS=deepseek/deepseek-chat
MODEL_SONNET=open_router/anthropic/claude-3.5-sonnet
MODEL_HAIKU=nvidia_nim/z-ai/glm4.7
```

> **Cost Tip:** Route cheap/fast requests (haiku) to local providers (Ollama, LMStudio)
> and expensive requests (opus) to cloud providers selectively.

> **نصيحة تكلفة:** وجّه الطلبات الرخيصة/السريعة (haiku) إلى مزودين محليين
> (Ollama، LMStudio) والطلبات المكلفة (opus) إلى مزودي السحابة بشكل انتقائي.

---

## 3. Key Rotation Strategy | استراتيجية تدوير المفاتيح

### 3.1 Rotation Without Downtime | التدوير بدون توقف

The gateway supports an **account pool** (`pool/account_pool.py`) that manages multiple
accounts per provider with automatic rotation. Use this for zero-downtime key rotation:

تدعم البوابة **تجمع حسابات** (`pool/account_pool.py`) يدير حسابات متعددة لكل
مزود مع تدوير تلقائي. استخدمه لتدوير المفاتيح بدون توقف:

```
Step 1: Generate new key on provider dashboard
  الخطوة 1: أنشئ مفتاحًا جديدًا في لوحة تحكم المزود

Step 2: Add new key to the account pool (both keys active)
  الخطوة 2: أضف المفتاح الجديد إلى تجمع الحسابات (كلا المفتاحين نشطان)

Step 3: Verify new key works (health check / test request)
  الخطوة 3: تحقق من عمل المفتاح الجديد (فحص صحة / طلب اختبار)

Step 4: Wait for all in-flight requests on old key to complete
  الخطوة 4: انتظر اكتمال جميع الطلبات الجارية على المفتاح القديم

Step 5: Remove old key from pool and revoke on provider dashboard
  الخطوة 5: أزل المفتاح القديم من التجمع وألغه في لوحة تحكم المزود
```

### 3.2 Using the Account Pool | استخدام تجمع الحسابات

The `AccountState` dataclass supports per-account configuration:

```python
# Conceptual — how the account pool tracks keys
# المفهوم — كيف يتتبع تجمع الحسابات المفاتيح
AccountState(
    account_id="nvidia-primary",
    provider_id="nvidia_nim",
    api_key="nvapi-xxx...",          # Current active key
    tier="pro",
    max_concurrent=5,
    rate_limit_per_minute=40,
    priority=10,                     # Higher priority = used first
)
```

### 3.3 Provider-Specific Rotation Notes | ملاحظات التدوير حسب المزود

| Provider | Key Lifetime | Rotation Method | ملاحظات |
|:---------|:-------------|:---------------|:--------|
| **NVIDIA NIM** | 90 days (recommended) | Create new key → update `.env` → restart | لا تنسَ تحديث متغير البيئة |
| **OpenRouter** | No expiration | Revoke old, create new | يمكن استخدام مفاتيح متعددة في نفس الوقت |
| **DeepSeek** | No expiration | Rotate via platform dashboard | تدوير دوري كل 90 يومًا |
| **Kimi** | No expiration | Rotate via Moonshot console | تحقق من حدود الاستخدام |
| **Wafer** | No expiration | Rotate via Wafer dashboard | تحقق من سياسة الاستخدام |

### 3.4 Automated Rotation Script | سكريبت التدوير التلقائي

```bash
#!/bin/bash
# rotate-key.sh — Example key rotation for NVIDIA NIM
# سكريبت تدوير المفاتيح — مثال لـ NVIDIA NIM

OLD_KEY=$(grep NVIDIA_NIM_API_KEY .env | cut -d= -f2)
NEW_KEY=$(openssl rand -hex 32)  # Or fetch from vault

# Backup old config
cp .env .env.backup.$(date +%Y%m%d)

# Update .env with new key
sed -i "s/^NVIDIA_NIM_API_KEY=.*/NVIDIA_NIM_API_KEY=${NEW_KEY}/" .env

# Restart gateway (graceful reload if supported)
kill -HUP $(pgrep -f gateway.server)

echo "Key rotated. Old key: ${OLD_KEY:0:8}... → New key: ${NEW_KEY:0:8}..."
echo "Revoke old key at: https://build.nvidia.com/settings/api-keys"
```

> **CRITICAL:** Always revoke old keys on the provider dashboard after rotation.
> Leaving orphaned keys active is a major security risk.

> **حرج:** ألغِ دائمًا المفاتيح القديمة في لوحة تحكم المزود بعد التدوير.
> ترك مفاتيح يتيمة نشطة هو خطر أمني كبير.

---

## 4. Rate Limiting & Cost Control | تقييد المعدل والتحكم في التكاليف

### 4.1 Provider Rate Limiting | تقييد المعدل للمزودين

The gateway implements a strict sliding-window rate limiter (`core/rate_limit.py`) and
per-provider rate-limit fallback (`pool/rate_limit_fallback.py`).

تنفّذ البوابة مقيّد معدل نافذة انزلاقية صارم (`core/rate_limit.py`)
وتجاوز تقييد المعدل لكل مزود (`pool/rate_limit_fallback.py`).

| Variable | Default | Description | الوصف |
|:---------|:--------|:------------|:------|
| `PROVIDER_RATE_LIMIT` | `40` | Max requests per provider within the rate window | أقصى عدد طلبات لكل مزود ضمن نافذة المعدل |
| `PROVIDER_RATE_WINDOW` | `60` | Rate window in seconds | نافذة المعدل بالثواني |
| `PROVIDER_MAX_CONCURRENCY` | `5` | Max concurrent outbound requests per provider | أقصى عدد طلبات متزامنة صادرة لكل مزود |

```bash
# Conservative settings for cost control
# إعدادات محافظة للتحكم في التكاليف
PROVIDER_RATE_LIMIT=20
PROVIDER_RATE_WINDOW=60
PROVIDER_MAX_CONCURRENCY=3
```

### 4.2 Messaging Rate Limiting | تقييد المعدل للرسائل

```bash
MESSAGING_RATE_LIMIT=1          # 1 message per window
MESSAGING_RATE_WINDOW=1.0       # 1 second window
```

### 4.3 Web Server Tools (SSRF Protection) | أدوات خادم الويب (حماية SSRF)

> Web server tools (`web_search`, `web_fetch`) are **disabled by default** because they
> perform outbound HTTP requests from the proxy, creating a Server-Side Request Forgery
> (SSRF) risk. Enable only with strict restrictions.

> أدوات خادم الويب (`web_search`، `web_fetch`) **معطّلة افتراضيًا** لأنها تنفذ
> طلبات HTTP صادرة من البروكسي، مما يُنشئ خطر تزوير الطلب من جانب الخادم (SSRF).
> فعّلها فقط مع قيود صارمة.

```bash
# Enable with caution | فعّل بحذر
ENABLE_WEB_SERVER_TOOLS=false              # Keep OFF unless needed
WEB_FETCH_ALLOWED_SCHEMES=http,https       # Only allow http/https
WEB_FETCH_ALLOW_PRIVATE_NETWORKS=false    # Block internal IPs (192.168.x, 10.x)
```

### 4.4 Cost Control Best Practices | أفضل ممارسات التحكم في التكاليف

1. **Use local providers for development** — Route all dev traffic through Ollama or LMStudio to avoid cloud API costs.
   **استخدم مزودين محليين للتطوير** — وجّه كل حركة مرور التطوير عبر Ollama أو LMStudio لتجنّب تكاليف API السحابة.

2. **Set per-provider budgets** — Most providers (NVIDIA NIM, OpenRouter, DeepSeek) offer dashboard spending limits. Set them.
   **حدد ميزانيات لكل مزود** — معظم المزودين يوفرون حدود إنفاق في لوحة التحكم. حددها.

3. **Monitor token usage** — The gateway logs metadata for every request. Set up alerts for unusual spikes.
   **راقب استخدام الرموز** — البوابة تسجّل البيانات الوصفية لكل طلب. أعد تنبيهات للزيادات غير المعتادة.

4. **Use cheaper models for bulk tasks** — Route summarization/classification to smaller models (haiku-tier), keep large models for complex reasoning.
   **استخدم نماذج أرخص للمهام الضخمة** — وجّه التلخيص/التصنيف إلى نماذج أصغر (مستوى haiku)، واحتفظ بالنماذج الكبيرة للاستدلال المعقد.

5. **Enable conversation pooling** — The `pool/conversation_pool.py` reduces redundant API calls by reusing conversation context.
   **فعّل تجمع المحادثات** — `pool/conversation_pool.py` يقلل مكالمات API المتكررة بإعادة استخدام سياق المحادثة.

### 4.5 HTTP Timeouts | مهلات HTTP

```bash
HTTP_READ_TIMEOUT=120       # Max time waiting for provider response
HTTP_WRITE_TIMEOUT=10       # Max time to send request body
HTTP_CONNECT_TIMEOUT=10     # Max time to establish connection
```

> Lower timeouts reduce the blast radius of a slow/stuck provider, preventing cascading failures.

> المهلات الأقل تقلل نطاق تأثير المزود البطيء/العالق، وتمنع حالات الفشل المتتالية.

---

## 5. Audit Logging | سجل التدقيق

### 5.1 Structured JSON Logging | تسجيل منظم بصيغة JSON

The gateway uses **Loguru** with JSON-line output to `server.log`. Every log entry includes:

تستخدم البوابة **Loguru** مع إخراج أسطر JSON إلى `server.log`. كل سجل يتضمن:

```json
{
  "time": "2025-07-10T14:30:00.000Z",
  "level": "INFO",
  "message": "provider request completed",
  "module": "providers.nvidia_nim.client",
  "function": "chat_completion",
  "line": 142,
  "request_id": "req-abc123",
  "node_id": "node-1",
  "chat_id": "chat-xyz789"
}
```

### 5.2 Sensitive Data Redaction | حجب البيانات الحساسة

The logging system (`config/logging_config.py`) **automatically redacts** sensitive data:

نظام التسجيل (`config/logging_config.py`) **يحجب تلقائيًا** البيانات الحساسة:

| Pattern | Redacted To | النمط | يُحوَّل إلى |
|:--------|:-----------|:------|:-----------|
| `https://api.telegram.org/bot<TOKEN>/` | `https://api.telegram.org/bot<redacted>/` | رابط Telegram | يُحجب |
| `Authorization: Bearer <TOKEN>` | `Authorization: Bearer <redacted>` | رأس المصادقة | يُحجب |

### 5.3 Debug Logging (Disabled by Default) | تسجيل التصحيح (معطّل افتراضيًا)

> **WARNING:** The following flags can log sensitive content (user messages, API payloads).
> Enable **only** in a secure development environment with no production data.

> **تحذير:** الأعلام التالية يمكنها تسجيل محتوى حساس (رسائل المستخدم، حمولات API).
> فعّلها **فقط** في بيئة تطوير آمنة بدون بيانات إنتاج.

| Variable | Default | Risk | المخاطر |
|:---------|:--------|:-----|:--------|
| `LOG_RAW_API_PAYLOADS` | `false` | **HIGH** — logs full request/response bodies | يسجّل أجسام الطلبات/الردود الكاملة |
| `LOG_RAW_SSE_EVENTS` | `false` | **HIGH** — logs streaming event data | يسجّل بيانات أحداث البث |
| `LOG_RAW_MESSAGING_CONTENT` | `false` | **HIGH** — logs message text and transcriptions | يسجّل نص الرسائل والنسخ |
| `LOG_RAW_CLI_DIAGNOSTICS` | `false` | **MEDIUM** — logs Claude CLI stderr | يسجّل مخرجات Claude CLI |
| `LOG_API_ERROR_TRACEBACKS` | `false` | **MEDIUM** — logs exception tracebacks | يسجّل تتبعات الاستثناءات |

### 5.4 Validation Logging | تسجيل التحقق

The `api/validation_log.py` module logs **safe metadata only** — message counts, content
types, tool names — never raw text. This is safe to leave enabled.

وحدة `api/validation_log.py` تسجّل **بيانات وصفية آمنة فقط** — عدد الرسائل، أنواع
المحتوى، أسماء الأدوات — وليس النص الخام. من الآمن تركها مفعّلة.

```python
# What gets logged (safe):
# ما يُسجَّل (آمن):
{"role": "user", "content_kind": "str", "content_length": 342}
{"role": "assistant", "content_kind": "list", "block_types": ["text", "tool_use"]}
```

### 5.5 Recommended Audit Setup | إعداد التدقيق الموصى به

```bash
# Production-safe logging configuration
# تهيئة تسجيل آمنة للإنتاج
LOG_RAW_API_PAYLOADS=false
LOG_RAW_SSE_EVENTS=false
LOG_RAW_MESSAGING_CONTENT=false
LOG_API_ERROR_TRACEBACKS=false
LOG_RAW_CLI_DIAGNOSTICS=false
```

For centralized log aggregation in production, stream `server.log` to your SIEM:
لجمع السجلات المركزي في الإنتاج، دفّق `server.log` إلى نظام SIEM:

```bash
# Example: Ship logs to ELK / Grafana Loki / Datadog
# مثال: إرسال السجلات إلى ELK / Grafana Loki / Datadog
tail -f packages/ai/gateway/server.log | vector --config vector.toml
```

---

## 6. .env.example Template | قالب ملف .env

Below is a complete `.env` template for the AI gateway with all provider keys and
security-relevant settings. Copy to `.env` and replace `CHANGE_ME` values.

فيما يلي قالب `.env` كامل لبوابة الذكاء الاصطناعي مع جميع مفاتيح المزودين
وإعدادات الأمان ذات الصلة. انسخ إلى `.env` واستبدل قيم `CHANGE_ME`.

```bash
# =============================================================================
# OmniMedical AI Gateway — Secure .env Template
# قالب .env آمن لبوابة الذكاء الاصطناعي
# =============================================================================
# Copy: cp packages/ai/gateway/.env.example packages/ai/gateway/.env
# Then replace all CHANGE_ME values with your actual keys.
# ثم استبدل جميع قيم CHANGE_ME بمفاتيحك الفعلية.
#
# SECURITY: Never commit this file. Add to .gitignore immediately.
# الأمان: لا ترسل هذا الملف أبدًا. أضفه إلى .gitignore فورًا.
# =============================================================================

# ---------------------------------------------------------------------------
# 🔑 Cloud Provider API Keys — Replace CHANGE_ME with actual keys
# 🔑 مفاتيح API لمزودي السحابة — استبدل CHANGE_ME بالمفاتيح الفعلية
# ---------------------------------------------------------------------------
NVIDIA_NIM_API_KEY=CHANGE_ME
DEEPSEEK_API_KEY=CHANGE_ME
OPENROUTER_API_KEY=CHANGE_ME
KIMI_API_KEY=CHANGE_ME
WAFER_API_KEY=CHANGE_ME

# ---------------------------------------------------------------------------
# 🏠 Local Provider Base URLs (no API keys needed)
# 🏠 عناوين URL للمزودين المحليين (لا حاجة لمفاتيح API)
# ---------------------------------------------------------------------------
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LLAMACPP_BASE_URL=http://localhost:8080/v1
OLLAMA_BASE_URL=http://localhost:11434

# ---------------------------------------------------------------------------
# 🛡️ Gateway Authentication — Protects all gateway endpoints
# 🛡️ مصادقة البوابة — تحمي جميع نقاط نهاية البوابة
# ---------------------------------------------------------------------------
# When set, clients must send: x-api-key: <ANTHROPIC_AUTH_TOKEN>
# عندما يتم تعيينه، يجب على العملاء إرسال: x-api-key: <ANTHROPIC_AUTH_TOKEN>
ANTHROPIC_AUTH_TOKEN=CHANGE_ME

# ---------------------------------------------------------------------------
# 🔄 Provider Proxies (optional — use only trusted proxies)
# 🔄 بروكسي المزودين (اختياري — استخدم فقط بروكسي موثوق)
# ---------------------------------------------------------------------------
# NVIDIA_NIM_PROXY=
# OPENROUTER_PROXY=
# LMSTUDIO_PROXY=
# LLAMACPP_PROXY=
# KIMI_PROXY=
# WAFER_PROXY=

# ---------------------------------------------------------------------------
# 🎯 Model Selection — provider_type/model/name format
# 🎯 اختيار النماذج — بتنسيق provider_type/model/name
# ---------------------------------------------------------------------------
MODEL=nvidia_nim/z-ai/glm4.7
# MODEL_OPUS=deepseek/deepseek-chat
# MODEL_SONNET=open_router/anthropic/claude-3.5-sonnet
# MODEL_HAIKU=lmstudio/local-model

# ---------------------------------------------------------------------------
# ⏱️ Provider Rate Limiting — Prevent runaway costs
# ⏱️ تقييد معدل المزودين — منع التكاليف غير المنضبطة
# ---------------------------------------------------------------------------
PROVIDER_RATE_LIMIT=40
PROVIDER_RATE_WINDOW=60
PROVIDER_MAX_CONCURRENCY=5

# ---------------------------------------------------------------------------
# 🔌 HTTP Client Timeouts (seconds)
# 🔌 مهلات عميل HTTP (بالثواني)
# ---------------------------------------------------------------------------
HTTP_READ_TIMEOUT=120
HTTP_WRITE_TIMEOUT=10
HTTP_CONNECT_TIMEOUT=10

# ---------------------------------------------------------------------------
# 🌐 Web Server Tools (SSRF risk — keep disabled unless needed)
# 🌐 أدوات خادم الويب (خطر SSRF — أبقِ معطّلة إلا عند الحاجة)
# ---------------------------------------------------------------------------
ENABLE_WEB_SERVER_TOOLS=false
WEB_FETCH_ALLOWED_SCHEMES=http,https
WEB_FETCH_ALLOW_PRIVATE_NETWORKS=false

# ---------------------------------------------------------------------------
# 💬 Messaging Platform Tokens
# 💬 رموز منصة الرسائل
# ---------------------------------------------------------------------------
MESSAGING_PLATFORM=none
# MESSAGING_PLATFORM=telegram
# TELEGRAM_BOT_TOKEN=CHANGE_ME
# ALLOWED_TELEGRAM_USER_ID=CHANGE_ME
# MESSAGING_PLATFORM=discord
# DISCORD_BOT_TOKEN=CHANGE_ME
# ALLOWED_DISCORD_CHANNELS=CHANGE_ME

# ---------------------------------------------------------------------------
# 🎙️ Voice Transcription (optional)
# 🎙️ النسخ الصوتي (اختياري)
# ---------------------------------------------------------------------------
VOICE_NOTE_ENABLED=true
WHISPER_DEVICE=cpu
WHISPER_MODEL=base
# HF_TOKEN=CHANGE_ME

# ---------------------------------------------------------------------------
# 📊 Debug Logging — ALL FALSE in production (may log sensitive content)
# 📊 تسجيل التصحيح — جميعها FALSE في الإنتاج (قد يسجّل محتوى حساس)
# ---------------------------------------------------------------------------
LOG_RAW_API_PAYLOADS=false
LOG_RAW_SSE_EVENTS=false
LOG_API_ERROR_TRACEBACKS=false
LOG_RAW_MESSAGING_CONTENT=false
LOG_RAW_CLI_DIAGNOSTICS=false
LOG_MESSAGING_ERROR_DETAILS=false
DEBUG_PLATFORM_EDITS=false
DEBUG_SUBAGENT_STACK=false

# ---------------------------------------------------------------------------
# 🖥️ Server
# 🖥️ الخادم
# ---------------------------------------------------------------------------
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8082
```

### Security Checklist | قائمة التحقق الأمني

Before deploying the gateway to any non-local environment, verify:

قبل نشر البوابة إلى أي بيئة غير محلية، تحقق:

- [ ] All `CHANGE_ME` values replaced with real keys
  جميع قيم `CHANGE_ME` استُبدلت بمفاتيح حقيقية
- [ ] `.env` file permissions set to `600`
  صلاحيات ملف `.env` مضبوطة على `600`
- [ ] `.env` added to `.gitignore`
  `.env` مُضاف إلى `.gitignore`
- [ ] `ANTHROPIC_AUTH_TOKEN` set for endpoint protection
  `ANTHROPIC_AUTH_TOKEN` مُعيّن لحماية نقاط النهاية
- [ ] Debug logging flags all `false`
  جميع أعلام تسجيل التصحيح `false`
- [ ] `ENABLE_WEB_SERVER_TOOLS=false` unless explicitly needed
  `ENABLE_WEB_SERVER_TOOLS=false` ما لم يكن مطلوبًا صراحة
- [ ] `WEB_FETCH_ALLOW_PRIVATE_NETWORKS=false`
  `WEB_FETCH_ALLOW_PRIVATE_NETWORKS=false`
- [ ] Local providers firewalled (not exposed to network)
  المزودون المحليون محميون بجدار حماية (غير معرّضين للشبكة)
- [ ] Rate limits configured per provider tier
  حدود المعدل مُهيأة حسب مستوى كل مزود
- [ ] Secrets sourced from vault (not only `.env`)
  الأسرار مُستَقاة من خزينة (وليس فقط من `.env`)
- [ ] Pre-commit hooks active for secret scanning
  خطافات ما قبل الإرسال نشطة لمسح الأسرار

---

*Last updated | آخر تحديث: 2025-07-10 — OmniMedical Suite AI Gateway*
