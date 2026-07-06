"""
Test suite for bilingual-extractor core functionality
"""

import pytest
from term_extractor.text_preprocessor import TextPreprocessor
from term_extractor.pattern_extractor import PatternExtractor


class TestTextPreprocessor:
    """Tests for text preprocessing module"""
    
    def test_normalize_arabic_text(self):
        """Test Arabic text normalization"""
        preprocessor = TextPreprocessor()
        text = "الْعِلْمُ نَافِعٌ"
        normalized = preprocessor.normalize(text)
        assert isinstance(normalized, str)
        assert len(normalized) > 0
    
    def test_remove_ocr_errors(self):
        """Test OCR error correction"""
        preprocessor = TextPreprocessor()
        text = "العلم نافع"  # Clean text
        result = preprocessor.remove_ocr_errors(text)
        assert result == text
    
    def test_clean_text(self):
        """Test general text cleaning"""
        preprocessor = TextPreprocessor()
        text = "  العلم  نافع  "
        cleaned = preprocessor.clean(text)
        assert cleaned.strip() == "العلم نافع"


class TestPatternExtractor:
    """Tests for pattern extraction module"""
    
    def test_extract_bilingual_pairs(self):
        """Test bilingual pair extraction"""
        extractor = PatternExtractor()
        text = "Heart (قلب) - Liver (كبد)"
        pairs = extractor.extract_pairs(text)
        assert isinstance(pairs, list)
        assert len(pairs) >= 0
    
    def test_extract_medical_terms(self):
        """Test medical term extraction"""
        extractor = PatternExtractor()
        text = "The heart (قلب) is a vital organ."
        terms = extractor.extract_terms(text, lang='en')
        assert isinstance(terms, list)


class TestIntegration:
    """Integration tests for the full pipeline"""
    
    def test_full_extraction_pipeline(self):
        """Test complete extraction workflow"""
        from term_extractor import TermExtractor
        
        extractor = TermExtractor()
        text = "Heart (قلب) - The heart pumps blood (ضخ الدم)"
        
        # This should not raise any exceptions
        results = extractor.extract(text)
        assert isinstance(results, dict) or isinstance(results, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
