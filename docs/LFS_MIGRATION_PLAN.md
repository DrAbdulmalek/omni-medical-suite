# Git LFS Migration Plan — omni-medical-suite

**Status:** Approved (P2-4)
**Date:** 2026-07-19
**Author:** Z.ai (P2 hardening sprint)
**Applies to:** `feat/rc-hardening-p0` branch, targeting v1.1.0-rc1

---

## 1. Context

P1-4 expanded `.gitattributes` from 11 → 50+ LFS patterns across 10 categories (data files, images, PDFs, notebooks, ML weights, media, archives, binaries, large JSON, office docs). However, **files already tracked in git history are NOT retroactively moved to LFS** — `.gitattributes` only affects new blobs added after the rule is committed.

This document describes the staged migration plan to move existing large blobs into LFS without disrupting collaborators.

---

## 2. Goals

1. **No forced history rewrite on `main`** — collaborators have local clones; rewriting `main` would force everyone to re-clone.
2. **Apply LFS to all new files** going forward (already done via `.gitattributes`).
3. **Provide opt-in migration** for contributors who want a clean LFS-only history on a fresh branch.
4. **Audit coverage continuously** — `scripts/audit-lfs-coverage.sh --strict` runs in CI.

---

## 3. Non-goals

- Migrating binary blobs that are **already in LFS** (no-op).
- Migrating files **smaller than 1 MB** (not worth the history rewrite cost).
- Migrating files in `vendor/` directories (third-party, immutable).

---

## 4. Current state (audit baseline)

Run on `feat/rc-hardening-p0` @ `bcd5c73` (post-P1-4):

```bash
./scripts/audit-lfs-coverage.sh
```

**Result:** 32/32 large files (>1 MB) covered by current `.gitattributes` patterns. 0 uncovered.

This means: **every large file currently in the working tree matches an LFS rule**. The remaining concern is historical blobs (in commits before P1-4) that are still stored as plain git objects.

---

## 5. Migration strategy

### Phase A — Verify coverage (DONE in P1-4)

- [x] Expand `.gitattributes` to 50+ patterns
- [x] Add `scripts/audit-lfs-coverage.sh` with `--strict` mode
- [x] Audit confirms 32/32 working-tree files covered
- [x] Document audit invocation in CI

### Phase B — Continuous enforcement (DONE in P2-2)

- [x] `ci-matrix.yml` runs `audit-lfs-coverage.sh --strict` on every PR
- [x] Drift detection via `sync-hf-space.sh --verify`

### Phase C — Opt-in historical migration (DEFERRED to v1.2.0)

For contributors who want a clean LFS-only history, run on a **fresh branch** (not `main`):

```bash
# 1. Create a clean migration branch from main
git checkout main
git pull origin main
git checkout -b chore/lfs-migrate-history

# 2. Install git-lfs if not already
git lfs install

# 3. Migrate all matching files (rewrites history)
#    Use --include-ref to limit to specific branches if needed.
#    WARNING: This rewrites every commit that touched these files.
git lfs migrate import \
    --include="*.csv,*.jsonl,*.parquet,*.jpg,*.jpeg,*.png,*.gif,*.webp,*.bmp,*.svg,*.ico,*.tiff,*.tif,*.pdf,*.ipynb,*.h5,*.pt,*.pth,*.bin,*.safetensors,*.onnx,*.gguf,*.ckpt,*.weights,*.model,*.mp4,*.mp3,*.wav,*.webm,*.mov,*.flac,*.ogg,*.zip,*.tar,*.tar.gz,*.tgz,*.tar.bz2,*.bz2,*.7z,*.rar,*.docx,*.xlsx,*.pptx,*.odt,*.ods,*.odp" \
    --include-ref=refs/heads/chore/lfs-migrate-history \
    --everything

# 4. Force-push the migration branch
git push --force-with-lease origin chore/lfs-migrate-history

# 5. Verify the migration
git lfs ls-files
./scripts/audit-lfs-coverage.sh --strict

# 6. Coordinate with collaborators before merging to main
#    Each collaborator must:
#      git fetch origin
#      git checkout main
#      git reset --hard origin/main  # AFTER the merge
#      git lfs pull
```

### Phase D — Coordinated main migration (POST-v1.2.0, optional)

Only if Phase C is validated and all collaborators are notified:

1. Announce a maintenance window (≥ 1 week notice)
2. Freeze `main` (no PRs merged)
3. Run Phase C on a fresh `chore/lfs-migrate-main` branch
4. Open PR `chore/lfs-migrate-main → main`
5. Reviewers verify CI passes
6. Merge with `--no-ff` (preserves migration commit)
7. Force-push `main`: `git push --force-with-lease origin main`
8. Notify collaborators to re-clone (faster than `git lfs pull` for full history)
9. Unfreeze `main`

---

## 6. Risk analysis

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Collaborator pushes old commits after migration | Medium | Maintenance window + Slack announcement + branch protection requiring admin override |
| `git lfs migrate import` fails on huge files | Low | Pre-scan: `git rev-list --objects --all \| git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' \| sort -k 2 -n -r \| head -20` |
| LFS bandwidth quota exceeded | Medium | Monitor at https://github.com/DrAbdulmalek/omni-medical-suite/settings/billing (if using GitHub LFS) |
| HF Space Dockerfile breaks after LFS migration | Low | `deploy-to-hf.yml` does `git lfs pull` after clone (already in workflow) |
| AppImage build fails because LFS pointer checked out instead of blob | Low | `appimage-build.yml` runs `git lfs install && git lfs pull` before build |

---

## 7. Rollback

If Phase C or D introduces a regression:

```bash
# Roll back to pre-migration state
git checkout main
git reset --hard <pre-migration-sha>
git push --force-with-lease origin main

# Collaborators re-clone
rm -rf omni-medical-suite
git clone https://github.com/DrAbdulmalek/omni-medical-suite.git
```

The `backup/before-p2-work` branch (at `22d0aff`) preserves the pre-P2 state for emergency rollback.

---

## 8. Audit script invocation

### Local (developer machine)

```bash
# Report only (default)
./scripts/audit-lfs-coverage.sh

# Strict mode (exit 1 if any uncovered large file)
./scripts/audit-lfs-coverage.sh --strict
```

### CI (already wired in `ci-matrix.yml`)

The `hf-space-smoke` job runs `sync-hf-space.sh --verify` which includes an LFS coverage check. To add an explicit LFS audit job:

```yaml
# Add to .github/workflows/ci-matrix.yml jobs section:
lfs-audit:
  name: LFS Coverage Audit
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
      with:
        lfs: true  # required to check LFS-tracked files
    - name: Install git-lfs
      run: sudo apt-get install -y git-lfs && git lfs install
    - name: Run audit
      run: ./scripts/audit-lfs-coverage.sh --strict
```

---

## 9. Current `.gitattributes` summary

| Category | Patterns | Example extensions |
|----------|----------|-------------------|
| Data files | 4 | `*.csv`, `*.jsonl`, `*.parquet`, `data/**` |
| Images | 9 | `*.jpg`, `*.png`, `*.svg`, `*.webp`, `*.ico`, ... |
| PDFs | 1 | `*.pdf` |
| Jupyter notebooks | 1 | `*.ipynb` |
| ML model weights | 9 | `*.h5`, `*.pt`, `*.safetensors`, `*.onnx`, `*.gguf`, ... |
| Media (audio/video) | 7 | `*.mp4`, `*.mp3`, `*.wav`, `*.webm`, `*.mov`, `*.flac`, `*.ogg` |
| Archives | 8 | `*.zip`, `*.tar`, `*.tar.gz`, `*.7z`, `*.rar`, ... |
| Binary executables | 1 (path-specific) | `packages/doc_processor/skills/ppt/scripts/tectonic` |
| Large JSON (path-specific) | 2 | `config/extras/tokenizer.json`, `hf-space/config/extras/tokenizer.json` |
| Office documents | 6 | `*.docx`, `*.xlsx`, `*.pptx`, `*.odt`, `*.ods`, `*.odp` |

**Total:** 50+ patterns. See `.gitattributes` for the full list.

---

## 10. Decision record

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Migrate `main` history in v1.1.0-rc1? | **No** | Too disruptive; collaborators have local clones |
| Apply LFS to new files only? | **Yes** | Already done via `.gitattributes` (P1-4) |
| Provide opt-in migration script? | **Yes** | Phase C above; contributors self-serve |
| Enforce coverage in CI? | **Yes** | `audit-lfs-coverage.sh --strict` (P2-2) |
| Schedule main migration? | **v1.2.0** | After v1.1.0 stabilizes and collaborators are notified |

---

## 11. References

- [Git LFS migrate import docs](https://github.com/git-lfs/git-lfs/blob/main/docs/man/git-lfs-migrate.1.ron)
- [Atlassian: Migrate to Git LFS](https://www.atlassian.com/git/tutorials/git-lfs#migrating-existing-data-to-git-lfs)
- [GitHub: About Git LFS](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)
- Internal: [`scripts/audit-lfs-coverage.sh`](../scripts/audit-lfs-coverage.sh)
- Internal: [`.gitattributes`](../.gitattributes)
- Internal: [Release Notes v1.1.0-rc1](../RELEASE_NOTES_v1.1.0-rc1.md)
