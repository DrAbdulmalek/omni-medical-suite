"""
batch_pipeline.py
Production-grade batch processing pipeline for scanner-fixer.

Processes directories of scanned document images in parallel, producing
CSV manifests, per-image JSON reports, before/after previews, quarantine
for failed images, and a batch summary.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import shutil
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


from .pipeline import fix_scan

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported image extensions (lower-case, with leading dot)
# ---------------------------------------------------------------------------
IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp", ".pbm", ".pgm",
})

# ---------------------------------------------------------------------------
# Optional tqdm import — graceful fallback
# ---------------------------------------------------------------------------
try:
    from tqdm import tqdm

    _HAS_TQDM = True
except ImportError:  # pragma: no cover
    _HAS_TQDM = False

    def tqdm(iterable, **kwargs):  # type: ignore[misc]
        """No-op fallback that just iterates."""
        total = kwargs.get("total")
        if total is not None:
            logger.info("Processing %d images (install tqdm for progress bar)", total)
        return iterable


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class BatchConfig:
    """Configuration for the batch processor."""

    workers: int = 1
    dry_run: bool = False
    quarantine_threshold_mb: float = 50.0
    generate_previews: bool = True
    manifest_format: str = "csv"  # "csv" or "json"
    # Pipeline options forwarded to fix_scan()
    do_crop: bool = True
    do_rotate: bool = False
    do_deskew: bool = True
    do_enhance: bool = True
    binarize: bool = False
    target_dpi: Optional[int] = 300
    use_tesseract_osd: bool = False
    deskew_method: str = "hough"
    crop_padding: int = 10


@dataclass
class ImageResult:
    """Result of processing a single image."""

    filename: str = ""
    original_path: str = ""
    fixed_path: str = ""
    status: str = "ok"  # ok | failed | quarantined
    processing_time_ms: float = 0.0
    steps_applied: str = ""
    error_message: str = ""
    file_size_kb: float = 0.0


# ---------------------------------------------------------------------------
# Worker function (must be picklable — top-level)
# ---------------------------------------------------------------------------
def _process_single_image(
    src_path: str,
    dst_path: str,
    config_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process a single image file.  Designed to run inside a worker process.

    Returns a dict with:
        status, processing_time_ms, steps_applied, error_message,
        file_size_kb, report, steps (intermediate images as base64 strings
        are intentionally omitted — we re-read from disk for previews).
    """
    src = Path(src_path)
    dst = Path(dst_path)

    start = time.perf_counter()

    # Build kwargs for fix_scan from config
    pipeline_kwargs = {
        "do_crop": config_dict.get("do_crop", True),
        "do_rotate": config_dict.get("do_rotate", False),
        "do_deskew": config_dict.get("do_deskew", True),
        "do_enhance": config_dict.get("do_enhance", True),
        "binarize": config_dict.get("binarize", False),
        "target_dpi": config_dict.get("target_dpi", 300),
        "use_tesseract_osd": config_dict.get("use_tesseract_osd", False),
        "deskew_method": config_dict.get("deskew_method", "hough"),
        "crop_padding": config_dict.get("crop_padding", 10),
    }

    try:
        result = fix_scan(str(src), output_path=str(dst), **pipeline_kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000.0

        # Determine which steps actually ran
        steps_keys = list(result.get("steps", {}).keys())
        # Remove "original" — it's always present
        steps_applied_list = [s for s in steps_keys if s != "original"]
        steps_applied = ",".join(steps_applied_list) if steps_applied_list else "none"

        file_size_kb = dst.stat().st_size / 1024.0 if dst.exists() else 0.0

        return {
            "status": "ok",
            "processing_time_ms": round(elapsed_ms, 2),
            "steps_applied": steps_applied,
            "error_message": "",
            "file_size_kb": round(file_size_kb, 2),
            "report": result.get("report", {}),
            "steps_keys": steps_keys,
        }
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.exception("Failed to process %s", src)
        return {
            "status": "failed",
            "processing_time_ms": round(elapsed_ms, 2),
            "steps_applied": "",
            "error_message": str(exc),
            "file_size_kb": 0.0,
            "report": {},
            "steps_keys": [],
        }


# ---------------------------------------------------------------------------
# Preview generation helper
# ---------------------------------------------------------------------------
def _generate_preview(
    original_path: Path,
    fixed_path: Path,
    preview_path: Path,
) -> None:
    """
    Create a side-by-side before/after PNG preview.

    Original on the left, fixed on the right, concatenated horizontally.
    """
    try:
        from PIL import Image

        orig_img = Image.open(original_path)
        fixed_img = Image.open(fixed_path)

        # Match heights by resizing the shorter one
        max_height = max(orig_img.height, fixed_img.height)
        if orig_img.height != max_height:
            ratio = max_height / orig_img.height
            orig_img = orig_img.resize(
                (int(orig_img.width * ratio), max_height), Image.LANCZOS
            )
        if fixed_img.height != max_height:
            ratio = max_height / fixed_img.height
            fixed_img = fixed_img.resize(
                (int(fixed_img.width * ratio), max_height), Image.LANCZOS
            )

        total_width = orig_img.width + fixed_img.width
        preview = Image.new("RGB", (total_width, max_height))
        preview.paste(orig_img, (0, 0))
        preview.paste(fixed_img, (orig_img.width, 0))

        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview.save(str(preview_path), "PNG")
    except Exception:
        logger.warning("Could not generate preview for %s", preview_path, exc_info=True)


# ---------------------------------------------------------------------------
# Main BatchProcessor class
# ---------------------------------------------------------------------------
class BatchProcessor:
    """
    Production-grade batch processor for scanned document images.

    Walks an input directory, processes every image through the scanner-fixer
    pipeline (in parallel), and produces:
      - A CSV (or JSON) manifest of all processed images
      - Per-image JSON reports in ``<output>/reports/``
      - Before/after preview PNGs in ``<output>/previews/``
      - Quarantined files in ``<output>/quarantine/`` for failures
      - A ``<output>/batch_summary.json`` with aggregate statistics
    """

    def __init__(
        self,
        input_dir: str | Path,
        output_dir: str | Path,
        config: Optional[BatchConfig] = None,
    ) -> None:
        self.input_dir = Path(input_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.config = config or BatchConfig()

        if not self.input_dir.is_dir():
            raise FileNotFoundError(f"Input directory does not exist: {self.input_dir}")

        # Derived sub-directories
        self.reports_dir = self.output_dir / "reports"
        self.previews_dir = self.output_dir / "previews"
        self.quarantine_dir = self.output_dir / "quarantine"
        self.fixed_dir = self.output_dir  # processed images go here (root of output)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> Dict[str, Any]:
        """
        Execute the full batch processing pipeline.

        Returns:
            The batch summary dict.
        """
        # Discover images
        image_paths = self._discover_images()
        total = len(image_paths)
        if total == 0:
            logger.warning("No image files found in %s", self.input_dir)
            return self._empty_summary()

        logger.info("Discovered %d image(s) in %s", total, self.input_dir)

        # Create output directories
        self._ensure_dirs()

        # Dry-run: write manifest only and return
        if self.config.dry_run:
            return self._dry_run(image_paths)

        batch_start = time.perf_counter()
        results: List[ImageResult] = []
        config_dict = asdict(self.config)

        # --- Parallel processing ---
        if self.config.workers <= 1:
            results = self._process_sequential(image_paths, config_dict)
        else:
            results = self._process_parallel(image_paths, config_dict, total)

        batch_elapsed = time.perf_counter() - batch_start

        # Post-processing: previews, reports, quarantine, manifest, summary
        self._write_reports(results)
        self._move_quarantined(results)
        if self.config.generate_previews:
            self._generate_previews(results)

        manifest_path = self._write_manifest(results)
        summary = self._write_summary(results, batch_elapsed)

        logger.info(
            "Batch complete: %s  |  %s",
            manifest_path,
            json.dumps({k: summary[k] for k in ("ok", "failed", "quarantined")}),
        )
        return summary

    # ------------------------------------------------------------------
    # Image discovery
    # ------------------------------------------------------------------
    def _discover_images(self) -> List[Path]:
        """Recursively find all image files in the input directory."""
        found: List[Path] = []
        for root, _dirs, files in os.walk(self.input_dir):
            for fname in files:
                fpath = Path(root) / fname
                if fpath.suffix.lower() in IMAGE_EXTENSIONS:
                    found.append(fpath)
        found.sort()
        return found

    # ------------------------------------------------------------------
    # Directory helpers
    # ------------------------------------------------------------------
    def _ensure_dirs(self) -> None:
        for d in (self.fixed_dir, self.reports_dir, self.previews_dir, self.quarantine_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Dry run
    # ------------------------------------------------------------------
    def _dry_run(self, image_paths: List[Path]) -> Dict[str, Any]:
        """Generate manifest without processing any images."""
        logger.info("Dry-run mode — no images will be processed.")
        results: List[ImageResult] = []
        for p in image_paths:
            file_size_kb = p.stat().st_size / 1024.0
            quarantined = file_size_kb > self.config.quarantine_threshold_mb * 1024
            results.append(
                ImageResult(
                    filename=p.name,
                    original_path=str(p),
                    fixed_path="",
                    status="quarantined" if quarantined else "ok",
                    processing_time_ms=0.0,
                    steps_applied="",
                    error_message="exceeds size threshold" if quarantined else "",
                    file_size_kb=round(file_size_kb, 2),
                )
            )
        self._write_manifest(results)
        summary = self._write_summary(results, 0.0)
        logger.info("Dry-run manifest written with %d entries.", len(results))
        return summary

    # ------------------------------------------------------------------
    # Sequential processing
    # ------------------------------------------------------------------
    def _process_sequential(
        self,
        image_paths: List[Path],
        config_dict: Dict[str, Any],
    ) -> List[ImageResult]:
        results: List[ImageResult] = []
        iterator = tqdm(image_paths, desc="Processing", unit="img") if _HAS_TQDM else image_paths

        for src in iterator:
            result = self._process_one(src, config_dict)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Parallel processing
    # ------------------------------------------------------------------
    def _process_parallel(
        self,
        image_paths: List[Path],
        config_dict: Dict[str, Any],
        total: int,
    ) -> List[ImageResult]:
        results: List[ImageResult] = []
        future_to_src: Dict[Any, Path] = {}

        with ProcessPoolExecutor(max_workers=self.config.workers) as pool:
            for src in image_paths:
                dst = self.fixed_dir / f"{src.stem}_fixed{src.suffix}"
                future = pool.submit(
                    _process_single_image,
                    str(src),
                    str(dst),
                    config_dict,
                )
                future_to_src[future] = src

            for future in tqdm(
                as_completed(future_to_src),
                total=total,
                desc="Processing",
                unit="img",
            ) if _HAS_TQDM else as_completed(future_to_src):
                src = future_to_src[future]
                worker_result = future.result()

                dst = self.fixed_dir / f"{src.stem}_fixed{src.suffix}"
                original_size_kb = src.stat().st_size / 1024.0

                img_result = ImageResult(
                    filename=src.name,
                    original_path=str(src),
                    fixed_path=str(dst) if worker_result["status"] == "ok" else "",
                    status=worker_result["status"],
                    processing_time_ms=worker_result["processing_time_ms"],
                    steps_applied=worker_result["steps_applied"],
                    error_message=worker_result["error_message"],
                    file_size_kb=round(original_size_kb, 2),
                )
                # Store the worker report for later JSON report generation
                img_result._worker_report = worker_result  # type: ignore[attr-defined]
                results.append(img_result)

        return results

    # ------------------------------------------------------------------
    # Process a single image (sequential path)
    # ------------------------------------------------------------------
    def _process_one(
        self,
        src: Path,
        config_dict: Dict[str, Any],
    ) -> ImageResult:
        dst = self.fixed_dir / f"{src.stem}_fixed{src.suffix}"

        # Quarantine check: file size
        size_mb = src.stat().st_size / (1024 * 1024)
        if size_mb > self.config.quarantine_threshold_mb:
            logger.warning("Quarantining %s (%.1f MB exceeds threshold)", src.name, size_mb)
            return ImageResult(
                filename=src.name,
                original_path=str(src),
                fixed_path="",
                status="quarantined",
                processing_time_ms=0.0,
                steps_applied="",
                error_message=f"file size {size_mb:.1f} MB exceeds threshold "
                              f"{self.config.quarantine_threshold_mb} MB",
                file_size_kb=round(src.stat().st_size / 1024.0, 2),
            )

        worker_result = _process_single_image(str(src), str(dst), config_dict)

        return ImageResult(
            filename=src.name,
            original_path=str(src),
            fixed_path=str(dst) if worker_result["status"] == "ok" else "",
            status=worker_result["status"],
            processing_time_ms=worker_result["processing_time_ms"],
            steps_applied=worker_result["steps_applied"],
            error_message=worker_result["error_message"],
            file_size_kb=round(src.stat().st_size / 1024.0, 2),
        )

    # ------------------------------------------------------------------
    # Per-image JSON reports
    # ------------------------------------------------------------------
    def _write_reports(self, results: List[ImageResult]) -> None:
        """Write a JSON report for each processed image."""
        for r in results:
            if r.status == "ok":
                fixed_path = Path(r.fixed_path)
                before_size_kb = Path(r.original_path).stat().st_size / 1024.0
                after_size_kb = fixed_path.stat().st_size / 1024.0 if fixed_path.exists() else 0.0
            else:
                before_size_kb = Path(r.original_path).stat().st_size / 1024.0
                after_size_kb = 0.0

            report: Dict[str, Any] = {
                "filename": r.filename,
                "original_path": r.original_path,
                "fixed_path": r.fixed_path,
                "status": r.status,
                "before_size_kb": round(before_size_kb, 2),
                "after_size_kb": round(after_size_kb, 2),
                "processing_time_ms": r.processing_time_ms,
                "steps_applied": r.steps_applied.split(",") if r.steps_applied else [],
                "error_message": r.error_message,
            }

            # Enrich with pipeline report if available
            worker_report = getattr(r, "_worker_report", None)
            if worker_report and isinstance(worker_report, dict):
                pipeline_report = worker_report.get("report", {})
                if pipeline_report:
                    report["pipeline_report"] = pipeline_report

            report_path = self.reports_dir / f"{Path(r.filename).stem}_report.json"
            try:
                with open(report_path, "w", encoding="utf-8") as f:
                    json.dump(report, f, indent=2, default=str)
            except OSError:
                logger.warning("Could not write report for %s", r.filename, exc_info=True)

    # ------------------------------------------------------------------
    # Quarantine
    # ------------------------------------------------------------------
    def _move_quarantined(self, results: List[ImageResult]) -> None:
        """Move failed and quarantined images to the quarantine directory."""
        for r in results:
            if r.status in ("failed", "quarantined"):
                src = Path(r.original_path)
                if src.exists():
                    dst = self.quarantine_dir / src.name
                    # Avoid name collisions
                    if dst.exists():
                        stem = src.stem
                        suffix = src.suffix
                        counter = 1
                        while dst.exists():
                            dst = self.quarantine_dir / f"{stem}_{counter}{suffix}"
                            counter += 1
                    try:
                        shutil.copy2(str(src), str(dst))
                        logger.info("Quarantined: %s -> %s", src.name, dst.name)
                    except OSError:
                        logger.warning(
                            "Could not quarantine %s", src.name, exc_info=True
                        )

    # ------------------------------------------------------------------
    # Previews
    # ------------------------------------------------------------------
    def _generate_previews(self, results: List[ImageResult]) -> None:
        """Generate before/after side-by-side preview PNGs."""
        for r in results:
            if r.status != "ok":
                continue
            orig = Path(r.original_path)
            fixed = Path(r.fixed_path)
            if not orig.exists() or not fixed.exists():
                continue
            preview_name = f"{orig.stem}_preview.png"
            preview_path = self.previews_dir / preview_name
            try:
                _generate_preview(orig, fixed, preview_path)
            except Exception:
                logger.warning(
                    "Preview generation failed for %s", r.filename, exc_info=True
                )

    # ------------------------------------------------------------------
    # Manifest (CSV or JSON)
    # ------------------------------------------------------------------
    def _write_manifest(self, results: List[ImageResult]) -> Path:
        """Write the batch manifest file."""
        if self.config.manifest_format == "json":
            return self._write_manifest_json(results)
        return self._write_manifest_csv(results)

    def _write_manifest_csv(self, results: List[ImageResult]) -> Path:
        manifest_path = self.output_dir / "manifest.csv"
        fieldnames = [
            "filename",
            "original_path",
            "fixed_path",
            "status",
            "processing_time_ms",
            "steps_applied",
            "error_message",
            "file_size_kb",
        ]
        with open(manifest_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow(asdict(r))
        logger.info("CSV manifest written to %s (%d rows)", manifest_path, len(results))
        return manifest_path

    def _write_manifest_json(self, results: List[ImageResult]) -> Path:
        manifest_path = self.output_dir / "manifest.json"
        data = [asdict(r) for r in results]
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("JSON manifest written to %s (%d rows)", manifest_path, len(results))
        return manifest_path

    # ------------------------------------------------------------------
    # Batch summary
    # ------------------------------------------------------------------
    def _write_summary(
        self, results: List[ImageResult], total_time: float
    ) -> Dict[str, Any]:
        """Write batch_summary.json and return the summary dict."""
        ok_count = sum(1 for r in results if r.status == "ok")
        failed_count = sum(1 for r in results if r.status == "failed")
        quarantined_count = sum(1 for r in results if r.status == "quarantined")
        total_count = len(results)

        processing_times = [
            r.processing_time_ms for r in results if r.processing_time_ms > 0
        ]
        avg_time = (
            sum(processing_times) / len(processing_times) if processing_times else 0.0
        )

        summary = {
            "total_images": total_count,
            "ok": ok_count,
            "failed": failed_count,
            "quarantined": quarantined_count,
            "total_time_seconds": round(total_time, 3),
            "average_time_per_image_ms": round(avg_time, 2),
            "input_directory": str(self.input_dir),
            "output_directory": str(self.output_dir),
        }

        summary_path = self.output_dir / "batch_summary.json"
        try:
            with open(summary_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            logger.info("Batch summary written to %s", summary_path)
        except OSError:
            logger.warning("Could not write batch summary", exc_info=True)

        return summary

    def _empty_summary(self) -> Dict[str, Any]:
        """Return a summary for the case where no images were found."""
        summary = {
            "total_images": 0,
            "ok": 0,
            "failed": 0,
            "quarantined": 0,
            "total_time_seconds": 0.0,
            "average_time_per_image_ms": 0.0,
            "input_directory": str(self.input_dir),
            "output_directory": str(self.output_dir),
        }
        self._ensure_dirs()
        summary_path = self.output_dir / "batch_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        return summary