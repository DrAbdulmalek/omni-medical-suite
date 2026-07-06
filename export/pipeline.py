"""
AI Fuel Engine - Export Pipeline

Unified export orchestrator that routes classified chunks to the
appropriate exporter based on the requested format.  Supports
multi-format exports and automatic report generation.

Usage::

    pipeline = ExportPipeline()
    path = pipeline.export(chunks, format="jsonl", output_path="output.jsonl")
    paths = pipeline.export_multi_format(chunks, formats=["jsonl", "csv"])
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.schemas import ClassifiedChunk
from export.csv_exporter import CSVExporter
from export.jsonl_exporter import JSONLExporter
from export.parquet_exporter import ParquetExporter
from export.rag_exporter import RAGExporter

logger = logging.getLogger(__name__)

# Map of format names to exporter classes
_FORMAT_REGISTRY = {
    "jsonl": JSONLExporter,
    "parquet": ParquetExporter,
    "rag": RAGExporter,
    "csv": CSVExporter,
}

# File extension mapping
_FORMAT_EXTENSIONS = {
    "jsonl": ".jsonl",
    "parquet": ".parquet",
    "csv": ".csv",
}

# Default multi-format list when none is specified
_DEFAULT_FORMATS = ["jsonl", "csv"]


class ExportPipeline:
    """Unified export pipeline supporting multiple formats.

    Centralises export logic so that downstream code does not need to
    know about individual exporter classes.  Simply specify a format
    string and the pipeline routes to the correct exporter.

    Args:
        config: Optional :class:`AIFuelConfig` for default settings
            (``export_format``, ``output_dir``, ``semantic_model_name``).
    """

    def __init__(self, config: Any = None) -> None:
        """Initialise the export pipeline.

        Args:
            config: Optional configuration object.  Extracted fields:
                - ``export_format`` (str) – default export format.
                - ``output_dir`` (str) – default output directory.
                - ``semantic_model_name`` (str) – model for RAG embeddings.
        """
        self.config = config

        # Resolve defaults from config or fallback
        if config is not None:
            self._default_format = getattr(config, "export_format", "jsonl")
            self._default_output_dir = getattr(config, "output_dir", "./datasets")
            self._semantic_model = getattr(
                config, "semantic_model_name",
                "paraphrase-multilingual-mpnet-base-v2",
            )
        else:
            self._default_format = "jsonl"
            self._default_output_dir = "./datasets"
            self._semantic_model = "paraphrase-multilingual-mpnet-base-v2"

        # Pre-create exporters (thread-safe, stateless)
        self._jsonl_exporter = JSONLExporter()
        self._csv_exporter = CSVExporter()

        # Lazily initialised (may raise if dependencies missing)
        self._parquet_exporter: Optional[ParquetExporter] = None
        self._rag_exporter: Optional[RAGExporter] = None

        self._exports_completed: int = 0

        logger.info(
            "ExportPipeline initialised (default_format=%s, output_dir=%s).",
            self._default_format,
            self._default_output_dir,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(
        self,
        chunks: List[ClassifiedChunk],
        format: str = "jsonl",
        output_path: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Export chunks in a specified format.

        Routes to the appropriate exporter based on the *format* argument.

        Args:
            chunks: List of :class:`ClassifiedChunk` objects.
            format: Target format.  One of: ``jsonl``, ``parquet``,
                ``rag``, ``csv``.
            output_path: Destination path.  If ``None``, auto-generates
                a path in the configured output directory.
            **kwargs: Additional keyword arguments forwarded to the
                underlying exporter (e.g. ``compression``, ``encoding``).

        Returns:
            Absolute path to the exported file or directory.

        Raises:
            ValueError: If *format* is unsupported or *chunks* is empty.
            RuntimeError: If a required dependency is missing.
        """
        format = format.lower().strip()
        if format not in _FORMAT_REGISTRY:
            raise ValueError(
                f"Unsupported format '{format}'. "
                f"Supported: {list(_FORMAT_REGISTRY.keys())}"
            )

        if not chunks:
            raise ValueError("No chunks to export.")

        # Auto-generate output path if not specified
        if output_path is None:
            output_path = self._auto_output_path(format, len(chunks))

        output_path = os.path.abspath(output_path)

        logger.info(
            "Exporting %d chunks to %s (format=%s).",
            len(chunks),
            output_path,
            format,
        )

        start_time = time.time()

        if format == "jsonl":
            result = self._jsonl_exporter.export(chunks, output_path, **kwargs)
        elif format == "csv":
            result = self._csv_exporter.export(chunks, output_path, **kwargs)
        elif format == "parquet":
            result = self._get_parquet_exporter().export(chunks, output_path, **kwargs)
        elif format == "rag":
            result = self._get_rag_exporter().export(chunks, output_path, **kwargs)
        else:
            raise ValueError(f"Unhandled format: {format}")

        elapsed = time.time() - start_time
        self._exports_completed += 1

        logger.info(
            "Export complete: %s (%d chunks, %.2fs).",
            output_path,
            len(chunks),
            elapsed,
        )
        return result

    def export_multi_format(
        self,
        chunks: List[ClassifiedChunk],
        formats: Optional[List[str]] = None,
        output_dir: Optional[str] = None,
    ) -> Dict[str, str]:
        """Export in multiple formats simultaneously.

        Args:
            chunks: List of :class:`ClassifiedChunk` objects.
            formats: List of format strings to export.  Defaults to
                ``["jsonl", "csv"]``.
            output_dir: Directory for all output files.  If ``None``,
                uses the configured default output directory.

        Returns:
            Dictionary mapping format name → output file path.

        Raises:
            ValueError: If any requested format is unsupported.
        """
        formats = formats or _DEFAULT_FORMATS
        output_dir = output_dir or self._default_output_dir

        # Validate formats
        for fmt in formats:
            if fmt not in _FORMAT_REGISTRY:
                raise ValueError(
                    f"Unsupported format '{fmt}' in multi-format export."
                )

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        results: Dict[str, str] = {}

        for fmt in formats:
            ext = _FORMAT_EXTENSIONS.get(fmt, "")
            filename = f"ai_fuel_export_{len(chunks)}_chunks{ext}"
            path = os.path.join(output_dir, filename)

            try:
                result_path = self.export(
                    chunks, format=fmt, output_path=path
                )
                results[fmt] = result_path
            except Exception as exc:
                logger.error(
                    "Failed to export format '%s': %s", fmt, exc
                )
                results[fmt] = f"ERROR: {exc}"

        logger.info(
            "Multi-format export: %d/%d formats succeeded.",
            sum(1 for v in results.values() if not v.startswith("ERROR")),
            len(formats),
        )
        return results

    def generate_report(
        self,
        chunks: List[ClassifiedChunk],
        output_path: Optional[str] = None,
    ) -> str:
        """Generate a processing report as a JSON file.

        The report contains aggregate statistics: total chunks, category
        distribution, confidence metrics, language breakdown, and source
        file summary.

        Args:
            chunks: List of :class:`ClassifiedChunk` objects.
            output_path: Path for the report file.  Defaults to
                ``<output_dir>/processing_report.json``.

        Returns:
            Absolute path to the report file.
        """
        if not chunks:
            logger.warning("No chunks; generating empty report.")

        if output_path is None:
            output_dir = self._default_output_dir
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            output_path = os.path.join(
                output_dir,
                f"processing_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json",
            )

        output_path = os.path.abspath(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # ── Compute statistics ────────────────────────────────────────
        total = len(chunks)

        # Category distribution
        cat_dist: Dict[str, int] = Counter(
            c.classification.category for c in chunks
        )

        # Confidence statistics
        confidences = [c.classification.confidence for c in chunks]
        avg_confidence = sum(confidences) / total if total else 0.0
        min_confidence = min(confidences) if confidences else 0.0
        max_confidence = max(confidences) if confidences else 0.0

        # Low-confidence count (< 0.7)
        low_conf_count = sum(1 for c in confidences if c < 0.7)

        # Language breakdown
        lang_dist: Dict[str, int] = Counter(
            c.chunk.language.value for c in chunks
        )

        # Classification method breakdown
        method_dist: Dict[str, int] = Counter(
            c.classification.method.value for c in chunks
        )

        # Source file breakdown
        source_dist: Dict[str, int] = Counter(
            c.chunk.source_file or "unknown" for c in chunks
        )

        # Token statistics
        total_tokens = sum(c.chunk.token_count for c in chunks)
        avg_tokens = total_tokens / total if total else 0

        # Subcategory counts
        subcat_dist: Dict[str, int] = Counter()
        for c in chunks:
            subcat = c.classification.subcategory
            if subcat:
                key = f"{c.classification.category}/{subcat}"
                subcat_dist[key] += 1

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "total_chunks": total,
                "total_tokens": total_tokens,
                "avg_tokens_per_chunk": round(avg_tokens, 2),
                "avg_confidence": round(avg_confidence, 4),
                "min_confidence": round(min_confidence, 4),
                "max_confidence": round(max_confidence, 4),
                "low_confidence_count": low_conf_count,
                "unique_categories": len(cat_dist),
                "unique_sources": len(source_dist),
            },
            "category_distribution": dict(cat_dist),
            "subcategory_distribution": dict(subcat_dist),
            "language_distribution": dict(lang_dist),
            "method_distribution": dict(method_dist),
            "source_distribution": dict(source_dist),
        }

        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2, ensure_ascii=False)

        logger.info("Processing report saved to %s", output_path)
        return output_path

    def get_stats(self) -> Dict:
        """Return pipeline statistics.

        Returns:
            Dictionary with ``exports_completed``, ``default_format``,
            and ``default_output_dir``.
        """
        return {
            "exports_completed": self._exports_completed,
            "default_format": self._default_format,
            "default_output_dir": self._default_output_dir,
            "semantic_model": self._semantic_model,
            "supported_formats": list(_FORMAT_REGISTRY.keys()),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _auto_output_path(self, fmt: str, chunk_count: int) -> str:
        """Generate an automatic output path based on format and timestamp."""
        ext = _FORMAT_EXTENSIONS.get(fmt, "")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"ai_fuel_export_{chunk_count}chunks_{timestamp}{ext}"
        return os.path.join(self._default_output_dir, filename)

    def _get_parquet_exporter(self) -> ParquetExporter:
        """Lazily create and return the Parquet exporter."""
        if self._parquet_exporter is None:
            try:
                self._parquet_exporter = ParquetExporter()
            except RuntimeError as exc:
                raise RuntimeError(
                    f"Parquet export unavailable: {exc}"
                ) from exc
        return self._parquet_exporter

    def _get_rag_exporter(self) -> RAGExporter:
        """Lazily create and return the RAG exporter."""
        if self._rag_exporter is None:
            self._rag_exporter = RAGExporter(model_name=self._semantic_model)
        return self._rag_exporter

    def __repr__(self) -> str:
        return (
            f"ExportPipeline(exports={self._exports_completed}, "
            f"default_format={self._default_format!r})"
        )
