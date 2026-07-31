# Security Policy - Medical Document Processor

## Overview

This document contains security guidelines for the Medical Document Processor project.
Since this application handles sensitive medical documents (PHI), security is critical.

## Authentication

### NextAuth.js Setup

The application uses NextAuth.js v4 with credentials-based authentication.

1. **Default Admin**: After deployment, visit `/api/auth/seed` to create the default admin user.
2. **Change Default Password**: Immediately change the default password (`admin123`) after first login.
3. **Session Management**: JWT sessions expire after 24 hours.
4. **Account Lockout**: Accounts are locked after 5 failed login attempts for 15 minutes.

### Protected Routes

All API routes under `/api/mistral/*`, `/api/process/*`, `/api/images/*`, etc. are protected.
Unauthenticated users are redirected to `/login`.

## Encryption

- **At Rest**: Medical images are encrypted using AES-256-GCM with PBKDF2 (480K iterations).
- **In Transit**: Always use HTTPS in production (Let's Encrypt recommended).
- **Database**: SQLite database contains only metadata; encrypted files are stored separately.

## Environment Variables

**NEVER commit `.env` or `.env.local` to Git.** Use `.env.example` as a template.

Required variables:
- `DATABASE_URL` - SQLite connection string
- `NEXTAUTH_SECRET` - Generate with `openssl rand -base64 32`

## Rate Limiting

API endpoints are protected with sliding-window rate limiting:
- Default: 100 requests per 60 seconds per IP
- Stricter limits for mutations (5 requests/60s)
- Returns HTTP 429 with `Retry-After` header when exceeded

## GPG Commit Signing

### Setup (Recommended)

```bash
# 1. Generate a GPG key
gpg --full-generate-key
# Select: RSA and RSA, 4096 bits, expiration: 1y

# 2. List your keys
gpg --list-secret-keys --keyid-format=long

# 3. Configure Git to use GPG
git config --global user.signingkey YOUR_KEY_ID
git config --global commit.gpgsign true

# 4. (Optional) Add GPG key to GitHub
gpg --armor --export YOUR_KEY_ID
# Go to: GitHub > Settings > SSH and GPG keys > New GPG key
# Paste the output
```

### Verify Signed Commits

```bash
git log --show-signature
```

Signed commits will show `Good signature` in the output.

## HIPAA / GDPR Considerations

- All patient images MUST be encrypted at rest
- Audit logging is enabled for all authentication events
- PII is automatically redacted from log files
- Access control is role-based (admin, user)
- Database backups should also be encrypted

## Reporting Security Issues

If you discover a security vulnerability, please report it privately to the repository maintainer.
Do NOT open a public issue for security vulnerabilities.
