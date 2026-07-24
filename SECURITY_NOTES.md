# Security Notes & Incident Log

> **Security Level**: CRITICAL — all exposed secrets must be treated as emergencies.
> This file tracks all security incidents, vulnerabilities, and remediation actions
> on `omni-medical-suite`.

## Active findings (as of 2026-07-24)

### Finding 1 — `.env.test` is tracked in git (MEDIUM)

**Location**: `apps/handwriting-demo/.env.test`
**Issue**: File contains explicit credentials:
- `DATABASE_URL=postgresql://ocr_test_user:ocr_test_password@localhost:5432/medical_ocr_test`
- `MINIO_ACCESS_KEY=testminioadmin`
- `MINIO_SECRET_KEY=testminioadmin123`
- `SECRET_KEY=test-secret-key-do-not-use-in-production-abc123xyz`

The file is marked "DO NOT use in production", but it is committed to the repo
and visible to anyone with read access. Test credentials should be:
1. Generated at test-runtime (random UUIDs) OR
2. Stored in GitHub Actions secrets and injected via `env:` in workflow

**Remediation**:
- Add `.env.test` to `.gitignore`
- Move test credential values to GitHub Actions secrets
- Update test runner to inject credentials via environment

**Status**: Open — to be fixed in `ci-cd-normalization` PR.

---

### Finding 2 — Default credentials in source code (HIGH)

**Locations**:
- `packages/doc_processor/src/app/api/auth/seed/route.ts:27` — `bcrypt.hash("admin123", 12)`
- `packages/doc_processor/doc-processor/src/app/api/auth/seed/route.ts:27` — same (duplicate)
- `packages/file_processor/docker-compose.yml:173` — Flower basic auth `admin:admin123`

**Issue**: Default passwords (`admin123`) are baked into the codebase. If the seed
endpoint is deployed without changes, the admin account is compromisable on day one.
The Flower monitoring UI exposes `admin:admin123` to anyone with network access.

**Remediation**:
- Replace `admin123` in `route.ts` with `os.environ.get("ADMIN_SEED_PASSWORD")`
  and fail loudly if unset.
- Replace `admin:admin123` in docker-compose with `admin:${FLOWER_PASSWORD:?missing}`
  to require explicit env var at startup.
- Remove the duplicate `doc-processor/` directory entirely (legacy copy).

**Status**: Open — to be fixed in `governance-and-security-audit` PR
(infra changes only, no behavior change).

---

### Finding 3 — `credential-scan.yml` is bypassable (LOW)

**Location**: `.github/workflows/credential-scan.yml`
**Issue**: The scanner uses a fixed-string allowlist of 9 patterns. Any pattern
NOT in the list passes silently. Real secrets (GitHub PATs, AWS keys, GCP service
account JSON) would not be caught. Additionally, `git grep -il` (lowercase L) is
the case-insensitive flag — it does NOT skip binary files, so binary matches may
produce false positives or miss real findings.

**Remediation**:
- Replace with `gitleaks` action (or `trufflehog`).
- Run on every PR + every push to main + scheduled weekly.
- Fail build on any HIGH-confidence finding.

**Status**: Open — to be fixed in `ci-cd-normalization` PR.

---

### Finding 4 — `2>/dev/null` masks install failures in intelli-file-manager CI (LOW)

> NOTE: This finding is on the **other** repo (`intelli-file-manager`), logged here
> for cross-repo visibility.

**Location**: `intelli-file-manager/.github/workflows/ci.yml:37`
```yaml
run: pip install -e ".[dev]" 2>/dev/null || pip install -r requirements.txt pytest
```
**Issue**: Silencing stderr on `pip install` hides real failures (network issues,
version conflicts, missing optional deps). The fallback `pip install -r requirements.txt`
may install a different version set than the editable install would.

**Remediation**: Remove `2>/dev/null`. If the dev install fails, fail the build.

**Status**: Open — to be fixed in `ci-cd-normalization` PR on intelli-file-manager.

---

## Resolved incidents

### v1.1.0/v1.1.1 AppImage OpenBLAS crash (RESOLVED on main, NOT released)

**Date discovered**: 2026-07-22 (reported by user)
**Date fixed on main**: 2026-07-23 (commit 9f348d0)
**Date fixed in scanner_fixer pyproject**: 2026-07-23 (PR `fix/appimage-numpy-openblas-crash`)
**Status**: Fix is on `main` AND on branch `fix/appimage-numpy-openblas-crash`.
Neither v1.1.0 nor v1.1.1 contains the fix. A new release tag `v1.1.2` is pending.

**Root cause**: numpy 2.x bundles an OpenBLAS shared library that fails to load on
modern Linux kernels with `ELF load command address/offset not page-aligned`.

**Fix**: Pin `numpy>=1.24.0,<2.0.0` in:
- `packages/desktop/requirements.txt` (was already pinned on main)
- `packages/scanner_fixer/pyproject.toml` (was missing — added in PR branch)

Plus runtime hook `hook_numpy_openblas.py` to pre-load OpenBLAS with `RTLD_GLOBAL`.

**Lessons learned**:
- Pin numpy<2.0.0 in EVERY build chain file, not just the top-level requirements.
- Editable installs of internal packages can silently override top-level pins.
- PyInstaller smoke test (`test_openblas_fix.py`) is now in the repo as regression test.

---

## Scanning tools in use

- `credential-scan.yml` — fixed-string allowlist (current, weak)
- `security-scan.yml` — `pip-audit` + `safety` weekly (current, ok)
- CodeQL — checked in `dependabot/github_actions/github/codeql-action-4` (upgrade pending)

## Recommended additions

- gitleaks action (replaces credential-scan.yml)
- `pip-audit` on every PR (currently weekly only)
- SBOM generation on release (`syft` + `grype`)

## Secret rotation log

| Date | Secret | Action | Reason |
|------|--------|--------|--------|
| 2026-07-23 | GITHUB_TOKEN (PAT) | User asked to revoke | Token was pasted in chat by accident |

If you find a leaked secret, **immediately**:
1. Revoke it at the provider (GitHub, HF, Docker Hub, etc.)
2. Rotate any tokens that had the same scope
3. Add an entry to this log
4. Open a SECURITY advisory on GitHub (private until patched)
