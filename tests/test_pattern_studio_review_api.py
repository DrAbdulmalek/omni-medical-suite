"""Security regressions for server-owned pattern review state."""

import asyncio
import base64

import cv2
import numpy as np
import pytest
from fastapi import HTTPException

from app.routers import pattern_studio
from app.routers.pattern_studio import (
    ExportIn,
    SnippetIn,
    _require_reviewer,
    _server_review_rows,
    confirm_snippet,
    save_snippet,
)
from app.db.models.auth import User
from packages.learning.pattern_db import PatternDB
from packages.learning.snippet_dataset import normalize_record


def _png_b64(value: int) -> str:
    image = np.full((16, 16), value, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def test_client_supplied_confirmed_review_is_ignored_on_save():
    payload = {
        "kind": "word",
        "text": "هيموغلوبين",
        "language": "ar",
        "image_png_base64": _png_b64(120),
        "review": "confirmed",
    }

    request = SnippetIn.model_validate(payload)
    assert "review" not in request.model_dump()

    # The server explicitly initializes persisted records as open.
    record = normalize_record({**request.model_dump(), "review": "open"})
    assert record["review"] == "open"


def test_export_source_contains_only_server_confirmed_rows(tmp_path):
    db = PatternDB(str(tmp_path / "patterns.sqlite3"))
    image_open = np.full((16, 16), 90, dtype=np.uint8)
    image_confirmed = np.full((16, 16), 180, dtype=np.uint8)

    open_id = db.save_pattern(
        image=image_open,
        predicted="OCR",
        corrected="open sample",
        language="en",
        confidence=0.0,
        category="word",
        context={"kind": "word", "channel": "fixture"},
    )
    confirmed_id = db.save_pattern(
        image=image_confirmed,
        predicted="OCR",
        corrected="confirmed sample",
        language="en",
        confidence=0.0,
        category="word",
        context={"kind": "word", "channel": "fixture"},
    )
    assert db.confirm_pattern(confirmed_id) is True

    rows = _server_review_rows(db)
    assert len(rows) == 1
    assert rows[0]["text"] == "confirmed sample"
    assert rows[0]["review"] == "confirmed"
    assert rows[0]["text"] != "open sample"


def test_confirmation_route_rejects_unauthenticated_caller():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(confirm_snippet(1, current_user=None))
    assert exc.value.status_code == 401



def test_bulk_export_cannot_inject_client_confirmed_records(tmp_path, monkeypatch):
    db = PatternDB(str(tmp_path / "empty-patterns.sqlite3"))
    monkeypatch.setattr(pattern_studio, "PatternDB", lambda: db)
    forged = {
        "kind": "word",
        "text": "client-forged",
        "language": "en",
        "image_png_base64": _png_b64(70),
        "review": "confirmed",
    }
    body = ExportIn(records=[forged])
    reviewer = User(
        id=1,
        username="test-reviewer",
        email="reviewer@example.invalid",
        hashed_password="not-a-real-password",
        is_superuser=True,
    )

    result = asyncio.run(pattern_studio.export_dataset(body, current_user=reviewer))
    assert result["jsonl"] == ""
    assert result["summary"]["trainable"] == 0


def test_save_endpoint_persists_open_even_when_client_sends_confirmed(tmp_path, monkeypatch):
    db = PatternDB(str(tmp_path / "patterns.sqlite3"))
    monkeypatch.setattr(pattern_studio, "PatternDB", lambda: db)
    payload = {
        "kind": "word",
        "text": "sample",
        "language": "en",
        "image_png_base64": _png_b64(140),
        "review": "confirmed",
    }
    request = SnippetIn.model_validate(payload)
    user = User(
        id=2,
        username="sample-user",
        email="sample@example.invalid",
        hashed_password="not-a-real-password",
        is_superuser=False,
    )

    result = asyncio.run(save_snippet(request, current_user=user))
    assert result["review"] == "open"
    assert result["trainable"] is False
    row = db.execute_one("SELECT review, corrected_text FROM patterns WHERE id = ?", (result["id"],))
    assert row == {"review": "open", "corrected_text": "sample"}



def test_unauthenticated_client_cannot_submit_forged_confirmed_review():
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    def fake_db():
        yield None

    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = fake_db
    try:
        response = TestClient(app).post(
            "/api/pattern-studio/snippets",
            json={
                "kind": "word",
                "text": "forged",
                "language": "en",
                "image_png_base64": _png_b64(110),
                "review": "confirmed",
            },
        )
    finally:
        if previous is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous

    assert response.status_code == 401



def test_authenticated_non_superuser_cannot_confirm():
    user = User(
        id=3,
        username="ordinary-user",
        email="ordinary@example.invalid",
        hashed_password="not-a-real-password",
        is_superuser=False,
    )
    with pytest.raises(HTTPException) as exc:
        _require_reviewer(user)
    assert exc.value.status_code == 403
