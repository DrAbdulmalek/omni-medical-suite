#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hybrid PII Scrubber v2 - Medical OCR Training Hub
Author: DrAbdulmalek
Description: Hybrid PII redaction engine combining:
             - Fast Regex for phones, dates, emails, IDs
             - AI-powered NER (CamelBERT) for Arabic names and organizations
This is PII Shield v2 - replacing pure-regex approach for better Arabic entity coverage.
"""

import re
import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class RedactionStats:
    """Statistics about what was redacted"""
    phones_found: int = 0
    dates_found: int = 0
    emails_found: int = 0
    ids_found: int = 0
    names_found: int = 0
    organizations_found: int = 0
    total_redactions: int = 0

    def to_dict(self) -> Dict:
        total = (self.phones_found + self.dates_found + self.emails_found +
                 self.ids_found + self.names_found + self.organizations_found)
        return {
            'phones': self.phones_found,
            'dates': self.dates_found,
            'emails': self.emails_found,
            'ids': self.ids_found,
            'names': self.names_found,
            'organizations': self.organizations_found,
            'total': total
        }


class HybridPIIScrubber:
    """
    Hybrid PII Scrubber combining Regex speed with NER accuracy.
    
    Architecture:
    ┌─────────────────────────────────────┐
    │          Input Text                 │
    └──────────┬──────────────────────────┘
               │
    ┌──────────▼──────────────────────────┐
    │  Layer 1: Regex (Fast, 0ms)         │
    │  - Phones (Syrian, KSA, UAE, INTL)  │
    │  - Dates (Gregorian, Arabic-numeral)│
    │  - Emails                           │
    │  - National IDs (10-12 digits)      │
    └──────────┬──────────────────────────┘
               │
    ┌──────────▼──────────────────────────┐
    │  Layer 2: NER (Accurate, ~500ms)    │
    │  - Arabic Person Names (PER)        │
    │  - Organizations (ORG)              │
    │  Model: CAMeL-Lab/bert-base-arabic   │
    │         camelbert-msa-ner           │
    └──────────┬──────────────────────────┘
               │
    ┌──────────▼──────────────────────────┐
    │          Redacted Text              │
    └─────────────────────────────────────┘
    """

    # Regex patterns for Layer 1 (Fast scrubbing)
    # ORDER MATTERS: dates, IDs, and emails must run BEFORE the generic phone
    # pattern to prevent the broad phone regex from consuming them.
    REGEX_PATTERNS: List[Tuple[re.Pattern, str]] = [
        # --- Dates (run first to avoid phone-pattern conflicts) ---

        # Gregorian dates: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD, etc.
        (re.compile(r'\b\d{1,2}[-/.\s]\d{1,2}[-/.\s]\d{2,4}\b'), '[REDACTED_DATE]'),

        # Arabic-numeral dates: using ٠-٩
        (re.compile(r'[٠-٩]{1,2}[-/.\s][٠-٩]{1,2}[-/.\s][٠-٩]{2,4}'), '[REDACTED_DATE]'),

        # --- National IDs (before generic phone to avoid false matches) ---

        # National IDs: 10-12 consecutive digits (not part of larger number)
        (re.compile(r'(?<!\d)\d{10,12}(?!\d)'), '[REDACTED_ID]'),

        # --- Emails ---

        # Email addresses
        (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[REDACTED_EMAIL]'),

        # --- Phone numbers (specific patterns first, generic last) ---

        # Syrian phone numbers: +963-xxx-xxx-xxxx or 09xx-xxx-xxxx
        (re.compile(r'\+?963[-.\s]?\d{1}[-.\s]?\d{3}[-.\s]?\d{4}'), '[REDACTED_PHONE]'),
        (re.compile(r'0?9\d{1}[-.\s]?\d{3}[-.\s]?\d{4}'), '[REDACTED_PHONE]'),

        # KSA phone numbers: +966-5x-xxx-xxxx or 05x-xxx-xxxx
        (re.compile(r'\+?966[-.\s]?5\d[-.\s]?\d{3}[-.\s]?\d{4}'), '[REDACTED_PHONE]'),
        (re.compile(r'0?5\d[-.\s]?\d{3}[-.\s]?\d{4}'), '[REDACTED_PHONE]'),

        # UAE phone numbers: +971-5x-xxx-xxxx
        (re.compile(r'\+?971[-.\s]?5\d[-.\s]?\d{3}[-.\s]?\d{4}'), '[REDACTED_PHONE]'),

        # International phone (generic) — requires at least one separator
        # to avoid matching dates or bare digit sequences
        (re.compile(r'\+?\d{1,4}[-.\s]\(?\d{1,4}\)?[-.\s]\d{1,4}[-.\s]?\d{1,9}'), '[REDACTED_PHONE]'),
    ]

    # Medical terms to PROTECT from redaction (false positive prevention)
    PROTECTED_MEDICAL_TERMS = {
        # Drug dosages that look like IDs
        '500mg', '250mg', '100mg', '50mg', '10mg', '5mg', '1mg',
        '500 mg', '250 mg', '100 mg', '50 mg', '10 mg', '5 mg', '1 mg',
        # Common medical codes
        'BP', 'HR', 'RR', 'SpO2', 'BMI',
        # Lab values that look like dates
    }

    def __init__(self, use_ner: bool = True, ner_model: Optional[str] = None):
        """
        Initialize the hybrid scrubber.
        
        Args:
            use_ner: Whether to use NER for name detection (slower but more accurate)
            ner_model: HuggingFace model name for NER (default: CamelBERT)
        """
        self.use_ner = use_ner
        self.ner_model_name = ner_model or "CAMeL-Lab/bert-base-arabic-camelbert-msa-ner"
        self._ner_pipeline = None
        self._ner_loaded = False

        # Compile regex patterns
        self._compiled_patterns = [
            (pattern, replacement) for pattern, replacement in self.REGEX_PATTERNS
        ]

    def _load_ner_model(self):
        """Lazy-load the NER model (only when first needed)"""
        if self._ner_loaded:
            return
        try:
            from transformers import pipeline
            logger.info(f"Loading NER model: {self.ner_model_name}...")
            self._ner_pipeline = pipeline(
                "ner",
                model=self.ner_model_name,
                aggregation_strategy="simple"
            )
            self._ner_loaded = True
            logger.info("NER model loaded successfully")
        except ImportError:
            logger.warning("transformers not installed, NER disabled. Install with: pip install transformers")
            self.use_ner = False
        except Exception as e:
            logger.warning(f"Failed to load NER model: {e}. Falling back to regex-only mode.")
            self.use_ner = False

    def scrub(self, text: str) -> Tuple[str, RedactionStats]:
        """
        Scrub PII from text using both Regex and NER layers.
        
        Args:
            text: Input text that may contain PII
            
        Returns:
            Tuple of (redacted_text, statistics)
        """
        stats = RedactionStats()
        redacted = text

        # Layer 1: Fast Regex scrubbing
        redacted, stats = self._regex_scrub(redacted, stats)

        # Layer 2: AI-powered NER scrubbing
        if self.use_ner:
            redacted, stats = self._ner_scrub(redacted, stats)

        stats.total_redactions = (
            stats.phones_found + stats.dates_found + stats.emails_found +
            stats.ids_found + stats.names_found + stats.organizations_found
        )

        return redacted, stats

    def _regex_scrub(self, text: str, stats: RedactionStats) -> Tuple[str, RedactionStats]:
        """Layer 1: Fast regex-based PII detection"""
        for pattern, replacement in self._compiled_patterns:
            matches = pattern.findall(text)
            text = pattern.sub(replacement, text)

            if '[REDACTED_PHONE]' in replacement and matches:
                stats.phones_found += len(matches)
            elif '[REDACTED_DATE]' in replacement and matches:
                stats.dates_found += len(matches)
            elif '[REDACTED_EMAIL]' in replacement and matches:
                stats.emails_found += len(matches)
            elif '[REDACTED_ID]' in replacement and matches:
                stats.ids_found += len(matches)

        return text, stats

    def _ner_scrub(self, text: str, stats: RedactionStats) -> Tuple[str, RedactionStats]:
        """Layer 2: NER-based entity detection for Arabic names and orgs"""
        self._load_ner_model()
        if not self._ner_pipeline:
            return text, stats

        try:
            entities = self._ner_pipeline(text)
            # Replace from right to left to preserve character indices
            for entity in reversed(entities):
                entity_group = entity.get('entity_group', '')
                if entity_group in ['PER', 'B-PER', 'I-PER']:
                    # Check it's not a medical term (false positive prevention)
                    entity_text = text[entity['start']:entity['end']]
                    if entity_text.strip() not in self.PROTECTED_MEDICAL_TERMS:
                        text = text[:entity['start']] + '[REDACTED_NAME]' + text[entity['end']:]
                        stats.names_found += 1
                elif entity_group in ['ORG', 'B-ORG', 'I-ORG']:
                    text = text[:entity['start']] + '[REDACTED_ORG]' + text[entity['end']:]
                    stats.organizations_found += 1
        except Exception as e:
            logger.error(f"NER scrubbing failed: {e}")

        return text, stats

    def scrub_batch(self, texts: List[str]) -> List[Tuple[str, RedactionStats]]:
        """Scrub multiple texts. Returns list of (redacted_text, stats) tuples."""
        results = []
        for text in texts:
            redacted, stats = self.scrub(text)
            results.append((redacted, stats))
        return results


# Convenience function for backward compatibility
def scrub_pii(text: str, use_ner: bool = True) -> Tuple[str, RedactionStats]:
    """
    Convenience function to scrub PII from text.
    Compatible with the existing v1 scrub_pii interface but adds NER support.
    """
    scrubber = HybridPIIScrubber(use_ner=use_ner)
    return scrubber.scrub(text)


if __name__ == '__main__':
    # Demo
    print("=" * 60)
    print("Hybrid PII Scrubber v2 - Demo")
    print("=" * 60)

    test_texts = [
        "Patient: Ahmed Al-Rashid, Phone: +963-911-234-567, DOB: 15/03/1985",
        "Dr. Mohammed works at Al-Mouwasat Hospital. Contact: 055-123-4567",
        "Email: patient@example.com, ID: 1234567890, Date: ٢٠٢٥/٠٦/٢٥",
        "Prescription: Amoxicillin 500mg three times daily",  # Should NOT redact 500mg
    ]

    scrubber = HybridPIIScrubber(use_ner=False)  # Start with regex-only for demo

    for text in test_texts:
        redacted, stats = scrubber.scrub(text)
        print(f"\nOriginal:  {text}")
        print(f"Redacted:  {redacted}")
        print(f"Stats:     {stats.to_dict()}")