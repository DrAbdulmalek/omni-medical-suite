# Branch & Archive Cleanup Recommendations

> Date: 2026-07-24
> Auditor: Architectural Review Bot
> Scope: Identify stale branches on origin that should be deleted after PR merge,
> and recommend archive policy for legacy directories.

## omni-medical-suite — branches on origin (41 total)

### Active / in-flight (KEEP)

- `main` — production
- `governance-and-security-audit` — PR open (this audit)
- `boundary-and-identity-audit` — PR open (this audit)
- `ci-cd-normalization` — PR open (this audit)
- `fix/appimage-numpy-openblas-crash` — PR open (previous session)

### Backup branches (REVIEW FOR DELETION)

These are point-in-time snapshots. They should be deleted once their
respective features have been merged or explicitly abandoned.

| Branch | Recommendation |
|--------|----------------|
| `backup/before-p2-work` | Delete if P2 work is merged |
| `backup/before-v1.1.0-stable` | Delete if v1.1.0 is tagged (it is, v1.1.1 too) |
| `backup/current-main-dictionaries` | Delete if dictionaries are on main |
| `backup/lost-monorepo-work-0273fc2` | Delete — name says "lost", no value |

### Dependabot branches (REVIEW PRs THEN DELETE)

| Branch | Action |
|--------|--------|
| `dependabot/github_actions/actions/setup-python-6` | Merge or close PR, then delete branch |
| `dependabot/github_actions/actions/upload-artifact-7` | Merge or close PR, then delete branch |
| `dependabot/github_actions/docker/metadata-action-6` | Merge or close PR, then delete branch |
| `dependabot/github_actions/github/codeql-action-4` | Merge or close PR, then delete branch |
| `dependabot/github_actions/softprops/action-gh-release-3` | Merge or close PR, then delete branch |
| `dependabot/pip/filelock-gte-3.31.0` | Merge or close PR, then delete branch |
| `dependabot/pip/gradio-gte-4.44.0-and-lt-7.0.0` | Merge or close PR, then delete branch |
| `dependabot/pip/opentelemetry-api-gte-1.44.0` | Merge or close PR, then delete branch |
| `dependabot/pip/opentelemetry-exporter-otlp-proto-http-gte-1.44.0` | Merge or close PR, then delete branch |
| `dependabot/pip/opentelemetry-sdk-gte-1.44.0` | Merge or close PR, then delete branch |
| `dependabot/pip/python-jose-gte-3.5.0` | Merge or close PR, then delete branch |
| `dependabot/pip/python-multipart-gte-0.0.32` | Merge or close PR, then delete branch |
| `dependabot/pip/requests-gte-2.34.2` | Merge or close PR, then delete branch |
| `dependabot/pip/sqlalchemy-gte-2.0.51` | Merge or close PR, then delete branch |
| `dependabot/pip/tqdm-gte-4.69.0` | Merge or close PR, then delete branch |

### Feature/fix branches (REVIEW FOR MERGE OR CLOSE)

| Branch | Status |
|--------|--------|
| `chore/unify-mobile-and-learning` | Review — name suggests merge candidate |
| `cleanup/final-pending-items` | Review — likely safe to merge or close |
| `docs/mobile-learning-loop` | Review — small docs PR |
| `feat/activate-pwa-docker` | Review |
| `feat/governance` | SUPERSEDED by `governance-and-security-audit` PR — delete after merge |
| `feat/mobile-server-wire-app-services` | Review |
| `feat/observability-llm-log-reviewer` | Review |
| `feat/rc-hardening-p0` | Review — likely merged into v1.1.0 |
| `feat/rc-hardening-p2` | Review — likely merged into v1.1.0 |
| `feat/scanner-fix-v2-clean-rewrite` | Review |
| `feat/scanner-fixer-auto-instrument` | Review |
| `feature/desktop-scanner-unify-package` | Review |
| `feature/full-integration-refactor` | Review |
| `feature/mobile-installer-and-appimage-freshness` | Review |
| `feature/wire-web-api-backend` | Review |
| `fix/pdf-ocr-processor-paddle-device` | Review |
| `fix/real-import-bugs-active-packages` | Review |
| `fix/scanner-fix-v2-bugs-only` | Review |
| `integrate/genspark-field-dedup` | Review |
| `refactor/scripts-pdf-ocr-thin-wrapper` | Review |
| `test/pdf-ocr-processor-suite` | Review |
| `unify/pdf-ocr-processor-engine-registry` | Review |

## Legacy directories in repo (REVIEW FOR ARCHIVAL)

These appear to be legacy / pre-restructure duplicates. They should be
moved to `legacy/` or deleted after confirming nothing depends on them.

| Path | Status | Recommendation |
|------|--------|----------------|
| `packages/doc_processor/doc-processor/` | DUPLICATE of `packages/doc_processor/` | Delete after audit |
| `packages/omnifile/` vs `packages/file_processor/` | 3-way duplicate of `__init__.py` (same MD5) | Consolidate to one |
| `apps/handwriting-demo/variants/handwriting-ocr/` | DUPLICATE of `packages/handwriting/` | Delete variant or merge |

## intelli-file-manager — branches on origin (24 total)

### Active (KEEP)

- `main` — production
- `intellifile-scope-reset` — PR open (this audit)
- `ci-cd-normalization` — PR open (this audit)

### Backup branches (REVIEW FOR DELETION)

| Branch | Recommendation |
|--------|----------------|
| `backup/pre-integration-20260719` | Delete — pre-merge backup, no longer needed |
| `ملاحظات-على-المشروع-8b739` | Rename to ASCII or delete — Arabic branch name causes tooling issues |

### Already-merged feature/fix branches (DELETE — merged into main)

These should be deleted because their work is already on main:

- `feat/governance` — merged
- `fix/scope-enforcement` — merged
- `repo-boundary-doc-cleanup` — merged
- `security-and-secret-audit` — merged

### Stale feature/fix branches (REVIEW)

- `feat/semantic-search-embeddings` — review for merge or close
- `fix/apk-artifact-path`, `fix/apk-build-system-deps`, `fix/apk-no-tail`,
  `fix/apk-yaml-v2`, `fix/ci-lint`, `fix/kivy-ndk-compat`,
  `fix/pyproject-build-backend` — review for merge or close
- `docs/development-roadmap` — small docs PR, likely safe to merge

### Dependabot branches (REVIEW PRs)

- `dependabot/github_actions/actions/checkout-7`
- `dependabot/github_actions/actions/setup-node-6`
- `dependabot/github_actions/actions/setup-python-6`
- `dependabot/pip/langchain-gte-1.3.11`
- `dependabot/pip/numpy-gte-2.2.6` — NOTE: this conflicts with REPO_POLICY
  (numpy<2.0.0 mandate). Should be CLOSED, not merged.
- `dependabot/pip/pillow-gte-12.3.0`
- `dependabot/pip/pyside6-gte-6.11.1`
- `dependabot/pip/sentence-transformers-gte-5.6.0`

## Cleanup commands (manual — for user to run after PR merges)

After merging the audit PRs and reviewing each branch above:

```bash
# omni-medical-suite — delete merged branches
git push origin --delete feat/governance

# intelli-file-manager — delete merged branches
git push origin --delete feat/governance
git push origin --delete fix/scope-enforcement
git push origin --delete repo-boundary-doc-cleanup
git push origin --delete security-and-secret-audit

# Both repos — close dependabot PRs that conflict with policy, then delete branches
# (do NOT auto-close dependabot PRs without review — some may be valid upgrades)
```

## Archive policy (binding)

- Backup branches older than 90 days with no activity → delete
- Dependabot PRs older than 60 days with no review → close PR + delete branch
- Feature branches older than 60 days with no activity → review for close + delete
- Legacy directories inside repo → move to `legacy/<date>-<name>/` after confirming no dependents
