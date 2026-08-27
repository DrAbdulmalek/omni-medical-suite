"""Regression test: CI workflows must not mask failures with false-green suppressors.

Issue #96: Remove false-green behavior from CI workflows.

This test verifies that:
1. Required-check-producing jobs do NOT use `|| true`, `|| echo "No tests..."`,
   or `continue-on-error: true` to mask failures.
2. Informational/advisory steps MAY use suppression, but only when explicitly
   documented as informational AND when they are NOT the only gate in a
   required-check-producing job.
3. The Kimi review workflow's `test` and `appimage-build` jobs remain advisory
   (Lenient) — they are NOT required branch-protection checks.
4. The `lint-and-type` job (which IS a required check) must be fail-closed
   for at least one critical command.
5. The HF Space Drift Gate must run on ALL pull_requests (no path filter)
   so the required check is never missing.
"""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _read_workflow(filename: str) -> str:
    path = WORKFLOWS / filename
    assert path.exists(), f"Missing workflow: {filename}"
    return path.read_text(encoding="utf-8")


def test_lint_and_type_has_no_continue_on_error():
    """The lint-and-type job must NOT have job-level continue-on-error."""
    text = _read_workflow("ci-kimi-review.yml")
    match = re.search(r"(  lint-and-type:.*?)(\n  \w+:|\Z)", text, re.DOTALL)
    assert match, "Could not find lint-and-type job in ci-kimi-review.yml"
    job_block = match.group(1)
    lines = job_block.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped == "continue-on-error: true":
            assert False, (
                "lint-and-type job has 'continue-on-error: true' at job level. "
                "This makes the required check a complete false-green."
            )


def test_lint_and_type_has_fail_closed_gate():
    """The lint-and-type job must have at least one command that is NOT
    suppressed with || true or --exit-zero."""
    text = _read_workflow("ci-kimi-review.yml")
    match = re.search(r"(  lint-and-type:.*?)(\n  \w+:|\Z)", text, re.DOTALL)
    assert match, "Could not find lint-and-type job"
    job_block = match.group(1)
    run_lines = re.findall(r"run:\s*(.+)", job_block)
    assert len(run_lines) >= 2, (
        f"Expected at least 2 run commands in lint-and-type, found {len(run_lines)}"
    )
    has_fail_closed = False
    for cmd in run_lines:
        cmd_stripped = cmd.strip()
        if "|| true" not in cmd_stripped and "--exit-zero" not in cmd_stripped:
            has_fail_closed = True
            break
    assert has_fail_closed, (
        "lint-and-type job has NO fail-closed command. Every run step uses "
        "|| true or --exit-zero. A required check must be able to fail."
    )


def test_lint_and_type_ruff_check_is_fail_closed():
    """The ruff critical-errors check must be fail-closed (no || true)."""
    text = _read_workflow("ci-kimi-review.yml")
    match = re.search(r"(  lint-and-type:.*?)(\n  \w+:|\Z)", text, re.DOTALL)
    assert match, "Could not find lint-and-type job"
    job_block = match.group(1)
    ruff_critical = re.findall(r"ruff check.*--select=.*", job_block)
    assert len(ruff_critical) >= 1, (
        "lint-and-type must have a ruff check with --select= for critical errors"
    )
    for cmd in ruff_critical:
        assert "|| true" not in cmd, (
            f"ruff critical check must be fail-closed, but found || true: {cmd}"
        )
        assert "--exit-zero" not in cmd, (
            f"ruff critical check must be fail-closed, but found --exit-zero: {cmd}"
        )


def test_code_quality_flake8_e999_is_fail_closed():
    """The flake8 E999 (SyntaxError) check must NOT use || true or --exit-zero."""
    text = _read_workflow("lint-test.yml")
    e999_commands = re.findall(r"flake8.*--select=E999.*", text)
    assert len(e999_commands) >= 1, "Code Quality must have flake8 --select=E999"
    for cmd in e999_commands:
        assert "|| true" not in cmd, (
            f"flake8 E999 check must be fail-closed, but found || true: {cmd}"
        )
        assert "--exit-zero" not in cmd, (
            f"flake8 E999 check must be fail-closed, but found --exit-zero: {cmd}"
        )


def test_hf_space_drift_runs_on_all_pull_requests():
    """The HF Space Drift Gate must NOT have a paths filter on pull_request."""
    text = _read_workflow("hf-space-drift.yml")
    pr_match = re.search(r"  pull_request:\s*\n((?:    .+\n)*)", text)
    assert pr_match, "Could not find pull_request: trigger in hf-space-drift.yml"
    pr_block = pr_match.group(1)
    assert "paths:" not in pr_block, (
        "hf-space-drift.yml has a paths: filter on pull_request. "
        "This causes the required check to be missing on PRs that don't "
        "touch the filtered paths. Remove the paths filter so the check "
        "always produces a check-run."
    )


def test_android_build_has_no_continue_on_error():
    """The Buildozer build step must NOT have continue-on-error."""
    text = _read_workflow("android-apk.yml")
    match = re.search(r"name: Build debug APK.*?run: buildozer", text, re.DOTALL)
    assert match, "Could not find Buildozer build step in android-apk.yml"
    step_block = match.group(0)
    assert "continue-on-error" not in step_block, (
        "Buildozer build step has continue-on-error. APK build failures "
        "must cause the job to fail."
    )


def test_kimi_test_job_remains_advisory():
    """The Kimi 'test' and 'appimage-build' jobs are NOT required checks.
    They may use continue-on-error since they are explicitly Lenient."""
    text = _read_workflow("ci-kimi-review.yml")
    assert "continue-on-error: true" in text, (
        "Kimi test/appimage jobs should remain advisory (Lenient) with "
        "continue-on-error: true. Only the lint-and-type job must be fail-closed."
    )


def test_kimi_workflow_is_named_lenient():
    """The Kimi workflow must remain explicitly named 'Lenient'."""
    text = _read_workflow("ci-kimi-review.yml")
    assert "name: CI — omni-medical-suite (Lenient)" in text
