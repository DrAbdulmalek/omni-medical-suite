#!/usr/bin/env python3
"""
validate_dataset.py — Validate Ground Truth Dataset Before Release
===================================================================
Quality gate validator for dataset versions.

Usage:
    python validate_dataset.py --version 1.0.0
    python validate_dataset.py --data-dir data/v1.0.0/
    python validate_dataset.py --data-dir data/v1.0.0/ --strict

Author: Dr. Abdulmalek
Version: 1.0.0
"""

import json
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field
import unicodedata
import re


@dataclass
class ValidationIssue:
    severity: str  # "error", "warning", "info"
    gate: str
    message: str
    file_path: str = ""
    line: int = 0


@dataclass
class ValidationReport:
    version: str = ""
    total_files: int = 0
    issues: List[ValidationIssue] = field(default_factory=list)
    gates_passed: List[str] = field(default_factory=list)
    gates_failed: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return all(i.severity != "error" for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text for consistency check."""
    text = unicodedata.normalize('NFC', text)
    text = text.replace('\u0623', '\u0627').replace('\u0625', '\u0627').replace('\u0622', '\u0627')
    text = text.replace('\u0649', '\u064a')
    return text.strip()


def check_completeness(data_dir: Path, report: ValidationReport) -> None:
    """Gate 1: Completeness check."""
    gate = "completeness"
    manifest_path = data_dir / "manifest.json"

    if not manifest_path.exists():
        report.issues.append(ValidationIssue(
            severity="error", gate=gate,
            message=f"Missing manifest.json in {data_dir}"
        ))
        return

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        report.version = manifest.get("version", "unknown")

        required_fields = ["version", "created_at", "sources", "statistics"]
        for field_name in required_fields:
            if field_name not in manifest:
                report.issues.append(ValidationIssue(
                    severity="error", gate=gate,
                    message=f"manifest.json missing required field: {field_name}",
                    file_path=str(manifest_path)
                ))

        # Check statistics sub-fields
        stats = manifest.get("statistics", {})
        for stat_field in ["total_pages", "total_lines", "languages"]:
            if stat_field not in stats:
                report.issues.append(ValidationIssue(
                    severity="warning", gate=gate,
                    message=f"manifest.json statistics missing: {stat_field}",
                    file_path=str(manifest_path)
                ))

    except json.JSONDecodeError as e:
        report.issues.append(ValidationIssue(
            severity="error", gate=gate,
            message=f"Invalid JSON in manifest.json: {e}",
            file_path=str(manifest_path)
        ))

    # Check golden directory exists
    golden_dir = data_dir / "golden"
    if not golden_dir.exists():
        report.issues.append(ValidationIssue(
            severity="warning", gate=gate,
            message=f"No golden/ directory found in {data_dir}"
        ))

    report.gates_passed.append(gate) if not any(
        i.severity == "error" and i.gate == gate for i in report.issues
    ) else report.gates_failed.append(gate)


def check_consistency(data_dir: Path, report: ValidationReport) -> None:
    """Gate 2: Consistency check."""
    gate = "consistency"
    text_files = list(data_dir.rglob("*.txt")) + list(data_dir.rglob("*.json"))

    seen_ids = set()
    for tf in text_files:
        if tf.name == "manifest.json":
            continue

        # Check UTF-8 encoding
        try:
            content = tf.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            report.issues.append(ValidationIssue(
                severity="error", gate=gate,
                message=f"File is not valid UTF-8",
                file_path=str(tf)
            ))
            continue

        # Check NFC normalization
        normalized = unicodedata.normalize('NFC', content)
        if content != normalized:
            report.issues.append(ValidationIssue(
                severity="warning", gate=gate,
                message=f"File is not NFC normalized",
                file_path=str(tf)
            ))

        # Check for duplicate IDs in JSON files
        if tf.suffix == '.json':
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'id' in item:
                            item_id = item['id']
                            if item_id in seen_ids:
                                report.issues.append(ValidationIssue(
                                    severity="error", gate=gate,
                                    message=f"Duplicate test case ID: {item_id}",
                                    file_path=str(tf)
                                ))
                            seen_ids.add(item_id)
            except json.JSONDecodeError:
                pass

    report.gates_passed.append(gate) if not any(
        i.severity == "error" and i.gate == gate for i in report.issues
    ) else report.gates_failed.append(gate)


def check_medical_accuracy(data_dir: Path, report: ValidationReport) -> None:
    """Gate 3: Medical accuracy check."""
    gate = "medical_accuracy"

    # Check for Arabic medical terms
    medical_patterns = [
        r'(?:ال)?(?:تهاب|خلع|متلازمة|داء|انزلاق|تشوه|شلل|ورم|عسرة)\w*',
        r'(?:ال)?(?:مشاش|مثاش|فخذ|كتف|قدم|دماغ|عصب|عظم|فقرات)\w*',
        r'\d+\s*(?:mg|ml|mcg|g|mmol|IU|unit)',
    ]

    text_files = list(data_dir.rglob("*.txt"))
    total_medical_terms = 0

    for tf in text_files:
        content = tf.read_text(encoding='utf-8')
        for pattern in medical_patterns:
            matches = re.findall(pattern, content)
            total_medical_terms += len(matches)

    if total_medical_terms == 0 and text_files:
        report.issues.append(ValidationIssue(
            severity="warning", gate=gate,
            message=f"No Arabic medical terms detected in {len(text_files)} text files"
        ))
    else:
        report.issues.append(ValidationIssue(
            severity="info", gate=gate,
            message=f"Found {total_medical_terms} Arabic medical term occurrences"
        ))

    report.gates_passed.append(gate) if not any(
        i.severity == "error" and i.gate == gate for i in report.issues
    ) else report.gates_failed.append(gate)


def check_integration(data_dir: Path, report: ValidationReport) -> None:
    """Gate 4: Integration check."""
    gate = "integration"

    # Check that manifest references upstream consumers
    manifest_path = data_dir / "manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)

            consumers = manifest.get("upstream_consumers", [])
            expected_consumers = [
                "medical-ocr-benchmarks",
                "medical-ocr-trainer",
                "medical-ocr-postprocessor",
                "omni-medical-suite"
            ]
            for ec in expected_consumers:
                if ec not in consumers:
                    report.issues.append(ValidationIssue(
                        severity="info", gate=gate,
                        message=f"upstream_consumers missing: {ec}",
                        file_path=str(manifest_path)
                    ))
        except (json.JSONDecodeError, IOError):
            pass

    report.gates_passed.append(gate) if not any(
        i.severity == "error" and i.gate == gate for i in report.issues
    ) else report.gates_failed.append(gate)


def main():
    parser = argparse.ArgumentParser(description="Validate ground truth dataset")
    parser.add_argument("--version", help="Dataset version (e.g. 1.0.0)")
    parser.add_argument("--data-dir", help="Path to dataset directory")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = parser.parse_args()

    if args.version:
        data_dir = Path(f"data/v{args.version}")
    elif args.data_dir:
        data_dir = Path(args.data_dir)
    else:
        data_dir = Path("data")

    if not data_dir.exists():
        print(f"Error: Dataset directory not found: {data_dir}")
        sys.exit(1)

    report = ValidationReport()
    report.total_files = len(list(data_dir.rglob("*")))

    print(f"Validating dataset: {data_dir}")
    print("=" * 60)

    check_completeness(data_dir, report)
    check_consistency(data_dir, report)
    check_medical_accuracy(data_dir, report)
    check_integration(data_dir, report)

    # Print results
    print(f"\nDataset Version: {report.version or 'unknown'}")
    print(f"Total Files: {report.total_files}")
    print(f"\nGates Passed: {len(report.gates_passed)}/4")
    print(f"Gates Failed: {len(report.gates_failed)}/4")

    if report.issues:
        print(f"\nIssues ({len(report.issues)} total, {report.error_count} errors, {report.warning_count} warnings):")
        for issue in sorted(report.issues, key=lambda i: (0 if i.severity == "error" else 1, i.gate)):
            icon = {"error": "X", "warning": "!", "info": "i"}[issue.severity]
            loc = f" ({issue.file_path}:{issue.line})" if issue.file_path else ""
            print(f"  [{icon}] [{issue.gate}]{loc} {issue.message}")
    else:
        print("\nNo issues found.")

    if args.strict and report.warning_count > 0:
        print(f"\nSTRICT MODE: {report.warning_count} warnings treated as errors")
        sys.exit(1)
    elif not report.is_valid:
        print(f"\nVALIDATION FAILED: {report.error_count} error(s)")
        sys.exit(1)
    else:
        print(f"\nVALIDATION PASSED")


if __name__ == "__main__":
    main()