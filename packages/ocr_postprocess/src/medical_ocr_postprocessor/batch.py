"""
Batch processing mode for medical OCR postprocessing.
وضع المعالجة الدفعية لنتائج OCR الطبية.

This module provides BatchProcessor for processing entire documents
without interactive review, with configurable concurrency and
confidence-based auto-acceptance.

Queue Draining Guide
====================
When using this with a task queue (e.g., Celery + Redis):

1. **Single-worker mode** (default):
   - One process handles all documents sequentially
   - Good for small backlogs (< 100 documents)
   - Command: ``medical-ocr-postprocess batch --input-dir pages/ --workers 1``

2. **Multi-worker mode**:
   - Scale horizontally by increasing --workers
   - Each worker pulls from a shared queue
   - Requires [production] extras: ``pip install medical-ocr-postprocessor[production]``
   - Command: ``medical-ocr-postprocess batch --input-dir pages/ --workers 4``

3. **Queue draining for large backlogs**:
   - Start with --workers equal to CPU cores (default: os.cpu_count())
   - Monitor with --monitoring flag (requires [monitoring] extras)
   - Auto-scale workers based on queue depth:
     - < 50 items: 2 workers
     - 50-500 items: 4 workers
     - > 500 items: 8+ workers
   - Estimated throughput: ~200-500 pages/minute per worker

4. **Backlog metrics** to monitor:
   - queue_depth: Number of pending items
   - processing_rate: Items processed per minute
   - avg_latency: Time from queue entry to completion
   - error_rate: Percentage of failed items
   - auto_accept_rate: Percentage auto-accepted (vs flagged for review)

Example: Drain a 10,000-page backlog
-------------------------------------
::

    # Step 1: Start 8 workers
    medical-ocr-postprocess batch \\
        --input-dir backlog/ \\
        --output-dir processed/ \\
        --workers 8 \\
        --confidence-threshold 0.85 \\
        --flag-low-confidence

    # Step 2: Monitor progress
    # Check output/flagged/ for items needing human review
    # Check output/reports/batch_summary.json for metrics

    # Step 3: Process flagged items interactively
    medical-ocr-postprocess correct \\
        --input output/flagged/ \\
        --output output/reviewed/
"""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from medical_ocr_postprocessor.core import CorrectionResult, PostProcessor

logger = logging.getLogger(__name__)


def _run_single_file(
    input_path: str,
    output_dir: str,
    config_dict: dict,
    dictionary_path: Optional[str] = None,
) -> dict:
    """Module-level helper for ProcessPoolExecutor workers.

    Creates a NEW PostProcessor instance inside each worker process,
    avoiding pickle issues with bound methods and shared state.

    Parameters
    ----------
    input_path : str
        Path to the input JSON file (as string, not Path).
    output_dir : str
        Output directory path as string.
    config_dict : dict
        Serialized BatchConfig dictionary.
    dictionary_path : str | None
        Optional path to medical dictionary file.

    Returns
    -------
    dict
        Processing result dictionary.
    """
    from pathlib import Path as _Path
    import json as _json
    import os as _os

    filepath = _Path(input_path)
    out_dir = _Path(output_dir)
    no_review = config_dict.get("no_review", False)
    confidence_threshold = config_dict.get("confidence_threshold", 0.85)
    flag_low_confidence = config_dict.get("flag_low_confidence", True)

    try:
        raw = _json.loads(filepath.read_text(encoding="utf-8"))

        # Support multiple input formats
        if isinstance(raw, list):
            words = [str(w) for w in raw]
            confidences = [0.5] * len(words)
            full_text = " ".join(words)
        elif isinstance(raw, dict):
            words = raw.get("words", [])
            confidences = raw.get("confidences", [0.5] * len(words))
            full_text = raw.get("text", " ".join(str(w) for w in words))
            if words and isinstance(words[0], dict):
                words = [w.get("text", str(w)) for w in words]
                confidences = [w.get("confidence", 0.5) for w in raw.get("words", [])]
        else:
            return {
                "file": str(filepath),
                "success": False,
                "error": f"Unsupported format: {type(raw).__name__}",
            }

        # Create a fresh PostProcessor in this worker process
        processor = PostProcessor(confidence_threshold=confidence_threshold)
        if dictionary_path and _Path(dictionary_path).exists():
            processor.load_medical_terms_from_file(dictionary_path)

        # Correct all words (skip_log for no-review mode)
        results = processor.batch_correct(words, confidences, skip_log=no_review)

        # Separate auto-accepted and flagged
        corrected_words = []
        flagged_words = []
        for r in results:
            corrected_words.append(r.corrected)
            if flag_low_confidence and not no_review and r.confidence < confidence_threshold:
                flagged_words.append(r.to_dict())

        # Build output
        output = {
            "file": str(filepath),
            "success": True,
            "original_text": full_text,
            "corrected_text": " ".join(corrected_words),
            "words": [] if no_review else [r.to_dict() for r in results],
            "total_words": len(results),
            "corrected_count": sum(1 for r in results if r.is_modified),
            "auto_accepted": len(results) - len(flagged_words),
            "flagged_count": len(flagged_words),
        }

        # Save corrected output
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)
            output_path = out_dir / filepath.name
            file_output = {
                "original_text": output.get("original_text", ""),
                "corrected_text": output.get("corrected_text", ""),
                "metadata": {
                    "source_file": str(filepath),
                    "total_words": output.get("total_words", 0),
                    "corrected_count": output.get("corrected_count", 0),
                    "auto_accepted": output.get("auto_accepted", 0),
                    "flagged_count": output.get("flagged_count", 0),
                },
            }
            output_path.write_text(
                _json.dumps(file_output, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            # Save flagged words separately if any
            if (not no_review and flag_low_confidence
                    and output.get("flagged_count", 0) > 0):
                flagged_dir = out_dir / "flagged"
                flagged_dir.mkdir(parents=True, exist_ok=True)
                flagged_path = flagged_dir / filepath.name
                flagged_data = {
                    "source_file": str(filepath),
                    "flagged_words": [
                        w for w in output.get("words", [])
                        if w.get("confidence", 1.0) < confidence_threshold
                    ],
                    "threshold": confidence_threshold,
                }
                flagged_path.write_text(
                    _json.dumps(flagged_data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

        return output

    except _json.JSONDecodeError as e:
        return {"file": str(filepath), "success": False, "error": f"JSON decode error: {e}"}
    except Exception as e:
        return {"file": str(filepath), "success": False, "error": str(e)}


@dataclass
class BatchConfig:
    """Configuration for batch processing.
    إعدادات المعالجة الدفعية."""

    input_dir: Path
    output_dir: Path
    workers: int = 1
    confidence_threshold: float = 0.85
    flag_low_confidence: bool = True
    save_flagged: bool = True
    save_summary: bool = True
    file_pattern: str = "*.json"
    use_processes: bool = False  # True = ProcessPoolExecutor, False = ThreadPoolExecutor
    no_review: bool = False  # When True, skip correction logging and flagged items
    dictionary_path: Optional[str] = None

    @property
    def flagged_dir(self) -> Path:
        return self.output_dir / "flagged"

    @property
    def reports_dir(self) -> Path:
        return self.output_dir / "reports"

    def to_dict(self) -> dict:
        """Serialize config to a plain dict (pickle-safe for ProcessPoolExecutor)."""
        return {
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "workers": self.workers,
            "confidence_threshold": self.confidence_threshold,
            "flag_low_confidence": self.flag_low_confidence,
            "save_flagged": self.save_flagged,
            "save_summary": self.save_summary,
            "file_pattern": self.file_pattern,
            "use_processes": self.use_processes,
            "no_review": self.no_review,
            "dictionary_path": self.dictionary_path,
        }

    def validate(self) -> list[str]:
        """Validate configuration. Returns list of error messages."""
        errors = []
        if not self.input_dir.exists():
            errors.append(f"Input directory does not exist: {self.input_dir}")
        if self.workers < 1:
            errors.append(f"Workers must be >= 1, got {self.workers}")
        if not 0.0 <= self.confidence_threshold <= 1.0:
            errors.append(f"Confidence threshold must be 0-1, got {self.confidence_threshold}")
        return errors


@dataclass
class BatchResult:
    """Result of a batch processing run.
    نتيجة عملية المعالجة الدفعية."""

    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    total_words: int = 0
    corrected_words: int = 0
    auto_accepted: int = 0
    flagged_for_review: int = 0
    start_time: float = 0.0
    end_time: float = 0.0
    errors: list[dict] = field(default_factory=list)
    per_file_results: list[dict] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return self.end_time - self.start_time if self.end_time > self.start_time else 0.0

    @property
    def processing_rate(self) -> float:
        """Files per minute."""
        if self.duration_seconds == 0:
            return 0.0
        return (self.processed_files / self.duration_seconds) * 60

    @property
    def correction_rate(self) -> float:
        """Percentage of words that were corrected."""
        if self.total_words == 0:
            return 0.0
        return round((self.corrected_words / self.total_words) * 100, 2)

    def to_dict(self) -> dict:
        return {
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "failed_files": self.failed_files,
            "total_words": self.total_words,
            "corrected_words": self.corrected_words,
            "auto_accepted": self.auto_accepted,
            "flagged_for_review": self.flagged_for_review,
            "duration_seconds": round(self.duration_seconds, 2),
            "processing_rate_per_min": round(self.processing_rate, 2),
            "correction_rate_pct": self.correction_rate,
            "errors": self.errors,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class BatchProcessor:
    """Batch processing engine for medical OCR postprocessing.

    محرك المعالجة الدفعية لنتائج OCR الطبية.

    Processes entire directories of OCR results without interactive review,
    auto-accepting high-confidence corrections and flagging low-confidence
    items for later review.

    Parameters
    ----------
    config : BatchConfig
        Batch processing configuration.
    processor : PostProcessor | None
        Custom PostProcessor instance. If None, creates one from config.
    """

    def __init__(
        self,
        config: BatchConfig,
        processor: Optional[PostProcessor] = None,
    ):
        self.config = config
        self.processor = processor or PostProcessor(
            confidence_threshold=config.confidence_threshold,
        )
        self._progress_callback: Optional[Callable[[int, int, str], None]] = None
        self._dictionary_path: Optional[str] = config.dictionary_path
        if self._dictionary_path:
            dict_path = Path(self._dictionary_path)
            if dict_path.exists():
                self.processor.load_medical_terms_from_file(dict_path)

    def set_progress_callback(
        self,
        callback: Callable[[int, int, str], None],
    ) -> None:
        """Set a callback for progress updates.

        Parameters
        ----------
        callback : callable(completed, total, filename)
            Called after each file is processed.
        """
        self._progress_callback = callback

    def _process_single_file(self, filepath: Path) -> dict:
        """Process a single OCR result file.

        معالجة ملف نتائج OCR واحد.

        Expected JSON format:
        ``{"words": [...], "confidences": [...], "text": "full text"}``
        or simple list of strings.
        """
        try:
            raw = json.loads(filepath.read_text(encoding="utf-8"))

            # Support multiple input formats
            if isinstance(raw, list):
                words = [str(w) for w in raw]
                confidences = [0.5] * len(words)
                full_text = " ".join(words)
            elif isinstance(raw, dict):
                words = raw.get("words", [])
                confidences = raw.get("confidences", [0.5] * len(words))
                full_text = raw.get("text", " ".join(str(w) for w in words))
                # If words contain dicts with 'text' key
                if words and isinstance(words[0], dict):
                    words = [w.get("text", str(w)) for w in words]
                    confidences = [w.get("confidence", 0.5) for w in raw.get("words", [])]
            else:
                return {
                    "file": str(filepath),
                    "success": False,
                    "error": f"Unsupported format: {type(raw).__name__}",
                }

            # Correct all words
            results = self.processor.batch_correct(
                words, confidences, skip_log=self.config.no_review,
            )

            # Separate auto-accepted and flagged
            corrected_words = []
            flagged_words = []
            for r in results:
                corrected_words.append(r.corrected)
                if self.config.flag_low_confidence and not self.config.no_review and r.confidence < self.config.confidence_threshold:
                    flagged_words.append(r.to_dict())

            # Build output
            output = {
                "file": str(filepath),
                "success": True,
                "original_text": full_text,
                "corrected_text": " ".join(corrected_words),
                "words": [] if self.config.no_review else [r.to_dict() for r in results],
                "total_words": len(results),
                "corrected_count": sum(1 for r in results if r.is_modified),
                "auto_accepted": len(results) - len(flagged_words),
                "flagged_count": len(flagged_words),
            }

            return output

        except json.JSONDecodeError as e:
            return {"file": str(filepath), "success": False, "error": f"JSON decode error: {e}"}
        except Exception as e:
            logger.exception(f"Error processing {filepath}")
            return {"file": str(filepath), "success": False, "error": str(e)}

    def _save_results(
        self,
        filepath: Path,
        file_result: dict,
    ) -> None:
        """Save processing results to output directory."""
        if not file_result.get("success"):
            return

        # In no-review mode, the process worker already saved output.
        # Only save from the main process when not using ProcessPoolExecutor.
        if self.config.use_processes:
            return

        # Save corrected output
        output_path = self.config.output_dir / filepath.name
        output = {
            "original_text": file_result.get("original_text", ""),
            "corrected_text": file_result.get("corrected_text", ""),
            "words": file_result.get("words", []),
            "metadata": {
                "source_file": str(filepath),
                "total_words": file_result.get("total_words", 0),
                "corrected_count": file_result.get("corrected_count", 0),
                "auto_accepted": file_result.get("auto_accepted", 0),
                "flagged_count": file_result.get("flagged_count", 0),
            },
        }
        output_path.write_text(
            json.dumps(output, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        # Skip flagged saving in no-review mode
        if self.config.no_review:
            return

        # Save flagged words separately if any
        if (self.config.save_flagged and self.config.flag_low_confidence
                and file_result.get("flagged_count", 0) > 0):
            self.config.flagged_dir.mkdir(parents=True, exist_ok=True)
            flagged_path = self.config.flagged_dir / filepath.name
            flagged_data = {
                "source_file": str(filepath),
                "flagged_words": [
                    w for w in file_result.get("words", [])
                    if w.get("confidence", 1.0) < self.config.confidence_threshold
                ],
                "threshold": self.config.confidence_threshold,
            }
            flagged_path.write_text(
                json.dumps(flagged_data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    def process(self) -> BatchResult:
        """Run batch processing on all matching files.

        تنفيذ المعالجة الدفعية على جميع الملفات المطابقة.

        Returns
        -------
        BatchResult
            Summary of the batch processing run.
        """
        # Validate config
        errors = self.config.validate()
        if errors:
            raise ValueError(f"Invalid config: {'; '.join(errors)}")

        # Create output directories
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        if self.config.flag_low_confidence and self.config.save_flagged:
            self.config.flagged_dir.mkdir(parents=True, exist_ok=True)
        if self.config.save_summary:
            self.config.reports_dir.mkdir(parents=True, exist_ok=True)

        # Collect input files
        input_files = sorted(self.config.input_dir.glob(self.config.file_pattern))
        if not input_files:
            logger.warning(f"No files matching '{self.config.file_pattern}' in {self.config.input_dir}")

        result = BatchResult(
            total_files=len(input_files),
            start_time=time.time(),
        )

        max_workers = min(self.config.workers, len(input_files)) if input_files else 1
        ExecutorClass = ProcessPoolExecutor if self.config.use_processes else ThreadPoolExecutor

        # For ProcessPoolExecutor, use the module-level helper (pickle-safe).
        # For ThreadPoolExecutor, use the bound method (reuses shared PostProcessor).
        use_process_helper = self.config.use_processes
        config_dict = self.config.to_dict()

        with ExecutorClass(max_workers=max_workers) as executor:
            future_to_file = {}
            for f in input_files:
                if use_process_helper:
                    fut = executor.submit(
                        _run_single_file,
                        str(f),
                        str(self.config.output_dir),
                        config_dict,
                        self._dictionary_path,
                    )
                else:
                    fut = executor.submit(self._process_single_file, f)
                future_to_file[fut] = f

            completed = 0
            for future in as_completed(future_to_file):
                filepath = future_to_file[future]
                completed += 1

                try:
                    file_result = future.result()
                except Exception as e:
                    file_result = {"file": str(filepath), "success": False, "error": str(e)}
                    logger.exception(f"Failed to process {filepath}")

                if file_result.get("success"):
                    result.processed_files += 1
                    result.total_words += file_result.get("total_words", 0)
                    result.corrected_words += file_result.get("corrected_count", 0)
                    result.auto_accepted += file_result.get("auto_accepted", 0)
                    result.flagged_for_review += file_result.get("flagged_count", 0)
                    self._save_results(filepath, file_result)
                else:
                    result.failed_files += 1
                    result.errors.append({
                        "file": str(filepath),
                        "error": file_result.get("error", "Unknown error"),
                    })

                result.per_file_results.append(file_result)

                # Progress callback
                if self._progress_callback:
                    self._progress_callback(completed, len(input_files), filepath.name)

                logger.info(
                    f"[{completed}/{len(input_files)}] Processed {filepath.name} — "
                    f"{file_result.get('total_words', 0)} words, "
                    f"{file_result.get('corrected_count', 0)} corrected"
                )

        result.end_time = time.time()

        # Save summary report
        if self.config.save_summary:
            summary_path = self.config.reports_dir / "batch_summary.json"
            summary_path.write_text(
                result.to_json(indent=2),
                encoding="utf-8",
            )
            logger.info(f"Batch summary saved to {summary_path}")
            logger.info(
                f"Batch complete: {result.processed_files}/{result.total_files} files, "
                f"{result.total_words} words, {result.corrected_words} corrected "
                f"({result.correction_rate}%), {result.flagged_for_review} flagged"
            )

        return result

    def drain_queue(
        self,
        max_items: Optional[int] = None,
        poll_interval: float = 1.0,
        timeout: float = 3600.0,
        workers: Optional[int] = None,
    ) -> BatchResult:
        """Continuously drain a queue of OCR results using parallel workers.

        استنزاف مستمر لقائمة نتائج OCR مع معالجة متوازية.

        Parameters
        ----------
        max_items : int | None
            Maximum items to process. None = unlimited.
        poll_interval : float
            Seconds between queue checks when empty.
        timeout : float
            Maximum seconds to run before stopping.
        workers : int | None
            Number of parallel workers. None = use config.workers.

        Returns
        -------
        BatchResult
            Combined results of all processed files.
        """
        start = time.time()
        combined = BatchResult(start_time=start)
        num_workers = workers or self.config.workers
        ExecutorClass = ProcessPoolExecutor if self.config.use_processes else ThreadPoolExecutor
        use_process_helper = self.config.use_processes
        config_dict = self.config.to_dict()

        while True:
            elapsed = time.time() - start
            if timeout > 0 and elapsed >= timeout:
                logger.info(f"Queue drain timeout reached ({timeout}s)")
                break

            # Check for new files
            input_files = sorted(self.config.input_dir.glob(self.config.file_pattern))
            if not input_files:
                if elapsed > 5:  # Wait a bit before declaring empty
                    logger.info("Queue is empty, stopping drain")
                break

            if max_items is not None and combined.total_files >= max_items:
                logger.info(f"Max items ({max_items}) reached, stopping drain")
                break

            # Process available files in parallel using the worker pool
            actual_workers = min(num_workers, len(input_files))
            with ExecutorClass(max_workers=actual_workers) as executor:
                future_to_file = {}
                for f in input_files:
                    if use_process_helper:
                        fut = executor.submit(
                            _run_single_file,
                            str(f),
                            str(self.config.output_dir),
                            config_dict,
                            self._dictionary_path,
                        )
                    else:
                        fut = executor.submit(self._process_single_file, f)
                    future_to_file[fut] = f

                for future in as_completed(future_to_file):
                    filepath = future_to_file[future]
                    try:
                        file_result = future.result()
                    except Exception as e:
                        file_result = {"file": str(filepath), "success": False, "error": str(e)}
                        logger.exception(f"Failed to process {filepath}")

                    if file_result.get("success"):
                        combined.processed_files += 1
                        combined.total_words += file_result.get("total_words", 0)
                        combined.corrected_words += file_result.get("corrected_count", 0)
                        combined.auto_accepted += file_result.get("auto_accepted", 0)
                        combined.flagged_for_review += file_result.get("flagged_count", 0)
                        # Save results (only for ThreadPoolExecutor; ProcessPool saves inline)
                        if not self.config.use_processes:
                            self._save_results(filepath, file_result)
                        # Move processed file to avoid reprocessing
                        processed_dir = self.config.input_dir / "processed"
                        processed_dir.mkdir(exist_ok=True)
                        try:
                            filepath.rename(processed_dir / filepath.name)
                        except OSError:
                            logger.warning(f"Could not move {filepath} to processed/")
                    else:
                        combined.failed_files += 1
                        combined.errors.append({
                            "file": str(filepath),
                            "error": file_result.get("error", "Unknown error"),
                        })

                    combined.total_files += 1
                    logger.info(
                        f"[drain] Processed {filepath.name} — "
                        f"{file_result.get('total_words', 0)} words, "
                        f"{file_result.get('corrected_count', 0)} corrected"
                    )

            # Brief pause before next poll
            time.sleep(poll_interval)

        combined.end_time = time.time()
        return combined
