#!/usr/bin/env python3
"""
Medical OCR Training Hub - Data Ingestion & Cleaning Script (v2.0 - Arabic Ready)
Author: DrAbdulmalek
Description: Pulls corrected OCR data from Hugging Face Spaces, validates structure,
             scrubs PII (including Arabic patterns), deduplicates, and outputs
             both JSON and TSV formats for model training.

Changelog (v1.1 → v2.0):
  - Added Arabic/middle-eastern phone number patterns (Syria, KSA, UAE, etc.)
  - Added Arabic-numeral date detection (e.g., ٢٤/٠٦/٢٠٢٦)
  - Added national ID / medical record number detection (10-12 digits)
  - Added hash-based deduplication to prevent duplicate entries
  - Added TSV output for sentence alignment (translation model training)
  - Added pipeline statistics report generation
  - Refactored PII patterns into a list for extensibility
  - Added huggingface_hub integration with fallback mock data
"""

import os
import json
import csv
import re
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime


# ══════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════
HF_DATASET_REPO = "DrAbdulmalek/medical-ocr-corrections"
HF_SPACE_API_URL = "https://huggingface.co/api/spaces/DrAbdulmalek/handwriting-ocr/host"
TARGET_OUTPUT_DIR = "./data/ingested_corrections"
REPORT_FILE_PATH = "./data/pipeline_report.md"


class DataIngestionPipeline:
    """Orchestrates data ingestion, PII scrubbing, deduplication, and quality validation."""

    def __init__(self, repo_id: str = HF_DATASET_REPO, output_dir: str = TARGET_OUTPUT_DIR):
        self.repo_id = repo_id
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        self.hf_token = os.getenv("HF_TOKEN")

        # ── Statistics ──
        self.stats = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "duplicates": 0,
            "pii_scrubbed": 0,
        }

        # ── Deduplication set ──
        self.seen_hashes: set = set()

        # ── PII Detection Patterns (Arabic + English + Regional) ──
        self.pii_patterns: List[tuple] = [
            # Syrian / Levantine mobile: +963 9xx xxx xxx  or  09xx xxx xxx
            (
                re.compile(r'(?:\+?963|0)?9\d{8}'),
                "[رقم_هاتف_محجوب]",
            ),
            # Saudi mobile: +966 5xx xxx xxxx
            (
                re.compile(r'(?:\+?966|0)?5\d{8}'),
                "[رقم_هاتف_محجوب]",
            ),
            # UAE mobile: +971 5x xxx xxxx
            (
                re.compile(r'(?:\+?971|0)?5\d{8}'),
                "[رقم_هاتف_محجوب]",
            ),
            # Generic international phone pattern
            (
                re.compile(r'\+?\d{1,3}[-.\s]?\(?\d{1,3}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}'),
                "[رقم_هاتف_محجوب]",
            ),
            # Gregorian dates: DD/MM/YYYY, YYYY-MM-DD, etc.
            (
                re.compile(r'\b\d{1,2}[-/\s.]\d{1,2}[-/\s.]\d{2,4}\b'),
                "[تاريخ_محجوب]",
            ),
            # Arabic-numeral dates: ٢٤/٠٦/٢٠٢٦  (٠١٢٣٤٥٦٧٨٩)
            (
                re.compile(r'[٠-٩]{1,2}[/\-][٠-٩]{1,2}[/\-][٠-٩]{2,4}'),
                "[تاريخ_محجوب]",
            ),
            # National ID / Medical record number (10-12 consecutive digits)
            (
                re.compile(r'\b\d{10,12}\b'),
                "[رقم_هوية_محجوب]",
            ),
            # Email addresses
            (
                re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
                "[بريد_محجوب]",
            ),
        ]

    # ────────────────────────────────────────────────────────
    # Data Fetching
    # ────────────────────────────────────────────────────────
    def fetch_corrections_from_hf(self) -> List[Dict[str, Any]]:
        """Fetch corrected data from Hugging Face dataset or Space API."""
        print(f"[INFO] Connecting to HF Repo: {self.repo_id} ...")

        # Strategy 1: Try huggingface_hub dataset download
        try:
            from huggingface_hub import hf_hub_download
            local_file = hf_hub_download(
                repo_id=self.repo_id,
                filename="corrections.json",
                repo_type="dataset",
                token=self.hf_token,
            )
            with open(local_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"[INFO] Fetched {len(data)} records from HF Dataset.")
            return data
        except Exception as e:
            print(f"[WARN] HF Dataset fetch failed: {e}")

        # Strategy 2: Try Space API
        try:
            import requests
            resp = requests.get(
                HF_SPACE_API_URL,
                headers={"Authorization": f"Bearer {self.hf_token}"},
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    print(f"[INFO] Fetched {len(data)} records from HF Space API.")
                    return data
        except Exception as e:
            print(f"[WARN] HF Space API fetch failed: {e}")

        # Fallback: mock data for local testing
        print("[WARN] Using fallback mock data for local testing.")
        return self._mock_data()

    @staticmethod
    def _mock_data() -> List[Dict[str, Any]]:
        """Generate mock data for pipeline testing (includes Arabic + PII)."""
        return [
            {
                "image_id": "scan_001.png",
                "predicted_text": "Patient John Doe with phone 0933112233 shows symptoms of acute appendicitis",
                "corrected_text": "Patient John Doe, DOB 12/05/1985, phone +963-933-112233 shows symptoms of acute appendicitis.",
                "confidence_score": 0.95,
                "metadata": {"dpi": 300, "is_handwritten": True},
            },
            {
                "image_id": "scan_002.png",
                "predicted_text": "المريض محمد أحمد الهاتف 0944123456",
                "corrected_text": "المريض محمد أحمد، تاريخ الميلاد ١٥/٠٣/١٩٩٠، الهاتف 0944123456. تشخيص: كسر في عظمة الساق.",
                "confidence_score": 0.88,
                "metadata": {"dpi": 200, "is_handwritten": True},
            },
            {
                "image_id": "scan_003.png",
                "predicted_text": "Patient with ID 12345678901 scheduled for surgery",
                "corrected_text": "Female patient, national ID 12345678901, scheduled for total knee replacement surgery on 2026-07-15.",
                "confidence_score": 0.92,
                "metadata": {"dpi": 300, "is_handwritten": False},
            },
            {
                "image_id": "scan_004.png",
                "predicted_text": "تقرير أشعة سينية للكتف الأيسر",
                "corrected_text": "تقرير أشعة سينية للكتف الأيسر - لا يوجد كسر. رقم السجل الطبي 9876543210. تاريخ الفحص ٢٥/٠٦/٢٠٢٦.",
                "confidence_score": 0.91,
                "metadata": {"dpi": 300, "is_handwritten": True},
            },
            # Duplicate entry (same corrected_text as scan_001) to test dedup
            {
                "image_id": "scan_005.png",
                "predicted_text": "Patient John Doe with phone 0933112233 shows symptoms of acute appendicitis",
                "corrected_text": "Patient John Doe, DOB 12/05/1985, phone +963-933-112233 shows symptoms of acute appendicitis.",
                "confidence_score": 0.95,
                "metadata": {"dpi": 300, "is_handwritten": True},
            },
        ]

    # ────────────────────────────────────────────────────────
    # PII Scrubbing
    # ────────────────────────────────────────────────────────
    def scrub_pii(self, text: str) -> str:
        """Redact PII using all registered patterns (Arabic + English + Regional)."""
        if not text:
            return text
        scrubbed = text
        for pattern, replacement in self.pii_patterns:
            if pattern.search(scrubbed):
                self.stats["pii_scrubbed"] += 1
                scrubbed = pattern.sub(replacement, scrubbed)
        return scrubbed

    # ────────────────────────────────────────────────────────
    # Deduplication
    # ────────────────────────────────────────────────────────
    def is_duplicate(self, text: str) -> bool:
        """Check if text has already been seen using MD5 hashing."""
        text_hash = hashlib.md5(text.strip().lower().encode("utf-8")).hexdigest()
        if text_hash in self.seen_hashes:
            return True
        self.seen_hashes.add(text_hash)
        return False

    # ────────────────────────────────────────────────────────
    # Validation & Saving
    # ────────────────────────────────────────────────────────
    def validate_and_save(self, packet: Dict[str, Any]) -> bool:
        """Quality gate: validate, deduplicate, scrub PII, and save as JSON + TSV."""
        required = ["image_id", "predicted_text", "corrected_text"]

        # Validate required fields
        if not all(k in packet and packet[k] for k in required):
            print(f"[WARN] Packet rejected: missing or empty required field.")
            self.stats["failed"] += 1
            return False

        # Validate minimum text length
        if len(packet["corrected_text"].strip()) < 3:
            print(f"[WARN] Packet {packet['image_id']} rejected: corrected text too short.")
            self.stats["failed"] += 1
            return False

        # Deduplication check
        if self.is_duplicate(packet["corrected_text"]):
            print(f"[INFO] Packet {packet['image_id']} skipped: duplicate corrected text.")
            self.stats["duplicates"] += 1
            return False

        # PII Scrubbing
        packet["predicted_text"] = self.scrub_pii(packet["predicted_text"])
        packet["corrected_text"] = self.scrub_pii(packet["corrected_text"])

        # Save as individual JSON
        json_path = os.path.join(self.output_dir, f"clean_{packet['image_id']}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(packet, f, ensure_ascii=False, indent=2)

        # Append to TSV (for sentence alignment / translation training)
        tsv_path = os.path.join(self.output_dir, "aligned_corpus.tsv")
        file_exists = os.path.isfile(tsv_path)
        with open(tsv_path, "a", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter="\t")
            if not file_exists:
                writer.writerow(["predicted_text", "corrected_text", "image_id", "confidence"])
            confidence = packet.get("confidence_score", "")
            writer.writerow([
                packet["predicted_text"],
                packet["corrected_text"],
                packet["image_id"],
                confidence,
            ])

        print(f"[SUCCESS] {packet['image_id']} — saved (JSON + TSV)")
        self.stats["passed"] += 1
        return True

    # ────────────────────────────────────────────────────────
    # Report Generation
    # ────────────────────────────────────────────────────────
    def generate_report(self):
        """Generate a Markdown pipeline execution report."""
        report = f"""# Pipeline Execution Report

**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Source:** {self.repo_id}

## Summary

| Metric | Count |
|--------|-------|
| Total Records | {self.stats['total']} |
| Passed | {self.stats['passed']} |
| Failed (validation) | {self.stats['failed']} |
| Duplicates Removed | {self.stats['duplicates']} |
| PII Instances Scrubbed | {self.stats['pii_scrubbed']} |

## Output

- **JSON files:** `{self.output_dir}/clean_*.json`
- **TSV corpus:** `{self.output_dir}/aligned_corpus.tsv`
"""
        os.makedirs(os.path.dirname(REPORT_FILE_PATH), exist_ok=True)
        with open(REPORT_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[INFO] Report saved to {REPORT_FILE_PATH}")

    # ────────────────────────────────────────────────────────
    # Main Pipeline
    # ────────────────────────────────────────────────────────
    def run(self):
        """Execute the full ingestion pipeline."""
        print("=" * 60)
        print("  Medical OCR Data Ingestion Pipeline v2.0 (Arabic Ready)")
        print("=" * 60)

        raw_data = self.fetch_corrections_from_hf()
        self.stats["total"] = len(raw_data)

        print(f"\n[INFO] Processing {self.stats['total']} records ...")
        for packet in raw_data:
            self.validate_and_save(packet)

        self.generate_report()

        print("\n" + "=" * 60)
        print(f"  Pipeline Complete")
        print(f"  Passed: {self.stats['passed']} | Duplicates: {self.stats['duplicates']} | Failed: {self.stats['failed']}")
        print(f"  PII Scrubbed: {self.stats['pii_scrubbed']} instances")
        print("=" * 60)


if __name__ == "__main__":
    pipeline = DataIngestionPipeline()
    pipeline.run()