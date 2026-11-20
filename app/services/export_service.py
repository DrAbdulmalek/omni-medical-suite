# app/services/export_service.py
"""Export Service — Export OCR results to CSV, JSON, and HuggingFace Dataset formats.

Provides a unified export interface used by the Gradio HITL app and
the advanced review app.
"""

import csv
import io
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def to_csv(
    records: list[dict[str, Any]],
    columns: list[str] | None = None,
) -> str:
    """Export records to CSV string.
    
    Args:
        records: List of dicts to export
        columns: Optional column order (defaults to keys of first record)
        
    Returns:
        CSV-formatted string
    """
    if not records:
        return ""
    
    if columns is None:
        columns = list(records[0].keys())
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue()


def to_json(
    records: list[dict[str, Any]],
    indent: int = 2,
    ensure_ascii: bool = False,
) -> str:
    """Export records to JSON string.
    
    Args:
        records: List of dicts to export
        indent: JSON indentation level
        ensure_ascii: If False, preserves Arabic characters
        
    Returns:
        JSON-formatted string
    """
    return json.dumps(records, indent=indent, ensure_ascii=ensure_ascii, default=str)


def to_hf_dataset_format(
    records: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Convert records to HuggingFace Dataset format (dict of lists).
    
    Args:
        records: List of dicts to convert
        
    Returns:
        Dict mapping column names to lists of values
    """
    if not records:
        return {}
    
    # Collect all keys across all records
    all_keys: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record.keys():
            if key not in seen:
                all_keys.append(key)
                seen.add(key)
    
    result: dict[str, list[Any]] = {key: [] for key in all_keys}
    for record in records:
        for key in all_keys:
            value = record.get(key, "")
            if isinstance(value, list):
                value = json.dumps(value, ensure_ascii=False)
            result[key].append(str(value) if value is not None else "")
    
    return result


def format_export_summary(
    total: int,
    format_name: str,
    columns: int | None = None,
) -> str:
    """Generate a human-readable export summary.
    
    Args:
        total: Number of records exported
        format_name: Export format (csv, json, hf)
        columns: Number of columns (if applicable)
        
    Returns:
        Summary string
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    parts = [f"Exported {total} records as {format_name.upper()}", f"Time: {ts}"]
    if columns is not None:
        parts.append(f"Columns: {columns}")
    return " | ".join(parts)