"""Smoke test: scanner_fixer pipeline runs end-to-end on a synthetic image."""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "packages" / "scanner_fixer" / "src"))

from scanner_fixer import fix_scanned_image, batch_fix_folder  # noqa: E402


def _make_synthetic_image(path: Path) -> None:
    """Create a noisy white image with some black text-like patches."""
    img = np.full((400, 600, 3), 245, dtype=np.uint8)
    # Add a few dark rectangles (pseudo-text)
    for y in range(80, 320, 40):
        for x in range(80, 520, 30):
            h, w = 18, 12
            cv2.rectangle(img, (x, y), (x + w, y + h), (30, 30, 30), thickness=-1)
    # Add some noise
    noise = np.random.normal(0, 12, img.shape).astype(np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)


def main() -> int:
    tmp_dir = Path("/tmp/scanner_fixer_smoke")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    src = tmp_dir / "input.png"
    _make_synthetic_image(src)

    fixed, meta = fix_scanned_image(src, output_path=tmp_dir / "output.png")
    assert fixed.ndim == 3 and fixed.shape[2] == 3, f"Bad shape: {fixed.shape}"
    assert meta["status"] == "success", meta
    print(f"✅ single-image OK — final shape {fixed.shape}")

    # Batch
    results = batch_fix_folder(tmp_dir, output_dir=tmp_dir / "_fixed")
    assert len(results) >= 1, "Batch returned empty"
    print(f"✅ batch OK — {len(results)} file(s) processed")
    for r in results:
        print("   ", r.get("file"), r.get("status"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
