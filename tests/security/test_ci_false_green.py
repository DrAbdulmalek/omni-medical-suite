"""Regression tests for CI false-green protections in Issue #96.

Required checks must contain genuine fail-closed gates. Informational diagnostics
may be non-blocking only when they are explicitly isolated from the required gate.
"""
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def _read_workflow(filename: str) -> str:
    path = WORKFLOWS / filename
    assert path.exists(), f"Missing workflow: {filename}"
    return path.read_text(encoding="utf-8")


def _job_block(text: str, job_name: str) -> str:
    match = re.search(rf"(  {re.escape(job_name)}:.*?)(\n  \w+:|\Z)", text, re.DOTALL)
    assert match, f"Could not find {job_name} job"
    return match.group(1)


def test_lint_and_type_has_no_continue_on_error():
    """The required lint-and-type job must NOT be job-level advisory."""
    job_block = _job_block(_read_workflow("ci-kimi-review.yml"), "lint-and-type")
    assert "\n    continue-on-error: true" not in job_block


def test_lint_and_type_has_fail_closed_gate():
    """The required lint-and-type job must have an unsuppressed command."""
    job_block = _job_block(_read_workflow("ci-kimi-review.yml"), "lint-and-type")
    run_lines = re.findall(r"run:\s*(.+)", job_block)
    assert len(run_lines) >= 2
    assert any(
        "|| true" not in cmd and "--exit-zero" not in cmd for cmd in run_lines
    ), "lint-and-type has no fail-closed command"


def test_lint_and_type_ruff_check_is_fail_closed():
    """The critical Ruff check must not suppress its exit status."""
    job_block = _job_block(_read_workflow("ci-kimi-review.yml"), "lint-and-type")
    commands = re.findall(r"ruff check.*--select=.*", job_block)
    assert commands, "lint-and-type must have a critical Ruff check"
    for cmd in commands:
        assert "|| true" not in cmd
        assert "--exit-zero" not in cmd


def test_kimi_pull_request_trigger_is_unfiltered():
    """The required lint-and-type check must be produced for every PR."""
    text = _read_workflow("ci-kimi-review.yml")
    match = re.search(r"  pull_request:\s*\n((?:    .+\n)*)", text)
    assert match, "Could not find pull_request trigger"
    assert "paths:" not in match.group(1)


def test_code_quality_flake8_e999_is_fail_closed():
    """The required Code Quality syntax gate must be fail-closed."""
    text = _read_workflow("lint-test.yml")
    job_block = _job_block(text, "lint")
    commands = re.findall(r"flake8.*--select=E999.*", job_block)
    assert commands, "Code Quality must have flake8 --select=E999"
    for cmd in commands:
        assert "|| true" not in cmd
        assert "--exit-zero" not in cmd


def test_code_quality_required_job_has_no_format_suppressors():
    """Black/isort suppressors must not live inside the required Code Quality job."""
    text = _read_workflow("lint-test.yml")
    job_block = _job_block(text, "lint")
    assert "black --check" not in job_block
    assert "isort --check-only" not in job_block
    assert "|| true" not in job_block


def test_formatting_report_is_explicitly_informational():
    """Formatting debt is isolated in a non-required informational job."""
    text = _read_workflow("lint-test.yml")
    job_block = _job_block(text, "format-report")
    assert "name: Formatting Report (Informational)" in job_block
    assert "black --check" in job_block
    assert "isort --check-only" in job_block
    assert job_block.count("|| true") == 2
    assert "Informational only:" in job_block


def test_hf_space_drift_runs_on_all_pull_requests():
    """The HF Space Drift Gate must not have a pull_request paths filter."""
    text = _read_workflow("hf-space-drift.yml")
    match = re.search(r"  pull_request:\s*\n((?:    .+\n)*)", text)
    assert match, "Could not find pull_request trigger in hf-space-drift.yml"
    assert "paths:" not in match.group(1)


def test_android_build_has_no_continue_on_error():
    """The actual Buildozer build must be fail-closed."""
    text = _read_workflow("android-apk.yml")
    match = re.search(r"name: Build debug APK.*?run: buildozer", text, re.DOTALL)
    assert match, "Could not find Buildozer build step"
    assert "continue-on-error" not in match.group(0)


def test_kimi_test_job_remains_advisory():
    """Kimi test/appimage jobs remain advisory because they are not required gates."""
    text = _read_workflow("ci-kimi-review.yml")
    assert "continue-on-error: true" in text


def test_kimi_workflow_is_named_lenient():
    """The Kimi workflow remains explicitly named Lenient."""
    text = _read_workflow("ci-kimi-review.yml")
    assert "name: CI — omni-medical-suite (Lenient)" in text
