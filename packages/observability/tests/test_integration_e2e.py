"""End-to-end test: instrument scanner_fixer, run a real pipeline,
then run the analyzer and verify stats were collected."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import cv2
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_OBS_SRC = _REPO_ROOT / "packages" / "observability" / "src"
_SCANNER_SRC = _REPO_ROOT / "packages" / "scanner_fixer" / "src"
for p in (str(_OBS_SRC), str(_SCANNER_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from observability import configure_logging, reset_session_id  # noqa: E402
from observability.integration import instrument_scanner_fixer  # noqa: E402


def _make_synthetic_image(path: Path) -> None:
    img = np.full((400, 600, 3), 245, dtype=np.uint8)
    for y in range(100, 320, 40):
        cv2.rectangle(img, (100, y), (500, y + 18), (30, 30, 30), -1)
    cv2.imwrite(str(path), img)


def test_instrumented_pipeline_emits_events(tmp_path):
    log_dir = tmp_path / "logs"
    # Use DEBUG level so start events are captured
    configure_logging(log_dir=log_dir, reset=True, console=False, level=logging.DEBUG)
    reset_session_id()

    # Instrument AFTER configure
    instrument_scanner_fixer()

    from scanner_fixer import fix_scan  # noqa: E402

    src = tmp_path / "input.png"
    _make_synthetic_image(src)

    # Call the instrumented function
    _ = fix_scan(str(src))

    # Verify omni.jsonl was written and contains our events
    jsonl = log_dir / "omni.jsonl"
    assert jsonl.exists()
    lines = [json.loads(l) for l in jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    events = [l["event"] for l in lines]
    assert "fix_scan.start" in events
    assert "fix_scan.success" in events
    assert any(l.get("duration_ms") is not None for l in lines if l["event"] == "fix_scan.success")


def test_analyzer_collects_instrumented_events(tmp_path):
    log_dir = tmp_path / "logs"
    configure_logging(log_dir=log_dir, reset=True, console=False, level=logging.DEBUG)
    reset_session_id()
    instrument_scanner_fixer()

    from scanner_fixer import auto_crop  # noqa: E402

    src = tmp_path / "input.png"
    _make_synthetic_image(src)
    img = cv2.imread(str(src))
    _ = auto_crop(img)

    # Run the analyzer
    out_dir = tmp_path / "reports"
    analyzer = _REPO_ROOT / "scripts" / "llm_log_analyzer.py"
    # Set cwd to repo root so relative paths in the analyzer resolve
    result = subprocess.run(
        [sys.executable, str(analyzer),
         "--log-dir", str(log_dir),
         "--out-dir", str(out_dir)],
        capture_output=True, text=True, timeout=30,
        cwd=str(_REPO_ROOT),
    )
    assert result.returncode == 0, f"analyzer failed: {result.stderr}\n{result.stdout}"

    stats_path = out_dir / "stats.json"
    assert stats_path.exists()
    stats = json.loads(stats_path.read_text())
    assert stats["total_events"] > 0
    assert "auto_crop.start" in stats["by_event"]
    assert "auto_crop.success" in stats["by_event"]
    assert "preprocess" in stats["by_category"]

    # Check Markdown summary
    md_path = out_dir / "summary.md"
    assert md_path.exists()
    md = md_path.read_text()
    assert "Log Review Report" in md
    assert "preprocess" in md
