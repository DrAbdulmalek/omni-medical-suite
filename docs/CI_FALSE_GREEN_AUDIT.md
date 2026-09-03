# CI false-green audit — Issue #96

## Scope

This audit covers the secondary workflows named by Issue #96:

- `.github/workflows/lint-test.yml`
- `.github/workflows/python-ci.yml`
- `.github/workflows/ci-kimi-review.yml`
- `.github/workflows/android-apk.yml`

The canonical RC/production gates are intentionally out of scope for modification.

## Classification and disposition

### `lint-test.yml`

**Classification: required test/syntax gate plus separate informational formatting report.**

The required `Code Quality` job is fail-closed for flake8 `E999` syntax errors and for its tool installation. The full flake8 style report remains informational via `--exit-zero`.

Black and isort are intentionally **not part of the required `Code Quality` gate** at this stage. They run in a separate `Formatting Report (Informational)` job because the current codebase contains substantial pre-existing formatting debt (approximately 170 Black violations). Their `|| true` suppressors are therefore isolated from the required check rather than being used to manufacture a green required check.

A follow-up code-formatting task should reduce the existing Black/isort debt and can subsequently make formatting checks fail-closed if desired.

Coverage upload remains informational (`fail_ci_if_error: false`) because the pytest command itself is the required test gate.

### `python-ci.yml`

**Classification: required test gate; Black remains informational in this non-required workflow.**

The test command and critical flake8 checks are fail-closed. Black reporting remains informational because the workflow is not one of the branch-protection required checks and the codebase has pre-existing formatting debt. The workflow must not be interpreted as proof that Black passes.

### `android-apk.yml`

**Classification: the APK build must fail closed.**

Removed `continue-on-error: true` from the actual Buildozer build. A failed APK build can no longer produce a successful build job. The model download fallback remains intentional: the workflow explicitly supports a placeholder/offline-model path. The optional Hugging Face login remains non-fatal when a token is present because login is not itself the artifact build gate.

### `ci-kimi-review.yml`

**Classification: mixed: required critical-lint gate plus explicitly advisory diagnostics.**

The workflow is deliberately named `Lenient`, but its `lint-and-type` job is a required branch-protection check in this repository. That job therefore has a genuine fail-closed Ruff critical-errors gate. Ruff full-report, formatting, and mypy diagnostics remain informational because the current codebase contains substantial pre-existing findings.

The separate `test` and `appimage-build` jobs remain advisory and may be non-blocking. They must not be used as evidence that those operations passed.

The `pull_request` trigger is intentionally unfiltered so the required `lint-and-type` check is produced for every PR.

### `hf-space-drift.yml`

**Classification: required mirror-integrity gate.**

The `pull_request` trigger is intentionally unfiltered so the required `Verify hf-space ↔ app/services mirror` check is always produced. The verification commands are fail-closed.

### `mirror-verify.yml`

**Classification: required repo-integrity gate — contains a HIGH-severity false-green that must be tracked for follow-up.**

The `Mirror Verify` workflow runs on every PR and on push to main, and is one of the required checks on this repository. Its `verify` job currently contains three steps:

1. `Check git remotes` — informational display.
2. `Verify submodule integrity` — informational display.
3. `Check for broken gitlinks (mode 160000 without .gitmodules entry)` — **the actual safety check**.

Step 3 runs a bash script that:
- Lists all gitlinks via `git ls-tree -r HEAD | grep '^160000'`
- For each gitlink, verifies it has a corresponding entry in `.gitmodules`
- If not, emits `::error:: Gitlink '$path' has no .gitmodules entry (will break checkout)` and calls `exit 1`

**The bug:** Step 3 has `continue-on-error: true` set at the step level. This tells GitHub Actions to ignore the step's exit code, so even when `exit 1` is called because a broken gitlink was detected, the step is reported as "successful" and the workflow passes. The `::error::` annotation is still emitted (it appears in the PR's annotations panel), but the **check-run conclusion is `success`** regardless.

This means:
- A broken gitlink (which would silently break `actions/checkout@v4` for end users cloning the repo) can be merged to `main` while `Mirror Verify` reports green.
- The check-run conclusion that branch protection enforces is "success", not "failure".
- The PR #100 audit ("fix(ci): remove false-green CI suppressors") covered `lint-test.yml`, `python-ci.yml`, `ci-kimi-review.yml`, and `android-apk.yml`, but **`mirror-verify.yml` was not in scope** at that time. This file was missed.

**History:** The `continue-on-error: true` was added in commit `6d228f5` (PR #76, "ci: harden remaining workflows"). It was not addressed by PR #100 because PR #100's scope explicitly excluded `mirror-verify.yml` (see the original audit above).

**Recommended fix:** Remove `continue-on-error: true` from the gitlinks step. The `::error::` annotation already correctly identifies the problem; the only thing missing is letting the exit code propagate to the check-run conclusion. A separate follow-up issue/PR should track this — it is out of scope for the snapshot-security PR (#102) but should be addressed before the next RC.

**Mitigation in the meantime:** Reviewers should manually inspect the `Mirror Verify` job's annotations on every PR. If any `::error:: Gitlink '...' has no .gitmodules entry` annotation appears, the PR must not be merged even though `Mirror Verify` shows green.

## Principle

A required check must contain a genuine fail-closed gate. Informational diagnostics may be non-blocking, but they must be isolated from the required gate or explicitly documented as informational and must never be represented as proof of success.

## Non-goals

- No changes to OCR runtime behavior.
- No changes to the canonical RC/production gates.
- No attempt to make every optional diagnostic workflow required.
- No bulk reformatting of the existing codebase in this CI hardening PR.

## Follow-up tracked

- **HIGH:** `mirror-verify.yml` step `Check for broken gitlinks` — remove `continue-on-error: true`. Tracked as a separate follow-up issue (snapshot-security PR #102 explicitly does not modify `mirror-verify.yml` because its scope is the snapshot exporter tool only).
