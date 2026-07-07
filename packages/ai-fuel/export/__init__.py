"""
AI Fuel Engine - Export Module

Provides a unified, multi-format export pipeline for classified and
deduplicated text chunks.  Supported formats:

- **JSONL** – one JSON object per line, ideal for LLM fine-tuning.
- **Parquet** – columnar, compressed storage for analytics.
- **RAG** – ready-to-use RAG corpus with pre-computed embeddings.
- **CSV** – spreadsheet-compatible export (BOM-marked for Excel).
"""

from export.jsonl_exporter import JSONLExporter
from export.parquet_exporter import ParquetExporter
from export.rag_exporter import RAGExporter
from export.csv_exporter import CSVExporter
from export.pipeline import ExportPipeline

__all__ = [
    "JSONLExporter",
    "ParquetExporter",
    "RAGExporter",
    "CSVExporter",
    "ExportPipeline",
]
