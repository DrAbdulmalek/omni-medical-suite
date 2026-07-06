"""
AI Fuel Engine — Main Orchestrator

The :class:`AIFuelEngine` class is the single entry-point for the entire
processing pipeline.  It coordinates PHI protection, text normalization,
segmentation, classification, deduplication, and export in a configurable,
lazy-initialized workflow.

Typical usage::

    engine = AIFuelEngine(config=AIFuelConfig.from_env())

    # Process a single piece of text
    result = engine.process_text(raw_text, source_file="note.txt")

    # Process a file
    result = engine.process_file("/data/reports/report.pdf")

    # Process a directory
    results = engine.process_directory("/data/reports/", extensions=[".txt", ".pdf"])

    # Export
    engine.export(results, format="jsonl", output_path="/data/output/corpus.jsonl")
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional

from core.config import AIFuelConfig
from core.schemas import (
    ChunkType,
    ClassificationMethod,
    ClassifiedChunk,
    ClassificationResult,
    DedupResult,
    DocumentResult,
    Language,
    ProcessingStats,
    TextChunk,
)
from core.utils import (
    calculate_similarity,
    chunk_overlap_text,
    clean_ocr_artifacts,
    compute_hash,
    count_tokens,
    detect_language,
    format_processing_time,
    normalize_arabic,
    safe_filename,
    setup_logging,
)
from core.phi_protection import PHIMasker
from core.metrics import (
    avg_confidence_score,
    chunks_created,
    classification_operations,
    dedup_duplicates_found,
    dedup_rate,
    documents_processed,
    export_operations,
    phi_detections,
    processing_duration,
)

logger = logging.getLogger("ai_fuel_engine")

# ======================================================================
# Custom Exceptions
# ======================================================================


class AIFuelEngineError(Exception):
    """Base exception for all AI Fuel Engine errors."""


class ConfigurationError(AIFuelEngineError):
    """Raised when the configuration is invalid."""


class ProcessingError(AIFuelEngineError):
    """Raised when document processing fails."""


class ExportError(AIFuelEngineError):
    """Raised when an export operation fails."""


class SegmentationError(ProcessingError):
    """Raised when text segmentation fails."""


class ClassificationError(ProcessingError):
    """Raised when text classification fails."""


# ======================================================================
# Default File Extensions
# ======================================================================

DEFAULT_EXTENSIONS: FrozenSet[str] = frozenset({
    ".txt", ".md", ".csv", ".json", ".jsonl",
    ".pdf", ".docx", ".doc", ".rtf", ".html", ".htm",
})


# ======================================================================
# AIFuelEngine
# ======================================================================


class AIFuelEngine:
    """High-level orchestrator for the AI Fuel Engine pipeline.

    Components are **lazy-initialized** — they are created on first use so
    that importing the class is cheap and configuration can be adjusted
    between construction and the first ``process_*`` call.

    Args:
        config: Optional :class:`AIFuelConfig`.  If ``None``, the default
            configuration is used.

    Example::

        engine = AIFuelEngine(config=AIFuelConfig(max_tokens=2000))
        doc_result = engine.process_text("Long Arabic/English medical text...")
        engine.export([doc_result], format="rag")
    """

    def __init__(self, config: Optional[AIFuelConfig] = None) -> None:
        self.config = config or AIFuelConfig()
        self._validate_config()

        # Lazy-initialized components
        self._phi_protector: Optional[PHIMasker] = None

        # Internal state
        self._seen_hashes: Dict[str, str] = {}  # hash → chunk_id (for dedup)
        self._aggregate_stats = ProcessingStats()
        self._initialized = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def phi_protector(self) -> PHIMasker:
        """Lazy-accessor for the :class:`PHIMasker` component."""
        if self._phi_protector is None:
            self._phi_protector = PHIMasker(
                masking_mode=self.config.phi_masking_mode,
                enabled=self.config.phi_protection_enabled,
            )
        return self._phi_protector

    # ------------------------------------------------------------------
    # Public API — Processing
    # ------------------------------------------------------------------

    def process_text(
        self,
        text: str,
        source_file: Optional[str] = None,
    ) -> DocumentResult:
        """Process raw text through the full pipeline.

        The pipeline steps are executed in order:

        1. **PHI Detection & Protection** — Detect and mask/tag/remove PHI.
        2. **Text Normalization** — Clean OCR artifacts, normalize Arabic.
        3. **Segmentation** — Split into token-bounded chunks with overlap.
        4. **Classification** — Assign categories via keyword matching.
        5. **Deduplication** — Remove exact and near-duplicate chunks.
        6. **Statistics Compilation** — Aggregate processing metrics.

        Args:
            text: Raw input text.
            source_file: Optional source file name for provenance tracking.

        Returns:
            A :class:`DocumentResult` containing classified chunks and stats.

        Raises:
            ProcessingError: If the pipeline encounters an unrecoverable error.
        """
        if not text or not text.strip():
            raise ProcessingError("Cannot process empty text")

        start_time = time.monotonic()
        source = source_file or "<string>"
        logger.info("Processing text from %s (%d chars)", source, len(text))

        try:
            # 1. PHI Detection & Protection
            protected_text, phi_count = self._protect_phi(text, source)

            # 2. Text Normalization
            normalized_text = self._normalize_text(protected_text)

            # 3. Segmentation
            chunks = self._segment(normalized_text, source_file=source)

            # 4. Classification
            classified_chunks = self._classify(chunks)

            # 5. Deduplication
            deduped_chunks = self._deduplicate(classified_chunks)

            # 6. Statistics
            elapsed = time.monotonic() - start_time
            stats = self._build_stats(
                source_file=source,
                chunks=chunks,
                deduped_chunks=deduped_chunks,
                elapsed=elapsed,
                phi_count=phi_count,
            )

            result = DocumentResult(
                source_file=source,
                chunks=deduped_chunks,
                stats=stats,
            )

            # Record metrics
            documents_processed.labels(
                source_type="text", status="success"
            ).inc()
            processing_duration.labels(source_type="text").observe(elapsed)

            logger.info(
                "Finished processing %s: %d chunks in %s",
                source,
                stats.total_chunks,
                format_processing_time(elapsed),
            )
            return result

        except ProcessingError:
            documents_processed.labels(
                source_type="text", status="error"
            ).inc()
            raise
        except Exception as exc:
            documents_processed.labels(
                source_type="text", status="error"
            ).inc()
            raise ProcessingError(
                f"Unexpected error processing text from {source}: {exc}"
            ) from exc

    def process_file(self, file_path: str) -> DocumentResult:
        """Read a file and process its contents through the full pipeline.

        Supports plain-text files (``.txt``, ``.md``, ``.csv``, ``.json``).
        For binary formats (``.pdf``, ``.docx``), the raw bytes are decoded
        with a best-effort strategy.

        Args:
            file_path: Path to the file to process.

        Returns:
            A :class:`DocumentResult` with classified chunks and stats.

        Raises:
            ProcessingError: If the file cannot be read or processed.
            FileNotFoundError: If the file does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        logger.info("Processing file: %s", file_path)
        text = self._read_file(path)
        return self.process_text(text, source_file=str(path))

    def process_directory(
        self,
        dir_path: str,
        extensions: Optional[List[str]] = None,
    ) -> List[DocumentResult]:
        """Process all supported files in a directory.

        Files are processed sequentially.  Processing continues even if
        individual files fail — errors are logged and the file is skipped.

        Args:
            dir_path: Path to the directory.
            extensions: Optional list of file extensions to include
                (e.g. ``[".txt", ".pdf"]``).  Defaults to :data:`DEFAULT_EXTENSIONS`.

        Returns:
            A list of :class:`DocumentResult` objects, one per successfully
            processed file.

        Raises:
            FileNotFoundError: If the directory does not exist.
        """
        dir_path_obj = Path(dir_path)
        if not dir_path_obj.is_dir():
            raise FileNotFoundError(f"Directory not found: {dir_path}")

        ext_set = frozenset(e.lower() for e in (extensions or list(DEFAULT_EXTENSIONS)))
        results: List[DocumentResult] = []

        files = sorted(
            p for p in dir_path_obj.rglob("*")
            if p.is_file() and p.suffix.lower() in ext_set
        )

        logger.info(
            "Processing directory %s: found %d matching files",
            dir_path,
            len(files),
        )

        for file_path in files:
            try:
                result = self.process_file(str(file_path))
                results.append(result)
            except (ProcessingError, FileNotFoundError) as exc:
                logger.error("Skipping %s: %s", file_path, exc)
                documents_processed.labels(
                    source_type="file", status="error"
                ).inc()

        logger.info(
            "Directory processing complete: %d/%d files succeeded",
            len(results),
            len(files),
        )
        return results

    # ------------------------------------------------------------------
    # Public API — Export
    # ------------------------------------------------------------------

    def export(
        self,
        results: List[DocumentResult],
        format: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """Export processed results to a file.

        Supported formats:

        - ``jsonl``: One JSON object per line (default).
        - ``csv``: Tabular export of chunk data.

        Args:
            results: List of :class:`DocumentResult` objects to export.
            format: Override export format.  Defaults to :attr:`AIFuelConfig.export_format`.
            output_path: Override output file path.  Defaults to
                ``{output_dir}/ai_fuel_export.{ext}``.

        Returns:
            The path to the exported file.

        Raises:
            ExportError: If the export fails.
        """
        fmt = format or self.config.export_format

        if not results:
            raise ExportError("No results to export")

        # Determine output path
        if output_path is None:
            out_dir = Path(self.config.output_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = str(out_dir / f"ai_fuel_export_{timestamp}.{fmt}")

        try:
            if fmt == "jsonl":
                self._export_jsonl(results, output_path)
            elif fmt == "csv":
                self._export_csv(results, output_path)
            elif fmt in ("parquet", "rag"):
                # For parquet/rag, export as JSONL with a note
                logger.warning(
                    "Format '%s' export uses JSONL fallback — "
                    "install pyarrow for native parquet support",
                    fmt,
                )
                self._export_jsonl(results, output_path)
            else:
                raise ExportError(f"Unsupported export format: {fmt}")

            export_operations.labels(format=fmt, status="success").inc()
            logger.info("Exported %d results to %s", len(results), output_path)
            return output_path

        except ExportError:
            export_operations.labels(format=fmt, status="error").inc()
            raise
        except Exception as exc:
            export_operations.labels(format=fmt, status="error").inc()
            raise ExportError(f"Export failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Public API — Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> ProcessingStats:
        """Return aggregate processing statistics across all runs.

        Returns:
            A :class:`ProcessingStats` snapshot.
        """
        return self._aggregate_stats.model_copy(deep=True)

    def reset_stats(self) -> None:
        """Reset all aggregate processing statistics to zero."""
        self._aggregate_stats = ProcessingStats()
        self._seen_hashes.clear()
        logger.info("Aggregate stats reset")

    # ------------------------------------------------------------------
    # Pipeline Steps (private)
    # ------------------------------------------------------------------

    def _protect_phi(
        self, text: str, source: str
    ) -> tuple[str, int]:
        """Run PHI protection on text.

        Returns:
            Tuple of (protected_text, phi_detection_count).
        """
        if not self.config.phi_protection_enabled:
            return text, 0

        detections = self.phi_protector.detect(text, source_file=source)
        protected_text = self.phi_protector.mask(text, source_file=source)

        for det in detections:
            phi_detections.labels(
                phi_type=det.phi_type,
                mode=self.config.phi_masking_mode,
            ).inc()

        logger.info(
            "PHI protection: %d detection(s) in %s",
            len(detections),
            source,
        )
        return protected_text, len(detections)

    def _normalize_text(self, text: str) -> str:
        """Apply text normalization: OCR cleaning and Arabic normalization."""
        cleaned = clean_ocr_artifacts(text)
        normalized = normalize_arabic(cleaned)
        return normalized

    def _segment(
        self,
        text: str,
        source_file: Optional[str] = None,
    ) -> List[TextChunk]:
        """Segment text into token-bounded chunks with overlap.

        Uses a simple sliding-window approach based on the configuration's
        ``max_tokens`` and ``overlap_tokens`` settings.

        Args:
            text: Normalized input text.
            source_file: Optional source file name.

        Returns:
            A list of :class:`TextChunk` objects.
        """
        chunks: List[TextChunk] = []
        total_tokens = count_tokens(text)
        max_tok = self.config.max_tokens
        overlap_tok = self.config.overlap_tokens
        min_tok = self.config.min_chunk_tokens

        if total_tokens <= max_tok:
            # Text fits in a single chunk
            chunk = self._make_chunk(text, 0, total_tokens, source_file)
            chunks.append(chunk)
            chunks_created.labels(chunk_type="size_based").inc()
            return chunks

        # Split by sentences/paragraphs first for cleaner boundaries
        sentences = self._split_sentences(text)
        current_text = ""
        current_tokens = 0
        start_token = 0

        for sentence in sentences:
            sentence_tokens = count_tokens(sentence)

            if current_tokens + sentence_tokens > max_tok and current_tokens >= min_tok:
                # Emit current chunk
                chunk = self._make_chunk(
                    current_text.strip(), start_token, start_token + current_tokens, source_file
                )
                if chunk.token_count >= min_tok:
                    chunks.append(chunk)
                    chunks_created.labels(chunk_type="size_based").inc()

                # Start new chunk with overlap from previous
                overlap_text = chunk_overlap_text(current_text, overlap_tok * 4)
                overlap_token_count = count_tokens(overlap_text)
                current_text = overlap_text + " " + sentence
                start_token = start_token + current_tokens - overlap_token_count
                current_tokens = overlap_token_count + sentence_tokens
            else:
                current_text += " " + sentence if current_text else sentence
                current_tokens += sentence_tokens

        # Flush remaining text
        if current_text.strip() and count_tokens(current_text.strip()) >= min_tok:
            chunk = self._make_chunk(
                current_text.strip(), start_token, start_token + current_tokens, source_file
            )
            chunks.append(chunk)
            chunks_created.labels(chunk_type="size_based").inc()

        logger.info("Segmented into %d chunks (total tokens: %d)", len(chunks), total_tokens)
        return chunks

    def _make_chunk(
        self,
        text: str,
        start_token: int,
        end_token: int,
        source_file: Optional[str] = None,
    ) -> TextChunk:
        """Create a :class:`TextChunk` with computed metadata."""
        language_str = detect_language(text)
        language = Language(language_str) if Language(language_str) else Language.UNKNOWN

        return TextChunk(
            text=text,
            chunk_type=ChunkType.SIZE_BASED,
            start_token=start_token,
            end_token=end_token,
            token_count=count_tokens(text),
            char_count=len(text),
            word_count=len(text.split()),
            language=language,
            source_file=source_file,
        )

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split text into sentences using common delimiters.

        Handles Arabic (٫), English (.), and mixed punctuation.
        """
        # Split on sentence-ending punctuation while keeping the delimiter
        parts = []
        for delimiter in ["٫", ".", "!", "?", "\n"]:
            new_parts = []
            for part in (parts if parts else [text]):
                subparts = part.split(delimiter)
                for i, sub in enumerate(subparts):
                    if sub.strip():
                        if i < len(subparts) - 1:
                            new_parts.append(sub.strip() + delimiter)
                        else:
                            if sub.strip():
                                new_parts.append(sub.strip())
            parts = new_parts

        return parts

    def _classify(self, chunks: List[TextChunk]) -> List[ClassifiedChunk]:
        """Classify each chunk using keyword-based matching.

        In this Phase 1 implementation, classification is keyword-based.
        Future phases will integrate semantic models and LLM-based
        classification.

        Args:
            chunks: List of :class:`TextChunk` objects.

        Returns:
            A list of :class:`ClassifiedChunk` objects.
        """
        classified: List[ClassifiedChunk] = []
        keyword_rules = self._get_keyword_rules()

        for chunk in chunks:
            start_time = time.monotonic()
            text_lower = chunk.text.lower()

            best_category = "general"
            best_subcategory = None
            best_confidence = 0.3  # baseline confidence
            alternatives: List[Dict[str, str | float]] = []

            for category, sub_rules in keyword_rules.items():
                for subcategory, keywords in sub_rules.items():
                    match_count = sum(1 for kw in keywords if kw in text_lower)
                    if match_count > 0:
                        confidence = min(
                            0.3 + (match_count / len(keywords)) * 0.7,
                            1.0,
                        )
                        alternatives.append({
                            "category": category,
                            "subcategory": subcategory,
                            "confidence": round(confidence, 4),
                        })
                        if confidence > best_confidence:
                            best_confidence = confidence
                            best_category = category
                            best_subcategory = subcategory

            # Sort alternatives by confidence descending
            alternatives.sort(key=lambda a: a["confidence"], reverse=True)

            elapsed_ms = (time.monotonic() - start_time) * 1000

            classification = ClassificationResult(
                chunk_id=chunk.id,
                category=best_category,
                subcategory=best_subcategory,
                confidence=round(best_confidence, 4),
                method=ClassificationMethod.KEYWORD,
                alternatives=alternatives[:5],  # Keep top 5
                processing_time_ms=round(elapsed_ms, 2),
            )

            classified.append(ClassifiedChunk(chunk=chunk, classification=classification))

            classification_operations.labels(
                method="keyword", category=best_category
            ).inc()

        logger.info("Classified %d chunks via keyword matching", len(classified))
        return classified

    def _deduplicate(
        self, classified_chunks: List[ClassifiedChunk]
    ) -> List[ClassifiedChunk]:
        """Remove duplicate chunks based on exact hashing.

        Semantic deduplication is planned for a future phase.

        Args:
            classified_chunks: List of classified chunks.

        Returns:
            Deduplicated list of :class:`ClassifiedChunk` objects.
        """
        if not self.config.dedup_enabled:
            return classified_chunks

        seen: Dict[str, str] = {}  # hash → chunk_id
        unique: List[ClassifiedChunk] = []
        duplicates_found = 0

        for cc in classified_chunks:
            text_hash = compute_hash(cc.chunk.text, algorithm="md5")

            if text_hash in seen:
                duplicates_found += 1
                dedup_duplicates_found.labels(method="exact").inc()
                logger.debug(
                    "Duplicate chunk %s (of %s) removed",
                    cc.chunk.id,
                    seen[text_hash],
                )
            else:
                seen[text_hash] = cc.chunk.id
                self._seen_hashes[text_hash] = cc.chunk.id
                unique.append(cc)

        total = len(classified_chunks)
        if total > 0:
            rate = duplicates_found / total
            dedup_rate.labels(method="exact").set(round(rate, 4))

        logger.info(
            "Deduplication: %d/%d duplicates removed",
            duplicates_found,
            total,
        )
        return unique

    def _build_stats(
        self,
        source_file: str,
        chunks: List[TextChunk],
        deduped_chunks: List[ClassifiedChunk],
        elapsed: float,
        phi_count: int,
    ) -> ProcessingStats:
        """Build a :class:`ProcessingStats` object for a single document."""
        # Classification distribution
        dist: Dict[str, int] = {}
        total_confidence = 0.0

        for cc in deduped_chunks:
            cat = cc.classification.category
            dist[cat] = dist.get(cat, 0) + 1
            total_confidence += cc.classification.confidence

        avg_conf = (
            round(total_confidence / len(deduped_chunks), 4)
            if deduped_chunks
            else 0.0
        )

        stats = ProcessingStats(
            total_documents=1,
            total_pages=0,
            total_chunks=len(chunks),
            chunks_after_dedup=len(deduped_chunks),
            classification_distribution=dist,
            processing_time_seconds=round(elapsed, 3),
            avg_confidence=avg_conf,
            phi_detections=phi_count,
        )

        # Update aggregate
        self._aggregate_stats.total_documents += stats.total_documents
        self._aggregate_stats.total_chunks += stats.total_chunks
        self._aggregate_stats.chunks_after_dedup += stats.chunks_after_dedup
        self._aggregate_stats.processing_time_seconds += stats.processing_time_seconds
        self._aggregate_stats.phi_detections += stats.phi_detections

        for cat, count in dist.items():
            self._aggregate_stats.classification_distribution[cat] = (
                self._aggregate_stats.classification_distribution.get(cat, 0) + count
            )

        # Update Prometheus gauge
        if deduped_chunks:
            avg_confidence_score.set(avg_conf)

        return stats

    # ------------------------------------------------------------------
    # Keyword Classification Rules
    # ------------------------------------------------------------------

    @staticmethod
    def _get_keyword_rules() -> Dict[str, Dict[str, List[str]]]:
        """Return keyword-based classification rules.

        Each top-level key is a **category**.  Nested keys are
        **subcategories** with their associated keyword lists.

        Returns:
            A nested dictionary of classification rules.
        """
        return {
            "radiology": {
                "general": [
                    "x-ray", "xray", "radiograph", "imaging", "ct scan",
                    "mri", "ultrasound", "sonograph", "fluoroscopy",
                    "الأشعة", "تصوير", "رنين مغناطيسي", "موجات فوق صوتية",
                    "أشعة سينية", "صورة طبقية",
                ],
                "report": [
                    "finding", "impression", "recommendation", "conclusion",
                    "النتيجة", "التوصية", "الاستنتاج", "الموجودات",
                ],
                "interventional": [
                    "biopsy", "drainage", "angiography", "embolization",
                    "خزعة", "تصوير الأوعية", "انصمام",
                ],
            },
            "laboratory": {
                "general": [
                    "lab result", "blood test", "urinalysis", "culture",
                    "biopsy result", "pathology", "histology",
                    "نتيجة مخبرية", "تحليل دم", "تحليل بول",
                    "زراعة", "علم الأمراض", "فحص نسجي",
                ],
                "chemistry": [
                    "glucose", "cholesterol", "triglyceride", "creatinine",
                    "bilirubin", "electrolyte", "sodium", "potassium",
                    "الجلوكوز", "الكوليسترول", "الكرياتينين",
                    "الصوديوم", "البوتاسيوم",
                ],
                "hematology": [
                    "hemoglobin", "wbc", "rbc", "platelet", "hematocrit",
                    "cbc", "complete blood count", "differential",
                    "الهيموغلوبين", "خلايا الدم البيضاء", "خلايا الدم الحمراء",
                    "الصفيحات", "عداد دم شامل",
                ],
            },
            "pharmacy": {
                "prescription": [
                    "prescription", "medication", "dosage", "frequency",
                    "drug", "tablet", "capsule", "injection", "syrup",
                    "وصفة طبية", "دواء", "جرعة", "تكرار",
                    "قرص", "كبسولة", "حقن", "شراب",
                ],
                "interaction": [
                    "drug interaction", "contraindication", "adverse effect",
                    "side effect", "allergy", "interaction",
                    "تأثير دوائي", "مضاد استطباب", "تأثير جانبي",
                    "حساسية", "تداخل",
                ],
            },
            "clinical_notes": {
                "general": [
                    "chief complaint", "history of present illness",
                    "physical exam", "assessment", "plan",
                    "الشكوى الرئيسية", "تاريخ المرض الحالي",
                    "الفحص السريري", "التقييم", "الخطة العلاجية",
                ],
                "progress_note": [
                    "progress note", "daily note", "rounds",
                    "ملاحظة تطور", "ملاحظة يومية", "جولة",
                ],
                "discharge_summary": [
                    "discharge summary", "discharge instructions",
                    "follow up", "disposition",
                    "ملخص خروج", "تعليمات الخروج", "متابعة",
                ],
            },
            "operative": {
                "general": [
                    "surgery", "operative", "procedure", "operation",
                    "incision", "closure", "anesthesia", "surgical",
                    "عملية جراحية", "إجراء", "جراحة", "شق", "تخدير",
                ],
                "pre_op": [
                    "pre-operative", "preop", "consent", "before surgery",
                    "قبل العملية", "موافقة", "تحضير",
                ],
            },
            "administrative": {
                "general": [
                    "admission", "discharge", "transfer", "referral",
                    "insurance", "authorization", "approval",
                    "دخول", "خروج", "تحويل", "إحالة",
                    "تأمين", "تصريح", "موافقة",
                ],
            },
            "general": {
                "unclassified": [],
            },
        }

    # ------------------------------------------------------------------
    # File I/O Helpers (private)
    # ------------------------------------------------------------------

    @staticmethod
    def _read_file(path: Path) -> str:
        """Read file content with encoding detection fallback.

        Attempts UTF-8 first, then falls back to latin-1 for maximum
        compatibility.

        Args:
            path: Path to the file.

        Returns:
            Decoded text content.

        Raises:
            ProcessingError: If the file cannot be decoded.
        """
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return path.read_text(encoding=encoding)
            except (UnicodeDecodeError, LookupError):
                continue

        raise ProcessingError(f"Cannot decode file: {path}")

    # ------------------------------------------------------------------
    # Export Helpers (private)
    # ------------------------------------------------------------------

    @staticmethod
    def _export_jsonl(results: List[DocumentResult], output_path: str) -> None:
        """Export results as JSONL (one JSON object per line).

        Each line contains the classified chunks from one document.

        Args:
            results: List of document results.
            output_path: Path to write the JSONL file.
        """
        import json

        out_dir = Path(output_path).parent
        out_dir.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as fh:
            for doc_result in results:
                for cc in doc_result.chunks:
                    record = {
                        "chunk_id": cc.chunk.id,
                        "text": cc.chunk.text,
                        "category": cc.classification.category,
                        "subcategory": cc.classification.subcategory,
                        "confidence": cc.classification.confidence,
                        "method": cc.classification.method.value,
                        "language": cc.chunk.language.value,
                        "token_count": cc.chunk.token_count,
                        "source_file": cc.chunk.source_file,
                    }
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _export_csv(results: List[DocumentResult], output_path: str) -> None:
        """Export results as a CSV file.

        Columns: chunk_id, text, category, subcategory, confidence,
        method, language, token_count, source_file.

        Args:
            results: List of document results.
            output_path: Path to write the CSV file.
        """
        import csv

        out_dir = Path(output_path).parent
        out_dir.mkdir(parents=True, exist_ok=True)

        headers = [
            "chunk_id", "text", "category", "subcategory",
            "confidence", "method", "language", "token_count", "source_file",
        ]

        with open(output_path, "w", encoding="utf-8-sig", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers)
            writer.writeheader()

            for doc_result in results:
                for cc in doc_result.chunks:
                    writer.writerow({
                        "chunk_id": cc.chunk.id,
                        "text": cc.chunk.text,
                        "category": cc.classification.category,
                        "subcategory": cc.classification.subcategory or "",
                        "confidence": cc.classification.confidence,
                        "method": cc.classification.method.value,
                        "language": cc.chunk.language.value,
                        "token_count": cc.chunk.token_count,
                        "source_file": cc.chunk.source_file or "",
                    })

    # ------------------------------------------------------------------
    # Configuration Validation (private)
    # ------------------------------------------------------------------

    def _validate_config(self) -> None:
        """Validate the engine configuration on construction."""
        if not isinstance(self.config, AIFuelConfig):
            raise ConfigurationError(
                f"config must be an AIFuelConfig instance, got {type(self.config)}"
            )

    def __repr__(self) -> str:
        return (
            f"AIFuelEngine("
            f"max_tokens={self.config.max_tokens}, "
            f"phi_enabled={self.config.phi_protection_enabled}, "
            f"dedup_enabled={self.config.dedup_enabled}"
            f")"
        )
