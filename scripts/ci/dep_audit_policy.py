#!/usr/bin/env python3
"""Dependency-audit waiver policy — the single source of truth for pip-audit ignores.

Why this exists
---------------
``security-scan.yml`` used to carry its exceptions as inline ``--ignore`` flags:

    pip-audit --desc --ignore PYSEC-2026-1325

An inline flag has no author, no justification, no expiry, and no test. Waivers
accumulate, the audit quietly narrows, and after a year nobody knows whether the
exception is still true. This module replaces the flag with a *policy*:

* waivers live in ``docs/security/dependency-waivers.json`` (stdlib-only parsing,
  so the gate runs in any CI job without PyYAML);
* every waiver needs ``reason``, ``mitigation``, ``added``, ``expires`` and
  ``review_owner`` — a waiver without a written justification is rejected;
* **expired waivers fail the build.** An unfixable advisory is a real state of the
  world, but it must be re-attested on a schedule, not inherited forever;
* ``expires`` may not be farther out than ``max_waiver_days`` (no permanent
  waivers by construction);
* ``tests/security/test_dependency_waiver_policy.py`` asserts that the flags the
  workflow actually passes are exactly the flags this policy produces, so the YAML
  and the JSON cannot drift apart.

Usage
-----
    python scripts/ci/dep_audit_policy.py print-active --format=flags
        -> "--ignore-vuln=PYSEC-2026-1325"          (for pip-audit)

    python scripts/ci/dep_audit_policy.py print-active --format=shell
        -> AUDIT_IGNORES=--ignore-vuln=PYSEC-2026-1325   (for $GITHUB_ENV)

    python scripts/ci/dep_audit_policy.py report
        -> human-readable table with days-until-expiry

Exit codes: 0 = policy valid, 2 = policy invalid / waiver expired / waiver too long.
Everything diagnostic goes to **stderr** so ``print-active`` output stays pipeable.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = REPO_ROOT / "docs" / "security" / "dependency-waivers.json"

REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "package",
    "reason",
    "mitigation",
    "added",
    "expires",
    "review_owner",
)

# Hard ceiling when the policy file does not declare one. One year: long enough to
# stop re-litigating an unfixable advisory every sprint, short enough that the
# justification has to be re-attested by someone who is still around.
DEFAULT_MAX_WAIVER_DAYS = 365
DEFAULT_SOON_WARN_DAYS = 30

EXIT_OK = 0
EXIT_POLICY_INVALID = 2


def _say(msg: str) -> None:
    """Diagnostics to stderr — stdout is reserved for machine-readable output."""
    print(msg, file=sys.stderr)


def _parse_date(value: Any, field: str, where: str) -> _dt.date:
    if not isinstance(value, str):
        raise PolicyError(f"{where}: '{field}' must be an ISO date string (YYYY-MM-DD)")
    try:
        return _dt.date.fromisoformat(value.strip())
    except ValueError as exc:
        raise PolicyError(f"{where}: '{field}' is not a valid ISO date ({value!r})") from exc


class PolicyError(RuntimeError):
    """Raised for any policy defect; converted to exit code 2 by main()."""


def load_policy(path: Path | None = None, *, today: _dt.date | None = None) -> dict:
    """Load and validate the waiver policy.

    Validation is deliberately strict and fail-closed: a malformed policy must
    never degrade into "no waivers, but also no error", because that would either
    break the build for an unrelated reason or silently widen the audit.
    """
    policy_path = Path(path) if path else DEFAULT_POLICY
    today = today or _dt.date.today()

    if not policy_path.exists():
        raise PolicyError(f"policy file not found: {policy_path}")

    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PolicyError(f"{policy_path}: invalid JSON ({exc})") from exc

    if not isinstance(policy, dict):
        raise PolicyError(f"{policy_path}: top level must be an object")

    waivers = policy.get("waivers")
    if not isinstance(waivers, list):
        raise PolicyError(f"{policy_path}: 'waivers' must be a list")

    max_days = policy.get("max_waiver_days", DEFAULT_MAX_WAIVER_DAYS)
    if not isinstance(max_days, int) or max_days <= 0:
        raise PolicyError(f"{policy_path}: 'max_waiver_days' must be a positive integer")

    seen: set[str] = set()
    validated: list[dict] = []

    for i, w in enumerate(waivers):
        where = f"{policy_path.name} waivers[{i}]"
        if not isinstance(w, dict):
            raise PolicyError(f"{where}: must be an object")

        missing = [f for f in REQUIRED_FIELDS if not str(w.get(f, "")).strip()]
        if missing:
            raise PolicyError(f"{where}: missing required field(s): {', '.join(missing)}")

        vid = str(w["id"]).strip()
        if vid in seen:
            raise PolicyError(f"{where}: duplicate waiver id {vid!r}")
        seen.add(vid)

        added = _parse_date(w["added"], "added", where)
        expires = _parse_date(w["expires"], "expires", where)

        if expires <= added:
            raise PolicyError(f"{where}: 'expires' ({expires}) must be after 'added' ({added})")

        lifetime = (expires - added).days
        if lifetime > max_days:
            raise PolicyError(
                f"{where}: waiver {vid!r} lives {lifetime} days but the policy ceiling is "
                f"{max_days} (max_waiver_days). Permanent waivers are not allowed — "
                f"shorten 'expires' or fix the dependency."
            )

        days_left = (expires - today).days
        entry = dict(w)
        entry["_days_left"] = days_left
        entry["_lifetime_days"] = lifetime
        validated.append(entry)

        if days_left < 0:
            raise PolicyError(
                f"{where}: waiver {vid!r} for {w['package']} EXPIRED {-days_left} day(s) ago "
                f"(expires={expires}, review_owner={w['review_owner']}). "
                f"Re-attest it with a new 'expires' or remove it and fix the dependency. "
                f"An expired waiver fails the build on purpose."
            )

    policy["_validated_waivers"] = validated
    policy["_today"] = today
    policy["_max_waiver_days"] = max_days
    policy["_soon_warn_days"] = policy.get("soon_expiry_warn_days", DEFAULT_SOON_WARN_DAYS)
    policy["_path"] = policy_path
    return policy


def active_ids(policy: dict) -> list[str]:
    """Waiver ids that are valid today, in policy order (stable, reviewable diffs)."""
    return [str(w["id"]).strip() for w in policy["_validated_waivers"]]


def as_flags(policy: dict) -> str:
    """pip-audit arguments for the active waivers (empty string when there are none)."""
    return " ".join(f"--ignore-vuln={vid}" for vid in active_ids(policy))


def as_shell(policy: dict) -> str:
    """``AUDIT_IGNORES=...`` line, ready to append to $GITHUB_ENV.

    Unquoted on purpose: the workflow expands $AUDIT_IGNORES without quotes so that
    an empty policy yields no argument at all instead of one empty one.
    """
    return f"AUDIT_IGNORES={as_flags(policy)}"


def report(policy: dict) -> int:
    """Print a human-readable waiver report. Returns an exit code."""
    today = policy["_today"]
    soon = policy["_soon_warn_days"]
    rows = policy["_validated_waivers"]

    _say(f"# Dependency-audit waiver policy — {policy['_path']}")
    _say(f"# today={today.isoformat()}  max_waiver_days={policy['_max_waiver_days']}")

    if not rows:
        _say("No waivers. The audit runs against the full declared dependency graph.")
        return EXIT_OK

    _say("")
    _say(f"{'ID':<20} {'PACKAGE':<16} {'EXPIRES':<12} {'DAYS LEFT':>9}  REVIEW OWNER")
    _say("-" * 78)
    rc = EXIT_OK
    for w in rows:
        days = w["_days_left"]
        _say(
            f"{str(w['id']):<20} {str(w['package']):<16} {str(w['expires']):<12} "
            f"{days:>9}  {w['review_owner']}"
        )
        if days <= soon:
            _say(f"{'':<4}-> expires within {soon} days: re-attest or fix ({w['review_owner']})")
            rc = EXIT_OK  # advisory only; expiry itself is what fails the build
        _say(f"{'':<4}reason: {w['reason']}")
        _say(f"{'':<4}mitigation: {w['mitigation']}")
        _say("")

    rejected = policy.get("rejected_or_unnecessary") or []
    if rejected:
        _say("# Recorded decisions that are NOT waivers (kept so the same false signal")
        _say("# is not 'fixed' by ignoring it again later):")
        for r in rejected:
            _say(f"#   {r.get('id')} / {r.get('package')}: {r.get('decision')}")
            _say(f"#     {r.get('reason')}")
            _say(f"#     {r.get('resolution')}")
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--policy",
        default=str(DEFAULT_POLICY),
        help=f"path to the waiver policy (default: {DEFAULT_POLICY.relative_to(REPO_ROOT)})",
    )
    ap.add_argument(
        "--today",
        default=None,
        help="override 'today' as YYYY-MM-DD (for deterministic tests)",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_active = sub.add_parser("print-active", help="print active waivers for pip-audit")
    p_active.add_argument("--format", choices=("flags", "shell", "ids"), default="flags")

    sub.add_parser("report", help="print a human-readable waiver report")
    sub.add_parser("check", help="validate the policy only (expired/too-long waivers fail)")

    args = ap.parse_args(argv)

    try:
        today = _dt.date.fromisoformat(args.today) if args.today else None
        policy = load_policy(Path(args.policy), today=today)
    except PolicyError as exc:
        _say(f"::error::dependency waiver policy invalid: {exc}")
        return EXIT_POLICY_INVALID

    if args.cmd == "print-active":
        if args.format == "flags":
            print(as_flags(policy))
        elif args.format == "shell":
            print(as_shell(policy))
        else:
            print("\n".join(active_ids(policy)))
        return EXIT_OK

    if args.cmd == "report":
        return report(policy)

    _say(f"policy OK: {len(active_ids(policy))} active waiver(s), none expired.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
