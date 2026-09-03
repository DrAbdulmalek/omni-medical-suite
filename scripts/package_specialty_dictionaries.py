#!/usr/bin/env python3
"""
scripts/package_specialty_dictionaries.py

Deterministic specialty dictionary archive packager and validator.

Creates a reproducible .tar.gz archive from data/dictionaries/specialty/
with normalized metadata (uid=0, gid=0, uname=root, gname=root),
deterministic timestamps, and sorted member ordering.

Also validates archives against the security policy:
  - Only regular files and directories allowed
  - No symlinks, hardlinks, FIFOs, devices, sockets
  - No absolute paths or path traversal
  - No executable data files (0644 only for regular files)
  - Only expected specialty dictionary files

Usage:
  # Create archive
  python3 scripts/package_specialty_dictionaries.py --output archive.tar.gz

  # Validate archive
  python3 scripts/package_specialty_dictionaries.py --validate-only archive.tar.gz

  # Build twice and verify reproducibility
  python3 scripts/package_specialty_dictionaries.py --output a.tar.gz
  python3 scripts/package_specialty_dictionaries.py --output b.tar.gz
  cmp a.tar.gz b.tar.gz
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import stat
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPECIALTY_DIR = PROJECT_ROOT / "data" / "dictionaries" / "specialty"

# Expected files in the specialty directory
EXPECTED_FILES = {
    "orthopedic_surgery.json",
    "anatomy.json",
    "general_medical.json",
    "surgery_general.json",
    "cardiovascular.json",
    "oncology.json",
    "abdomen_pelvis.json",
    "endocrinology.json",
    "_summary.json",
    "_quarantined.json",
    "_monolingual_corpus.json",
    "_hashes.json",
}

# Archive root directory name
ARCHIVE_ROOT = "malek-specialty-dictionaries"
SPECIALTY_SUBDIR = "specialty"

# Deterministic timestamp (SOURCE_DATE_EPOCH or fixed default)
DEFAULT_TIMESTAMP = 1700000000  # 2023-11-14T22:13:20Z


def _get_timestamp() -> int:
    """Get deterministic timestamp from SOURCE_DATE_EPOCH or default."""
    env = os.environ.get("SOURCE_DATE_EPOCH")
    if env:
        try:
            return int(env)
        except ValueError:
            pass
    return DEFAULT_TIMESTAMP


class ArchivePolicyError(Exception):
    """Raised when an archive violates the security policy."""


def validate_archive(path: Path) -> None:
    """Validate an archive against the release security policy.

    The validator deliberately enforces the archive layout as well as member
    safety. Checking only basenames would allow duplicate or misplaced members
    to satisfy the expected-file set while carrying unrelated content.
    """
    errors: list[str] = []
    expected_root = ARCHIVE_ROOT
    expected_dir = f"{ARCHIVE_ROOT}/{SPECIALTY_SUBDIR}"
    expected_paths = {
        f"{expected_dir}/{name}" for name in EXPECTED_FILES
    }
    seen_paths: set[str] = set()

    with tarfile.open(path, "r:gz") as tar:
        members = tar.getmembers()
        for m in members:
            name = m.name.rstrip("/")
            if m.name.startswith("/") or ".." in Path(m.name).parts:
                errors.append(f"Unsafe archive path rejected: {m.name}")
                continue

            if m.issym() or m.islnk() or m.isfifo() or m.ischr() or m.isblk():
                errors.append(f"Unsupported archive member type rejected: {m.name}")
                continue
            if not (m.isdir() or m.isfile()):
                errors.append(f"Unknown archive member type rejected: {m.name}")
                continue

            if m.isdir():
                if name not in {expected_root, expected_dir}:
                    errors.append(f"Unexpected directory in archive: {m.name}")
                if m.mode != 0o755:
                    errors.append(f"Directory mode must be 0755: {m.name} ({oct(m.mode)})")
                continue

            # Regular files must live exactly under the canonical specialty path.
            if name not in expected_paths:
                errors.append(f"Unexpected file path in archive: {m.name}")
                continue
            if name in seen_paths:
                errors.append(f"Duplicate archive member: {m.name}")
                continue
            seen_paths.add(name)

            if m.mode != 0o644:
                errors.append(f"Regular file mode must be 0644: {m.name} ({oct(m.mode)})")
            if m.uid != 0 or m.gid != 0 or m.uname != "root" or m.gname != "root":
                errors.append(f"Non-normalized ownership rejected: {m.name}")

        missing = expected_paths - seen_paths
        if missing:
            errors.append(f"Missing expected files: {sorted(missing)}")

    if errors:
        raise ArchivePolicyError(
            "Archive policy validation failed:\n  " + "\n  ".join(errors)
        )

def create_archive(source_dir: Path, output: Path) -> str:
    """Create a deterministic .tar.gz archive.

    Returns the SHA-256 of the created archive.
    """
    timestamp = _get_timestamp()

    # Collect and sort files
    files_to_pack: list[tuple[str, bytes]] = []
    for f in sorted(source_dir.iterdir()):
        if f.is_file() and f.name in EXPECTED_FILES:
            rel_path = f"{ARCHIVE_ROOT}/{SPECIALTY_SUBDIR}/{f.name}"
            files_to_pack.append((rel_path, f.read_bytes()))

    if not files_to_pack:
        raise ValueError(f"No expected specialty files found in {source_dir}")

    # Check for missing files
    found_names = {os.path.basename(p) for p, _ in files_to_pack}
    missing = EXPECTED_FILES - found_names
    if missing:
        raise ValueError(f"Missing expected files: {sorted(missing)}")

    # Create tar archive in memory
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
        # Add root directory
        root_info = tarfile.TarInfo(name=ARCHIVE_ROOT)
        root_info.type = tarfile.DIRTYPE
        root_info.mode = 0o755
        root_info.uid = 0
        root_info.gid = 0
        root_info.uname = "root"
        root_info.gname = "root"
        root_info.mtime = timestamp
        tar.addfile(root_info)

        # Add specialty subdirectory
        subdir_info = tarfile.TarInfo(name=f"{ARCHIVE_ROOT}/{SPECIALTY_SUBDIR}")
        subdir_info.type = tarfile.DIRTYPE
        subdir_info.mode = 0o755
        subdir_info.uid = 0
        subdir_info.gid = 0
        subdir_info.uname = "root"
        subdir_info.gname = "root"
        subdir_info.mtime = timestamp
        tar.addfile(subdir_info)

        # Add files
        for rel_path, data in files_to_pack:
            info = tarfile.TarInfo(name=rel_path)
            info.size = len(data)
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mtime = timestamp
            info.type = tarfile.REGTYPE
            tar.addfile(info, io.BytesIO(data))

    # Write gzip with deterministic metadata
    tar_bytes = tar_buffer.getvalue()
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "wb") as f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=timestamp) as gz:
            gz.write(tar_bytes)

    # Calculate SHA-256
    sha256 = hashlib.sha256(output.read_bytes()).hexdigest()
    return output


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic specialty dictionary archive packager/validator."
    )
    parser.add_argument(
        "--output", "-o",
        help="Output archive path (for creation mode)"
    )
    parser.add_argument(
        "--validate-only",
        metavar="ARCHIVE",
        help="Validate an existing archive against the security policy"
    )
    parser.add_argument(
        "--source-dir",
        default=str(SPECIALTY_DIR),
        help=f"Source directory (default: {SPECIALTY_DIR})"
    )
    args = parser.parse_args()

    if args.validate_only:
        archive_path = Path(args.validate_only)
        if not archive_path.exists():
            print(f"ERROR: Archive not found: {archive_path}", file=sys.stderr)
            sys.exit(1)
        try:
            validate_archive(archive_path)
            print(f"✅ Archive valid: {archive_path}")
            sha = hashlib.sha256(archive_path.read_bytes()).hexdigest()
            print(f"SHA-256: {sha}")
        except ArchivePolicyError as e:
            print(f"❌ Archive policy violation:\n{e}", file=sys.stderr)
            sys.exit(1)
        return

    if args.output:
        source = Path(args.source_dir)
        if not source.exists():
            print(f"ERROR: Source directory not found: {source}", file=sys.stderr)
            sys.exit(1)

        archive_path = create_archive(source, Path(args.output))
        sha = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        print(f"✅ Archive created: {args.output}")
        print(f"SHA-256: {sha}")

        # Validate the created archive
        try:
            validate_archive(Path(args.output))
            print(f"✅ Archive validated against security policy")
        except ArchivePolicyError as e:
            print(f"❌ Created archive failed validation:\n{e}", file=sys.stderr)
            sys.exit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
