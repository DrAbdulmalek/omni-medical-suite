from pathlib import Path

import pytest

from app.core.file_security import resolve_workspace_path, validate_image_path, workspace_root


def test_relative_path_is_resolved_inside_workspace(monkeypatch, tmp_path):
    monkeypatch.setenv("OMNI_WORKSPACE_DIR", str(tmp_path))
    resolved = resolve_workspace_path("incoming/image.png")
    assert resolved == (tmp_path / "incoming/image.png").resolve()


def test_absolute_path_outside_workspace_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("OMNI_WORKSPACE_DIR", str(tmp_path / "workspace"))
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(PermissionError):
        resolve_workspace_path(outside)


def test_traversal_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("OMNI_WORKSPACE_DIR", str(tmp_path / "workspace"))

    with pytest.raises(PermissionError):
        resolve_workspace_path("../secret.txt")


def test_symlink_image_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("OMNI_WORKSPACE_DIR", str(tmp_path / "workspace"))
    root = workspace_root()
    source = tmp_path / "source.png"
    source.write_bytes(b"not-a-real-image")
    link = root / "link.png"
    link.symlink_to(source)

    with pytest.raises(ValueError):
        validate_image_path(link)


def test_non_image_extension_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("OMNI_WORKSPACE_DIR", str(tmp_path))
    path = Path(tmp_path) / "document.pdf"
    path.write_bytes(b"pdf")

    with pytest.raises(ValueError):
        validate_image_path(path)
