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

## Principle

A required check must contain a genuine fail-closed gate. Informational diagnostics may be non-blocking, but they must be isolated from the required gate or explicitly documented as informational and must never be represented as proof of success.

## Non-goals

- No changes to OCR runtime behavior.
- No changes to the canonical RC/production gates.
- No attempt to make every optional diagnostic workflow required.
- No bulk reformatting of the existing codebase in this CI hardening PR.
