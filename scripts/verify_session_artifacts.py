#!/usr/bin/env python3
"""verify_session_artifacts.py — الإثبات الآلي لقاعدة الحفظ الدائم.

Reads docs/SESSION_ARTIFACTS_LEDGER.md and verifies, for every row:
  1. the artifact exists in git at the RECORDED containing commit
     (`git cat-file -e <commit>:<path>`),
  2. sha256 of the blob `git show <commit>:<path>` matches the ledger hash
     EXACTLY (git-blob verification keeps the ledger append-only: rows for
     superseded historical versions stay valid forever),
  3. the file is git-TRACKED in HEAD — an uncommitted artifact fails,
  4. the recorded commit actually touched the file
     (`git log -n 1 <commit> -- <path>` resolves to that commit).

Exit code: 0 = PASS (all rows verified), 1 = FAIL (any check broken).
Run before ending EVERY session (docs/SESSION_ARTIFACTS_POLICY.md, rule 3).

Note: the ledger and this verifier are protocol INFRASTRUCTURE; their own
integrity rests on the git commit graph (final commit SHA is recorded in
worklog.md + the owner-facing closure message), not on self-referential rows.
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / "docs" / "SESSION_ARTIFACTS_LEDGER.md"
ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|")


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
        problems = []

        # 1+2. blob exists at recorded commit + sha256 matches
        blob = git("show", f"{r['commit']}:{r['path']}")
        if blob.returncode != 0:
            problems.append(f"BLOB MISSING AT COMMIT: {r['commit']}:{r['path']}")
        else:
            actual = hashlib.sha256(blob.stdout.encode("utf-8")).hexdigest()
            if actual != r["sha256"]:
                problems.append(f"SHA MISMATCH (blob@commit={actual})")

        # 3. tracked by git in HEAD
        tracked = git("ls-files", "--error-unmatch", r["path"])
        if tracked.returncode != 0:
            problems.append("NOT GIT-TRACKED (uncommitted artifact!)")

        # 4. recorded commit actually touched the file
        touches = git("log", "--format=%H", "-n", "1", r["commit"], "--", r["path"])
        if touches.stdout.strip() != r["commit"]:
            problems.append(
                f"COMMIT DID NOT TOUCH FILE (last toucher: {touches.stdout.strip()})"
            )

        status = "PASS" if not problems else "FAIL"
        if problems:
            failures += 1
        print(f"  [{status}] #{r['num']} {r['path']} ({r['session']})")
        for p in problems:
            print(f"         -> {p}")

    if failures:
        print(f"RESULT: FAIL ({failures}/{len(rows)} rows broken)")
        return 1
    print("RESULT: PASS — all ledger artifacts exist at their recorded commits, "
          "hash-match (git blob sha256), are git-tracked, and their recorded "
          "commits touched them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
