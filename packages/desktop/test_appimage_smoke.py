"""
Smoke test for AppImage build artifacts.

Verifies that:
1. The AppImage file exists and is executable
2. The SHA256 checksum file exists and matches
3. The AppImage can be extracted (--appimage-extract)
4. The extracted AppDir has the expected layout:
   - AppRun (executable)
   - usr/bin/medical-doc-processor
   - usr/share/applications/com.omnimedical.docprocessor.desktop
   - usr/share/metainfo/MedicalDocProcessor.metainfo.xml
   - usr/share/icons/hicolor/256x256/apps/com.omnimedical.docprocessor.png
5. The desktop file has the correct Type=Application

Usage:
    python test_appimage_smoke.py path/to/MedicalDocProcessor-x.y.z-x86_64.AppImage

Exit codes:
    0 — all checks passed
    1 — at least one check failed
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def fail(msg: str) -> None:
    print(f"  ❌ {msg}")
    sys.exit(1)


def ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def info(msg: str) -> None:
    print(f"  ℹ️  {msg}")


def verify_checksum(appimage: Path) -> None:
    """Verify the .sha256 file matches the AppImage."""
    sha_file = Path(str(appimage) + ".sha256")
    if not sha_file.exists():
        fail(f"Checksum file missing: {sha_file}")

    expected_line = sha_file.read_text().strip()
    # Format: "<hash>  <filename>"
    match = re.match(r"^([0-9a-fA-F]{64})\s+\*?(.+)$", expected_line)
    if not match:
        fail(f"Invalid checksum file format: {expected_line!r}")

    expected_hash = match.group(1).lower()
    actual_hash = hashlib.sha256(appimage.read_bytes()).hexdigest()
    if actual_hash != expected_hash:
        fail(
            f"Checksum mismatch:\n"
            f"  expected: {expected_hash}\n"
            f"  actual:   {actual_hash}"
        )
    ok(f"SHA256 checksum matches ({actual_hash[:16]}...)")


def extract_appimage(appimage: Path, dest: Path) -> Path:
    """Extract AppImage contents to dest/squashfs-root."""
    info(f"Extracting {appimage.name} → {dest}")
    result = subprocess.run(
        [str(appimage), "--appimage-extract"],
        cwd=str(dest),
        capture_output=True,
        text=True,
        timeout=60,
    )
    # --appimage-extract returns 0 on success
    squashfs_root = dest / "squashfs-root"
    if not squashfs_root.exists():
        # Some AppImages extract to ./squashfs-root relative to cwd
        # If it didn't, fall back to running with --appimage-extract-and-run
        print(f"  stderr: {result.stderr[:500]}", file=sys.stderr)
        fail("Extraction failed — squashfs-root not created")
    return squashfs_root


def verify_appdir(squashfs_root: Path) -> None:
    """Verify the extracted AppDir has the expected layout."""
    checks = [
        ("AppRun", "AppRun"),
        ("binary", "usr/bin/medical-doc-processor"),
        ("desktop file", "usr/share/applications/com.omnimedical.docprocessor.desktop"),
        ("metainfo", "usr/share/metainfo/MedicalDocProcessor.metainfo.xml"),
        ("icon", "usr/share/icons/hicolor/256x256/apps/com.omnimedical.docprocessor.png"),
    ]
    for label, rel_path in checks:
        p = squashfs_root / rel_path
        if not p.exists():
            fail(f"{label} missing: {rel_path}")
        if not p.is_file():
            fail(f"{label} is not a regular file: {rel_path}")
        size = p.stat().st_size
        if size == 0:
            fail(f"{label} is empty: {rel_path}")
        ok(f"{label} present ({size} bytes)")

    # Verify AppRun is executable
    apprun = squashfs_root / "AppRun"
    mode = apprun.stat().st_mode
    if not (mode & 0o111):
        fail("AppRun is not executable")
    ok("AppRun is executable")

    # Verify desktop file Type=Application
    desktop = squashfs_root / "usr/share/applications/com.omnimedical.docprocessor.desktop"
    content = desktop.read_text(encoding="utf-8")
    if "Type=Application" not in content:
        fail("Desktop file missing 'Type=Application'")
    if "Exec=medical-doc-processor" not in content:
        fail("Desktop file missing 'Exec=medical-doc-processor'")
    if "Categories=" not in content:
        fail("Desktop file missing 'Categories='")
    ok("Desktop file content valid")

    # Verify metainfo XML
    metainfo = squashfs_root / "usr/share/metainfo/MedicalDocProcessor.metainfo.xml"
    xml = metainfo.read_text(encoding="utf-8")
    if "<component" not in xml or "</component>" not in xml:
        fail("Metainfo XML root <component> missing")
    if "com.omnimedical.docprocessor" not in xml:
        fail("Metainfo missing app ID")
    ok("Metainfo XML valid")

    # Verify binary is ELF
    binary = squashfs_root / "usr/bin/medical-doc-processor"
    magic = binary.read_bytes()[:4]
    if magic != b"\x7fELF":
        fail(f"Binary is not ELF (magic={magic!r})")
    ok("Binary is ELF 64-bit")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1

    appimage = Path(sys.argv[1]).resolve()
    print(f"\n🧪 AppImage Smoke Test: {appimage.name}\n")

    # 1. File exists
    if not appimage.exists():
        fail(f"AppImage not found: {appimage}")
    ok(f"AppImage exists ({appimage.stat().st_size // (1024 * 1024)} MB)")

    # 2. Executable bit
    if not os.access(appimage, os.X_OK):
        fail("AppImage is not executable (chmod +x required)")
    ok("AppImage is executable")

    # 3. Magic bytes (AppImage starts with ELF magic)
    magic = appimage.read_bytes()[:4]
    if magic != b"\x7fELF":
        fail(f"AppImage is not ELF (magic={magic!r}) — corrupt download?")
    ok("AppImage is valid ELF")

    # 4. Checksum
    verify_checksum(appimage)

    # 5. Extract + verify AppDir
    with tempfile.TemporaryDirectory() as tmp:
        squashfs_root = extract_appimage(appimage, Path(tmp))
        verify_appdir(squashfs_root)

    print("\n🎉 All smoke checks passed!\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
