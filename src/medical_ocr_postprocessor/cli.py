"""
CLI interface for medical-ocr-postprocessor.
واجهة سطر الأوامر لمعالج ما بعد OCR الطبي.

Usage:
    medical-ocr-postprocess correct --input results.json --output corrected.json
    medical-ocr-postprocess batch --input-dir pages/ --output-dir output/
    medical-ocr-postprocess validate --text "مستند طبي" --lang ar
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from medical_ocr_postprocessor import __version__
from medical_ocr_postprocessor.batch import BatchConfig, BatchProcessor
from medical_ocr_postprocessor.core import PostProcessor

logger = logging.getLogger("medical-ocr-postprocessor")


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def _cmd_correct(args: argparse.Namespace) -> int:
    """Handle 'correct' subcommand — correct a single OCR result file."""
    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return 1

    processor = PostProcessor(
        confidence_threshold=args.confidence,
    )

    # Load optional custom dictionary
    if args.dictionary:
        dict_path = Path(args.dictionary)
        if dict_path.exists():
            count = processor.load_medical_terms_from_file(dict_path)
            logger.info(f"Loaded {count} medical terms from {dict_path}")
        else:
            logger.warning(f"Dictionary file not found: {dict_path}")

    # Read input
    try:
        raw = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse input JSON: {e}")
        return 1

    # Handle different input formats
    if isinstance(raw, list):
        words = [str(w) for w in raw]
        confidences = [0.5] * len(words)
    elif isinstance(raw, dict):
        words = raw.get("words", [])
        confidences = raw.get("confidences", [0.5] * len(words))
        if words and isinstance(words[0], dict):
            words = [w.get("text", str(w)) for w in words]
            confidences = [w.get("confidence", 0.5) for w in raw.get("words", [])]
    else:
        logger.error(f"Unsupported input format: {type(raw).__name__}")
        return 1

    # Process
    logger.info(f"Processing {len(words)} words from {input_path}")
    results = processor.batch_correct(words, confidences)

    # Build output
    corrected_words = [r.corrected for r in results]
    output_data = {
        "original_words": [r.original for r in results],
        "corrected_words": corrected_words,
        "corrections": [r.to_dict() for r in results],
        "summary": processor.get_stats(),
        "corrected_text": " ".join(corrected_words),
    }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Print summary
    stats = processor.get_stats()
    logger.info(f"Processed {stats['total_processed']} words")
    logger.info(f"Modified: {stats['total_modified']} ({stats['modification_rate']:.1%})")
    logger.info(f"Medical terms matched: {stats['medical_term_matches']}")
    logger.info(f"Output saved to {output_path}")

    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    """Handle 'batch' subcommand — batch process a directory of OCR files."""
    config = BatchConfig(
        input_dir=Path(args.input_dir),
        output_dir=Path(args.output_dir),
        workers=args.workers,
        confidence_threshold=args.confidence,
        flag_low_confidence=not args.no_flag,
        save_flagged=not args.no_flag,
        save_summary=True,
        file_pattern=args.pattern,
        use_processes=args.use_processes,
        no_review=args.no_review,
        dictionary_path=args.dictionary,
    )

    # Validate
    errors = config.validate()
    if errors:
        logger.error(f"Configuration errors: {'; '.join(errors)}")
        return 1

    processor = PostProcessor(
        confidence_threshold=config.confidence_threshold,
    )

    # Load optional dictionary
    if args.dictionary:
        dict_path = Path(args.dictionary)
        if dict_path.exists():
            count = processor.load_medical_terms_from_file(dict_path)
            logger.info(f"Loaded {count} medical terms from {dict_path}")

    batch = BatchProcessor(config=config, processor=processor)

    # Progress callback
    def progress_callback(completed: int, total: int, filename: str) -> None:
        logger.info(f"Progress: {completed}/{total} — {filename}")

    batch.set_progress_callback(progress_callback)

    logger.info(
        f"Starting batch processing: {config.input_dir} → {config.output_dir} "
        f"({config.workers} workers, threshold={config.confidence_threshold})"
    )

    result = batch.process()

    # Print summary
    logger.info("=" * 60)
    logger.info("Batch Processing Complete")
    logger.info("=" * 60)
    logger.info(f"Files: {result.processed_files}/{result.total_files} processed, "
                f"{result.failed_files} failed")
    logger.info(f"Words: {result.total_words} total, {result.corrected_words} corrected "
                f"({result.correction_rate}%)")
    logger.info(f"Auto-accepted: {result.auto_accepted}, "
                f"Flagged for review: {result.flagged_for_review}")
    logger.info(f"Duration: {result.duration_seconds:.1f}s "
                f"({result.processing_rate:.1f} files/min)")

    if result.errors:
        logger.warning(f"Errors in {len(result.errors)} files:")
        for err in result.errors[:5]:
            logger.warning(f"  - {err['file']}: {err['error']}")

    return 0 if result.failed_files == 0 else 1


def _cmd_validate(args: argparse.Namespace) -> int:
    """Handle 'validate' subcommand — validate text for OCR issues."""
    text = args.text
    if not text:
        logger.error("--text is required for validate command")
        return 1

    # Read from file if path provided
    text_path = Path(text)
    if text_path.exists():
        text = text_path.read_text(encoding="utf-8")

    processor = PostProcessor(
        confidence_threshold=args.confidence,
    )

    # Load optional dictionary
    if args.dictionary:
        dict_path = Path(args.dictionary)
        if dict_path.exists():
            processor.load_medical_terms_from_file(dict_path)

    # Arabic validation
    if args.lang in ("ar", "arabic", "both"):
        arabic_result = processor.validate_arabic(text)
        logger.info("Arabic Text Validation Results / نتائج التحقق من النص العربي")
        logger.info("-" * 50)
        logger.info(f"Valid: {arabic_result['is_valid']}")
        logger.info(f"Word count: {arabic_result['metrics']['word_count']}")
        logger.info(f"Arabic ratio: {arabic_result['metrics']['arabic_ratio']:.1%}")
        if arabic_result["issues"]:
            logger.info("Issues found:")
            for issue in arabic_result["issues"]:
                logger.info(f"  [{issue['severity']}] {issue['message']}")
        else:
            logger.info("No issues found ✅")

    # Medical term validation
    if args.check_terms:
        medical_result = processor.validate_medical_terms(text)
        logger.info("\nMedical Term Validation / التحقق من المصطلحات الطبية")
        logger.info("-" * 50)
        logger.info(f"Coverage: {medical_result['coverage']:.1%}")
        logger.info(f"Found terms: {len(medical_result['found_terms'])}")
        logger.info(f"Unmatched: {len(medical_result['unmatched_segments'])}")
        if medical_result["suggestions"]:
            logger.info("Suggestions:")
            for sug in medical_result["suggestions"][:10]:
                logger.info(f"  '{sug['original']}' → '{sug['suggestion']}' (score: {sug['score']})")

    # Output JSON if requested
    if args.output:
        output_data = {
            "arabic_validation": processor.validate_arabic(text) if args.lang in ("ar", "arabic", "both") else None,
            "medical_validation": processor.validate_medical_terms(text) if args.check_terms else None,
        }
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info(f"\nResults saved to {output_path}")

    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="medical-ocr-postprocess",
        description="Post-process medical OCR results — Arabic normalization, "
                    "medical term validation, batch correction\n"
                    "معالجة نتائج OCR الطبية — توحيد النص العربي والتحقق من المصطلحات الطبية",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"medical-ocr-postprocessor {__version__}",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- correct ---
    correct_parser = subparsers.add_parser(
        "correct",
        help="Correct a single OCR result file",
        description="Correct words in a single OCR result JSON file.",
    )
    correct_parser.add_argument("-i", "--input", required=True, help="Input JSON file path")
    correct_parser.add_argument("-o", "--output", required=True, help="Output JSON file path")
    correct_parser.add_argument(
        "-c", "--confidence", type=float, default=0.85,
        help="Confidence threshold (0-1). Default: 0.85",
    )
    correct_parser.add_argument(
        "-d", "--dictionary",
        help="Path to custom medical terms dictionary file",
    )

    # --- batch ---
    batch_parser = subparsers.add_parser(
        "batch",
        help="Batch process a directory of OCR files",
        description="Process an entire directory of OCR result files without interactive review.",
    )
    batch_parser.add_argument("--input-dir", required=True, help="Directory containing OCR JSON files")
    batch_parser.add_argument("--output-dir", required=True, help="Output directory for corrected files")
    batch_parser.add_argument(
        "-w", "--workers", type=int, default=1,
        help="Number of concurrent workers. Default: 1",
    )
    batch_parser.add_argument(
        "-c", "--confidence", type=float, default=0.85,
        help="Auto-accept threshold. Default: 0.85",
    )
    batch_parser.add_argument(
        "--no-flag", action="store_true",
        help="Do not flag low-confidence words for review",
    )
    batch_parser.add_argument(
        "-p", "--pattern", default="*.json",
        help="File glob pattern. Default: *.json",
    )
    batch_parser.add_argument(
        "--use-processes", action="store_true",
        help="Use processes instead of threads for parallelism",
    )
    batch_parser.add_argument(
        "--no-review", action="store_true",
        help="Skip correction logging and flagged items for higher throughput (3-5x faster)",
    )
    batch_parser.add_argument(
        "-d", "--dictionary",
        help="Path to custom medical terms dictionary file",
    )

    # --- validate ---
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate text for OCR issues",
        description="Check Arabic text for OCR artifacts and validate medical terms.",
    )
    validate_parser.add_argument(
        "-t", "--text", required=True,
        help="Text to validate (or path to a text file)",
    )
    validate_parser.add_argument(
        "-l", "--lang", default="ar",
        choices=["ar", "arabic", "en", "english", "both"],
        help="Language of the text. Default: ar",
    )
    validate_parser.add_argument(
        "--check-terms", action="store_true",
        help="Also check for medical term coverage",
    )
    validate_parser.add_argument(
        "-o", "--output",
        help="Save validation results as JSON",
    )
    validate_parser.add_argument(
        "-c", "--confidence", type=float, default=0.85,
        help="Confidence threshold. Default: 0.85",
    )
    validate_parser.add_argument(
        "-d", "--dictionary",
        help="Path to custom medical terms dictionary file",
    )

    args = parser.parse_args()
    _setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "correct": _cmd_correct,
        "batch": _cmd_batch,
        "validate": _cmd_validate,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
