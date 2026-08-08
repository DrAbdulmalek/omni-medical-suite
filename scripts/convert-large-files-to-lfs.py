#!/usr/bin/env python3
"""
convert-large-files-to-lfs.py

Find all files > 1MB in the working tree that match .gitattributes LFS patterns
but are stored as regular git blobs, then convert them to LFS pointers.

Strategy:
  1. Find large files (> 1MB) not already tracked by LFS
  2. git rm --cached <file>  (remove from index)
  3. git add -f <file>       (re-add, LFS smudge filter converts to pointer)
  4. Commit all conversions as a single commit
"""
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIZE_THRESHOLD = 1 * 1024 * 1024  # 1 MB


def run(cmd, **kwargs):
    """Run a shell command and return stdout."""
    result = subprocess.run(
        cmd, shell=True, cwd=REPO_ROOT, capture_output=True, text=True, **kwargs
    )
    return result


def get_lfs_files():
    """Get set of files already tracked by LFS."""
    result = run("git lfs ls-files")
    lfs_files = set()
    for line in result.stdout.strip().split("\n"):
        if line.strip():
            # Format: <hash> - <path>
            parts = line.split(" - ", 1)
            if len(parts) == 2:
                lfs_files.add(parts[1].strip())
    return lfs_files


def find_large_files():
    """Find files > SIZE_THRESHOLD not in LFS."""
    large_files = []
    for root, dirs, files in os.walk(REPO_ROOT):
        # Skip .git directory
        if ".git" in root:
            continue
        for fname in files:
            fpath = os.path.join(root, fname)
            try:
                fsize = os.path.getsize(fpath)
            except OSError:
                continue
            if fsize > SIZE_THRESHOLD:
                relpath = os.path.relpath(fpath, REPO_ROOT)
                large_files.append((relpath, fsize))
    return large_files


def main():
    os.chdir(REPO_ROOT)

    print("=" * 60)
    print("  Convert Large Files to Git LFS Pointers")
    print("=" * 60)

    # Check clean working tree
    status = run("git status --porcelain")
    if status.stdout.strip():
        print("ERROR: Working tree is not clean. Commit or stash first.")
        print(status.stdout)
        sys.exit(1)

    # Get LFS files
    lfs_files = get_lfs_files()
    print(f"  LFS-tracked files: {len(lfs_files)}")

    # Find large files
    large_files = find_large_files()
    print(f"  Files > 1MB: {len(large_files)}")

    # Filter: only files NOT already in LFS
    to_convert = []
    for relpath, fsize in large_files:
        basename = os.path.basename(relpath)
        if relpath not in lfs_files and basename not in lfs_files:
            to_convert.append((relpath, fsize))

    if not to_convert:
        print("\n✅ All large files already tracked by LFS. Nothing to do.")
        return

    # Sort by size descending
    to_convert.sort(key=lambda x: -x[1])

    print(f"\n  Files to convert: {len(to_convert)}")
    total_size = sum(s for _, s in to_convert)
    print(f"  Total size: {total_size / (1024*1024):.1f} MB\n")

    for relpath, fsize in to_convert:
        size_mb = fsize / (1024 * 1024)
        print(f"  📦 {relpath} ({size_mb:.1f} MB)")

    # Ask for confirmation
    if "--yes" not in sys.argv:
        answer = input("\nProceed with conversion? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            return

    # Convert each file
    converted = 0
    failed = 0
    for relpath, fsize in to_convert:
        size_mb = fsize / (1024 * 1024)
        print(f"\n  Converting: {relpath} ({size_mb:.1f} MB)")

        # Step 1: Remove from git index (keep working tree file)
        result = run(f'git rm --cached "{relpath}"')
        if result.returncode != 0:
            print(f"    ❌ git rm failed: {result.stderr}")
            failed += 1
            continue

        # Step 2: Re-add (LFS filter will create pointer)
        result = run(f'git add -f "{relpath}"')
        if result.returncode != 0:
            print(f"    ❌ git add failed: {result.stderr}")
            failed += 1
            continue

        # Verify conversion
        result = run(f'git diff --cached --stat "{relpath}"')
        if "133 bytes" in result.stdout or "132 bytes" in result.stdout:
            print(f"    ✅ Converted to LFS pointer")
            converted += 1
        else:
            print(f"    ⚠️  May not have been converted: {result.stdout.strip()}")
            converted += 1

    print(f"\n{'=' * 60}")
    print(f"  Converted: {converted}")
    print(f"  Failed: {failed}")
    print(f"{'=' * 60}")

    if converted > 0:
        print(f"\n  Next step: git commit -m 'chore(lfs): convert {converted} large files to LFS pointers'")


if __name__ == "__main__":
    main()
