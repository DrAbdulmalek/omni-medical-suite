#!/usr/bin/env python3
"""
check_appimage_freshness.py — Detect stale AppImage builds.

Compares the git commit recorded in ``packages/desktop/.last_build_commit``
against the latest commit that touched the AppImage's *functional surface*
— specifically the four scanner_fixer modules plus the desktop GUI entry
point. Scoping to these five files avoids false positives when unrelated
parts of the monorepo change (docs, mobile, training_hub, etc.).

Tracked files (relative to repo root):
    packages/scanner_fixer/src/scanner_fixer/deskew.py
    packages/scanner_fixer/src/scanner_fixer/crop.py
    packages/scanner_fixer/src/scanner_fixer/normalize.py
    packages/scanner_fixer/src/scanner_fixer/dedup.py
    packages/desktop/medical_doc_gui_final.py

Exit codes:
    0 — AppImage is fresh (no rebuild needed)
    1 — AppImage is stale (rebuild needed)
    2 — No previous build recorded (.last_build_commit missing) — fresh build
        needed; prints an actionable hint
    3 — Configuration error (not a git repo, scanner_fixer missing, ...)

Usage:
    python3 scripts/check_appimage_freshness.py
    python3 scripts/check_appimage_freshness.py --json
    python3 scripts/check_appimage_freshness.py --repo /path/to/repo
    python3 scripts/check_appimage_freshness.py --quiet

CI integration (warning-only):
    The GitHub Actions workflow in .github/workflows/appimage-freshness.yml
    runs this script on every push/PR and surfaces the result as a warning
    annotation via GitHub Actions output. It never fails the build.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# ─── Constants ───────────────────────────────────────────────────────────────

# Files whose change should trigger an AppImage rebuild.
# Scoped deliberately — NOT the whole scanner_fixer package, to avoid
# false positives when only tests/__init__/docs change.
TRACKED_FILES: tuple[str, ...] = (
    "packages/scanner_fixer/src/scanner_fixer/deskew.py",
    "packages/scanner_fixer/src/scanner_fixer/crop.py",
    "packages/scanner_fixer/src/scanner_fixer/normalize.py",
    "packages/scanner_fixer/src/scanner_fixer/dedup.py",
    "packages/desktop/medical_doc_gui_final.py",
)

LAST_BUILD_COMMIT_FILE = "packages/desktop/.last_build_commit"

# Exit codes (mirrored in module docstring)
EXIT_FRESH = 0
EXIT_STALE = 1
EXIT_NO_BUILD = 2
EXIT_CONFIG_ERROR = 3


# ─── Helpers ─────────────────────────────────────────────────────────────────


def run_git(repo_root: Path, args: list[str]) -> str:
    """Run a git command in repo_root and return stripped stdout.

    Raises RuntimeError on non-zero exit. Output is decoded as UTF-8 with
    errors='replace' to tolerate stray non-UTF-8 bytes in commit messages.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()


def is_git_repo(repo_root: Path) -> bool:
    """True if repo_root is inside a git working tree."""
    try:
        out = run_git(repo_root, ["rev-parse", "--is-inside-work-tree"])
        return out == "true"
    except (RuntimeError, FileNotFoundError, OSError):
        return False


def read_last_build_commit(repo_root: Path) -> Optional[str]:
    """Read the commit hash recorded by build_appimage.sh.

    Returns None if the file is missing or empty. Trims whitespace and
    ignores comment lines (lines starting with '#').
    """
    path = repo_root / LAST_BUILD_COMMIT_FILE
    if not path.is_file():
        return None
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Take the first non-comment, non-empty token (a 40-char or short hash)
        return line.split()[0]
    return None


def latest_commit_touching(repo_root: Path, paths: tuple[str, ...]) -> Optional[str]:
    """Return the latest commit hash that modified any of the given paths.

    Returns None if no commit touches any of them (extremely unlikely in
    practice, but we handle it gracefully).
    """
    # Verify all tracked files exist in the working tree — a missing file
    # is a config error worth surfacing.
    missing = [p for p in paths if not (repo_root / p).is_file()]
    if missing:
        # Special case: scanner_fixer is a submodule in some forks. If the
        # submodule isn't checked out, we cannot reliably check freshness;
        # treat as config error.
        raise RuntimeError(
            f"Tracked file(s) not found in working tree: {missing}. "
            "Make sure all submodules are initialized: `git submodule update --init --recursive`."
        )

    try:
        # --max-count=1 → only the most recent commit
        # -z is unnecessary since none of our paths contain whitespace/LF
        out = run_git(repo_root, ["log", "-n", "1", "--format=%H", "--", *paths])
    except RuntimeError as exc:
        # Re-raise with clearer context
        raise RuntimeError(f"Could not query git log for tracked files: {exc}") from exc

    if not out:
        # No commit in history touches any of these paths — this happens
        # only in a fresh repo before any of these files were added. Treat
        # as "fresh build needed" since we have no baseline.
        return None

    return out


def commit_short(hash_long: str, repo_root: Path, length: int = 7) -> str:
    """Shorten a commit hash for display."""
    try:
        return run_git(repo_root, ["rev-parse", "--short=%d" % length, hash_long])
    except RuntimeError:
        return hash_long[:length]


def commit_subject(hash_long: str, repo_root: Path) -> str:
    """Return the one-line subject of a commit."""
    try:
        return run_git(repo_root, ["log", "-n", "1", "--format=%s", hash_long])
    except RuntimeError:
        return "(unknown)"


def commit_date(hash_long: str, repo_root: Path) -> str:
    """Return ISO-8601 commit date (author date) of a commit."""
    try:
        return run_git(
            repo_root,
            ["log", "-n", "1", "--format=%cI", hash_long],
        )
    except RuntimeError:
        return "(unknown)"


# ─── Main freshness check ───────────────────────────────────────────────────


def check_freshness(repo_root: Path) -> dict:
    """Run the freshness check and return a structured result.

    Returns a dict with keys:
        status: "fresh" | "stale" | "no_build" | "error"
        exit_code: int (one of EXIT_*)
        last_build_commit: str | None
        last_build_commit_short: str | None
        latest_tracked_commit: str | None
        latest_tracked_commit_short: str | None
        message: str (human-readable summary)
        hint: str | None (next action for the user)
    """
    result = {
        "status": "error",
        "exit_code": EXIT_CONFIG_ERROR,
        "last_build_commit": None,
        "last_build_commit_short": None,
        "latest_tracked_commit": None,
        "latest_tracked_commit_short": None,
        "message": "",
        "hint": None,
    }

    if not is_git_repo(repo_root):
        result["message"] = f"Not a git repository: {repo_root}"
        result["hint"] = "Run this script from inside the omni-medical-suite checkout."
        return result

    last_build = read_last_build_commit(repo_root)
    result["last_build_commit"] = last_build
    if last_build:
        result["last_build_commit_short"] = commit_short(last_build, repo_root)

    try:
        latest = latest_commit_touching(repo_root, TRACKED_FILES)
    except RuntimeError as exc:
        result["message"] = str(exc)
        result["hint"] = (
            "Verify that scanner_fixer is checked out (it may be a submodule)."
        )
        return result

    result["latest_tracked_commit"] = latest
    if latest:
        result["latest_tracked_commit_short"] = commit_short(latest, repo_root)

    if last_build is None:
        result["status"] = "no_build"
        result["exit_code"] = EXIT_NO_BUILD
        result["message"] = (
            f"No previous AppImage build recorded "
            f"({LAST_BUILD_COMMIT_FILE} missing)."
        )
        result["hint"] = (
            "Run `bash packages/desktop/build_appimage.sh` to build the AppImage; "
            "it will write .last_build_commit automatically."
        )
        return result

    if latest is None:
        # No commit touches any tracked file (e.g., fresh repo). The
        # existing .last_build_commit cannot be stale w.r.t. these files.
        result["status"] = "fresh"
        result["exit_code"] = EXIT_FRESH
        result["message"] = (
            "No commits touch the tracked scanner_fixer/GUI files yet — "
            "AppImage is considered fresh by default."
        )
        return result

    if last_build == latest:
        result["status"] = "fresh"
        result["exit_code"] = EXIT_FRESH
        result["message"] = (
            f"AppImage is fresh. Last build commit "
            f"({result['last_build_commit_short']}) matches latest tracked "
            f"commit ({result['latest_tracked_commit_short']}). No rebuild needed."
        )
        return result

    # Stale: latest tracked commit is newer than (or different from) last build.
    # Verify ordering by date — if last_build is *ahead* of latest, something
    # odd happened (e.g., .last_build_commit was hand-edited); still report
    # stale but note it.
    is_ancestor = False
    try:
        # `git merge-base --is-ancestor A B` returns 0 if A is ancestor of B
        subprocess.run(
            ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", latest, last_build],
            capture_output=True,
            check=False,
        )
        # If latest is ancestor of last_build → last_build is newer (rare)
        rc_newer = subprocess.run(
            ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", last_build, latest],
            capture_output=True,
            check=False,
        ).returncode
        is_ancestor = rc_newer == 0
    except (FileNotFoundError, OSError):
        pass

    if is_ancestor:
        # last_build is ancestor of latest → latest is strictly newer → stale
        stale_reason = (
            f"Tracked files changed in {result['latest_tracked_commit_short']} "
            f"(after last build {result['last_build_commit_short']})."
        )
    else:
        # last_build is NOT an ancestor of latest → branches diverged or
        # .last_build_commit was hand-edited. Either way, rebuild is safer.
        stale_reason = (
            f"Last build commit ({result['last_build_commit_short']}) is not an "
            f"ancestor of the latest tracked commit "
            f"({result['latest_tracked_commit_short']}). Branches may have "
            f"diverged — rebuild recommended."
        )

    result["status"] = "stale"
    result["exit_code"] = EXIT_STALE
    result["message"] = f"AppImage is STALE. {stale_reason}"
    result["hint"] = (
        "Rebuild with: `bash packages/desktop/build_appimage.sh` "
        "(or `--version-from-git` for a tagged release)."
    )
    return result


# ─── CLI ─────────────────────────────────────────────────────────────────────


def format_human(result: dict) -> str:
    """Format the result for human-readable terminal output."""
    status = result["status"].upper()
    icon = {
        "fresh": "✓",
        "stale": "⚠",
        "no_build": "ℹ",
        "error": "✗",
    }.get(result["status"], "?")

    lines = [
        f"{icon} AppImage freshness: {status}",
        f"  {result['message']}",
    ]
    if result.get("last_build_commit_short"):
        lines.append(
            f"  Last build commit : {result['last_build_commit_short']} "
            f"({commit_date(result['last_build_commit'], Path.cwd())})"
        )
    if result.get("latest_tracked_commit_short"):
        lines.append(
            f"  Latest tracked    : {result['latest_tracked_commit_short']} "
            f"— {commit_subject(result['latest_tracked_commit'], Path.cwd())[:70]}"
        )
    if result.get("hint"):
        lines.append(f"  → {result['hint']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check if the AppImage needs rebuilding based on tracked source files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Tracked files:\n  " + "\n  ".join(TRACKED_FILES) + "\n\n"
            "Exit codes: 0=fresh, 1=stale, 2=no previous build, 3=config error"
        ),
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Path to the omni-medical-suite repo root (default: parent of this script).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all output; only return the exit code.",
    )
    args = parser.parse_args()

    result = check_freshness(args.repo)

    if not args.quiet:
        if args.json:
            # JSON output goes to stdout for CI parsing
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(format_human(result))

    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
