"""Command-line interface for the ABBYY teacher pipeline.

Usage (from the repository root):

    python -m tools.abbyy_teacher parse   --xml export.xml --json summary.json
    python -m tools.abbyy_teacher crop    --xml export.xml --image page.png --out-dir crops/
    python -m tools.abbyy_teacher align   --ocr-text ocr.txt --truth-text truth.txt --out pairs.jsonl
    python -m tools.abbyy_teacher align   --xml export.xml --truth-text truth.txt --out pairs.jsonl
    python -m tools.abbyy_teacher build   --xml export.xml --image page.png --out-dir dataset/
    python -m tools.abbyy_teacher cascade --xml export.xml
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .alignment import build_correction_pair, line_pairs_from_trusted_text, pairs_to_jsonl
from .cascade import CascadeRouter, CascadeThresholds
from .cropping import crop_segments
from .dataset_builder import build_layout_yolo, crop_records_to_pairs, write_ocr_jsonl
from .models import CorrectionPair
from .xml_parsing import parse_abbyy_xml


def _load_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _write_jsonl(lines: list[str], out: str) -> int:
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def cmd_parse(args: argparse.Namespace) -> int:
    annotation = parse_abbyy_xml(args.xml)
    payload = annotation.summary()
    payload["full_text"] = annotation.full_text()
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def cmd_crop(args: argparse.Namespace) -> int:
    annotation = parse_abbyy_xml(args.xml)
    records = crop_segments(
        annotation,
        image_path=args.image,
        out_dir=args.out_dir,
        levels=tuple(args.levels.split(",")),
        padding=args.padding,
        prefix=args.prefix,
    )
    print(f"cropped {len(records)} snippets -> {args.out_dir}/manifest.jsonl")
    return 0


def cmd_align(args: argparse.Namespace) -> int:
    truth = _load_text(args.truth_text)
    pairs: list[CorrectionPair]
    if args.xml:
        annotation = parse_abbyy_xml(args.xml)
        pairs = line_pairs_from_trusted_text(annotation, truth, source_file=args.source_file)
    else:
        ocr = _load_text(args.ocr_text)
        # Whole-document pair (caller supplies already segmented texts).
        pairs = [
            build_correction_pair(
                ocr,
                truth,
                source_file=args.source_file,
                page_num=args.page_num,
                level="document",
            )
        ]
    # Drop no-op pairs where OCR already equals ground truth is WRONG for
    # recognition training (equal pairs are valid 'equal' examples), so we
    # keep them; only fully-empty pairs are dropped.
    pairs = [p for p in pairs if p.ocr_text or p.corrected_text]
    n = _write_jsonl(pairs_to_jsonl(pairs), args.out)
    print(f"wrote {n} correction pairs -> {args.out}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    """Full pipeline: parse -> crop -> recognition JSONL + YOLO layout labels."""
    annotation = parse_abbyy_xml(args.xml)
    out_dir = Path(args.out_dir)
    crops_dir = out_dir / "crops"

    records = []
    if args.image:
        records = crop_segments(
            annotation,
            image_path=args.image,
            out_dir=crops_dir,
            levels=("line", "word"),
            padding=args.padding,
        )

    rows = crop_records_to_pairs(records, source_file=args.source_file or Path(args.xml).name)
    n_jsonl = write_ocr_jsonl(rows, out_dir / "data.jsonl")

    label_block = build_layout_yolo(annotation, out_dir / "layout", image_path=args.image, level="block")
    label_line = build_layout_yolo(annotation, out_dir / "layout", image_path=args.image, level="line")

    from .dataset_builder import write_dataset_card

    write_dataset_card(out_dir, n_jsonl, source_note=f"teacher format: {annotation.source_format.value}")

    print(json.dumps({
        "out_dir": str(out_dir),
        "records_jsonl": n_jsonl,
        "crops": len(records),
        "yolo_block_labels": str(label_block) if label_block else None,
        "yolo_line_labels": str(label_line) if label_line else None,
        "dataset_card": str(out_dir / "DATASET_CARD.md"),
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_cascade(args: argparse.Namespace) -> int:
    annotation = parse_abbyy_xml(args.xml)
    router = CascadeRouter(
        CascadeThresholds(accept=args.accept, escalate=args.escalate)
    )
    report = router.route_page(annotation)
    payload = report.to_dict()
    payload["page"] = annotation.summary()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m tools.abbyy_teacher",
        description="ABBYY FineReader teacher pipeline: XML -> crops -> datasets -> cascade routing",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("parse", help="parse an ABBYY/ALTO/PAGE XML export and print a summary")
    p.add_argument("--xml", required=True)
    p.add_argument("--json", help="also write the summary to this file")
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("crop", help="crop line/word snippets from the page image")
    p.add_argument("--xml", required=True)
    p.add_argument("--image", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--levels", default="line,word", help="comma list: line,word")
    p.add_argument("--padding", type=float, default=0.10)
    p.add_argument("--prefix", default="")
    p.set_defaults(func=cmd_crop)

    p = sub.add_parser("align", help="align OCR output with trusted text -> correction pairs JSONL")
    p.add_argument("--xml", help="teacher XML (line-level alignment against --truth-text)")
    p.add_argument("--ocr-text", help="plain OCR text file (document-level pair)")
    p.add_argument("--truth-text", required=True)
    p.add_argument("--out", required=True, help="output JSONL path")
    p.add_argument("--source-file", default="")
    p.add_argument("--page-num", type=int, default=1)
    p.set_defaults(func=cmd_align)

    p = sub.add_parser("build", help="full pipeline: crops + recognition JSONL + YOLO layout")
    p.add_argument("--xml", required=True)
    p.add_argument("--image", help="page image (optional; skips crops when absent)")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--padding", type=float, default=0.10)
    p.add_argument("--source-file", default="")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("cascade", help="print hybrid routing decisions for a teacher page")
    p.add_argument("--xml", required=True)
    p.add_argument("--accept", type=float, default=0.92)
    p.add_argument("--escalate", type=float, default=0.60)
    p.set_defaults(func=cmd_cascade)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
