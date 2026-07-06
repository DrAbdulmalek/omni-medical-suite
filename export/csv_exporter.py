"""
AI Fuel Engine - CSV Exporter

Exports classified chunks to CSV format with UTF-8 BOM encoding for
broad compatibility.  The BOM marker ensures that Microsoft Excel
(and other tools) correctly detect Arabic / multilingual text encoding.
"""

from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from typing import Dict, List

from core.schemas import ClassifiedChunk

logger = logging.getLogger(__name__)

# Column header order for CSV output
_CSV_COLUMNS = [
    "chunk_id",
    "text",
    "category",
    "subcategory",
    "confidence",
    "method",
    "token_count",
    "char_count",
    "word_count",
    "language",
    "source_file",
    "source_page",
]


class CSVExporter:
    """Export to CSV format for spreadsheet review.

    Outputs a UTF-8 BOM-marked CSV file that opens correctly in
    Microsoft Excel, Google Sheets, and LibreOffice Calc with proper
    Arabic text rendering.
    """

    def __init__(self) -> None:
        """Initialise the exporter."""
        self._files_exported: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(
        self,
        chunks: List[ClassifiedChunk],
        output_path: str,
        encoding: str = "utf-8-sig",
    ) -> str:
        """Export classified chunks to CSV.

        Args:
            chunks: List of :class:`ClassifiedChunk` objects.
            output_path: Filesystem path for the output ``.csv`` file.
            encoding: File encoding.  Defaults to ``utf-8-sig`` which
                prepends a UTF-8 BOM for Excel compatibility.

        Returns:
            Absolute path to the exported file.

        Raises:
            ValueError: If *chunks* is empty.
        """
        if not chunks:
            raise ValueError("No chunks to export.")

        output_path = os.path.abspath(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        row_count = 0

        with open(output_path, "w", encoding=encoding, newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
            writer.writeheader()

            for classified in chunks:
                row = self._chunk_to_row(classified)
                writer.writerow(row)
                row_count += 1

        self._files_exported += 1
        logger.info(
            "Exported %d rows to CSV (encoding=%s): %s",
            row_count,
            encoding,
            output_path,
        )
        return output_path

    def export_summary(
        self,
        chunks: List[ClassifiedChunk],
        output_path: str,
        encoding: str = "utf-8-sig",
    ) -> str:
        """Export a category summary CSV.

        Produces a lightweight CSV with one row per category showing
        chunk count, average confidence, and example texts.

        Args:
            chunks: List of :class:`ClassifiedChunk` objects.
            output_path: Filesystem path for the output file.
            encoding: File encoding.

        Returns:
            Absolute path to the exported file.
        """
        from collections import defaultdict

        if not chunks:
            raise ValueError("No chunks to export.")

        output_path = os.path.abspath(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Aggregate per category
        cat_data: Dict[str, List[ClassifiedChunk]] = defaultdict(list)
        for classified in chunks:
            cat_data[classified.classification.category].append(classified)

        summary_columns = [
            "category",
            "chunk_count",
            "avg_confidence",
            "example_text_1",
            "example_text_2",
        ]

        with open(output_path, "w", encoding=encoding, newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=summary_columns)
            writer.writeheader()

            for cat, cat_chunks in sorted(cat_data.items()):
                avg_conf = sum(
                    c.classification.confidence for c in cat_chunks
                ) / len(cat_chunks)

                examples = [c.chunk.text[:200] for c in cat_chunks[:2]]
                while len(examples) < 2:
                    examples.append("")

                writer.writerow(
                    {
                        "category": cat,
                        "chunk_count": len(cat_chunks),
                        "avg_confidence": round(avg_conf, 4),
                        "example_text_1": examples[0],
                        "example_text_2": examples[1],
                    }
                )

        logger.info("Exported summary CSV (%d categories): %s", len(cat_data), output_path)
        return output_path

    def get_stats(self) -> Dict:
        """Return exporter statistics.

        Returns:
            Dictionary with ``files_exported`` count.
        """
        return {"files_exported": self._files_exported}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _chunk_to_row(chunk: ClassifiedChunk) -> Dict:
        """Convert a :class:`ClassifiedChunk` to a CSV row dictionary."""
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
            "source_file": chunk.chunk.source_file or "",
            "source_page": chunk.chunk.source_page or "",
        }

    def __repr__(self) -> str:
        return f"CSVExporter(files_exported={self._files_exported})"
