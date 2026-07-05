#!/usr/bin/env python3
"""
Fix HuggingFace dataset schema mismatches for `arabic-medical-ocr-corrections`.

Resolves DatasetGenerationError / CastError caused by inconsistent columns
or type mismatches across rows in a JSONL dataset file.

Usage:
    python fix_hf_dataset_schema.py \
        --input  raw_data.jsonl \
        --output fixed_data.jsonl

Requires only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Canonical schema every output row must conform to
# ---------------------------------------------------------------------------
CANONICAL_COLUMNS = [
    "original_text",
    "corrected_text",
    "source",
    "language",
    "correction_type",
]

# Mapping of known variant column names to canonical names
COLUMN_ALIASES: dict[str, str] = {
    "ocr_text": "original_text",
    "raw_text": "original_text",
    "input_text": "original_text",
    "before": "original_text",
    "source_text": "original_text",
    "fixed_text": "corrected_text",
    "corrected": "corrected_text",
    "output_text": "corrected_text",
    "after": "corrected_text",
    "target_text": "corrected_text",
    "src": "source",
    "data_source": "source",
    "lang": "language",
    "type": "correction_type",
    "correction": "correction_type",
    "error_type": "correction_type",
}

# Expected types for canonical columns (all string by default)
CANONICAL_TYPES: dict[str, type] = {
    "original_text": str,
    "corrected_text": str,
    "source": str,
    "language": str,
    "correction_type": str,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL file into a list of dicts. Skips blank / malformed lines."""
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
                if isinstance(obj, dict):
                    rows.append(obj)
                else:
                    print(f"  [WARN] Line {lineno}: expected dict, got {type(obj).__name__} — skipped")
            except json.JSONDecodeError as exc:
                print(f"  [WARN] Line {lineno}: JSON decode error ({exc}) — skipped")
    return rows


def analyze_schema(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return analysis of column names, missing/extra columns, and type mismatches."""
    all_columns = Counter[str]()
    column_schemas: dict[str, list[set[type]]] = {}  # col -> list of type-sets per row

    for idx, row in enumerate(rows):
        row_keys = set(row.keys())
        for col in row_keys:
            all_columns[col] += 1

        for col, val in row.items():
            types = column_schemas.setdefault(col, [])
            types.append(_value_types(val))

    # Determine majority schema (columns present in >50% of rows)
    majority_threshold = len(rows) * 0.5
    majority_columns = {col for col, cnt in all_columns.items() if cnt >= majority_threshold}

    # Rows with missing/extra columns relative to majority
    rows_missing: list[tuple[int, list[str]]] = []
    rows_extra: list[tuple[int, list[str]]] = []

    for idx, row in enumerate(rows):
        row_keys = set(row.keys())
        missing = sorted(majority_columns - row_keys)
        extra = sorted(row_keys - majority_columns)
        if missing:
            rows_missing.append((idx, missing))
        if extra:
            rows_extra.append((idx, extra))

    # Type mismatches (same column, different types across rows)
    type_mismatches: dict[str, list[type]] = {}
    for col, type_sets in column_schemas.items():
        unified: set[type] = set()
        for ts in type_sets:
            unified |= ts
        # Strip NoneType if at least one non-None exists
        non_none = unified - {type(None)}
        if len(non_none) > 1:
            type_mismatches[col] = sorted(non_none, key=lambda t: t.__name__)

    return {
        "total_rows": len(rows),
        "unique_columns": dict(all_columns.most_common()),
        "majority_columns": sorted(majority_columns),
        "rows_with_missing_columns": rows_missing,
        "rows_with_extra_columns": rows_extra,
        "type_mismatches": type_mismatches,
    }


def _value_types(val: Any) -> set[type]:
    """Return the Python type(s) for a value (handles lists/dicts by returning the element types)."""
    if val is None:
        return {type(None)}
    if isinstance(val, list):
        types: set[type] = set()
        for item in val:
            types |= _value_types(item)
        return types if types else {list}
    return {type(val)}


def to_string(val: Any) -> str | None:
    """Coerce a value to string. Returns None if the input is None."""
    if val is None:
        return None
    if isinstance(val, bool):
        return str(val).lower()
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, list):
        return json.dumps(val, ensure_ascii=False)
    if isinstance(val, dict):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def normalize_row(row: dict[str, Any], drop_extra: bool = True) -> dict[str, Any] | None:
    """
    Normalize a single row to the canonical schema.

    - Maps alias column names to canonical names.
    - Fills missing canonical columns with None.
    - Removes extra columns (unless *drop_extra* is False).
    - Coerces all values to strings.

    Returns None if the row has no original_text or corrected_text after mapping.
    """
    mapped: dict[str, Any] = {}

    # First pass: map aliases
    for col, val in row.items():
        canonical = COLUMN_ALIASES.get(col, col)
        mapped[canonical] = val

    # Build the canonical row
    normalized: dict[str, Any] = {}
    for col in CANONICAL_COLUMNS:
        if col in mapped:
            normalized[col] = to_string(mapped[col])
        else:
            normalized[col] = None

    # Drop rows that lack core text fields
    if normalized["original_text"] is None and normalized["corrected_text"] is None:
        return None

    # Set sensible defaults for metadata columns
    if normalized["source"] is None:
        normalized["source"] = "unknown"
    if normalized["language"] is None:
        normalized["language"] = "ar"
    if normalized["correction_type"] is None:
        normalized["correction_type"] = "general"

    # Optionally strip extra columns
    if drop_extra:
        extra_keys = [k for k in normalized if k not in CANONICAL_COLUMNS]
        for k in extra_keys:
            del normalized[k]

    return normalized


def validate_row(row: dict[str, Any], row_idx: int) -> list[str]:
    """Return a list of validation errors for a normalized row."""
    errors: list[str] = []
    keys = set(row.keys())

    # Check exact column set
    expected = set(CANONICAL_COLUMNS)
    if keys != expected:
        missing = sorted(expected - keys)
        extra = sorted(keys - expected)
        if missing:
            errors.append(f"missing columns: {missing}")
        if extra:
            errors.append(f"extra columns: {extra}")

    # Check types
    for col in CANONICAL_COLUMNS:
        val = row.get(col)
        if val is not None and not isinstance(val, str):
            errors.append(f"column '{col}' expected str, got {type(val).__name__}")

    return errors


def write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    """Write rows as JSONL with consistent key ordering."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            ordered = {col: row[col] for col in CANONICAL_COLUMNS}
            fh.write(json.dumps(ordered, ensure_ascii=False) + "\n")


def generate_dataset_card(
    output_path: Path,
    total_rows: int,
    rows_fixed: int,
    rows_dropped: int,
) -> None:
    """Generate a HuggingFace dataset card (README.md / dataset_card.md)."""
    card = f"""---
license: mit
language:
- ar
size_categories:
- n<1K
---

# Arabic Medical OCR Corrections

## Dataset Description

A curated collection of Arabic medical text pairs designed for training and evaluating \
OCR post-processing and spelling-correction models. Each record contains an **original \
(OCR-extracted) text** and its **corrected version**, along with provenance metadata.

## Languages

- **Primary:** Arabic (ar)
- Scripts: Arabic script with optional Latin medical terminology

## Supported Tasks

- Text correction / Grammatical Error Correction (GEC) for Arabic medical domain
- OCR post-processing
- Spelling correction fine-tuning

## Dataset Schema

| Column            | Type   | Description |
|-------------------|--------|-------------|
| `original_text`   | string | The raw OCR-extracted text before correction |
| `corrected_text`  | string | The corrected / ground-truth text |
| `source`          | string | Provenance of the text pair (e.g., prescription, report) |
| `language`        | string | ISO 639-1 language code (default: `ar`) |
| `correction_type` | string | Category of correction applied (e.g., spelling, diacritics) |

## Size Summary

| Metric            | Value |
|-------------------|-------|
| Total rows        | {total_rows} |
| Rows fixed        | {rows_fixed} |
| Rows dropped      | {rows_dropped} |
| Final rows        | {total_rows - rows_dropped} |

## License

MIT

## How This Dataset Was Prepared

This dataset was cleaned and normalized using the companion script \
`fix_hf_dataset_schema.py`, which resolves schema inconsistencies (missing/extra \
columns, type mismatches) that caused `DatasetGenerationError` in the HuggingFace \
Datasets viewer.
"""
    card_path = output_path / "dataset_card.md"
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(card, encoding="utf-8")
    return card_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix HuggingFace dataset schema mismatches for arabic-medical-ocr-corrections."
    )
    parser.add_argument(
        "--input", "-i",
        type=Path,
        required=True,
        help="Path to the input JSONL file.",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        required=True,
        help="Path to write the fixed JSONL file.",
    )
    parser.add_argument(
        "--card-dir",
        type=Path,
        default=None,
        help="Directory to write the dataset_card.md (defaults to same dir as --output).",
    )
    parser.add_argument(
        "--drop-orphans",
        action="store_true",
        default=True,
        help="Drop rows that have neither original_text nor corrected_text after mapping (default: True).",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"[ERROR] Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    print("=" * 64)
    print("  HF Dataset Schema Fix — arabic-medical-ocr-corrections")
    print("=" * 64)
    print()

    # ── 1. Load ───────────────────────────────────────────────────────────
    print(f"[1/6] Loading input file: {args.input}")
    rows = load_jsonl(args.input)
    print(f"      Loaded {len(rows)} valid rows")
    print()

    if not rows:
        print("[ERROR] No valid rows found in input file.", file=sys.stderr)
        sys.exit(1)

    # ── 2. Analyze ────────────────────────────────────────────────────────
    print("[2/6] Analyzing schema...")
    analysis = analyze_schema(rows)

    print(f"      Unique columns across all rows: {len(analysis['unique_columns'])}")
    for col, cnt in analysis["unique_columns"].items():
        pct = cnt / analysis["total_rows"] * 100
        marker = " *" if col not in CANONICAL_COLUMNS else ""
        print(f"        {col:<30s}  {cnt:>5d} rows  ({pct:5.1f}%){marker}")
    print(f"      Majority schema columns: {analysis['majority_columns']}")
    print()

    if analysis["rows_with_missing_columns"]:
        print(f"      Rows with missing columns: {len(analysis['rows_with_missing_columns'])}")
        for idx, cols in analysis["rows_with_missing_columns"][:5]:
            print(f"        Row {idx}: missing {cols}")
        if len(analysis["rows_with_missing_columns"]) > 5:
            print(f"        ... and {len(analysis['rows_with_missing_columns']) - 5} more")

    if analysis["rows_with_extra_columns"]:
        print(f"      Rows with extra columns: {len(analysis['rows_with_extra_columns'])}")
        for idx, cols in analysis["rows_with_extra_columns"][:5]:
            print(f"        Row {idx}: extra {cols}")
        if len(analysis["rows_with_extra_columns"]) > 5:
            print(f"        ... and {len(analysis['rows_with_extra_columns']) - 5} more")

    if analysis["type_mismatches"]:
        print(f"      Type mismatches detected:")
        for col, types in analysis["type_mismatches"].items():
            print(f"        {col}: {types}")
    print()

    # ── 3. Normalize ──────────────────────────────────────────────────────
    print("[3/6] Normalizing schema...")
    normalized_rows: list[dict[str, Any]] = []
    dropped_count = 0
    fixed_count = 0

    for idx, row in enumerate(rows):
        result = normalize_row(row, drop_extra=True)
        if result is None:
            dropped_count += 1
            continue
        # Check if anything changed
        if set(result.keys()) != set(row.keys()):
            fixed_count += 1
        normalized_rows.append(result)

    print(f"      Rows normalized: {len(normalized_rows)}")
    print(f"      Rows fixed:      {fixed_count}")
    print(f"      Rows dropped:    {dropped_count}")
    print()

    # ── 4. Validate ───────────────────────────────────────────────────────
    print("[4/6] Validating normalized rows...")
    validation_errors: list[tuple[int, list[str]]] = []
    for idx, row in enumerate(normalized_rows):
        errs = validate_row(row, idx)
        if errs:
            validation_errors.append((idx, errs))

    if validation_errors:
        print(f"      [WARN] {len(validation_errors)} row(s) still have validation issues:")
        for idx, errs in validation_errors[:10]:
            print(f"        Row {idx}: {'; '.join(errs)}")
    else:
        print("      All rows pass validation.")
    print()

    # ── 5. Write ──────────────────────────────────────────────────────────
    print(f"[5/6] Writing fixed JSONL to: {args.output}")
    write_jsonl(normalized_rows, args.output)
    out_size = args.output.stat().st_size
    print(f"      Written {len(normalized_rows)} rows ({out_size:,} bytes)")
    print()

    # ── 6. Generate dataset card ──────────────────────────────────────────
    card_dir = args.card_dir if args.card_dir else args.output.parent
    card_path = generate_dataset_card(card_dir, len(rows), fixed_count, dropped_count)
    print(f"[6/6] Dataset card written to: {card_path}")
    print()

    # ── Summary ───────────────────────────────────────────────────────────
    print("=" * 64)
    print("  SUMMARY")
    print("=" * 64)
    print(f"  Input file:           {args.input}")
    print(f"  Output file:          {args.output}")
    print(f"  Total rows read:      {len(rows)}")
    print(f"  Rows fixed:           {fixed_count}")
    print(f"  Rows dropped:         {dropped_count}")
    print(f"  Final rows written:   {len(normalized_rows)}")
    print()
    print("  Schema BEFORE:")
    before_cols = sorted(analysis["unique_columns"].keys())
    for col in before_cols:
        cnt = analysis["unique_columns"][col]
        print(f"    {col:<30s}  ({cnt} rows)")
    print()
    print("  Schema AFTER (canonical):")
    for col in CANONICAL_COLUMNS:
        print(f"    {col:<30s}  str")
    print()
    if analysis["type_mismatches"]:
        print("  Type mismatches resolved:")
        for col, types in analysis["type_mismatches"].items():
            print(f"    {col}: {types}  ->  str")
        print()
    print("Done.")


if __name__ == "__main__":
    main()