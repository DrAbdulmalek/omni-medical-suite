# Repository Policy & Development Rules

## Overview

These policies apply to **all repositories** under `DrAbdulmalek`. Violations will be flagged and must be corrected immediately.

---

## 🔒 Git Workflow Rules

### Branching Strategy

| Rule | Description | Enforcement |
|------|-------------|-------------|
| **No direct pushes to main** | All changes must go through PRs | BLOCKING |
| **No force-push to main** | Force pushes to main are forbidden | BLOCKING |
| **Small PRs only** | PRs must be focused and reviewable (< 500 lines changed) | REQUIRED |
| **Feature branches only** | No long-lived branches except main | REQUIRED |
| **Branch naming** | `feat/`, `fix/`, `docs/`, `refactor/` prefixes | REQUIRED |

### Branch Cleanup

**Current State (2026-07-22):**
- intelli-file-manager: 24 branches (target: ≤ 5)
- omni-medical-suite: 30 branches (target: ≤ 5)
- **Total to delete: 47 branches**

**Cleanup Criteria:**
- Delete merged branches older than 7 days
- Delete stale branches (> 30 days without activity)
- Archive experimental branches as issues
- Keep only: main, active feature branches, release branches

---

## 🤖 AI Agent Rules

### Execution Agent

| Agent | Role | Permissions |
|-------|------|-------------|
| **Mistral (Vibe)** | Sole execution agent | Read/Write to all repos |
| **Z.ai** | Verifier only | Read-only (NO coding) |
| **Other AIs** | Forbidden | No access |

**Enforcement:**
- Only Mistral (Vibe) may modify repositories
- Z.ai may only: verify, cross-check, smoke test, release QA
- Any other AI session on these repos must be terminated immediately

### Parallel Work Restriction

**NO parallel AI sessions on the same repository.**

- If Mistral is working on intelli-file-manager, Z.ai may NOT work on it
- Z.ai may work on omni-medical-suite while Mistral works on intelli-file-manager
- Coordination required via shared work log

---

## 📝 Pull Request Rules

### Before Creating a PR

- [ ] Run all tests locally
- [ ] Run linter (ruff) and fix all errors
- [ ] Update documentation
- [ ] Add tests for new functionality
- [ ] Verify no secrets in changes

### PR Requirements

- **Title:** Clear and descriptive (use conventional commits)
- **Description:** Must include:
  - What problem this solves
  - What changes were made
  - How it was tested
  - Screenshots if UI changes
- **Labels:** At least one of: `feat`, `fix`, `docs`, `refactor`, `chore`
- **Reviewers:** At least 1 human reviewer (DrAbdulmalek)
- **Approval:** Requires approval before merge

### Merge Requirements

- [ ] All CI checks pass
- [ ] All tests pass
- [ ] No lint errors
- [ ] Approved by human reviewer
- [ ] Squash merge preferred
- [ ] Merge commit message follows conventional commits

---

## 🔐 Security Rules

### Secret Management

| Rule | Description |
|------|-------------|
| **No hardcoded secrets** | Never commit API keys, tokens, passwords |
| **No exposed PAT tokens** | Any exposed token must be revoked immediately |
| **Environment variables** | Use `.env` files (add to `.gitignore`) |
| **GitHub Secrets** | Use GitHub Actions secrets for CI/CD |

**If a secret is exposed:**
1. **IMMEDIATELY** revoke the exposed secret
2. Rotate all related credentials
3. Audit repository for other exposures
4. Document incident in SECURITY_NOTES.md
5. All work stops until remediation is complete

### Dependency Security

- [ ] Use `pip-audit` to check for vulnerable dependencies
- [ ] Update dependencies regularly
- [ ] Pin major versions in pyproject.toml
- [ ] Use `numpy<2.0.0` (OpenBLAS ELF alignment compatibility)

---

## 📦 Build & Deployment Rules

### Versioning

- Use semantic versioning (SemVer)
- Version format: `MAJOR.MINOR.PATCH`
- Pre-release: `MAJOR.MINOR.PATCH-rc.N`

### Release Process

1. Create release branch: `release/vX.Y.Z`
2. Update version in pyproject.toml
3. Update CHANGELOG.md
4. Run full test suite
5. Create PR to main
6. After merge, create GitHub release
7. Upload APK/PWA artifacts to release

---

## 🧪 Testing Rules

### Test Requirements

- Unit tests for all new functionality
- Integration tests for module interactions
- E2E tests for user flows
- Minimum test coverage: 80%

### Test Execution

- Run tests before every commit
- All tests must pass before PR creation
- CI must run tests on all supported Python versions (3.10+)

---

## 📊 Code Quality Rules

### Linting

- Use `ruff` for linting
- Zero lint errors required for PR
- Config in `pyproject.toml`

### Formatting

- Use `black` for code formatting
- Line length: 88 characters
- Run formatter before commit

### Type Checking

- Use `mypy` for type checking
- All public functions must have type hints
- Fix all type errors before PR

---

## 🚨 Violation Consequences

| Violation | Consequence |
|-----------|-------------|
| Direct push to main | Immediate revert, warning |
| Force push to main | Immediate revert, access review |
| Exposed secret | All work stops, full audit |
| Parallel AI sessions | Terminate extra sessions |
| Scope violation | Code removal, PR rejection |
| No tests | PR rejection |
| Lint errors | PR rejection |

---

## Approval

**Status:** APPROVED
**Approver:** DrAbdulmalek
**Review Date:** 2026-07-22
**Effective Date:** 2026-07-22