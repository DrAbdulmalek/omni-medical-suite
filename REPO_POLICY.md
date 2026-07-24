# Repository Policy & Development Rules

> These policies apply to **this repository only** (omni-medical-suite).
> For cross-repo policy, see `intelli-file-manager/REPO_POLICY.md` and the
> portfolio strategy in `docs/ADR/005-repo-portfolio-strategy.md`.

## Branch protection

- `main` is protected.
- No direct push to `main`. All changes via PR.
- No force-push to `main` (history is immutable on main).
- Short-lived feature branches only (`<feature>/<short-name>` or `fix/<short-name>`).
- Branches older than 30 days without activity should be deleted or rebased.

## PR rules

- One PR = one concern. No "spring cleanup" mega-PRs.
- PR description must state: what changes, why, what's tested, what's deferred.
- Tests must pass before merge.
- New dependencies require explicit approval (document why, what for, what cost).
- No "good idea" merges. Unverified code is treated as risk until proven otherwise.

## Boundary rules (binding)

- This repo MUST NOT import from `intelli-file-manager`'s source tree.
- This repo MUST NOT configure CI that touches `intelli-file-manager`.
- Backup scripts MUST NOT bundle sibling repos. Each repo backs up itself.
- Release tags follow `v<MAJOR>.<MINOR>.<PATCH>` semantic versioning.
- Artifact names (`MedicalDocProcessor-*.AppImage`, `omni-medical-*.apk`) MUST
  start with `Medical` or `omni` prefix. No `intelli-*` artifact names.

## Security rules

- No real secrets in tracked files. `.env*` files MUST be in `.gitignore` except
  `.env.example` (which must contain only placeholder values).
- Default passwords (`admin123`, `change-me`, `dev-secret`, etc.) MUST NOT appear
  in source code (excluding `.env.example`). Use `os.environ.get(...)` with safe
  defaults only in test fixtures.
- The credential-scan workflow (`.github/workflows/credential-scan.yml`) MUST
  use a regex-based scanner (gitleaks or trufflehog) — not a fixed-string allowlist.
  The current fixed-string allowlist is a known gap (see SECURITY_NOTES.md).
- All `secrets.*` references in workflows must reference named GitHub secrets —
  no inline base64 blobs, no `env:PAT_*` constructed at runtime.

## Dependency rules

- numpy MUST stay `<2.0.0` for the AppImage build chain (OpenBLAS ELF alignment bug).
  This applies to: `packages/desktop/requirements.txt`, `packages/scanner_fixer/pyproject.toml`.
- Python 3.10+ required.
- Heavy ML deps (sentence-transformers, chromadb, ollama) are lazy-imported in core modules.

## Test rules

- Unit tests live under `tests/` or `packages/<name>/tests/`.
- Integration tests live under `tests/integration/` or per-package equivalents.
- Smoke tests for AppImage (e.g. `packages/desktop/test_appimage_smoke.py`) MUST be
  run in CI before any release tag is pushed.
- No test may make real network calls. Mock all HTTP / SDK calls.

## Forbidden patterns

- "Spring cleanup" commits that touch >50 files in unrelated areas.
- Refactor PRs that also add features.
- "While I was here" changes that drift from the PR title.
- Marketing language in technical docs ("revolutionary", "world-class", etc.).
