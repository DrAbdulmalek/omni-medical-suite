"""F-13: _provenance_row must score normalize_v1(ref) vs normalize_v1(hyp)."""
from __future__ import annotations

from pathlib import Path

import pytest

from packages.evaluation.golden_harness import _provenance_row


def _sample(tmp_path: Path, reference: str) -> dict:
    png = tmp_path / "tiny.png"
    png.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
        )
    )
    return {
        "id": "f13_synthetic",
        "category": "dosage_table",
        "reference": reference,
        "path": png,
    }


def _row(tmp_path: Path, reference: str, hyp: str) -> dict:
    return _provenance_row(
        _sample(tmp_path, reference),
        "tesseract_ara",
        {"text": hyp, "model": "test", "latency_ms": 1.0, "cloud": False},
    )


def test_provenance_cer_is_symmetric(tmp_path: Path) -> None:
    """Indic digits + Arabic comma in gold vs ASCII in hyp must not dominate CER."""
    ref = "٥٠٠ ملغ من الدواء، مرتين"
    hyp = "500 ملغ من الدواء, مرتين"
    row = _row(tmp_path, ref, hyp)
    assert row["cer"] < 0.05, row
    assert row["normalize_policy"]["symmetric"] is True


def test_provenance_exposes_raw_and_artifact_share(tmp_path: Path) -> None:
    ref = "٥٠٠ ملغ من الدواء، مرتين"
    hyp = "500 ملغ من الدواء, مرتين"
    row = _row(tmp_path, ref, hyp)
    assert "cer_raw" in row and "encoding_artifact_share" in row
    assert row["cer_raw"] > row["cer"]
    assert row["encoding_artifact_share"] == pytest.approx(
        row["cer_raw"] - row["cer"], abs=1e-6
    )


def test_real_recognition_errors_still_caught(tmp_path: Path) -> None:
    """F-13 must not hide a dropped word."""
    ref = "٥٠٠ ملغ من الدواء، مرتين يوميا"
    hyp = "500 ملغ من الدواء, مرتين"  # missing يوميا
    row = _row(tmp_path, ref, hyp)
    assert row["cer"] > 0.08, row
