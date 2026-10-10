"""Security regressions for server-owned pattern review state."""

import asyncio
import base64

import cv2
import numpy as np
import pytest
from fastapi import HTTPException

from app.routers.pattern_studio import (
    SnippetIn,
    _server_review_rows,
    confirm_snippet,
)
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
        asyncio.run(confirm_snippet(1, current_user=None, db=None))
    assert exc.value.status_code == 401
