"""Security regression tests for the Telegram OCR API router."""
import os

import pytest
from fastapi.params import Depends

from app.routers.telegram_ocr import _confined_inbox_path, router, TrainingSyncBody
from app.core.security import get_current_user


def test_telegram_ocr_router_requires_authenticated_user():
    assert any(
        isinstance(dependency, Depends) and dependency.dependency is get_current_user
        for dependency in router.dependencies
    )


def test_confined_path_accepts_regular_file_inside_inbox(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    source = inbox / "scan.png"
    source.write_bytes(b"test")
    assert _confined_inbox_path(str(source), str(inbox)) == str(source.resolve())


def test_confined_path_rejects_sibling_prefix_path(tmp_path):
    inbox = tmp_path / "inbox"
    sibling = tmp_path / "inbox-escape"
    inbox.mkdir()
    sibling.mkdir()
    source = sibling / "secret.png"
    source.write_bytes(b"test")
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _confined_inbox_path(str(source), str(inbox))
    assert exc.value.status_code == 400


def test_confined_path_rejects_path_outside_inbox(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    source = tmp_path / "outside.png"
    source.write_bytes(b"test")
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _confined_inbox_path(str(source), str(inbox))
    assert exc.value.status_code == 400


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_confined_path_rejects_symlink_escape(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"test")
    link = inbox / "link.png"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation not permitted")
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        _confined_inbox_path(str(link), str(inbox))
    assert exc.value.status_code == 400



def test_training_sync_requires_explicit_batch_confirmation_by_default():
    assert TrainingSyncBody().confirm_reviewed_batch is False
    assert TrainingSyncBody(confirm_reviewed_batch=True).confirm_reviewed_batch is True
