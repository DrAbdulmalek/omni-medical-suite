"""TASK 012 regression guard — ArabicWordSegmenter must never return 0 words.

Failure proven on GT588 proxy (PHASE 2): word agreement was 1/23 because
gap_threshold = line_height * gap_factor * 255 classified almost every
ink column as a gap. This test renders the GT588 lines with a measured
ink band and asserts every line yields >= 1 word.

Skips automatically when no Arabic font exists (e.g. bare CI runners).
"""
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load_word_segmenter():
    """Load ArabicWordSegmenter directly from hf-space path.

    Deliberately NOT via `packages.vision...` import: inserting hf-space
    into sys.path shadows the root `packages` namespace (hf-space/packages
    copy lacks PHASE-1 TASK-004 router edits) and breaks unrelated tests.
    word_segmenter.py has no intra-repo imports -> safe to load standalone.
    """
    path = REPO / "hf-space" / "packages" / "vision" / "htr" / "word_segmenter.py"
    spec = importlib.util.spec_from_file_location("gt588_word_segmenter", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.ArabicWordSegmenter

GT_LINES = [
    "جدول المحتويات",
    "١- أذيات المشاش واضطرابات النمو",
    "٢- الخرع Rickets",
    "٣- التهاب المفاصل القيحي الناكس",
    "٦- انزلاق مثاش رأس الفخذ",
    "٢١- عسرة تصنع الورك التطورية",
]


def _arabic_font():
    try:
        out = subprocess.run(
            ["fc-list", ":lang=ar", "--format=%{file}\n"],
            capture_output=True, text=True, timeout=20,
        )
        fonts = [f for f in out.stdout.splitlines() if f.strip()]
        for f in fonts:
            if "amiri" in f.lower() and "italic" not in f.lower() and "quran" not in f.lower():
                return f
        return fonts[0] if fonts else None
    except Exception:
        return None


@pytest.mark.skipif(shutil.which("fc-list") is None, reason="no fontconfig")
def test_gt588_lines_yield_words():
    font_path = _arabic_font()
    if not font_path:
        pytest.skip("no Arabic font available")

    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    import arabic_reshaper
    from bidi.algorithm import get_display

    ArabicWordSegmenter = _load_word_segmenter()

    font = ImageFont.truetype(font_path, 44)
    width, line_h, margin = 1400, 72, 60
    page = Image.new("RGB", (width, margin * 2 + line_h * len(GT_LINES)), "white")
    draw = ImageDraw.Draw(page)
    bands = []
    y = margin
    for ln in GT_LINES:
        draw.text((margin, y), get_display(arabic_reshaper.reshape(ln)), font=font, fill="black")
        bands.append((y, y + line_h))
        y += line_h

    g = np.array(page.convert("L"))
    seg = ArabicWordSegmenter()
    words_per_line = []
    for (y0, y1) in bands:
        region = g[y0:y1, :]
        rows = np.where((region < 128).any(axis=1))[0]
        assert len(rows), "rendered line must contain ink"
        band = (int(y0 + rows[0]), int(y0 + rows[-1] + 1))
        crop = page.crop((0, band[0], page.width, band[1]))
        n = len(seg.segment(crop))
        words_per_line.append(n)

    assert all(n >= 1 for n in words_per_line), (
        f"regression: 0 words on some line -> {words_per_line}"
    )
    assert sum(words_per_line) >= len(GT_LINES) * 2, (
        f"too few words overall -> {words_per_line}"
    )
