#!/usr/bin/env python3
"""
batch_process.py
CLI wrapper for the scanner-fixer BatchProcessor.

Usage:
    python scripts/batch_process.py -i ./scans -o ./output -w 4
    python scripts/batch_process.py -i ./scans --dry-run --format json
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

# Ensure the package is importable when running from the repo root
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scanner_fixer.batch_pipeline import BatchConfig, BatchProcessor  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog="batch_process",
        description=(
            "Batch-process scanned document images through the scanner-fixer "
            "pipeline. Produces manifests, per-image reports, previews, "
            "quarantine for failures, and a batch summary."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s -i ./scans -o ./output\n"
            "  %(prog)s -i ./scans -o ./output -w 8 --no-previews\n"
            "  %(prog)s -i ./scans --dry-run --format json\n"
        ),
    )

    # Required / positional
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input directory containing scanned images (required).",
    )
    parser.add_argument(
        "--output", "-o",
        default="./output",
        help="Output directory for processed images and reports (default: ./output).",
    )
    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=os.cpu_count() or 1,
        help="Number of parallel worker processes (default: CPU count).",
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Output format for the manifest file (default: csv).",
    )
    parser.add_argument(
        "--no-previews",
        action="store_true",
        default=False,
        help="Skip before/after preview PNG generation.",
    )
    parser.add_argument(
        "--quarantine-threshold",
        type=float,
        default=50.0,
        metavar="MB",
        help="Maximum file size in MB to process; larger files are quarantined (default: 50).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Generate manifest only without processing any images.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable verbose (DEBUG-level) logging.",
    )

    # Pipeline control flags
    pipeline_group = parser.add_argument_group("Pipeline control")
    pipeline_group.add_argument(
        "--no-crop",
        action="store_true",
        default=False,
        help="Disable auto-crop step.",
    )
    pipeline_group.add_argument(
        "--rotate",
        action="store_true",
        default=False,
        help="Enable 180-degree rotation detection (off by default).",
    )
    pipeline_group.add_argument(
        "--no-deskew",
        action="store_true",
        default=False,
        help="Disable deskew step.",
    )
    pipeline_group.add_argument(
        "--no-enhance",
        action="store_true",
        default=False,
        help="Disable OCR enhancement step.",
    )
    pipeline_group.add_argument(
        "--binarize",
        action="store_true",
        default=False,
        help="Convert output to black-and-white (good for text-only pages).",
    )
    pipeline_group.add_argument(
        "--target-dpi",
        type=int,
        default=300,
        help="Target DPI for OCR enhancement (default: 300).",
    )
    pipeline_group.add_argument(
        "--deskew-method",
        choices=["hough", "projection"],
        default="hough",
        help="Deskew algorithm to use (default: hough).",
    )
    pipeline_group.add_argument(
        "--crop-padding",
        type=int,
        default=10,
        help="Padding in pixels around auto-cropped content (default: 10).",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI script."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Logging setup
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    # Validate input directory
    if not os.path.isdir(args.input):
        logger.error("Input directory does not exist: %s", args.input)
        return 1

    # Build config
    config = BatchConfig(
        workers=args.workers,
        dry_run=args.dry_run,
        quarantine_threshold_mb=args.quarantine_threshold,
        generate_previews=not args.no_previews,
        manifest_format=args.format,
        do_crop=not args.no_crop,
        do_rotate=args.rotate,
        do_deskew=not args.no_deskew,
        do_enhance=not args.no_enhance,
        binarize=args.binarize,
        target_dpi=args.target_dpi,
        deskew_method=args.deskew_method,
        crop_padding=args.crop_padding,
    )

    logger.info("BatchProcessor starting — input: %s, output: %s, workers: %d",
                args.input, args.output, config.workers)
    if config.dry_run:
        logger.info("DRY-RUN MODE: no images will be modified.")

    try:
        processor = BatchProcessor(
            input_dir=args.input,
            output_dir=args.output,
            config=config,
        )
        summary = processor.run()
    except Exception:
        logger.exception("Batch processing failed")
        return 1

    # Print summary to stdout
    print("\n=== Batch Summary ===")
    print(f"  Total images : {summary['total_images']}")
    print(f"  OK           : {summary['ok']}")
    print(f"  Failed       : {summary['failed']}")
    print(f"  Quarantined  : {summary['quarantined']}")
    print(f"  Total time   : {summary['total_time_seconds']:.2f}s")
    if summary['total_images'] > 0:
        print(f"  Avg per image: {summary['average_time_per_image_ms']:.1f}ms")
    print(f"  Output dir   : {summary['output_directory']}")

    if summary["failed"] > 0 or summary["quarantined"] > 0:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())