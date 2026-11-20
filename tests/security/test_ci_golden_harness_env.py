"""Regression tests: every CI job that runs the golden harness must provision its
environment, and must not be allowed to pass without doing so.

What broke (2026-09-29, PR #148 / run 36597490725)
--------------------------------------------------
``tests/evaluation/test_golden_harness.py`` failed 4/13 in CI for two independent
environment reasons that had nothing to do with the code under test:

1. ``python-ci.yml`` (job ``test``) never installed the ``tesseract`` binary, so
   ``packages/evaluation/golden_harness.py``'s ``subprocess.run(["tesseract", ...])``
   raised ``FileNotFoundError: [Errno 2] No such file or directory: 'tesseract'``.
2. The checkout steps had no ``lfs: true``, so ``golden_set/samples/*.png`` and
   ``golden_set/*.jsonl`` arrived as 129-byte LFS *pointer* files. ``load_samples()``
   then raised ``RuntimeError: sample … drifted: sha256 mismatch`` and
   ``test_ingest_marks_cloud_and_excludes_confidence`` raised
   ``json.JSONDecodeError: Expecting value: line 1 column 1`` — the "empty JSON"
   symptom, which is really "JSON that is an LFS pointer".

Verified locally, both directions:

    no LFS content + tesseract installed   -> 4 failed, 9 passed
    real LFS content + tesseract installed -> 13 passed

The harness is a *measurement* gate and its contract is to fail loudly on a broken
environment ("لا نتائج فارغة صامتة" — no silent empty results). So the correct fix is
to provision the environment, never to skip the test. These tests lock that choice in.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

# Jobs that run `pytest tests/` (and therefore tests/evaluation/test_golden_harness.py)
# and are *not* allowed to be red for environmental reasons.
HARNESS_WORKFLOWS = {
    "python-ci.yml": "test",
    "lint-test.yml": "test",
}

TESSERACT_PACKAGES = ("tesseract-ocr", "tesseract-ocr-ara")


def _read(name: str) -> str:
    path = WORKFLOWS / name
    assert path.exists(), f"missing workflow: {name}"
    return path.read_text(encoding="utf-8")


def _job_block(text: str, job_name: str) -> str:
    """Extract one top-level GitHub Actions job (same helper shape as test_ci_false_green)."""
    match = re.search(rf"(  {re.escape(job_name)}:.*?)(\n  [\w-]+:|\Z)", text, re.DOTALL)
    assert match, f"could not find job '{job_name}'"
    return match.group(1)


# ---------------------------------------------------------------------------
# tesseract binary
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("workflow,job", sorted(HARNESS_WORKFLOWS.items()))
def test_job_installs_tesseract_binary(workflow, job):
    """golden_harness.py shells out to `tesseract`; the runner must have it."""
    block = _job_block(_read(workflow), job)
    for pkg in TESSERACT_PACKAGES:
        assert pkg in block, (
            f"{workflow}:{job} does not install {pkg} — the golden harness will die "
            f"with FileNotFoundError: 'tesseract'"
        )


@pytest.mark.parametrize("workflow,job", sorted(HARNESS_WORKFLOWS.items()))
def test_tesseract_install_is_not_suppressed(workflow, job):
    """`|| true` here would reproduce the original failure with a green check mark."""
    block = _job_block(_read(workflow), job)
    for line in block.splitlines():
        if "apt-get install" in line:
            assert "|| true" not in line, f"{workflow}:{job} silently tolerates a missing tesseract"
            assert "2>/dev/null" not in line, f"{workflow}:{job} hides apt failures"


# ---------------------------------------------------------------------------
# Git LFS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("workflow,job", sorted(HARNESS_WORKFLOWS.items()))
def test_checkout_fetches_lfs(workflow, job):
    """golden_set/ is LFS-tracked; without lfs:true the tests read 129-byte pointers."""
    block = _job_block(_read(workflow), job)
    checkouts = re.findall(
        r"-\s*uses:\s*actions/checkout@v\d+\n((?:\s{6,}.*\n)*)", block
    )
    assert checkouts, f"{workflow}:{job} has no actions/checkout step"
    for with_block in checkouts:
        assert re.search(r"^\s*lfs:\s*true\s*$", with_block, re.MULTILINE), (
            f"{workflow}:{job} checks out without lfs:true — golden_set/*.jsonl and "
            f"samples/*.png arrive as LFS pointers and tests/evaluation fails with "
            f"JSONDecodeError / sha256 mismatch"
        )


def test_golden_set_is_actually_lfs_tracked():
    """If .gitattributes ever stops tracking golden_set, the lfs:true steps are cargo cult."""
    attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.png" in attrs or "packages/evaluation/**" in attrs
    assert "*.jsonl" in attrs


def test_golden_harness_still_requires_the_binary():
    """The tests above assume the harness shells out to a real tesseract.

    If it ever becomes hermetic (bundled engine / stub), these provisioning
    assertions should be deleted rather than left to rot.
    """
    src = (ROOT / "packages" / "evaluation" / "golden_harness.py").read_text(encoding="utf-8")
    assert '"tesseract"' in src or "'tesseract'" in src


def test_golden_harness_fails_loudly_on_drift():
    """The property that made the LFS failure diagnosable instead of silent."""
    src = (ROOT / "packages" / "evaluation" / "golden_harness.py").read_text(encoding="utf-8")
    assert "sha256 mismatch" in src
    assert "not available" in src  # missing language pack -> RuntimeError, not empty text
