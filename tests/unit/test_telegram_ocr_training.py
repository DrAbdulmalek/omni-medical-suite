"""Tests for Telegram OCR training stores and deterministic export."""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from src.ocr.pattern_store import PatternStore
from src.ocr.slice_store import SliceStore
from src.ocr.training_export import _split_for, export_all


def _sample_image() -> np.ndarray:
    image = np.zeros((80, 160, 3), dtype=np.uint8)
    cv2.putText(image, "OCR", (12, 52), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
    return image


def test_slice_store_clips_and_records_provenance(tmp_path: Path) -> None:
    store = SliceStore(tmp_path)
    record = store.add_slice(
        _sample_image(),
        [0, 0, 100, 70],
        "OCR",
        level="word",
        lang="en",
        source_meta={"channel": "@ortho_homs", "msg_id": 123},
    )
    assert record["image"].startswith("slices/")
    assert len(record["image_sha256"]) == 64
    assert store.count() == 1
    assert store.list_slices()[0]["source"]["channel"] == "@ortho_homs"


def test_slice_store_rejects_empty_annotation(tmp_path: Path) -> None:
    store = SliceStore(tmp_path)
    try:
        store.add_slice(_sample_image(), [0, 0, 20, 20], " ")
    except ValueError as exc:
        assert "text" in str(exc)
    else:
        raise AssertionError("empty annotation must be rejected")


def test_pattern_store_learns_and_matches(tmp_path: Path) -> None:
    image = _sample_image()
    store = PatternStore(tmp_path)
    record = store.add_pattern("OCR", image, level="word", script="en", source_ref="slices/demo")
    assert record["key"]
    assert store.count() == 1
    hits = store.match(image, top_k=1, min_score=0.99, script="en", level="word")
    assert hits and hits[0]["label"] == "OCR"
    assert hits[0]["score"] >= 0.99


def test_export_is_deterministic_and_complete(tmp_path: Path) -> None:
    store = SliceStore(tmp_path)
    for i, label in enumerate(("one", "two", "three")):
        store.add_slice(
            _sample_image(),
            [i * 10, 0, 60, 60],
            label,
            level="word",
            lang="en",
            source_meta={"source": "test"},
        )
    out = tmp_path / "export"
    summary = export_all(str(tmp_path), str(out))
    assert summary["slices"]["total"] == 3
    labels = [json.loads(line) for line in (out / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(labels) == 3
    assert {row["split"] for row in labels} <= {"train", "val", "test"}
    assert all((out / row["image"]).exists() for row in labels)
    assert _split_for("stable-id") == _split_for("stable-id")
