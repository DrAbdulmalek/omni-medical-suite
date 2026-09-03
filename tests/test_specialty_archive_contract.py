#!/usr/bin/env python3
"""Adversarial security tests for the specialty dictionary archive contract."""
from __future__ import annotations

import gzip
import hashlib
import io
import subprocess
import sys
import tarfile
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


def _make_valid_specialty_dir(tmp: Path) -> Path:
    specialty = tmp / "specialty"
    specialty.mkdir()
    for name in EXPECTED_FILES:
        (specialty / name).write_text('{"test": true}', encoding="utf-8")
    return tmp


def _make_archive(members: list[tuple[str, bytes, int]], tmp: Path) -> Path:
    archive = tmp / "test.tar.gz"
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
        for name, content, mode in members:
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            info.mode = mode
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mtime = 1700000000
            info.type = tarfile.REGTYPE
            tar.addfile(info, io.BytesIO(content))
    with open(archive, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=1700000000) as gz:
            gz.write(tar_buffer.getvalue())
    return archive


def _make_archive_with_type(name: str, member_type: int, tmp: Path, linkname: str = "") -> Path:
    archive = tmp / "test.tar.gz"
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
        info = tarfile.TarInfo(name=name)
        info.mode = 0o644
        info.uid = 0
        info.gid = 0
        info.uname = "root"
        info.gname = "root"
        info.mtime = 1700000000
        info.type = member_type
        if linkname:
            info.linkname = linkname
        tar.addfile(info)
    with open(archive, "wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=1700000000) as gz:
            gz.write(tar_buffer.getvalue())
    return archive


class TestArchivePolicyValidation:
    def test_valid_archive_accepted(self, tmp_path):
        source = _make_valid_specialty_dir(tmp_path)
        archive = create_archive(source / "specialty", tmp_path / "valid.tar.gz")
        validate_archive(archive)

    def test_executable_json_rejected(self, tmp_path):
        members = [(f"malek-specialty-dictionaries/specialty/{n}", b'{"test": true}', 0o755) for n in EXPECTED_FILES]
        archive = _make_archive(members, tmp_path)
        with pytest.raises(ArchivePolicyError):
            validate_archive(archive)

    def test_path_traversal_rejected(self, tmp_path):
        members = [(f"malek-specialty-dictionaries/specialty/{n}", b'{"test": true}', 0o644) for n in EXPECTED_FILES]
        members.append(("../evil.json", b'{"evil": true}', 0o644))
        archive = _make_archive(members, tmp_path)
        with pytest.raises(ArchivePolicyError):
            validate_archive(archive)

    def test_absolute_path_rejected(self, tmp_path):
        members = [(f"malek-specialty-dictionaries/specialty/{n}", b'{"test": true}', 0o644) for n in EXPECTED_FILES]
        members.append(("/etc/passwd", b"root:x:0:0", 0o644))
        archive = _make_archive(members, tmp_path)
        with pytest.raises(ArchivePolicyError):
            validate_archive(archive)

    def test_symlink_rejected(self, tmp_path):
        archive = _make_archive_with_type(
            "malek-specialty-dictionaries/specialty/symlink.json",
            tarfile.SYMTYPE, tmp_path, "/etc/passwd")
        with pytest.raises(ArchivePolicyError):
            validate_archive(archive)

    def test_hardlink_rejected(self, tmp_path):
        archive = _make_archive_with_type(
            "malek-specialty-dictionaries/specialty/hardlink.json",
            tarfile.LNKTYPE, tmp_path,
            "malek-specialty-dictionaries/specialty/orthopedic_surgery.json")
        with pytest.raises(ArchivePolicyError):
            validate_archive(archive)

    def test_fifo_rejected(self, tmp_path):
        archive = _make_archive_with_type(
            "malek-specialty-dictionaries/specialty/fifo.json",
            tarfile.FIFOTYPE, tmp_path)
        with pytest.raises(ArchivePolicyError):
            validate_archive(archive)

    def test_unexpected_file_rejected(self, tmp_path):
        members = [(f"malek-specialty-dictionaries/specialty/{n}", b'{"test": true}', 0o644) for n in EXPECTED_FILES]
        members.append(("malek-specialty-dictionaries/specialty/malicious.sh", b'#!/bin/bash\nrm -rf /\n', 0o755))
        archive = _make_archive(members, tmp_path)
        with pytest.raises(ArchivePolicyError):
            validate_archive(archive)

    def test_missing_files_rejected(self, tmp_path):
        members = [(f"malek-specialty-dictionaries/specialty/{n}", b'{"test": true}', 0o644) for n in list(EXPECTED_FILES)[:3]]
        archive = _make_archive(members, tmp_path)
        with pytest.raises(ArchivePolicyError):
            validate_archive(archive)


class TestArchiveReproducibility:
    def test_two_builds_produce_identical_archives(self, tmp_path):
        source = _make_valid_specialty_dir(tmp_path)
        archive1 = tmp_path / "build1.tar.gz"
        archive2 = tmp_path / "build2.tar.gz"
        create_archive(source / "specialty", archive1)
        create_archive(source / "specialty", archive2)
        assert hashlib.sha256(archive1.read_bytes()).hexdigest() == hashlib.sha256(archive2.read_bytes()).hexdigest()
        assert archive1.read_bytes() == archive2.read_bytes()

    def test_archive_has_deterministic_permissions(self, tmp_path):
        source = _make_valid_specialty_dir(tmp_path)
        archive = create_archive(source / "specialty", tmp_path / "test.tar.gz")
        with tarfile.open(archive, "r:gz") as tar:
            for m in tar.getmembers():
                if m.isfile():
                    assert m.mode == 0o644

    def test_archive_has_normalized_ownership(self, tmp_path):
        source = _make_valid_specialty_dir(tmp_path)
        archive = create_archive(source / "specialty", tmp_path / "test.tar.gz")
        with tarfile.open(archive, "r:gz") as tar:
            for m in tar.getmembers():
                assert (m.uid, m.gid, m.uname, m.gname) == (0, 0, "root", "root")

    def test_archive_has_no_symlinks_or_hardlinks(self, tmp_path):
        source = _make_valid_specialty_dir(tmp_path)
        archive = create_archive(source / "specialty", tmp_path / "test.tar.gz")
        with tarfile.open(archive, "r:gz") as tar:
            assert all(not m.issym() and not m.islnk() for m in tar.getmembers())


class TestPackagerCLI:
    def test_validate_only_flag_works(self, tmp_path):
        source = _make_valid_specialty_dir(tmp_path)
        archive = tmp_path / "test.tar.gz"
        create_archive(source / "specialty", archive)
        result = subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "package_specialty_dictionaries.py"), "--validate-only", str(archive)], capture_output=True, text=True)
        assert result.returncode == 0
        assert "valid" in result.stdout.lower()

    def test_validate_only_rejects_bad_archive(self, tmp_path):
        members = [(f"malek-specialty-dictionaries/specialty/{n}", b'{"test": true}', 0o755) for n in EXPECTED_FILES]
        archive = _make_archive(members, tmp_path)
        result = subprocess.run([sys.executable, str(PROJECT_ROOT / "scripts" / "package_specialty_dictionaries.py"), "--validate-only", str(archive)], capture_output=True, text=True)
        assert result.returncode == 1
        assert "violation" in result.stderr.lower()
