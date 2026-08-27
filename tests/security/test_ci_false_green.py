"""Regression test: CI workflows must not mask failures with false-green suppressors.

Issue #96: Remove false-green behavior from CI workflows.

This test verifies that:
1. Required/test/build paths do NOT use `|| true`, `|| echo "No tests..."`,
   or `continue-on-error: true` to mask failures.
2. Informational/advisory paths (coverage upload, style reports) MAY use
   suppression, but only when explicitly documented as informational.
3. The Kimi review workflow remains explicitly advisory (Lenient).
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


# Patterns that must NEVER appear in required/test/build steps.
# These are the false-green suppressors that #96 removes.
FORBIDDEN_IN_TEST_PATHS = {
    "lint-test.yml": (
        # pytest must not be suppressed
        '|| echo "No tests yet"',
        # apt-get must not be suppressed (was hiding tesseract install failures)
        "apt-get install -y -qq tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng libtesseract-dev 2>/dev/null || true",
    ),
    "python-ci.yml": (
        '|| echo "No tests found"',
    ),
    "android-apk.yml": (
        "continue-on-error: true",
    ),
}

# Patterns that ARE allowed in informational/advisory steps.
# These must be explicitly documented as informational in the workflow.
ALLOWED_INFORMATIONAL_PATTERNS = {
    "lint-test.yml": (
        "fail_ci_if_error: false",  # coverage upload is informational
        "# black formatting is informational",
        "# isort is informational",
        "--exit-zero",  # flake8 style report is informational
    ),
    "python-ci.yml": (
        "# black --check is informational",
    ),
}


def test_required_gates_do_not_mask_failures():
    """Required test/build paths must not use false-green suppressors."""
    for filename, forbidden in FORBIDDEN_IN_TEST_PATHS.items():
        path = WORKFLOWS / filename
        assert path.exists(), f"Missing workflow: {filename}"
        text = path.read_text(encoding="utf-8")
        for pattern in forbidden:
            assert pattern not in text, (
                f"{filename} still masks failures with: {pattern!r}. "
                f"This is a false-green suppressor that must be removed."
            )


def test_informational_steps_are_documented():
    """Informational suppression must be explicitly documented."""
    for filename, required_comments in ALLOWED_INFORMATIONAL_PATTERNS.items():
        path = WORKFLOWS / filename
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for comment in required_comments:
            assert comment in text, (
                f"{filename} uses informational suppression but does not "
                f"document it with: {comment!r}"
            )


def test_kimi_review_remains_explicitly_advisory():
    """The Kimi review workflow must remain explicitly advisory (Lenient)."""
    text = (WORKFLOWS / "ci-kimi-review.yml").read_text(encoding="utf-8")
    assert "name: CI — omni-medical-suite (Lenient)" in text
    assert "continue-on-error: true" in text
    assert "non-blocking" in text
