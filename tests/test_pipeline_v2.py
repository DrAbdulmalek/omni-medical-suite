#!/usr/bin/env python3
"""
Tests for Data Ingestion Pipeline v2.0
Covers: PII scrubbing (Arabic + English), Deduplication, TSV output, Validation.
"""

import os
import sys
import json
import csv
import tempfile
import shutil

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ingestion.ingest_and_clean_v2 import DataIngestionPipeline


class TestPIIScrubbing:
    """Test PII detection and scrubbing for Arabic and English patterns."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.pipeline = DataIngestionPipeline(output_dir=self.tmp_dir)

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_syrian_phone_scrubbed(self):
        text = "الهاتف 0933112233"
        result = self.pipeline.scrub_pii(text)
        assert "0933112233" not in result
        assert "محجوب" in result

    def test_syrian_phone_with_country_code(self):
        text = "phone +963-933-112233"
        result = self.pipeline.scrub_pii(text)
        assert "+963" not in result
        assert "محجوب" in result

    def test_saudi_phone_scrubbed(self):
        text = "0551234567"
        result = self.pipeline.scrub_pii(text)
        assert "0551234567" not in result

    def test_uae_phone_scrubbed(self):
        text = "+971 50 123 4567"
        result = self.pipeline.scrub_pii(text)
        assert "971" not in result

    def test_gregorian_date_scrubbed(self):
        text = "DOB 12/05/1985"
        result = self.pipeline.scrub_pii(text)
        assert "12/05/1985" not in result
        assert "محجوب" in result

    def test_iso_date_scrubbed(self):
        text = "surgery on 2026-07-15"
        result = self.pipeline.scrub_pii(text)
        assert "2026-07-15" not in result

    def test_arabic_numeral_date_scrubbed(self):
        text = "تاريخ الفحص ٢٥/٠٦/٢٠٢٦"
        result = self.pipeline.scrub_pii(text)
        assert "٢٥/٠٦/٢٠٢٦" not in result
        assert "محجوب" in result

    def test_national_id_scrubbed(self):
        text = "national ID 12345678901"
        result = self.pipeline.scrub_pii(text)
        assert "12345678901" not in result
        assert "هوية" in result or "محجوب" in result

    def test_email_scrubbed(self):
        text = "email: doctor@example.com"
        result = self.pipeline.scrub_pii(text)
        assert "doctor@example.com" not in result
        assert "محجوب" in result

    def test_empty_text_unchanged(self):
        assert self.pipeline.scrub_pii("") == ""
        assert self.pipeline.scrub_pii(None) is None

    def test_medical_text_preserved(self):
        """Ensure medical terminology is NOT falsely redacted."""
        text = "تشخيص: كسر في عظمة الساق. Total knee replacement."
        result = self.pipeline.scrub_pii(text)
        assert "كسر" in result
        assert "عظمة" in result
        assert "knee" in result


class TestDeduplication:
    """Test hash-based deduplication."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.pipeline = DataIngestionPipeline(output_dir=self.tmp_dir)

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_identical_text_detected_as_duplicate(self):
        assert self.pipeline.is_duplicate("مرحبا بالعالم") is False
        assert self.pipeline.is_duplicate("مرحبا بالعالم") is True

    def test_different_text_not_duplicate(self):
        assert self.pipeline.is_duplicate("نص أول") is False
        assert self.pipeline.is_duplicate("نص ثاني") is False

    def test_case_insensitive_dedup(self):
        assert self.pipeline.is_duplicate("Hello World") is False
        assert self.pipeline.is_duplicate("hello world") is True

    def test_whitespace_normalized_dedup(self):
        assert self.pipeline.is_duplicate("نص مع مسافات  ") is False
        assert self.pipeline.is_duplicate("  نص مع مسافات") is True


class TestValidation:
    """Test packet validation logic."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.pipeline = DataIngestionPipeline(output_dir=self.tmp_dir)

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_valid_packet_passes(self):
        packet = {
            "image_id": "test_001.png",
            "predicted_text": " predicted text",
            "corrected_text": "corrected text long enough",
        }
        assert self.pipeline.validate_and_save(packet) is True
        assert self.pipeline.stats["passed"] == 1

    def test_missing_field_fails(self):
        packet = {
            "image_id": "test_002.png",
            "predicted_text": "some text",
            # missing corrected_text
        }
        assert self.pipeline.validate_and_save(packet) is False
        assert self.pipeline.stats["failed"] == 1

    def test_short_text_fails(self):
        packet = {
            "image_id": "test_003.png",
            "predicted_text": "text",
            "corrected_text": "ab",
        }
        assert self.pipeline.validate_and_save(packet) is False

    def test_duplicate_packet_skipped(self):
        packet = {
            "image_id": "test_004.png",
            "predicted_text": "original",
            "corrected_text": "this is a unique correction text for testing",
        }
        assert self.pipeline.validate_and_save(packet) is True

        packet2 = {
            "image_id": "test_005.png",
            "predicted_text": "other",
            "corrected_text": "this is a unique correction text for testing",
        }
        assert self.pipeline.validate_and_save(packet2) is False
        assert self.pipeline.stats["duplicates"] == 1


class TestTSVOutput:
    """Test TSV file generation for sentence alignment."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.pipeline = DataIngestionPipeline(output_dir=self.tmp_dir)

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_tsv_file_created(self):
        packet = {
            "image_id": "tsv_test.png",
            "predicted_text": "predicted",
            "corrected_text": "corrected text for tsv test",
            "confidence_score": 0.95,
        }
        self.pipeline.validate_and_save(packet)

        tsv_path = os.path.join(self.tmp_dir, "aligned_corpus.tsv")
        assert os.path.isfile(tsv_path)

    def test_tsv_header(self):
        packet = {
            "image_id": "header_test.png",
            "predicted_text": "p",
            "corrected_text": "corrected text for header test",
        }
        self.pipeline.validate_and_save(packet)

        tsv_path = os.path.join(self.tmp_dir, "aligned_corpus.tsv")
        with open(tsv_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            header = next(reader)
            assert "predicted_text" in header
            assert "corrected_text" in header
            assert "image_id" in header

    def test_tsv_rows_match_passed_packets(self):
        for i in range(3):
            packet = {
                "image_id": f"row_{i}.png",
                "predicted_text": f"predicted {i}",
                "corrected_text": f"corrected text number {i}",
            }
            self.pipeline.validate_and_save(packet)

        tsv_path = os.path.join(self.tmp_dir, "aligned_corpus.tsv")
        with open(tsv_path, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f, delimiter="\t"))
            # 1 header + 3 data rows
            assert len(rows) == 4

    def test_pii_scrubbed_in_tsv(self):
        packet = {
            "image_id": "pii_tsv.png",
            "predicted_text": "phone 0933112233",
            "corrected_text": "patient called 0933112233 for appointment",
        }
        self.pipeline.validate_and_save(packet)

        tsv_path = os.path.join(self.tmp_dir, "aligned_corpus.tsv")
        with open(tsv_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "0933112233" not in content


class TestEndToEnd:
    """Full pipeline execution test with mock data."""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.pipeline = DataIngestionPipeline(output_dir=self.tmp_dir)

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_full_pipeline_with_mock_data(self):
        """Run pipeline with built-in mock data and verify outputs."""
        self.pipeline.fetch_corrections_from_hf = lambda: self.pipeline._mock_data()
        self.pipeline.run()

        # 5 mock records, 1 is a duplicate of scan_001 → 4 unique
        assert self.pipeline.stats["total"] == 5
        assert self.pipeline.stats["passed"] == 4
        assert self.pipeline.stats["duplicates"] == 1
        assert self.pipeline.stats["pii_scrubbed"] > 0

        # Verify JSON files created
        json_files = [f for f in os.listdir(self.tmp_dir) if f.endswith(".json")]
        assert len(json_files) == 4  # 5 - 1 duplicate

        # Verify TSV created
        tsv_path = os.path.join(self.tmp_dir, "aligned_corpus.tsv")
        assert os.path.isfile(tsv_path)

        # Verify PII redacted in saved JSON
        for jf in json_files:
            with open(os.path.join(self.tmp_dir, jf), "r", encoding="utf-8") as f:
                data = json.load(f)
                # No raw phone numbers should remain
                assert "0933" not in json.dumps(data)
                assert "12345678901" not in json.dumps(data)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))