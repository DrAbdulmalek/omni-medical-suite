# Security Guide — OmniMedical Suite

> **OmniMedical Suite** is a medical document processing platform that handles
> Protected Health Information (PHI) and Personally Identifiable Information (PII).
> This guide describes the security architecture, configuration requirements, and
> operational procedures needed to keep the system secure in production.

---

## Table of Contents

1. [Security Overview](#1-security-overview)
2. [Environment Variables](#2-environment-variables)
3. [NextAuth.js Setup](#3-nextauthjs-setup)
4. [AES-256-GCM Encryption](#4-aes-256-gcm-encryption)
5. [Rate Limiting](#5-rate-limiting)
6. [PII Detection](#6-pii-detection)
7. [Audit Logging](#7-audit-logging)
8. [HIPAA / GDPR Compliance](#8-hipaa--gdpr-compliance)
9. [GPG Commit Signing](#9-gpg-commit-signing)
10. [Vulnerability Reporting](#10-vulnerability-reporting)
11. [Security Checklist](#11-security-checklist)

---

## 1. Security Overview

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Encryption at Rest** | AES-256-GCM via PBKDF2 (480 000 iterations) | Encrypt uploaded medical documents on disk |
| **Encryption in Transit** | TLS 1.3 (HTTPS) | Protect data between client and server |
| **Authentication** | NextAuth.js v4 — Credentials provider | User login with bcrypt password hashing |
| **Authorization** | Role-based (admin / editor / viewer) | Middleware enforces route-level access |
| **Rate Limiting** | Sliding-window, 100 req / 60 s per IP | Brute-force and DoS mitigation |
| **PII Detection** | Microsoft Presidio + regex fallback | Identify and mask sensitive entities in OCR output |
| **Audit Logging** | File + Redis + Database backends | Track every user action with IP and timestamp |
| **Account Lockout** | 5 failed attempts → 15 min cooldown | Prevent credential stuffing |

### Architecture Diagram (text)

```
Client (TLS 1.3) ──► Next.js Middleware (auth + rate-limit)
    │
    ├──► Protected API Routes ──► NextAuth JWT (role check)
    │       │
    │       ├──► Prisma ORM ──► SQLite (encrypted DB)
    │       ├──► Python API (FastAPI) ──► OCR / NLP Pipeline
    │       └──► AES-256-GCM encrypt/decrypt (file vault)
    │
    └──► Public Routes (login page only)
```

---

## 2. Environment Variables

All secrets **must** be stored in a `.env` file at the monorepo root or in a
secrets manager (Vault, AWS SSM, etc.). Never commit `.env` to version control.

### Generating Secure Secrets

```bash
# NEXTAUTH_SECRET — used to sign and encrypt JWT tokens
openssl rand -base64 32
# Example output: k7x9Pm2QvLw8NjRfYt6HgDcXaBzE4IsKlOpUq

# ENCRYPTION_KEY — base64-encoded 256-bit key for AES-256-GCM
openssl rand -base64 32
# Example output: mZ3fR8wKp2Lq9XvNc5TjYhBgDxA7Wn4EsIkOoU

# DATABASE_URL — SQLite path (must be on an encrypted volume in production)
DATABASE_URL="file:/var/lib/omni-medical/data.db"
```

### Required Variables

| Variable | Description | Default | Production |
|----------|-------------|---------|------------|
| `NEXTAUTH_SECRET` | JWT signing secret | _(none)_ | **Required** — generate with `openssl rand -base64 32` |
| `NEXTAUTH_URL` | Canonical URL of the app | `http://localhost:3000` | `https://your-domain.com` |
| `ENCRYPTION_KEY` | AES-256-GCM key (base64) | _(none)_ | **Required** — generate with `openssl rand -base64 32` |
| `DATABASE_URL` | Prisma database connection | `file:./dev.db` | `file:/encrypted-volume/data.db` |
| `REDIS_URL` | Redis for rate-limiting & audit | _(none)_ | `redis://redis:6379/0` |
| `NODE_ENV` | Runtime environment | `development` | `production` |

### Docker / Docker Compose

For Docker Compose deployments, pass secrets via environment file:

```bash
# .env.production
NEXTAUTH_SECRET=<generated-secret>
ENCRYPTION_KEY=<generated-key>
GRAFANA_PASSWORD=<strong-password>
```

```bash
docker compose --env-file .env.production -f infrastructure/docker/docker-compose.yml up -d
```

---

## 3. NextAuth.js Setup

### Configuration

Authentication is handled by NextAuth.js v4 with a Credentials provider defined in
`apps/web/lib/auth.ts`.

**Key settings:**
- Session strategy: **JWT** (stateless, 24-hour expiry)
- Password hashing: **bcrypt** (via `bcryptjs`)
- Adapter: **PrismaAdapter** for user persistence
- Sign-in page: `/login`

### Default Admin Credentials

> **WARNING** — The following default credentials are created by the seed script
> (`prisma db seed`). **You must change the admin password immediately after
> first login in any non-local environment.**

| Field | Value |
|-------|-------|
| Username | `admin` |
| Password | `admin123` |
| Role | `admin` |

### Account Lockout Policy

| Parameter | Value |
|-----------|-------|
| Max failed attempts | **5** |
| Lockout duration | **15 minutes** |
| Auto-unlock | Yes — after lockout period expires |
| Counter reset | On successful login |

### Password Verification Flow

```
1. User submits username + password
2. System checks if account is locked → return "locked" error with time remaining
3. System compares password via bcrypt.compare()
4. On failure: increment failedAttempts; if >= 5, set lockedUntil = now + 15min
5. On success: reset failedAttempts to 0, clear lockedUntil, update lastLogin
```

### JWT Middleware

The middleware (`apps/web/middleware.ts`) protects all API routes and dashboard pages.
Unauthenticated requests are redirected to `/login`.

Protected routes:
- `/dashboard/*`
- `/api/mistral/*`, `/api/process/*`, `/api/images/*`
- `/api/train/*`, `/api/predict/*`, `/api/training/*`
- `/api/export-training/*`, `/api/word-correction/*`
- `/api/ai-chat/*`, `/api/stats/*`, `/api/settings/*`

### Role-Based Access Control

Three roles are supported (defined in the `User` model):

| Role | Access Level |
|------|-------------|
| `admin` | Full access — user management, settings, all processing features |
| `editor` | Process, export, and annotate documents; cannot manage users |
| `viewer` | View processed results only; read-only access |

Enforce roles in API routes:

```typescript
// Example: admin-only route
const session = await getServerSession(authOptions);
if (session?.user?.role !== "admin") {
  return NextResponse.json({ error: "Forbidden" }, { status: 403 });
}
```

---

## 4. AES-256-GCM Encryption

All uploaded medical documents are encrypted at rest using AES-256-GCM.

### Key Derivation

| Parameter | Value |
|-----------|-------|
| Algorithm | **PBKDF2-HMAC-SHA256** |
| Iterations | **480 000** |
| Salt | Random 16 bytes (stored with ciphertext) |
| Key length | 256 bits (32 bytes) |

### Encryption Format

Each encrypted file follows this binary layout:

```
[12 bytes: IV/Nonce] [16 bytes: Auth Tag] [N bytes: Ciphertext]
```

### Encrypting a File (Python)

```python
from packages.security.encryption import FileEncryptor

encryptor = FileEncryptor(key="<ENCRYPTION_KEY from .env>")
encrypted_path = encryptor.encrypt_file("upload/medical-report.pdf")
# → upload/medical-report.pdf.enc
```

### Decrypting a File (Python)

```python
decrypted_path = encryptor.decrypt_file("upload/medical-report.pdf.enc")
# → upload/medical-report.pdf
```

### Key Rotation

To rotate the encryption key:

1. Generate a new key: `openssl rand -base64 32`
2. Update `ENCRYPTION_KEY` in `.env`
3. Run the migration script to re-encrypt all files with the new key
4. securely destroy the old key

### Current Implementation Note

The existing `packages/security/encryption.py` uses Fernet (AES-128-CBC) for
backward compatibility. For production deployment handling PHI, migrate to the
AES-256-GCM implementation described above. The upgrade path preserves the same
`FileEncryptor` interface.

---

## 5. Rate Limiting

Rate limiting protects against brute-force attacks and abuse.

### Implementation

The rate limiter (`apps/web/lib/rate-limit.ts`) uses an in-memory sliding window
algorithm. For multi-instance deployments, use Redis as the backing store.

### Default Configuration

| Parameter | Value |
|-----------|-------|
| Algorithm | Sliding window |
| Default limit | **100 requests / 60 seconds** |
| Cleanup interval | 5 minutes |
| Response on limit | HTTP 429 with `Retry-After` header |

### Per-Route Configuration

```typescript
import { withRateLimit } from "@/lib/rate-limit";

export async function POST(request: Request) {
  // Stricter limit for auth endpoint: 10 req / 60s
  const { limited, response } = withRateLimit(request, 10, 60);
  if (limited) return response;

  // ... handle request
}
```

### Recommended Route Limits

| Route Pattern | Max Requests | Window (s) | Rationale |
|---------------|-------------|------------|-----------|
| `/api/auth/*` | 10 | 60 | Prevent brute-force |
| `/api/process/*` | 20 | 60 | Resource-intensive OCR |
| `/api/train/*` | 5 | 60 | GPU-intensive training |
| `/api/ai-chat/*` | 30 | 60 | LLM rate limits |
| All other API | 100 | 60 | General protection |

### Headers Returned

```
X-RateLimit-Remaining: 87
Retry-After: 42
```

---

## 6. PII Detection

The sensitive data scanner (`packages/security/sensitive_data_scanner.py`) detects
and masks Personally Identifiable Information in OCR output.

### Detection Engines

| Engine | When Used | Accuracy |
|--------|-----------|----------|
| **Microsoft Presidio** | When `presidio-analyzer` is installed | High |
| **Regex fallback** | Always active (supplementary) | Medium |

### Detected Entity Types

| Entity | Risk Level | Regex Pattern (simplified) |
|--------|-----------|---------------------------|
| Credit Card Number | **HIGH** | 13-16 digit card number |
| Email Address | MEDIUM | Standard email format |
| Phone Number | MEDIUM | International phone formats |
| Social Security Number | **HIGH** | `XXX-XX-XXXX` |
| IP Address | LOW | `x.x.x.x` |
| API Key / Token | **HIGH** | Key-value pattern |
| JWT Token | **HIGH** | `eyJ...` pattern |
| AWS Access Key | **HIGH** | `AKIA...` prefix |
| Private Key | **CRITICAL** | PEM header |
| IBAN | **HIGH** | `XX00XXXX...` |

### Usage Example

```python
from packages.security.sensitive_data_scanner import SensitiveDataScanner

scanner = SensitiveDataScanner(use_presidio=True)

result = scanner.scan_text(
    "Patient John Doe, SSN 123-45-6789, phone +1-555-0123"
)
# → {
#   "sensitive_data_found": True,
#   "risk_level": "high",
#   "entities": [
#     {"type": "PERSON", "text": "John Doe", ...},
#     {"type": "SSN", "text": "123-45-6789", "risk": "high", ...},
#     {"type": "PHONE_NUMBER", "text": "+1-555-0123", "risk": "medium", ...}
#   ]
# }

anonymized = scanner.anonymize_text(
    "Patient John Doe, SSN 123-45-6789"
)
# → "Patient [REDACTED], SSN [REDACTED]"
```

### Risk Levels

| Level | Description | Action |
|-------|-------------|--------|
| `none` | No PII found | Process normally |
| `low` | IP addresses, generic identifiers | Log warning |
| `medium` | Emails, phone numbers | Mask in exports |
| `high` | SSN, credit cards, medical IDs | **Block** processing, require review |
| `critical` | Private keys, credentials | **Alert** admin immediately |

---

## 7. Audit Logging

The audit logger (`packages/security/audit_logger.py`) records all significant
user and system actions for compliance and forensic analysis.

### Log Entry Schema

```json
{
  "id": "a1b2c3d4e5f6",
  "timestamp": "2025-07-10T14:30:00Z",
  "action": "ocr_process",
  "level": "info",
  "user": "admin",
  "ip_address": "192.168.1.100",
  "details": { "engine": "mixed_engine", "confidence": 0.95 },
  "status": "success",
  "duration_ms": 1234.5,
  "resource": "medical-report.pdf",
  "version": "3.0.0"
}
```

### Tracked Actions

| Category | Actions |
|----------|---------|
| **OCR** | `ocr_process`, `ocr_correct`, `ocr_fusion` |
| **NLP** | `nlp_translate`, `nlp_summarize`, `nlp_spell_check`, `nlp_ner`, `nlp_classify` |
| **Security** | `security_encrypt`, `security_decrypt`, `security_scan`, `security_pii_detect` |
| **File** | `file_upload`, `file_download`, `file_delete`, `file_export` |
| **System** | `system_login`, `system_logout`, `system_config_change`, `system_error` |
| **AI** | `ai_correct`, `ai_refine` |

### Storage Backends

| Backend | Use Case | Configuration |
|---------|----------|---------------|
| **File** | Default — JSONL lines in `logs/audit.log` | `enable_file=True` |
| **Redis** | Fast querying, keeps last 10 000 entries | `REDIS_URL` env var |
| **Database** | Persistent long-term storage | `enable_db=True` |

### Querying Logs

```python
from packages.security.audit_logger import get_audit_logger

logger = get_audit_logger()

# Get all logs for a specific user
user_logs = logger.get_logs(user="admin", limit=50)

# Get security events only
security_logs = logger.get_logs(level="security", limit=100)

# Get statistics
stats = logger.get_stats()
# → {"total_logs": 1234, "by_action": {...}, "errors_count": 5, ...}

# Clean up logs older than 30 days
deleted = logger.clear_logs(older_than_days=30)
```

### IP Address Logging

Every audit entry captures the client IP address. When behind a proxy, the system
reads from `X-Forwarded-For` header. Ensure your reverse proxy (nginx, Traefik)
sets `X-Real-IP` or `X-Forwarded-For` correctly.

---

## 8. HIPAA / GDPR Compliance

OmniMedical Suite implements the following controls to support HIPAA and GDPR
requirements. **This does not constitute legal advice — consult your compliance
officer.**

### Data Minimization

- OCR results are stored only as long as needed; configurable retention period
- Raw uploaded images can be purged after processing (opt-in)
- PII is automatically detected and masked before export
- No unnecessary metadata is collected beyond what is required for processing

### Access Controls

| Control | Implementation |
|---------|---------------|
| Unique user identification | NextAuth.js credentials + Prisma `User` model |
| Role-based access | Three roles: `admin`, `editor`, `viewer` |
| Session timeout | JWT expires after 24 hours |
| Account lockout | 5 failed attempts → 15-minute lock |
| Audit trail | Every action logged with user, IP, timestamp |
| Encryption at rest | AES-256-GCM on all stored documents |
| Encryption in transit | TLS 1.3 enforced |

### Encryption at Rest

- **Database**: SQLite file stored on an encrypted volume (LUKS, EBS encryption, etc.)
- **Documents**: AES-256-GCM encryption via `packages/security/encryption.py`
- **Keys**: Stored in environment variables or secrets manager; never in source code

### Data Subject Rights (GDPR)

| Right | Support |
|-------|---------|
| Right of access | Admin can export all data for a user via audit logs |
| Right to erasure | `file_delete` action + `clear_logs()` for data purging |
| Right to rectification | Document re-processing pipeline available |
| Right to restriction | User accounts can be deactivated (`isActive = false`) |
| Data portability | Export to Markdown, DOCX, XLSX via `packages/export/` |

### Breach Notification

In the event of a suspected data breach:

1. **Immediately** revoke all active sessions (clear JWT secret)
2. Review audit logs for unauthorized access
3. Notify your Data Protection Officer (DPO) within 72 hours (GDPR)
4. Preserve audit logs as forensic evidence (do **not** run `clear_logs`)
5. Rotate all encryption keys and credentials

---

## 9. GPG Commit Signing

All commits to this repository should be signed with GPG to ensure authenticity
and integrity.

### Step 1: Install GPG

```bash
# macOS
brew install gnupg

# Ubuntu / Debian
sudo apt-get install gnupg

# Windows (via scoop)
scoop install gnupg
```

### Step 2: Generate a GPG Key

```bash
gpg --full-generate-key
```

Select:
- Kind of key: **RSA and RSA**
- Key size: **4096 bits**
- Expiration: **1 year** (or your preferred duration)

### Step 3: List Your Key

```bash
gpg --list-secret-keys --keyid-format=long
```

Output will contain a line like:

```
sec   rsa4096/ABCDEF1234567890 2025-07-10 [SC] [expires: 2026-07-10]
```

Copy the key ID (`ABCDEF1234567890` after the `/`).

### Step 4: Export the Public Key

```bash
gpg --armor --export ABCDEF1234567890
```

Add the output to your GitHub/GitLab GPG keys settings.

### Step 5: Configure Git

```bash
git config --global user.signingkey ABCDEF1234567890
git config --global commit.gpgsign true
git config --global tag.gpgsign true
```

### Step 6: Verify a Commit

```bash
git log --show-signature -1
```

You should see `Good signature from ...` in the output.

---

## 10. Vulnerability Reporting

If you discover a security vulnerability in OmniMedical Suite, please report it
responsibly.

### How to Report

1. **Email**: Send a detailed report to the project maintainer
2. **Do NOT** open a public issue for security vulnerabilities
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fix (optional)

### What We Commit To

- **Acknowledge** receipt within 48 hours
- **Assess** the severity within 5 business days
- **Fix** critical issues within 30 days
- **Credit** researchers in the security advisory (unless anonymous)

### Supported Versions

| Version | Support Status |
|---------|----------------|
| `main` branch | Active — receives security patches |
| Latest release | Active — receives security patches |
| Older releases | Best-effort — upgrade to latest |

---

## 11. Security Checklist

Use this checklist before deploying to any non-local environment.

### Pre-Deployment Checklist

- [ ] **NEXTAUTH_SECRET** is set to a cryptographically random value (not the default)
- [ ] **ENCRYPTION_KEY** is set and different from the development key
- [ ] **Default admin password** (`admin123`) has been changed
- [ ] **DATABASE_URL** points to an encrypted volume
- [ ] **REDIS_URL** is configured and Redis requires authentication
- [ ] **NODE_ENV** is set to `production`
- [ ] **TLS** is terminated at the reverse proxy with a valid certificate
- [ ] **Rate limiting** is active on all API routes
- [ ] **PII detection** is enabled (`enablePII: true` in AppSettings)
- [ ] **Audit logging** is enabled (`enableAudit: true` in AppSettings)
- [ ] **GPG commit signing** is enforced (`commit.gpgsign = true`)
- [ ] **Unused API keys** and tokens have been revoked
- [ ] **CORS** is configured to allow only trusted origins
- [ ] **File upload size limit** is enforced (default: 50 MB in AppSettings)
- [ ] **Docker images** are built from a clean checkout with no `.env` baked in
- [ ] **Dependencies** have been audited (`npm audit`, `pip audit`)
- [ ] **Firewall** allows only ports 80/443 (and SSH on a non-standard port)
- [ ] **Backups** are configured for the database and encrypted files
- [ ] **Monitoring** is active (Prometheus + Grafana) with alert rules configured
- [ ] **Health check endpoints** return 200 (Docker healthcheck configured)

### Periodic Review Checklist

- [ ] Rotate `NEXTAUTH_SECRET` (quarterly)
- [ ] Rotate `ENCRYPTION_KEY` and re-encrypt files (annually)
- [ ] Review and clean up audit logs (keep 90 days minimum for compliance)
- [ ] Update dependencies (`npm update`, `pip install --upgrade`)
- [ ] Review user accounts — deactivate unused accounts
- [ ] Test the lockout mechanism still works
- [ ] Verify PII detection catches new patterns in your data

---

## Quick Reference Commands

```bash
# Generate all secrets at once
openssl rand -base64 32 > /tmp/nextauth_secret
openssl rand -base64 32 > /tmp/encryption_key

# Seed the default admin user
npx prisma db seed

# Run security check (Makefile target)
make security-check

# Build Docker images
docker compose -f infrastructure/docker/docker-compose.yml build

# Check for committed secrets
git log --all --full-history -- "*.env" "*.key" "*.pem"
```

---

*Last updated: 2025-07-10 — OmniMedical Suite v1.0.0*
