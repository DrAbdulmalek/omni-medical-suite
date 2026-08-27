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

**Classification: must fail on lint/test failures.**

Removed `|| true` from flake8, Black, isort, Tesseract package installation, and pytest. A failed test run must no longer be converted into a successful job. Coverage upload remains informational (`fail_ci_if_error: false`) because the test command itself is the gate.

### `python-ci.yml`

**Classification: must fail on test/quality failures.**

Removed the test fallback (`|| echo "No tests found"`) and the `|| true` suppressors from flake8 and Black. A missing/broken test run or quality failure now fails the job.

### `android-apk.yml`

**Classification: the APK build must fail closed.**

Removed `continue-on-error: true` from the actual Buildozer build. A failed APK build can no longer produce a successful build job. The model download fallback remains intentional: the workflow explicitly supports a placeholder/offline-model path. The optional Hugging Face login remains non-fatal when a token is present because login is not itself the artifact build gate.

### `ci-kimi-review.yml`

**Classification: explicitly advisory/lenient, not a release or merge gate.**

This workflow is deliberately named `Lenient` and is not one of the required branch-protection checks. Its non-blocking behavior is therefore retained rather than silently converted into a new required gate. It must not be used as evidence that tests, typing, or an AppImage build passed. The canonical production/RC gates remain fail-closed.

## Principle

A workflow may be advisory, but an advisory workflow must not be treated as proof of success. Artifact-producing and test-gating steps are fail-closed; explicitly optional diagnostics remain non-blocking.

## Non-goals

- No changes to OCR runtime behavior.
- No changes to the canonical RC/production gates.
- No attempt to make every optional diagnostic workflow required.
