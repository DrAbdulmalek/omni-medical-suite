from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_installer_validates_archive_member_types_before_extracting():
    text = (ROOT / "scripts/setup_dictionaries.sh").read_text(encoding="utf-8")
    assert "tarfile.open" in text
    assert "member.issym()" in text
    assert "member.islnk()" in text
    assert "member.isdev()" in text
    assert "member.isfifo()" in text
    assert "member.isfile() and (member.mode & 0o111)" in text


def test_installer_rejects_traversal_and_duplicate_members():
    text = (ROOT / "scripts/setup_dictionaries.sh").read_text(encoding="utf-8")
    assert 'path.is_absolute() or ".." in path.parts' in text
    assert "if name in seen:" in text


def test_installer_extracts_only_after_validation():
    text = (ROOT / "scripts/setup_dictionaries.sh").read_text(encoding="utf-8")
    assert text.index('python3 - "$TMP_ARCHIVE"') < text.index("tar --no-same-owner")
