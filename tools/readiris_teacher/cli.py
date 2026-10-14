"""Command-line interface for the Readiris teacher pipeline.

Every command that ingests a Readiris export clears the license gate
(:func:`tools.readiris_teacher.licensing.require_license`): pass
``--i-own-license`` and set ``READIRIS_LICENSE_CONFIRMED=1``.

Usage (from the repository root):

    export READIRIS_LICENSE_CONFIRMED=1

    python -m tools.readiris_teacher parse   --export exports/page_01.txt --i-own-license
    python -m tools.readiris_teacher parse   --export exports/page_01.html --i-own-license --json summary.json
    python -m tools.readiris_teacher crop    --export exports/page_01.html --image page.png --out-dir crops/ --i-own-license
    python -m tools.readiris_teacher align   --export exports/page_01.txt --truth-text truth.txt --out pairs.jsonl --i-own-license
    python -m tools.readiris_teacher build   --export exports/page_01.html --image page.png --out-dir dataset/ --i-own-license
    python -m tools.readiris_teacher cascade --export exports/page_01.html --i-own-license
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .alignment import build_correction_pair, line_pairs_from_trusted_text, pairs_to_jsonl
from .cascade import CascadeRouter, CascadeThresholds
from .dataset_builder import build_layout_yolo, crop_records_to_pairs, lines_to_pairs, write_dataset_card, write_ocr_jsonl
from .export_parsing import parse_readiris_export, parse_readiris_export_all
from .licensing import LicenseGateError, require_license
from .models import CorrectionPair


def _load_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _write_jsonl(lines: list[str], out: str) -> int:
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)


def cmd_parse(args: argparse.Namespace) -> int:
    annotations = parse_readiris_export_all(args.export, rtf_codepage=args.rtf_codepage)
    payloads = []
    for annotation in annotations:
        payload = annotation.summary()
        payload["full_text"] = annotation.full_text()
        payloads.append(payload)
    text = json.dumps(payloads[0] if len(payloads) == 1 else payloads, ensure_ascii=False, indent=2)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


def cmd_crop(args: argparse.Namespace) -> int:
    from .cropping import crop_segments  # lazy: Pillow only needed here

    annotation = parse_readiris_export(args.export, rtf_codepage=args.rtf_codepage)
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
    annotation = parse_readiris_export(args.export, rtf_codepage=args.rtf_codepage)
    if not annotation.has_geometry:
        # Text-only export: document-level pair (caller supplies segmented text).
        pairs = [
            build_correction_pair(
                annotation.full_text(),
                truth,
                source_file=args.source_file or annotation.source_path,
                page_num=args.page_num,
                level="document",
                source_format=annotation.source_format.value,
                export_sha256=annotation.export_sha256,
            )
        ]
    else:
        pairs = line_pairs_from_trusted_text(annotation, truth, source_file=args.source_file)
    # Keep equal pairs (valid 'equal' examples for recognition training);
    # only fully-empty pairs are dropped.
    pairs = [p for p in pairs if p.ocr_text or p.corrected_text]
    n = _write_jsonl(pairs_to_jsonl(pairs), args.out)
    print(f"wrote {n} correction pairs -> {args.out}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    """Full pipeline: parse -> crop (when possible) -> JSONL + YOLO layout."""
    annotation = parse_readiris_export(args.export, rtf_codepage=args.rtf_codepage)
    out_dir = Path(args.out_dir)
    crops_dir = out_dir / "crops"

    records = []
    if args.image and annotation.has_geometry:
        from .cropping import crop_segments  # lazy: Pillow only needed here

        records = crop_segments(
            annotation,
            image_path=args.image,
            out_dir=crops_dir,
            levels=("line", "word"),
            padding=args.padding,
        )

    source_file = args.source_file or annotation.source_path
    if records:
        rows = crop_records_to_pairs(records, source_file=source_file)
    else:
        # Text-only export or no image: line-level JSONL without geometry.
        rows = lines_to_pairs(annotation, source_file=source_file)
    n_jsonl = write_ocr_jsonl(rows, out_dir / "data.jsonl")

    label_block = build_layout_yolo(annotation, out_dir / "layout", image_path=args.image, level="block")
    label_line = build_layout_yolo(annotation, out_dir / "layout", image_path=args.image, level="line")

    write_dataset_card(
        out_dir, n_jsonl,
        source_note=(
            f"teacher format: {annotation.source_format.value}"
            + ("" if label_block else "; no geometry in export -> YOLO layout skipped")
        ),
    )

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
    annotation = parse_readiris_export(args.export, rtf_codepage=args.rtf_codepage)
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
        prog="python -m tools.readiris_teacher",
        description=(
            "Readiris teacher pipeline: TXT/HTML/RTF exports -> crops -> datasets "
            "-> cascade routing (consumes exports of a locally licensed copy only)"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def _add_gate(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--i-own-license", action="store_true",
            help="declaration: I run a licensed or official-trial Readiris copy locally",
        )

    def _add_export(p: argparse.ArgumentParser) -> None:
        p.add_argument("--export", required=True, help="Readiris export file (.txt/.html/.rtf)")
        p.add_argument("--rtf-codepage", default="cp1256",
                       help="codepage for RTF \\'hh byte escapes (default: cp1256 Arabic Windows)")

    p = sub.add_parser("parse", help="parse a Readiris export and print a summary")
    _add_export(p)
    p.add_argument("--json", help="also write the summary to this file")
    _add_gate(p)
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("crop", help="crop line/word snippets from the page image (geometry needed)")
    _add_export(p)
    p.add_argument("--image", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--levels", default="line,word", help="comma list: line,word")
    p.add_argument("--padding", type=float, default=0.10)
    p.add_argument("--prefix", default="")
    _add_gate(p)
    p.set_defaults(func=cmd_crop)

    p = sub.add_parser("align", help="align Readiris output with trusted text -> correction pairs JSONL")
    _add_export(p)
    p.add_argument("--truth-text", required=True)
    p.add_argument("--out", required=True, help="output JSONL path")
    p.add_argument("--source-file", default="")
    p.add_argument("--page-num", type=int, default=1)
    _add_gate(p)
    p.set_defaults(func=cmd_align)

    p = sub.add_parser("build", help="full pipeline: crops (if geometry) + JSONL + YOLO layout (if geometry)")
    _add_export(p)
    p.add_argument("--image", help="page image (optional; text-only exports skip crops)")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--padding", type=float, default=0.10)
    p.add_argument("--source-file", default="")
    _add_gate(p)
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("cascade", help="print hybrid routing decisions for a teacher page")
    _add_export(p)
    p.add_argument("--accept", type=float, default=0.92)
    p.add_argument("--escalate", type=float, default=0.60)
    _add_gate(p)
    p.set_defaults(func=cmd_cascade)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        require_license(getattr(args, "i_own_license", False))
        return args.func(args)
    except LicenseGateError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - CLI boundary
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
