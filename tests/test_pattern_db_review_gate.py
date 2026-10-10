"""Regression tests for explicit human review before legacy PatternDB training."""

import numpy as np

from packages.learning.pattern_db import PatternDB


def test_training_samples_require_explicit_confirmation(tmp_path):
    db = PatternDB(str(tmp_path / "patterns.sqlite3"))
    image = np.full((16, 16), 127, dtype=np.uint8)

    pattern_id = db.save_pattern(
        image=image,
        predicted="Chats",
        corrected="Chats",
        language="en",
        confidence=0.99,
        writer_id="fixture",
    )

    # Saving a correction or accumulating usage is not human approval.
    assert db.get_training_samples(writer_id="fixture", min_usage=1) == []

    assert db.confirm_pattern(pattern_id) is True
    samples = db.get_training_samples(writer_id="fixture", min_usage=1)
    assert len(samples) == 1
    assert samples[0]["label"] == "Chats"

    # A later correction to the same visual pattern invalidates prior approval.
    db.save_pattern(
        image=image,
        predicted="Chats",
        corrected="Channels",
        language="en",
        confidence=0.98,
        writer_id="fixture",
    )
    assert db.get_training_samples(writer_id="fixture", min_usage=1) == []
    assert db.confirm_pattern(pattern_id) is True

    assert db.reject_pattern(pattern_id) is True
    assert db.get_training_samples(writer_id="fixture", min_usage=1) == []


def test_unknown_pattern_cannot_be_confirmed_or_rejected(tmp_path):
    db = PatternDB(str(tmp_path / "patterns.sqlite3"))

    assert db.confirm_pattern(999999) is False
    assert db.reject_pattern(999999) is False
    assert db.confirm_pattern(0) is False
    assert db.reject_pattern(-1) is False
