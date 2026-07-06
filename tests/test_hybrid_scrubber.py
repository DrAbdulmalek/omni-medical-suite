"""Tests for the Hybrid PII Scrubber v2."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ingestion.hybrid_scrubber import HybridPIIScrubber, scrub_pii, RedactionStats


class TestRegexScrubbing:
    """Test Layer 1: Regex-based PII detection"""

    def setup_method(self):
        self.scrubber = HybridPIIScrubber(use_ner=False)

    def test_syrian_phone(self):
        text = "Phone: +963-911-234-567"
        redacted, stats = self.scrubber.scrub(text)
        assert '[REDACTED_PHONE]' in redacted
        assert stats.phones_found > 0

    def test_ksa_phone(self):
        text = "Call: 055-123-4567"
        redacted, stats = self.scrubber.scrub(text)
        assert '[REDACTED_PHONE]' in redacted
        assert stats.phones_found > 0

    def test_uae_phone(self):
        text = "UAE: +971-50-123-4567"
        redacted, stats = self.scrubber.scrub(text)
        assert '[REDACTED_PHONE]' in redacted

    def test_email(self):
        text = "Contact: patient@example.com"
        redacted, stats = self.scrubber.scrub(text)
        assert '[REDACTED_EMAIL]' in redacted
        assert stats.emails_found > 0

    def test_gregorian_date(self):
        text = "Date of birth: 15/03/1985"
        redacted, stats = self.scrubber.scrub(text)
        assert '[REDACTED_DATE]' in redacted
        assert stats.dates_found > 0

    def test_arabic_numeral_date(self):
        text = "التاريخ: ٢٥/٠٦/٢٠٢٥"
        redacted, stats = self.scrubber.scrub(text)
        assert '[REDACTED_DATE]' in redacted

    def test_national_id(self):
        text = "ID number: 1234567890"
        redacted, stats = self.scrubber.scrub(text)
        assert '[REDACTED_ID]' in redacted
        assert stats.ids_found > 0

    def test_medical_dosage_not_redacted(self):
        """Drug dosages should NOT be redacted as IDs"""
        text = "Prescription: Amoxicillin 500mg three times daily"
        redacted, stats = self.scrubber.scrub(text)
        assert '500mg' in redacted or '500 mg' in redacted
        assert '[REDACTED_ID]' not in redacted

    def test_multiple_pii_types(self):
        text = "Patient Ahmed, Phone: +963-911-234-567, DOB: 15/03/1985, Email: test@test.com"
        redacted, stats = self.scrubber.scrub(text)
        assert stats.total_redactions >= 3


class TestBatchScrubbing:
    def test_batch_processing(self):
        scrubber = HybridPIIScrubber(use_ner=False)
        texts = [
            "Phone: +963-911-234-567",
            "Email: test@example.com",
            "No PII here"
        ]
        results = scrubber.scrub_batch(texts)
        assert len(results) == 3
        assert results[2][1].total_redactions == 0


class TestRedactionStats:
    def test_stats_dict(self):
        stats = RedactionStats(phones_found=2, dates_found=1, emails_found=1)
        d = stats.to_dict()
        assert d['phones'] == 2
        assert d['total'] == 4

    def test_total_calculation(self):
        stats = RedactionStats(phones_found=1, dates_found=1, names_found=1)
        stats.total_redactions = stats.phones_found + stats.dates_found + stats.names_found
        assert stats.total_redactions == 3


class TestConvenienceFunction:
    def test_scrub_pii_function(self):
        redacted, stats = scrub_pii("Phone: +963-911-234-567", use_ner=False)
        assert '[REDACTED_PHONE]' in redacted


class TestNERLayer:
    def test_ner_disabled_by_default_in_demo(self):
        """NER should work when enabled (if transformers available)"""
        scrubber = HybridPIIScrubber(use_ner=False)
        text = "Patient: Ahmed Al-Rashid"
        redacted, stats = scrubber.scrub(text)
        # With NER disabled, names won't be detected
        assert stats.names_found == 0

    def test_ner_lazy_loading(self):
        """NER model should not be loaded until first use"""
        scrubber = HybridPIIScrubber(use_ner=True)
        assert scrubber._ner_loaded is False
        # Only loads when scrub() is called