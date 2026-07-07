"""
AI Fuel Engine - Parquet Exporter

Exports classified chunks to Apache Parquet format for efficient,
columnar storage and downstream analytics.  Uses **pandas** when
available (preferred for data manipulation), with a fallback to
**pyarrow** directly.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.schemas import ClassifiedChunk

logger = logging.getLogger(__name__)

# Lazy-load detection
_pandas_available = False
_pyarrow_available = False

try:
    import pandas as _pd  # type: ignore[import-untyped]

    _pandas_available = True
except ImportError:  # pragma: no cover
    _pd = None  # type: ignore[assignment]

try:
    import pyarrow as _pa  # type: ignore[import-untyped]

    _pyarrow_available = True
except ImportError:  # pragma: no cover
    _pa = None  # type: ignore[assignment]


class ParquetExporter:
    """Export to Parquet format for efficient storage and analysis.

    Supports multiple compression codecs (snappy, gzip, zstd, lz4).
    Prefers pandas for the conversion but falls back to pyarrow when
    pandas is not installed.

    Attributes:
        default_compression: Compression codec to use when not specified.
    """

    def __init__(self, default_compression: str = "snappy") -> None:
        """Initialise the exporter.

        Args:
            default_compression: Default compression codec.  Supported:
                ``snappy``, ``gzip``, ``zstd``, ``lz4``, ``brotli``,
                ``none``.

        Raises:
            RuntimeError: If neither pandas nor pyarrow is available.
        """
        valid_codecs = {"snappy", "gzip", "zstd", "lz4", "brotli", "none"}
        if default_compression not in valid_codecs:
            raise ValueError(
                f"Invalid compression codec '{default_compression}'. "
                f"Must be one of {valid_codecs}."
            )

        if not _pandas_available and not _pyarrow_available:
            raise RuntimeError(
                "Parquet export requires 'pandas' or 'pyarrow'. "
                "Install with: pip install pandas pyarrow"
            )

        self.default_compression = default_compression
        self._files_exported: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(
        self,
        chunks: List[ClassifiedChunk],
        output_path: str,
        compression: Optional[str] = None,
    ) -> str:
        """Export classified chunks to Parquet.

        Args:
            chunks: List of :class:`ClassifiedChunk` objects.
            output_path: Filesystem path for the output ``.parquet`` file.
            compression: Compression codec override.  Defaults to the
                instance's ``default_compression``.

        Returns:
            Absolute path to the exported file.

        Raises:
            ValueError: If *chunks* is empty.
            RuntimeError: If no suitable writer library is available.
        """
        if not chunks:
            raise ValueError("No chunks to export.")

        compression = compression or self.default_compression
        output_path = os.path.abspath(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        records = [self._chunk_to_dict(c) for c in chunks]

        if _pandas_available:
            self._export_via_pandas(records, output_path, compression)
        elif _pyarrow_available:
            self._export_via_pyarrow(records, output_path, compression)
        else:
            raise RuntimeError(
                "No Parquet writer available. Install pandas or pyarrow."
            )

        self._files_exported += 1
        logger.info(
            "Exported %d records to Parquet (compression=%s): %s",
            len(records),
            compression,
            output_path,
        )
        return output_path

    def get_stats(self) -> Dict:
        """Return exporter statistics.

        Returns:
            Dictionary with ``files_exported`` and ``backend`` info.
        """
        return {
            "files_exported": self._files_exported,
            "default_compression": self.default_compression,
            "backend": "pandas" if _pandas_available else (
                "pyarrow" if _pyarrow_available else "none"
            ),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _chunk_to_dict(chunk: ClassifiedChunk) -> Dict[str, Any]:
        """Convert a :class:`ClassifiedChunk` to a flat dictionary."""
        return {
            "chunk_id": chunk.chunk.id,
            "text": chunk.chunk.text,
            "category": chunk.classification.category,
            "subcategory": chunk.classification.subcategory or "",
            "confidence": chunk.classification.confidence,
            "method": chunk.classification.method.value,
            "token_count": chunk.chunk.token_count,
            "char_count": chunk.chunk.char_count,
            "word_count": chunk.chunk.word_count,
            "language": chunk.chunk.language.value,
            "chunk_type": chunk.chunk.chunk_type.value,
            "source_file": chunk.chunk.source_file or "",
            "source_page": chunk.chunk.source_page or 0,
            "alternatives": str(chunk.classification.alternatives)
            if chunk.classification.alternatives
            else "",
        }

    @staticmethod
    def _export_via_pandas(
        records: List[Dict[str, Any]],
        output_path: str,
        compression: str,
    ) -> None:
        """Write records using pandas DataFrame."""
        df = _pd.DataFrame(records)  # type: ignore[union-attr]
        df.to_parquet(
            output_path,
            engine="pyarrow",
            compression=compression,
            index=False,
        )

    @staticmethod
    def _export_via_pyarrow(
        records: List[Dict[str, Any]],
        output_path: str,
        compression: str,
    ) -> None:
        """Write records using pyarrow directly (no pandas)."""
        # Infer schema from the first record
        table = _pa.table(records)  # type: ignore[union-attr]
        _pa.parquet.write_table(  # type: ignore[union-attr]
            table,
            output_path,
            compression=compression if compression != "none" else None,
        )

    def __repr__(self) -> str:
        return (
            f"ParquetExporter(compression={self.default_compression}, "
            f"files_exported={self._files_exported})"
        )
