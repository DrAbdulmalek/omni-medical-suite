#!/usr/bin/env python3
"""
tests/test_specialty_archive_contract.py

Adversarial security tests for the specialty dictionary archive packager
and installer trust boundary.

Tests use real adversarial tar fixtures (not string assertions) to verify:
  1. Valid archive → accepted
  2. Executable JSON (mode 0755) → rejected
  3. Path traversal (../evil.json) → rejected
  4. Absolute path → rejected
  5. Symlink member → rejected
  6. Hardlink member → rejected
  7. FIFO member → rejected
  8. Unexpected file (malicious.sh) → rejected
  9. Reproducible packaging → byte-identical archives
  10. Installed files have 0644 permissions
"""
from __future__ import annotations

import gzip
import hashlib
import io
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.package_specialty_dictionaries import (
    validate_archive,
    create_archive,
    ArchivePolicyError,
    EXPECTED_FILES,
)

SCRIPTS_DIR = PROJECT_ROOT / "scripts"
INSTALLER = SCRIPTS_DIR / "setup_dictionaries.sh"


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_valid_specialty_dir(tmp: Path) -> Path:
    """Create a temp directory with all expected specialty files."""
    specialty = tmp / "specialty"
    specialty.mkdir()
    for name in EXPECTED_FILES:
        (specialty / name).write_text('{"test": true}', encoding="utf-8")
    return tmp


def _make_archive(members: list[tuple[str, bytes, int]], tmp: Path) -> Path:
    """Create a tar.gz with arbitrary members.

    members: list of (name, content, mode)
    """
    archive = tmp / "test.tar.gz"
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
        for name, content, mode in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            info.mode = mode
            info.uid = 0
            info.gid = 0
            info.mtime = 1700000000
            info.type = tarfile.REGTYPE
            tar.addfile(info, io.BytesIO(content))
    with gzip.GzipFile(filename="", mode="wb", fileobj=open(archive, "wb"), mtime=1700000000) as gz:
        gz.write(tar_buffer.getvalue())
    return archive


def _make_archive_with_type(name: str, member_type: int, tmp: Path, linkname: str = "") -> Path:
    """Create a tar.gz with a special member type."""
    archive = tmp / "test.tar.gz"
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
        info = tarfile.TarInfo(name=name)
        info.mode = 0o644
        info.uid = 0
        info.gid = 0
        info.mtime = 1700000000
        info.type = member_type
        if linkname:
            info.linkname = linkname
        if member_type == tarfile.REGTYPE:
            info.size = 5
            tar.addfile(info, io.BytesIO(b"test\n"))
        else:
            tar.addfile(info)
    with gzip.GzipFile(filename="", mode="wb", fileobj=open(archive, "wb"), mtime=1700000000) as gz:
        gz.write(tar_buffer.getvalue())
    return archive


# ── Packager validation tests ────────────────────────────────────────────

class TestArchivePolicyValidation:
    """Test the archive validator with adversarial fixtures."""

    def test_valid_archive_accepted(self, tmp_path):
        """A valid archive with all expected files should be accepted."""
        source = _make_valid_specialty_dir(tmp_path)
        archive = create_archive(source / "specialty", tmp_path / "valid.tar.gz")
        # Should not raise
        validate_archive(archive)

    def test_executable_json_rejected(self, tmp_path):
        """JSON files with mode 0755 should be rejected."""
        members = [
            (f"malek-specialty-dictionaries/specialty/{name}",
             b'{"test": true}', 0o755)
            for name in EXPECTED_FILES
        ]
        archive = _make_archive(members, tmp_path)
        with pytest.raises(ArchivePolicyError, match="Executable data file"):
            validate_archive(archive)

    def test_path_traversal_rejected(self, tmp_path):
        """../traversal paths should be rejected."""
        members = [
            (f"malek-specialty-dictionaries/specialty/{name}",
             b'{"test": true}', 0o644)
            for name in EXPECTED_FILES
        ]
        members.append(("../evil.json", b'{"evil": true}', 0o644))
        archive = _make_archive(members, tmp_path)
        with pytest.raises(ArchivePolicyError, match="Path traversal"):
            validate_archive(archive)

    def test_absolute_path_rejected(self, tmp_path):
        """Absolute paths should be rejected."""
        members = [
            (f"malek-specialty-dictionaries/specialty/{name}",
             b'{"test": true}', 0o644)
            for name in EXPECTED_FILES
        ]
        members.append(("/etc/passwd", b"root:x:0:0", 0o644))
        archive = _make_archive(members, tmp_path)
        with pytest.raises(ArchivePolicyError, match="Absolute path"):
            validate_archive(archive)

    def test_symlink_rejected(self, tmp_path):
        """Symlink members should be rejected."""
        archive = _make_archive_with_type(
            "malek-specialty-dictionaries/specialty/symlink.json",
            tarfile.SYMTYPE,
            tmp_path,
            linkname="/etc/passwd"
        )
        with pytest.raises(ArchivePolicyError, match="Symlink"):
            validate_archive(archive)

    def test_hardlink_rejected(self, tmp_path):
        """Hardlink members should be rejected."""
        archive = _make_archive_with_type(
            "malek-specialty-dictionaries/specialty/hardlink.json",
            tarfile.LNKTYPE,
            tmp_path,
            linkname="malek-specialty-dictionaries/specialty/orthopedic_surgery.json"
        )
        with pytest.raises(ArchivePolicyError, match="Hardlink"):
            validate_archive(archive)

    def test_fifo_rejected(self, tmp_path):
        """FIFO members should be rejected."""
        archive = _make_archive_with_type(
            "malek-specialty-dictionaries/specialty/fifo.json",
            tarfile.FIFOTYPE,
            tmp_path
        )
        with pytest.raises(ArchivePolicyError, match="FIFO"):
            validate_archive(archive)

    def test_unexpected_file_rejected(self, tmp_path):
        """Unexpected files like malicious.sh should be rejected."""
        members = [
            (f"malek-specialty-dictionaries/specialty/{name}",
             b'{"test": true}', 0o644)
            for name in EXPECTED_FILES
        ]
        members.append(("malek-specialty-dictionaries/specialty/malicious.sh",
                        b'#!/bin/bash\nrm -rf /\n', 0o755))
        archive = _make_archive(members, tmp_path)
        with pytest.raises(ArchivePolicyError, match="Unexpected files"):
            validate_archive(archive)

    def test_missing_files_rejected(self, tmp_path):
        """Archives missing expected files should be rejected."""
        members = [
            (f"malek-specialty-dictionaries/specialty/{name}",
             b'{"test": true}', 0o644)
            for name in list(EXPECTED_FILES)[:3]  # only 3 of 12
        ]
        archive = _make_archive(members, tmp_path)
        with pytest.raises(ArchivePolicyError, match="Missing expected files"):
            validate_archive(archive)


# ── Reproducibility tests ─────────────────────────────────────────────────

class TestArchiveReproducibility:
    """Verify that the packager produces byte-identical archives."""

    def test_two_builds_produce_identical_archives(self, tmp_path):
        """Building the same source twice must produce byte-identical archives."""
        source = _make_valid_specialty_dir(tmp_path)

        archive1 = tmp_path / "build1.tar.gz"
        archive2 = tmp_path / "build2.tar.gz"

        create_archive(source / "specialty", archive1)
        create_archive(source / "specialty", archive2)

        sha1 = hashlib.sha256(archive1.read_bytes()).hexdigest()
        sha2 = hashlib.sha256(archive2.read_bytes()).hexdigest()
        assert sha1 == sha2, f"SHA-256 must match for identical sources: {sha1} vs {sha2}"
        assert archive1.read_bytes() == archive2.read_bytes(), (
            "Archives must be byte-identical"
        )

    def test_archive_has_deterministic_permissions(self, tmp_path):
        """All regular files in the archive must have mode 0644."""
        source = _make_valid_specialty_dir(tmp_path)
        archive = create_archive(source / "specialty", tmp_path / "test.tar.gz")

        with tarfile.open(archive, "r:gz") as tar:
            for m in tar.getmembers():
                if m.isfile():
                    assert m.mode == 0o644, (
                        f"File {m.name} has mode {oct(m.mode)}, expected 0644"
                    )

    def test_archive_has_normalized_ownership(self, tmp_path):
        """All members must have uid=0, gid=0, uname=root, gname=root."""
        source = _make_valid_specialty_dir(tmp_path)
        archive = create_archive(source / "specialty", tmp_path / "test.tar.gz")

        with tarfile.open(archive, "r:gz") as tar:
            for m in tar.getmembers():
                assert m.uid == 0, f"{m.name} has uid={m.uid}, expected 0"
                assert m.gid == 0, f"{m.name} has gid={m.gid}, expected 0"
                assert m.uname == "root", f"{m.name} has uname={m.uname}"
                assert m.gname == "root", f"{m.name} has gname={m.gname}"

    def test_archive_has_no_symlinks_or_hardlinks(self, tmp_path):
        """Archive must not contain symlinks or hardlinks."""
        source = _make_valid_specialty_dir(tmp_path)
        archive = create_archive(source / "specialty", tmp_path / "test.tar.gz")

        with tarfile.open(archive, "r:gz") as tar:
            for m in tar.getmembers():
                assert not m.issym(), f"Symlink found: {m.name}"
                assert not m.islnk(), f"Hardlink found: {m.name}"


# ── CLI integration tests ──────────────────────────────────────────────────

class TestPackagerCLI:
    """Test the packager CLI."""

    def test_validate_only_flag_works(self, tmp_path):
        """--validate-only should validate an existing archive."""
        source = _make_valid_specialty_dir(tmp_path)
        archive = tmp_path / "test.tar.gz"
        create_archive(source / "specialty", archive)

        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "package_specialty_dictionaries.py"),
             "--validate-only", str(archive)],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "valid" in result.stdout.lower()

    def test_validate_only_rejects_bad_archive(self, tmp_path):
        """--validate-only should reject policy-violating archives."""
        members = [
            (f"malek-specialty-dictionaries/specialty/{name}",
             b'{"test": true}', 0o755)  # executable
            for name in EXPECTED_FILES
        ]
        archive = _make_archive(members, tmp_path)

        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "package_specialty_dictionaries.py"),
             "--validate-only", str(archive)],
            capture_output=True, text=True
        )
        assert result.returncode == 1
        assert "Executable" in result.stderr or "violation" in result.stderr.lower()
