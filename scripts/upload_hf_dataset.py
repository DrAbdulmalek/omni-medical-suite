#!/usr/bin/env python3
"""
Re-upload arabic-medical-ocr-corrections to HuggingFace with fixed schema.

Normalizes all data files to the canonical 4-column schema:
  incorrect_ocr_output, correct_text, category, form

Usage:
    python upload_hf_dataset.py --input corrections.jsonl --repo DrAbdulmalek/arabic-medical-ocr-corrections
    python upload_hf_dataset.py --input corrections.csv --repo DrAbdulmalek/arabic-medical-ocr-corrections --private

Requirements:
    pip install datasets pandas
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List

CANONICAL_COLUMNS = ["incorrect_ocr_output", "correct_text", "category", "form"]

# Column name mapping: variant → canonical
COLUMN_ALIASES = {
    "original_text": "incorrect_ocr_output",
    "ocr_text": "incorrect_ocr_output",
    "ocr_output": "incorrect_ocr_output",
    "raw_text": "incorrect_ocr_output",
    "incorrect": "incorrect_ocr_output",
    "before": "incorrect_ocr_output",
    "corrected_text": "correct_text",
    "fixed_text": "correct_text",
    "correct_text": "correct_text",
    "ground_truth": "correct_text",
    "reference": "correct_text",
    "after": "correct_text",
    "correction_type": "category",
    "type": "category",
    "error_type": "category",
    "text_form": "form",
    "source_type": "form",
    "modality": "form",
}


def load_data(input_path: Path) -> List[Dict]:
    """Load data from JSONL or CSV."""
    suffix = input_path.suffix.lower()
    rows = []

    if suffix in (".jsonl", ".json"):
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"WARN: Skipping malformed line: {line[:80]}...")
    elif suffix in (".csv", ".tsv"):
        delimiter = "\t" if suffix == ".tsv" else ","
        with open(input_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                rows.append(dict(row))
    else:
        print(f"ERROR: Unsupported format: {suffix}")
        sys.exit(1)

    print(f"Loaded {len(rows)} rows from {input_path.name}")
    return rows


def normalize_row(row: Dict) -> Dict:
    """Normalize a single row to canonical schema."""
    normalized = {}
    for key, value in row.items():
        clean_key = key.strip().lower().replace(" ", "_")
        canonical = COLUMN_ALIASES.get(clean_key, clean_key)
        if canonical in CANONICAL_COLUMNS:
            normalized[canonical] = str(value).strip() if value else ""

    # Fill missing columns with defaults
    for col in CANONICAL_COLUMNS:
        if col not in normalized or not normalized[col]:
            if col == "category":
                normalized[col] = "other"
            elif col == "form":
                normalized[col] = "mixed"
            else:
                normalized[col] = ""

    return {col: normalized[col] for col in CANONICAL_COLUMNS}


def main():
    parser = argparse.ArgumentParser(description="Upload fixed dataset to HuggingFace")
    parser.add_argument("--input", "-i", required=True, help="Input file (JSONL or CSV)")
    parser.add_argument("--repo", "-r", default="DrAbdulmalek/arabic-medical-ocr-corrections", help="HF repo ID")
    parser.add_argument("--private", action="store_true", help="Make dataset private")
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview without uploading")
    parser.add_argument("--output", "-o", help="Save normalized file locally instead of uploading")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: {input_path} not found")
        sys.exit(1)

    # Load and normalize
    raw_rows = load_data(input_path)
    normalized = [normalize_row(r) for r in raw_rows]

    # Validate
    empty_text = sum(1 for r in normalized if not r["incorrect_ocr_output"] or not r["correct_text"])
    if empty_text:
        print(f"WARN: {empty_text} rows have empty text fields")

    print(f"Normalized: {len(normalized)} rows, {len(CANONICAL_COLUMNS)} columns")
    print(f"Columns: {CANONICAL_COLUMNS}")
    print(f"Sample row: {json.dumps(normalized[0], ensure_ascii=False)}")

    # Local output
    if args.output:
        out_path = Path(args.output)
        if out_path.suffix == ".jsonl":
            with open(out_path, "w", encoding="utf-8") as f:
                for row in normalized:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
        else:
            with open(out_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=CANONICAL_COLUMNS)
                writer.writeheader()
                writer.writerows(normalized)
        print(f"Saved to {out_path}")

    # Upload to HF
    if not args.dry_run and not args.output:
        try:
            from datasets import Dataset
            import pandas as pd

            df = pd.DataFrame(normalized)
            # Ensure string types
            for col in CANONICAL_COLUMNS:
                df[col] = df[col].astype(str)

            dataset = Dataset.from_pandas(df)
            dataset.push_to_hub(args.repo, private=args.private)
            print(f"Uploaded {len(normalized)} rows to https://huggingface.co/datasets/{args.repo}")
        except ImportError:
            print("ERROR: Install dependencies first: pip install datasets pandas")
            sys.exit(1)
    elif args.dry_run:
        print("\n[DRY RUN] No upload performed. Use without --dry-run to upload.")


if __name__ == "__main__":
    main()