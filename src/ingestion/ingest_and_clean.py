#!/usr/bin/env python3
"""
Medical OCR Training Hub - Data Ingestion & Cleaning Script (v1.1)
Author: DrAbdulmalek
Description: Automatically pulls corrected OCR data from Hugging Face Spaces,
             validates structure, and scrubs PII (Anonymization) before Ground Truth routing.
"""

import os
import json
import re
from typing import Dict, Any, List

# Configuration
HF_SPACE_API_URL = "https://huggingface.co/api/spaces/DrAbdulmalek/handwriting-ocr/host"
TARGET_OUTPUT_DIR = "./data/ingested_corrections"


class DataIngestionPipeline:
    """Orchestrates data ingestion, PII scrubbing, and quality validation."""

    def __init__(self, api_url: str, output_dir: str):
        self.api_url = api_url
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"[INFO] Pipeline initialized. Output directory: {self.output_dir}")

        # PII detection patterns
        self.phone_pattern = re.compile(
            r'\+?\d{1,4}[-.\s]?\(?\d{1,3}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}'
        )
        self.date_pattern = re.compile(r'\b\d{1,2}[-/\s]\d{1,2}[-/\s]\d{2,4}\b')

    def fetch_corrections_from_hf(self) -> List[Dict[str, Any]]:
        """Fetch corrected data from Hugging Face Space API."""
        print("[INFO] Fetching latest correction logs from Hugging Face Space...")
        # Mock data for initial testing — replace with actual HF API call
        mock_data = [
            {
                "image_id": "scan_002.png",
                "predicted_text": "Patient John Doe with phone 0933112233 shows symptoms of acute appendicitis",
                "corrected_text": "Patient John Doe, DOB 12/05/1985, phone +963-933-112233 shows symptoms of acute appendicitis.",
                "confidence_score": 0.95,
                "metadata": {"dpi": 300, "is_handwritten": True}
            }
        ]
        return mock_data

    def scrub_pii(self, text: str) -> str:
        """Redact PII: phone numbers, dates, and sensitive identifiers."""
        scrubbed_text = text
        scrubbed_text = self.phone_pattern.sub("[REDACTED_PHONE]", scrubbed_text)
        scrubbed_text = self.date_pattern.sub("[REDACTED_DATE]", scrubbed_text)
        return scrubbed_text

    def validate_and_clean(self, data_packet: Dict[str, Any]) -> bool:
        """Quality gate: validate required fields and data quality."""
        required_fields = ["image_id", "predicted_text", "corrected_text"]

        for field in required_fields:
            if field not in data_packet or not data_packet[field]:
                print(f"[WARN] Packet rejected: Missing or empty required field '{field}'")
                return False

        if len(data_packet["corrected_text"].strip()) < 3:
            print(f"[WARN] Packet {data_packet['image_id']} rejected: Corrected text is too short.")
            return False

        print(f"[SUCCESS] Packet {data_packet['image_id']} passed structural validation.")
        return True

    def save_to_hub(self, valid_packet: Dict[str, Any]):
        """Apply PII scrubbing and save cleaned data."""
        valid_packet["corrected_text"] = self.scrub_pii(valid_packet["corrected_text"])
        valid_packet["predicted_text"] = self.scrub_pii(valid_packet["predicted_text"])

        output_file = os.path.join(self.output_dir, f"clean_{valid_packet['image_id']}.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(valid_packet, f, ensure_ascii=False, indent=4)
        print(f"[INFO] Securely scrubbed data saved to {output_file}")

    def run_pipeline(self):
        """Execute the full ingestion pipeline."""
        raw_data = self.fetch_corrections_from_hf()
        for packet in raw_data:
            if self.validate_and_clean(packet):
                self.save_to_hub(packet)
        print("[INFO] Pipeline execution finished successfully.")


if __name__ == "__main__":
    pipeline = DataIngestionPipeline(api_url=HF_SPACE_API_URL, output_dir=TARGET_OUTPUT_DIR)
    pipeline.run_pipeline()