"""Crop line/word snippets (قصاصات) from page images using teacher bounding boxes.

Each snippet is saved as PNG together with a JSONL manifest that links the
image file to its recognised text, box and confidence - exactly the
"(crop the lines/words + link them to the text)" stage of the teacher-student
pipeline.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Optional, Union

from .models import BBox, CropLevel, CropRecord, PageAnnotation

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover
    raise ImportError("Pillow is required for cropping: pip install Pillow") from exc


def crop_segments(
    annotation: PageAnnotation,
    image_path: Union[str, Path],
    out_dir: Union[str, Path],
    levels: Iterable[str] = ("line", "word"),
    padding: float = 0.10,
    min_size: int = 8,
    prefix: str = "",
) -> list[CropRecord]:
    """Crop every line/word of ``annotation`` from ``image_path``.

    Args:
        annotation: parsed teacher annotation for this page.
        image_path: the scanned page image the XML was produced from.
        out_dir: directory that receives ``<level>_NNN.png`` files plus
            ``manifest.jsonl``.
        levels: subset of ``{"line", "word"}``.
        padding: extra margin added around each box, as a fraction of the
            box height (clamped to the image bounds).
        min_size: snippets smaller than this on either axis are skipped.
        prefix: optional filename prefix (e.g. ``page001_``).

    Returns:
        The list of :class:`CropRecord` that were written. A
        ``manifest.jsonl`` file is written to ``out_dir`` as well.
    """
    wanted = {CropLevel(l) for l in levels}
    image_path = Path(image_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(image_path) as img:
        img_w, img_h = img.size
        rgb = img.convert("RGB") if img.mode not in ("RGB", "L") else img

        records: list[CropRecord] = []
        counters = {"line": 0, "word": 0}

        def do_crop(level: CropLevel, text: str, bbox: BBox, confidence: float, idx: int) -> None:
            pad = int(round(padding * max(1, bbox.h)))
            box = BBox(
                x=bbox.x - pad,
                y=bbox.y - pad,
                w=bbox.w + 2 * pad,
                h=bbox.h + 2 * pad,
            ).clamp_to(img_w, img_h)
            if box.w < min_size or box.h < min_size:
                return
            snippet = rgb.crop((box.x, box.y, box.x1, box.y1))
            name = f"{prefix}{level.value}_{idx:04d}.png"
            snippet.save(out_dir / name)
            records.append(
                CropRecord(
                    crop_path=str((out_dir / name).resolve()),
                    level=level,
                    text=text,
                    bbox=box,
                    confidence=confidence,
                    source_image=str(image_path.resolve()),
                    page_index=0,
                    source_format=annotation.source_format,
                )
            )

        for line in annotation.lines:
            if CropLevel.LINE in wanted and line.text.strip():
                do_crop(CropLevel.LINE, line.text, line.bbox, line.confidence, counters["line"])
                counters["line"] += 1
            if CropLevel.WORD in wanted:
                for word in line.words:
                    if word.text.strip():
                        do_crop(CropLevel.WORD, word.text, word.bbox, word.confidence, counters["word"])
                        counters["word"] += 1

    manifest = out_dir / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec.to_jsonl_dict(), ensure_ascii=False) + "\n")
    return records


def load_manifest(path: Union[str, Path]) -> list[dict]:
    """Read back a ``manifest.jsonl`` written by :func:`crop_segments`."""
    out: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def crop_single_box(
    image_path: Union[str, Path],
    bbox: BBox,
    out_path: Union[str, Path],
    padding: float = 0.10,
    min_size: int = 8,
) -> Optional[tuple[int, int, int, int]]:
    """Crop one arbitrary box (useful for review UIs); returns the applied box."""
    image_path, out_path = Path(image_path), Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_path) as img:
        img_w, img_h = img.size
        pad = int(round(padding * max(1, bbox.h)))
        box = BBox(bbox.x - pad, bbox.y - pad, bbox.w + 2 * pad, bbox.h + 2 * pad).clamp_to(img_w, img_h)
        if box.w < min_size or box.h < min_size:
            return None
        snippet = img.convert("RGB") if img.mode not in ("RGB", "L") else img
        snippet.crop((box.x, box.y, box.x1, box.y1)).save(out_path)
        return (box.x, box.y, box.w, box.h)
