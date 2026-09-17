#!/usr/bin/env python3
"""ahw02_recon_compare.py — AHW-02 §K.2 machine-readable test reconciliation.

Compares two pytest-json-report files (BASE @ 39640a6d vs AHW-02 branch):
  - summary counters (collected / passed / failed / skipped /
    collection errors / test-level runtime errors / duration),
  - IDENTIFIER-LEVEL sets (failed / error / skipped node-id lists,
    sha256 of the sorted lists) — set identity, not count similarity,
  - collector-error modules (both sides).

Writes scripts/ahw02_recon_compare_result.json and prints a verdict:
    BASE FAILURE SET == AHW-02 FAILURE SET -> TRUE/FALSE
Re-created 2026-09-17 (SESSION-22) per docs/SESSION_ARTIFACTS_POLICY.md —
the original SESSION-21 run artifacts were lost with the environment.
"""
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE_JSON = REPO / "scripts" / "ahw02_recon_base.json"
BRANCH_JSON = REPO / "scripts" / "ahw02_recon_branch.json"
OUT_JSON = REPO / "scripts" / "ahw02_recon_compare_result.json"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def id_hash(ids) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode("utf-8")).hexdigest()


def summarize(name: str, rep: dict) -> dict:
    summary = rep.get("summary", {})
    tests = rep.get("tests", [])
    collectors = rep.get("collectors", [])

    failed_ids = [t["nodeid"] for t in tests if t.get("outcome") == "failed"]
    error_ids = [t["nodeid"] for t in tests if t.get("outcome") == "error"]
    skipped_ids = [t["nodeid"] for t in tests if t.get("outcome") == "skipped"]
    passed_ids_n = sum(1 for t in tests if t.get("outcome") == "passed")
    coll_err_modules = sorted(
        c.get("nodeid", "?") for c in collectors if c.get("outcome") == "failed"
    )

    return {
        "label": name,
        "exitcode": rep.get("exitcode"),
        "duration_s": round(rep.get("duration", 0.0), 2),
        "collected": summary.get("collected", len(tests)),
        "passed": summary.get("passed", passed_ids_n),
        "failed": summary.get("failed", len(failed_ids)),
        "skipped": summary.get("skipped", len(skipped_ids)),
        "test_level_errors": summary.get("error", len(error_ids)),
        "collection_errors": len(coll_err_modules),
        "failed_set_sha256": id_hash(failed_ids),
        "error_set_sha256": id_hash(error_ids),
        "skipped_set_sha256": id_hash(skipped_ids),
        "collector_error_modules": coll_err_modules,
        "_failed_ids": sorted(failed_ids),
        "_error_ids": sorted(error_ids),
        "_skipped_ids": sorted(skipped_ids),
    }


def main() -> int:
    base = summarize("BASE (clean @ 39640a6d)", load(BASE_JSON))
    branch = summarize("AHW-02 (branch HEAD)", load(BRANCH_JSON))

    identity = {
        "failed_set_equal": base["failed_set_sha256"] == branch["failed_set_sha256"]
        and base["_failed_ids"] == branch["_failed_ids"],
        "error_set_equal": base["error_set_sha256"] == branch["error_set_sha256"]
        and base["_error_ids"] == branch["_error_ids"],
        "skipped_set_equal": base["skipped_set_sha256"] == branch["skipped_set_sha256"]
        and base["_skipped_ids"] == branch["_skipped_ids"],
        "collector_error_modules_equal": base["collector_error_modules"]
        == branch["collector_error_modules"],
    }
    failure_set_identity = all(identity.values())

    table_cols = [
        "collected", "passed", "failed", "skipped",
        "collection_errors", "test_level_errors", "duration_s",
    ]
    delta = {c: branch[c] - base[c] for c in table_cols}

    result = {
        "method": {
            "plugin": "pytest-json-report",
            "id_hash_method": "sha256 over '\\n'.join(sorted(node_ids)) (utf-8)",
            "re_created": "2026-09-17 SESSION-22 per docs/SESSION_ARTIFACTS_POLICY.md",
            "command": "python -m pytest -q --continue-on-collection-errors "
            "--json-report --json-report-file=<scripts/ahw02_recon_{base,branch}.json>",
        },
        "base": {k: v for k, v in base.items() if not k.startswith("_")},
        "branch": {k: v for k, v in branch.items() if not k.startswith("_")},
        "delta": delta,
        "identifier_identity": identity,
        "base_failure_set_equals_ahw02_failure_set": failure_set_identity,
        "regression": "ZERO" if failure_set_identity else "NONZERO — INVESTIGATE",
    }
    OUT_JSON.write_text(json.dumps(result, indent=2, ensure_ascii=False), "utf-8")

    print(f"{'metric':<22}{'BASE':>10}{'AHW-02':>10}{'DELTA':>10}")
    for c in table_cols:
        print(f"{c:<22}{base[c]:>10}{branch[c]:>10}{delta[c]:>10}")
    print()
    for key, val in identity.items():
        print(f"  {key}: {'IDENTICAL' if val else 'DIFFERENT'}")
    print()
    print(f"failed-set sha256  base   = {base['failed_set_sha256']}")
    print(f"failed-set sha256  branch = {branch['failed_set_sha256']}")
    print(f"error-set sha256   base   = {base['error_set_sha256']}")
    print(f"error-set sha256   branch = {branch['error_set_sha256']}")
    print(f"skipped-set sha256 base   = {base['skipped_set_sha256']}")
    print(f"skipped-set sha256 branch = {branch['skipped_set_sha256']}")
    print(f"collector-error modules (identical both sides): "
          f"{base['collector_error_modules']}")
    print()
    print(f"BASE FAILURE SET == AHW-02 FAILURE SET -> "
          f"{'TRUE' if failure_set_identity else 'FALSE'}")
    print(f"REGRESSION = {result['regression']}")
    return 0 if failure_set_identity else 1


if __name__ == "__main__":
    sys.exit(main())
