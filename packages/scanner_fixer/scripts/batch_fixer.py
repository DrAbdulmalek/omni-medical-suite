# scripts/batch_fixer.py
"""
Batch document preprocessing using enhanced preprocessor.
Processes all images in a directory through the full pipeline.

Usage:
    python scripts/batch_fixer.py --input ./data/raw --output ./data/cleaned
    python scripts/batch_fixer.py --input ./data/raw --output ./data/cleaned --workers 4 --debug
"""
import argparse
import logging
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from src.scanner_fixer.enhanced_preprocessor import DocumentPreprocessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".webp"}


def process_single(args: tuple) -> dict:
    """Process a single image. Returns result dict."""
    input_path, output_path, debug = args
    try:
        proc = DocumentPreprocessor(debug=debug)
        result = proc.process(str(input_path), str(output_path))
        if result is not None:
            return {"file": input_path.name, "status": "success"}
        else:
            return {"file": input_path.name, "status": "failed", "reason": "None result"}
    except Exception as e:
        return {"file": input_path.name, "status": "error", "reason": str(e)}


def batch_process(input_dir: str, output_dir: str, max_workers: int = 4,
                  debug_first: int = 0) -> dict:
    """
    Process all images in input_dir and save to output_dir.

    Args:
        input_dir: Directory containing input images.
        output_dir: Directory for processed output images.
        max_workers: Number of parallel workers.
        debug_first: Save debug images for first N files (0 = no debug).

    Returns:
        Dict with success/fail counts.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Collect image files
    images = []
    for ext in SUPPORTED_EXTENSIONS:
        images.extend(input_path.glob(f"*{ext}"))
        images.extend(input_path.glob(f"*{ext.upper()}"))

    if not images:
        logger.warning(f"No images found in {input_dir}")
        return {"total": 0, "success": 0, "failed": 0}

    logger.info(f"Found {len(images)} images to process")

    # Prepare tasks
    tasks = []
    for i, img_path in enumerate(sorted(images)):
        out_path = output_path / img_path.name
        debug = (i < debug_first) if debug_first > 0 else False
        tasks.append((img_path, out_path, debug))

    # Execute
    results = {"success": 0, "failed": 0, "errors": []}

    if max_workers > 1 and len(tasks) > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_single, task): task for task in tasks}
            for future in as_completed(futures):
                result = future.result()
                if result["status"] == "success":
                    results["success"] += 1
                    logger.info(f"  OK: {result['file']}")
                else:
                    results["failed"] += 1
                    results["errors"].append(result)
                    logger.error(f"  FAIL: {result['file']} - {result.get('reason', 'unknown')}")
    else:
        for task in tasks:
            result = process_single(task)
            if result["status"] == "success":
                results["success"] += 1
                logger.info(f"  OK: {result['file']}")
            else:
                results["failed"] += 1
                results["errors"].append(result)
                logger.error(f"  FAIL: {result['file']} - {result.get('reason', 'unknown')}")

    results["total"] = len(tasks)
    logger.info(f"Batch complete: {results['success']}/{results['total']} succeeded")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Batch document preprocessing for medical OCR"
    )
    parser.add_argument("--input", "-i", required=True,
                        help="Input directory containing images")
    parser.add_argument("--output", "-o", required=True,
                        help="Output directory for processed images")
    parser.add_argument("--workers", "-w", type=int, default=4,
                        help="Number of parallel workers (default: 4)")
    parser.add_argument("--debug", "-d", action="store_true",
                        help="Save debug images for first 5 files")
    args = parser.parse_args()

    debug_count = 5 if args.debug else 0
    batch_process(args.input, args.output, args.workers, debug_count)


if __name__ == "__main__":
    main()