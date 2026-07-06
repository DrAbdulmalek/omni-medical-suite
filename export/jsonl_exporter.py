"""
AI Fuel Engine - JSONL Exporter

Exports classified chunks to JSONL format, the de-facto standard for
LLM fine-tuning data.  Each line is a self-contained JSON object with
the chunk text, classification metadata, and optional auxiliary fields.

All text is encoded as UTF-8 to support Arabic and mixed-language content.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from core.schemas import ClassifiedChunk

logger = logging.getLogger(__name__)

# Default instruction template for instruction-tuning format
_DEFAULT_INSTRUCTION_TEMPLATE = (
    "Classify the following medical text into the appropriate category."
)


class JSONLExporter:
    """Export classified chunks to JSONL format for LLM fine-tuning.

    Each line in the output file contains a JSON object:

    .. code-block:: json

        {
            "text": "...",
            "category": "...",
            "subcategory": "...",
            "confidence": 0.95,
            "method": "keyword",
            "metadata": { ... }
        }

    The exporter also supports an **instruction-tuning** format suitable
    for supervised fine-tuning of instruction-following models.
    """

    def __init__(self) -> None:
        """Initialise the exporter."""
        self._records_exported: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def export(
        self,
        chunks: List[ClassifiedChunk],
        output_path: str,
        include_metadata: bool = True,
    ) -> str:
        """Export classified chunks to JSONL format.

        Args:
            chunks: List of :class:`ClassifiedChunk` objects.
            output_path: Filesystem path for the output file.
            include_metadata: If ``True``, include chunk-level metadata
                (source file, page, token count, etc.) in each record.

        Returns:
            Absolute path to the exported file.

        Raises:
            ValueError: If *chunks* is empty.
            OSError: If the output file cannot be written.
        """
        if not chunks:
            raise ValueError("No chunks to export.")

        output_path = os.path.abspath(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        line_count = 0

        with open(output_path, "w", encoding="utf-8") as fh:
            for classified in chunks:
                record = self._serialise_chunk(classified, include_metadata)
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                line_count += 1

        self._records_exported += line_count

        logger.info(
            "Exported %d records to JSONL: %s", line_count, output_path
        )
        return output_path

    def export_instruction_format(
        self,
        chunks: List[ClassifiedChunk],
        output_path: str,
        instruction_template: Optional[str] = None,
    ) -> str:
        """Export in instruction-tuning format.

        Each line is a JSON object with three fields:

        .. code-block:: json

            {
                "instruction": "Classify the following medical text...",
                "input": "<chunk text>",
                "output": "<category>"
            }

        Suitable for supervised fine-tuning of instruction-following
        models (e.g. Alpaca, LLaMA, Mistral).

        Args:
            chunks: List of :class:`ClassifiedChunk` objects.
            output_path: Filesystem path for the output file.
            instruction_template: Custom instruction text.  Defaults to
                a generic medical classification prompt.

        Returns:
            Absolute path to the exported file.
        """
        if not chunks:
            raise ValueError("No chunks to export.")

        template = instruction_template or _DEFAULT_INSTRUCTION_TEMPLATE
        output_path = os.path.abspath(output_path)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        line_count = 0

        with open(output_path, "w", encoding="utf-8") as fh:
            for classified in chunks:
                record = {
                    "instruction": template,
                    "input": classified.chunk.text,
                    "output": classified.classification.category,
                }

                # Include subcategory if available
                if classified.classification.subcategory:
                    record["output"] = (
                        f"{classified.classification.category} > "
                        f"{classified.classification.subcategory}"
                    )

                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                line_count += 1

        logger.info(
            "Exported %d instruction-tuning records to: %s",
            line_count,
            output_path,
        )
        return output_path

    def get_stats(self) -> Dict:
        """Return exporter statistics.

        Returns:
            Dictionary with ``records_exported`` count.
        """
        return {"records_exported": self._records_exported}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _serialise_chunk(
        chunk: ClassifiedChunk,
        include_metadata: bool,
    ) -> Dict:
        """Convert a :class:`ClassifiedChunk` to a JSON-serialisable dict."""
        record: Dict = {
            "text": chunk.chunk.text,
            "category": chunk.classification.category,
            "confidence": chunk.classification.confidence,
            "method": chunk.classification.method.value,
        }

        # Optional fields
        if chunk.classification.subcategory:
            record["subcategory"] = chunk.classification.subcategory

        if chunk.classification.alternatives:
            record["alternatives"] = chunk.classification.alternatives

        if include_metadata:
            metadata: Dict = {}
            metadata["chunk_id"] = chunk.chunk.id
            metadata["token_count"] = chunk.chunk.token_count
            metadata["char_count"] = chunk.chunk.char_count
            metadata["word_count"] = chunk.chunk.word_count
            metadata["language"] = chunk.chunk.language.value
            metadata["chunk_type"] = chunk.chunk.chunk_type.value

            if chunk.chunk.source_file:
                metadata["source_file"] = chunk.chunk.source_file
            if chunk.chunk.source_page is not None:
                metadata["source_page"] = chunk.chunk.source_page

            # Merge any custom metadata from the chunk
            metadata.update(chunk.chunk.metadata)

            record["metadata"] = metadata

        return record

    def __repr__(self) -> str:
        return f"JSONLExporter(records_exported={self._records_exported})"
