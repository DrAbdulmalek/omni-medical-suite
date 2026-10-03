"""Regression tests for the dependency-audit waiver policy.

Guards the fix for the ``Scan Dependencies`` failure of 2026-09-29
(run 36597490659), where the job failed on ``nltk / PYSEC-2026-3740`` — a package
that is **not** a dependency of this project. ``safety`` (the scanner) requires
``nltk>=3.9``, and because the job installed the scanners into the project
interpreter and then audited *the installed environment*, the scanner's own
transitive dependency became a build failure on an advisory with no patched
release: unsatisfiable by code, so the gate could never go green.

Two properties are locked down here:

1. **Scope** — the audit targets the *declared* requirements files, and the
   scanners live in a venv that is never an audit target. This is what makes a
   tool's own dependencies unable to fail the project's build again.
2. **Policy** — exceptions are data (``docs/security/dependency-waivers.json``)
   with an author, a justification and an expiry, not inline ``--ignore`` flags.
   Expired waivers fail the build, and the workflow may not smuggle in an
   undocumented id.

These tests are pure filesystem + stdlib: no network, no pip, no scanner needed.
"""

from __future__ import annotations

import datetime as _dt
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
POLICY_PATH = ROOT / "docs" / "security" / "dependency-waivers.json"
SCRIPT_PATH = ROOT / "scripts" / "ci" / "dep_audit_policy.py"
SECURITY_SCAN = WORKFLOWS / "security-scan.yml"

# Every requirements file that declares an installable surface of this project.
# requirements.txt is the legacy umbrella (-r requirements/api.txt + -r ml.txt),
# so auditing it would duplicate api+ml without adding coverage.
AUDITED_REQUIREMENTS = (
    "requirements/api.txt",
    "requirements/ml.txt",
    "requirements/gradio.txt",
    "requirements/dev.txt",
    "requirements/optional.txt",
)

REQUIRED_WAIVER_FIELDS = (
    "id",
    "package",
    "reason",
    "mitigation",
    "added",
    "expires",
    "review_owner",
)


def _load_policy_module():
    """Import scripts/ci/dep_audit_policy.py without needing scripts/ci on sys.path."""
    assert SCRIPT_PATH.exists(), f"missing policy generator: {SCRIPT_PATH}"
    spec = importlib.util.spec_from_file_location("dep_audit_policy", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def policy_mod():
    return _load_policy_module()


@pytest.fixture(scope="module")
def scan_text() -> str:
    assert SECURITY_SCAN.exists(), f"missing workflow: {SECURITY_SCAN.name}"
    return SECURITY_SCAN.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. Policy file integrity
# ---------------------------------------------------------------------------


def test_policy_file_is_valid_json_with_version():
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    assert policy["version"] == 1
    assert isinstance(policy["waivers"], list)


def test_every_waiver_is_justified_and_dated(policy_mod):
    """A waiver without a written reason/expiry/owner is not a waiver, it's a hole."""
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    for i, w in enumerate(policy["waivers"]):
        for field in REQUIRED_WAIVER_FIELDS:
            assert str(w.get(field, "")).strip(), f"waivers[{i}] missing '{field}'"
        # reasons must be substantive, not a placeholder
        assert len(w["reason"]) >= 40, f"waivers[{i}] reason is too thin to review"
        assert len(w["mitigation"]) >= 40, f"waivers[{i}] mitigation is too thin to review"


def test_no_waiver_is_expired_or_unbounded(policy_mod):
    """load_policy() raises on expired / too-long waivers — that is the gate."""
    policy = policy_mod.load_policy(POLICY_PATH)
    max_days = policy["_max_waiver_days"]
    assert max_days <= 365, "waiver ceiling must not exceed one year"
    for w in policy["_validated_waivers"]:
        assert w["_days_left"] >= 0, f"{w['id']} expired"
        assert w["_lifetime_days"] <= max_days, f"{w['id']} is effectively permanent"


def test_load_policy_rejects_expired_waiver(policy_mod, tmp_path):
    """Fail-closed proof: an expired waiver must break the build, not warn."""
    today = _dt.date(2026, 10, 1)
    bad = {
        "version": 1,
        "max_waiver_days": 365,
        "waivers": [
            {
                "id": "PYSEC-0000-0000",
                "package": "example",
                "reason": "x" * 50,
                "mitigation": "y" * 50,
                "added": "2026-06-01",
                "expires": "2026-09-30",  # yesterday, relative to `today`
                "review_owner": "@nobody",
            }
        ],
    }
    p = tmp_path / "expired.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(policy_mod.PolicyError) as exc:
        policy_mod.load_policy(p, today=today)
    assert "EXPIRED" in str(exc.value)


def test_load_policy_rejects_permanent_waiver(policy_mod, tmp_path):
    """Fail-closed proof: 'expires in 10 years' is a permanent waiver in disguise."""
    bad = {
        "version": 1,
        "max_waiver_days": 365,
        "waivers": [
            {
                "id": "PYSEC-0000-0001",
                "package": "example",
                "reason": "x" * 50,
                "mitigation": "y" * 50,
                "added": "2026-01-01",
                "expires": "2036-01-01",
                "review_owner": "@nobody",
            }
        ],
    }
    p = tmp_path / "permanent.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(policy_mod.PolicyError) as exc:
        policy_mod.load_policy(p, today=_dt.date(2026, 10, 1))
    assert "max_waiver_days" in str(exc.value)


def test_load_policy_rejects_incomplete_waiver(policy_mod, tmp_path):
    bad = {"version": 1, "waivers": [{"id": "PYSEC-0000-0002", "package": "example"}]}
    p = tmp_path / "incomplete.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(policy_mod.PolicyError) as exc:
        policy_mod.load_policy(p, today=_dt.date(2026, 10, 1))
    assert "missing required field" in str(exc.value)


def test_generator_emits_pip_audit_flags(policy_mod):
    """The flag name must stay the one pip-audit actually accepts (--ignore-vuln)."""
    policy = policy_mod.load_policy(POLICY_PATH)
    flags = policy_mod.as_flags(policy)
    for vid in policy_mod.active_ids(policy):
        assert f"--ignore-vuln={vid}" in flags
    assert "--ignore-vuln-id" not in flags, "pip-audit has no --ignore-vuln-id option"


# ---------------------------------------------------------------------------
# 2. Workflow ↔ policy agreement (no drift, no smuggling)
# ---------------------------------------------------------------------------


def test_no_inline_ignore_flags_in_security_scan(scan_text):
    """Exceptions must come from the policy file, never from an inline flag.

    ``--ignore-vuln`` is still allowed *inside* the generated $AUDIT_IGNORES
    expansion, but it must not be hardcoded in the YAML where nobody reviews it.
    """
    hardcoded = re.findall(r"--ignore(?:-vuln)?[= ]\S+", scan_text)
    # safety's own numeric ignores are a separate, documented exception list
    hardcoded = [h for h in hardcoded if not h.startswith("--ignore 6")]
    assert not hardcoded, (
        "security-scan.yml hardcodes pip-audit ignore flags; move them to "
        f"docs/security/dependency-waivers.json instead: {hardcoded}"
    )


def test_audit_ignores_come_from_the_policy_generator(scan_text):
    assert "scripts/ci/dep_audit_policy.py" in scan_text
    assert "print-active" in scan_text
    assert "$AUDIT_IGNORES" in scan_text, "the generated waivers are never used"


def test_workflow_and_generator_agree_on_the_policy_path(policy_mod, scan_text):
    """The YAML must point at the same file the generator defaults to.

    This is a real bug class, not a hypothetical: the first draft of this workflow
    passed ``--policy docs/security/dependency-waivers.yml`` while the policy file
    (and the generator's default) were ``.json``. Every invocation would have died
    with "policy file not found" — and the failure would have looked like a policy
    problem rather than a typo.
    """
    expected = policy_mod.DEFAULT_POLICY.relative_to(ROOT).as_posix()

    # The workflow passes the path through a shell variable, so resolve one level of
    # VAR=value assignments before looking at the --policy arguments.
    env = dict(re.findall(r"^\s*([A-Z_][A-Z0-9_]*)=(\S+)\s*$", scan_text, re.MULTILINE))
    referenced = set()
    for raw in re.findall(r"--policy\s+(\S+)", scan_text):
        value = raw.strip('"\'')
        referenced.add(env.get(value.lstrip("$"), value))

    assert referenced, "the workflow never passes --policy"
    assert referenced == {expected}, (
        f"workflow references {sorted(referenced)} but the policy lives at {expected}"
    )
    # ...and the trigger filter must watch the same file, or policy edits won't run CI
    assert f"'{expected}'" in scan_text, "policy file is not in the workflow's paths filter"


def test_audit_is_scoped_to_declared_requirements(scan_text):
    """Requirements mode is the actual fix: the audit can only see what we ship.

    If this regresses to a bare ``pip-audit`` (environment mode), the scanners' own
    transitive dependencies become build failures again — which is exactly how
    nltk/PYSEC-2026-3740 turned this job red.
    """
    for req in AUDITED_REQUIREMENTS:
        assert req in scan_text, f"{req} is no longer audited"
    # every pip-audit invocation must be a requirements-mode invocation
    invocations = re.findall(r"pip-audit[^\n]*(?:\\\n[^\n]*)*", scan_text)
    assert invocations, "pip-audit is not called at all"
    assert "-r \"$req\"" in scan_text or "-r $req" in scan_text


def test_scanners_are_isolated_from_the_project_environment(scan_text):
    """Belt and braces: the tools must not be installed into the audited interpreter."""
    assert ".scanner-venv" in scan_text
    assert re.search(r"^\s*pip install .*\bsafety\b", scan_text, re.MULTILINE) is None, (
        "scanners must be installed into .scanner-venv, not the project environment"
    )


def test_security_scan_stays_blocking(scan_text):
    """Scoping the audit is not the same as making it advisory.

    No ``continue-on-error``, no ``|| true``, no ``--exit-zero`` anywhere in the
    blocking steps — same standard as tests/security/test_ci_false_green.py.
    """
    assert "continue-on-error" not in scan_text
    for line in scan_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "|| true" not in stripped, f"suppressed failure: {stripped}"
        assert "--exit-zero" not in stripped, f"suppressed failure: {stripped}"


def test_nltk_false_signal_is_recorded_not_waived():
    """The nltk advisory must stay documented as *out of scope*, never as a waiver.

    Recording it in ``rejected_or_unnecessary`` is what stops the next person from
    'fixing' the same red build by ignoring a vulnerability in a package this
    project does not even use.
    """
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    waived = {w["id"] for w in policy["waivers"]}
    recorded = {r["id"] for r in policy.get("rejected_or_unnecessary", [])}
    assert "PYSEC-2026-3740" in recorded
    assert "PYSEC-2026-3740" not in waived
    entry = next(r for r in policy["rejected_or_unnecessary"] if r["id"] == "PYSEC-2026-3740")
    assert entry["package"] == "nltk"
    assert entry.get("resolution")


def test_nltk_is_not_a_declared_dependency():
    """The claim the whole fix rests on, asserted against the files themselves."""
    for req in AUDITED_REQUIREMENTS + ("requirements/base.txt", "requirements.txt"):
        path = ROOT / req
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            code = line.split("#", 1)[0].strip().lower()
            assert not code.startswith("nltk"), f"nltk became a real dependency in {req}"
