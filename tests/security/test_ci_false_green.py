from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


FAIL_CLOSED_WORKFLOWS = {
    "lint-test.yml": (
        "|| true",
        "|| echo \"No tests yet\"",
    ),
    "python-ci.yml": (
        "|| true",
        "|| echo \"No tests found\"",
    ),
    "android-apk.yml": (
        "continue-on-error: true",
    ),
}


def test_secondary_gates_do_not_mask_required_failures():
    for filename, forbidden in FAIL_CLOSED_WORKFLOWS.items():
        text = (WORKFLOWS / filename).read_text(encoding="utf-8")
        for pattern in forbidden:
            assert pattern not in text, f"{filename} still masks failures: {pattern}"


def test_kimi_review_remains_explicitly_advisory():
    text = (WORKFLOWS / "ci-kimi-review.yml").read_text(encoding="utf-8")
    assert "name: CI — omni-medical-suite (Lenient)" in text
    assert "continue-on-error: true" in text
    assert "non-blocking" in text
