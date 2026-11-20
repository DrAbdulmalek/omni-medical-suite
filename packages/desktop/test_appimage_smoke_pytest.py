"""
Pytest wrapper for AppImage smoke tests.

When a real AppImage is not available (e.g., during normal CI without the
desktop build job), these tests are skipped. When MEDICAL_DOC_APPIMAGE
env var points to a built AppImage, the tests run.

Run:
    MEDICAL_DOC_APPIMAGE=path/to/MedicalDocProcessor-x.y.z-x86_64.AppImage \
        pytest packages/desktop/test_appimage_smoke_pytest.py -v
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

APPIMAGE_ENV = "MEDICAL_DOC_APPIMAGE"


def _get_appimage() -> Path | None:
    p = os.environ.get(APPIMAGE_ENV)
    if not p:
        return None
    path = Path(p).expanduser().resolve()
    if not path.exists():
        return None
    return path


APPIMAGE = _get_appimage()
pytestmark = pytest.mark.skipif(
    APPIMAGE is None,
    reason=f"Set {APPIMAGE_ENV} env var to point to a built AppImage to run these tests",
)


def test_appimage_exists():
    assert APPIMAGE is not None
    assert APPIMAGE.exists(), f"AppImage missing: {APPIMAGE}"


def test_appimage_is_executable():
    assert APPIMAGE is not None
    assert os.access(APPIMAGE, os.X_OK), "AppImage must be chmod +x"


def test_appimage_is_elf():
    assert APPIMAGE is not None
    magic = APPIMAGE.read_bytes()[:4]
    assert magic == b"\x7fELF", f"Expected ELF magic, got {magic!r}"


def test_checksum_file_exists():
    assert APPIMAGE is not None
    sha_file = Path(str(APPIMAGE) + ".sha256")
    assert sha_file.exists(), f"Checksum file missing: {sha_file}"


def test_checksum_matches():
    assert APPIMAGE is not None
    import hashlib
    import re

    sha_file = Path(str(APPIMAGE) + ".sha256")
    line = sha_file.read_text().strip()
    match = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+)$", line)
    assert match, f"Invalid checksum format: {line!r}"
    expected = match.group(1).lower()
    actual = hashlib.sha256(APPIMAGE.read_bytes()).hexdigest()
    assert actual == expected, f"Checksum mismatch: {expected} vs {actual}"


def test_appimage_extractable(tmp_path: Path):
    assert APPIMAGE is not None
    result = subprocess.run(
        [str(APPIMAGE), "--appimage-extract"],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=60,
    )
    squashfs_root = tmp_path / "squashfs-root"
    assert squashfs_root.exists(), (
        f"squashfs-root not created (exit={result.returncode}, "
        f"stderr={result.stderr[:300]})"
    )


@pytest.fixture(scope="module")
def squashfs_root(tmp_path_factory):
    """Extract the AppImage once for all layout tests."""
    if APPIMAGE is None:
        pytest.skip("No AppImage available")
    tmp = tmp_path_factory.mktemp("appimage_extract")
    subprocess.run(
        [str(APPIMAGE), "--appimage-extract"],
        cwd=str(tmp),
        check=True,
        capture_output=True,
        timeout=60,
    )
    return tmp / "squashfs-root"


def test_appdir_has_apprun(squashfs_root):
    p = squashfs_root / "AppRun"
    assert p.is_file(), f"AppRun missing: {p}"
    assert os.access(p, os.X_OK), "AppRun not executable"


def test_appdir_has_binary(squashfs_root):
    p = squashfs_root / "usr/bin/medical-doc-processor"
    assert p.is_file(), f"Binary missing: {p}"
    assert p.stat().st_size > 1_000_000, "Binary suspiciously small (<1MB)"
    # Verify ELF magic
    assert p.read_bytes()[:4] == b"\x7fELF", "Binary is not ELF"


def test_appdir_has_desktop_file(squashfs_root):
    p = squashfs_root / "usr/share/applications/com.omnimedical.docprocessor.desktop"
    assert p.is_file(), f"Desktop file missing: {p}"
    content = p.read_text(encoding="utf-8")
    assert "Type=Application" in content
    assert "Exec=medical-doc-processor" in content
    assert "Categories=" in content


def test_appdir_has_metainfo(squashfs_root):
    p = squashfs_root / "usr/share/metainfo/MedicalDocProcessor.metainfo.xml"
    assert p.is_file(), f"Metainfo missing: {p}"
    xml = p.read_text(encoding="utf-8")
    assert "<component" in xml
    assert "</component>" in xml
    assert "com.omnimedical.docprocessor" in xml


def test_appdir_has_icon(squashfs_root):
    p = squashfs_root / "usr/share/icons/hicolor/256x256/apps/com.omnimedical.docprocessor.png"
    assert p.is_file(), f"Icon missing: {p}"
    assert p.stat().st_size > 100, "Icon suspiciously small (<100 bytes)"
    # Verify PNG magic
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "Icon is not a PNG"
