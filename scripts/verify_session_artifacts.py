#!/usr/bin/env python3
"""verify_session_artifacts.py — الإثبات الآلي لقاعدة الحفظ الدائم.

Reads docs/SESSION_ARTIFACTS_LEDGER.md and verifies, for every row:
  1. the artifact file exists (repo-root-relative),
  2. its sha256 matches the ledger value exactly,
  3. the file is git-TRACKED (committed) — an untracked artifact fails,
  4. the containing-commit SHA recorded in the ledger is a real ancestor
     commit that actually contains the file (verified via `git log -1`).

Exit code: 0 = PASS (all rows verified), 1 = FAIL (any check broken).
Run before ending EVERY session (docs/SESSION_ARTIFACTS_POLICY.md, rule 3).
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / "docs" / "SESSION_ARTIFACTS_LEDGER.md"
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=REPO, capture_output=True, text=True
    )


def parse_ledger():
    rows = []
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if not ROW_RE.match(line):
            continue
        cells = [c.strip() for c in line.split("|")]
        # cells[0] is '' before the leading '|'; expected: '', num, session,
        # path, sha256, commit, note, ''
        if len(cells) < 7:
            continue
        rows.append(
            {
                "num": cells[1],
                "session": cells[2],
                "path": cells[3],
                "sha256": cells[4].lower(),
                "commit": cells[5].lower(),
                "note": cells[6],
            }
        )
    return rows


def main() -> int:
    if not LEDGER.exists():
        print("FAIL: ledger missing:", LEDGER)
        return 1
    rows = parse_ledger()
    if not rows:
        print("FAIL: ledger has no artifact rows")
        return 1

    failures = 0
    print(f"verify_session_artifacts: {len(rows)} ledger row(s)")
    for r in rows:
        path = REPO / r["path"]
        problems = []

        # 1. existence
        if not path.is_file():
            problems.append("FILE MISSING")

        # 2. sha256
        actual = sha256_of(path) if path.is_file() else None
        if actual != r["sha256"]:
            problems.append(f"SHA MISMATCH (actual={actual})")

        # 3. tracked by git
        tracked = git("ls-files", "--error-unmatch", r["path"])
        if tracked.returncode != 0:
            problems.append("NOT GIT-TRACKED (uncommitted artifact!)")

        # 4. recorded commit exists and contains the file
        contains = git(
            "log", "--format=%H", "-n", "1", r["commit"], "--", r["path"]
        )
        if not contains.stdout.strip():
            problems.append(f"COMMIT DOES NOT CONTAIN FILE: {r['commit']}")

        status = "PASS" if not problems else "FAIL"
        if problems:
            failures += 1
        print(f"  [{status}] #{r['num']} {r['path']} ({r['session']})")
        for p in problems:
            print(f"         -> {p}")

    if failures:
        print(f"RESULT: FAIL ({failures}/{len(rows)} rows broken)")
        return 1
    print("RESULT: PASS — all ledger artifacts exist, hash-match, "
          "are git-tracked, and are contained in their recorded commits.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
