"""Build training datasets from teacher annotations.

Two export flavours, both directly usable downstream:

1. **OCR recognition pairs** - JSONL in the exact schema already used by
   ``training-data/corrections/handwriting_gt.jsonl`` (see
   ``training-data/README.md``), loadable with
   ``datasets.load_dataset("json", data_files=...)``.
2. **Layout detection labels** - YOLO-format ``labels/*.txt`` for training
   document segmentation models (YOLO-Doc / LayoutLM pretraining crops).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Union

from .models import CropRecord, PageAnnotation

# block_type -> YOLO class id (document layout taxonomy)
BLOCK_TYPE_TO_CLASS = {
    "paragraph": 0,
    "text": 0,
    "heading": 1,
    "table": 2,
    "picture": 3,
    "image": 3,
    "chart": 4,
    "separator": 5,
}
YOLO_CLASS_NAMES = ["paragraph", "heading", "table", "picture", "chart", "separator"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def crop_records_to_pairs(
    records: Iterable[CropRecord],
    source_file: str = "",
    language: str = "unknown",
) -> list[dict]:
    """Convert crop manifests into recognition-training JSONL dicts.

    The produced dicts carry the repo-contract fields plus teacher extras.
    """
    out: list[dict] = []
    now = _now_iso()
    for rec in records:
        out.append(
            {
                "ocr_text": rec.text,  # teacher output = initial hypothesis
                "corrected_text": rec.text,  # teacher-reviewed export: treated as ground truth
                "language": language if language != "unknown" else _guess(rec.text),
                "source_file": source_file or rec.source_image,
                "page_num": rec.page_index + 1,
                "confidence": round(rec.confidence, 4),
                "created_at": now,
                # teacher-specific extras (additive, contract stays compatible)
                "level": rec.level.value,
                "bbox": rec.bbox.to_list(),
                "crop_path": rec.crop_path,
                "source_format": rec.source_format.value,
            }
        )
    return out


def _guess(text: str) -> str:
    from .alignment import guess_language

    return guess_language(text)


def write_ocr_jsonl(
    rows: Iterable[Union[dict, CropRecord, "object"]],
    out_path: Union[str, Path],
    source_file: str = "",
    language: str = "unknown",
) -> int:
    """Write recognition JSONL; accepts dicts, CropRecords or CorrectionPairs.

    Returns the number of records written.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            if isinstance(row, dict):
                record = row
            elif isinstance(row, CropRecord):
                record = crop_records_to_pairs([row], source_file=source_file, language=language)[0]
            else:  # CorrectionPair duck-typing (avoids import cycle)
                record = {
                    "ocr_text": row.ocr_text,
                    "corrected_text": row.corrected_text,
                    "language": row.language,
                    "source_file": row.source_file,
                    "page_num": row.page_num,
                    "confidence": row.confidence,
                    "created_at": row.created_at or _now_iso(),
                    "level": row.level,
                    "bbox": row.bbox,
                    "cer": row.cer,
                    "source_format": row.source_format,
                }
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def build_layout_yolo(
    annotation: PageAnnotation,
    out_dir: Union[str, Path],
    image_path: Union[str, Path, None] = None,
    level: str = "block",
    class_map: Optional[dict[str, int]] = None,
) -> Optional[Path]:
    """Export layout boxes in YOLO format (normalised ``cls cx cy w h``).

    Args:
        annotation: parsed teacher page.
        out_dir: root that receives ``images/`` (optional symlink/copy is NOT
            done - pass ``image_path`` to record it in ``train.txt``) and
            ``labels/<stem>.txt``.
        image_path: original page image; its relative path is appended to
            ``train.txt`` so the folder is a ready YOLO dataset entry.
        level: ``block`` uses TextBlock boxes; ``line`` uses TextLine boxes
            (all lines get class 0).
        class_map: override for block_type -> class id.

    Returns:
        Path of the written label file, or ``None`` when there was nothing
        to export.
    """
    out_dir = Path(out_dir)
    labels_dir = out_dir / "labels"
    labels_dir.mkdir(parents=True, exist_ok=True)

    cmap = class_map or BLOCK_TYPE_TO_CLASS
    entries: list[tuple[int, int, int, int, int]] = []  # (cls, cx, cy, w, h) pixels

    if level == "block":
        for block in annotation.blocks:
            cls = cmap.get(block.block_type.lower(), 0)
            b = block.bbox
            if b.w > 0 and b.h > 0:
                entries.append((cls, b.x + b.w // 2, b.y + b.h // 2, b.w, b.h))
    elif level == "line":
        for line in annotation.lines:
            b = line.bbox
            if b.w > 0 and b.h > 0:
                entries.append((0, b.x + b.w // 2, b.y + b.h // 2, b.w, b.h))
    else:
        raise ValueError("level must be 'block' or 'line'")

    if not entries or annotation.width <= 0 or annotation.height <= 0:
        return None

    stem = Path(annotation.image_filename).stem or "page"
    label_path = labels_dir / f"{stem}.txt"
    lines_out: list[str] = []
    for cls, cx, cy, w, h in entries:
        ncx = min(1.0, max(0.0, cx / annotation.width))
        ncy = min(1.0, max(0.0, cy / annotation.height))
        nw = min(1.0, max(0.0, w / annotation.width))
        nh = min(1.0, max(0.0, h / annotation.height))
        lines_out.append(f"{cls} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}")

    label_path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")

    if image_path is not None:
        train_txt = out_dir / "train.txt"
        with train_txt.open("a", encoding="utf-8") as fh:
            fh.write(f"{Path(image_path).resolve()}\n")

    return label_path


def write_dataset_card(out_dir: Union[str, Path], n_records: int, source_note: str = "") -> Path:
    """Minimal HuggingFace-style dataset card next to the JSONL export."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    card = out_dir / "DATASET_CARD.md"
    card.write_text(
        "# Teacher OCR Dataset\n\n"
        f"- Records: {n_records}\n"
        f"- Generated: {_now_iso()}\n"
        f"- Origin: ABBYY FineReader reviewed XML exports (teacher)\n"
        f"- Note: {source_note or 'n/a'}\n\n"
        "Load with:\n\n"
        "```python\n"
        "from datasets import load_dataset\n"
        "ds = load_dataset('json', data_files='data.jsonl', split='train')\n"
        "```\n",
        encoding="utf-8",
    )
    return card
