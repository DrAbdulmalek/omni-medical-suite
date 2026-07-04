"""OmniMedical Suite v2.0 — Fusion V2 Tests"""

import pytest
from omnimedical_gradio_ui import OCRFusionV2, SpatialToken


class TestOCRFusionV2:
    """Test suite for OCR Fusion V2 spatial-confidence engine."""

    def test_fusion_basic(self, mock_ocr_engine_results):
        """Test basic fusion of multiple engine outputs."""
        fusion = OCRFusionV2(spatial_eps=20.0)
        result = fusion.fuse(mock_ocr_engine_results)

        assert len(result) > 0
        # Should merge "كسر في عظم" + "فخد"/"الفخذ" → "كسر في عظم الفخذ"
        texts = [t.text for t in result]
        assert any("كسر" in t for t in texts)

    def test_fusion_confidence_calculation(self, mock_ocr_engine_results):
        """Test that fused confidence is within valid range."""
        fusion = OCRFusionV2()
        result = fusion.fuse(mock_ocr_engine_results)

        for token in result:
            assert 0.0 <= token.confidence <= 1.0
            # Higher agreement should yield higher confidence
            if token.engine == "fusion_v2":
                assert token.confidence >= 0.55  # min_conf threshold

    def test_fusion_medical_term_boost(self):
        """Test that medical terms get confidence boost."""
        fusion = OCRFusionV2()

        # Create tokens with medical term
        medical_tokens = [
            [SpatialToken("عظم الفخذ", 0.80, (10, 20, 100, 40), "tesseract")],
            [SpatialToken("عظم الفخذ", 0.85, (12, 22, 98, 38), "easyocr")],
        ]

        result = fusion.fuse(medical_tokens)
        assert len(result) == 1
        assert result[0].text == "عظم الفخذ"
        # Medical term should have boosted confidence
        assert result[0].confidence > 0.80

    def test_fusion_empty_input(self):
        """Test fusion handles empty input gracefully."""
        fusion = OCRFusionV2()
        result = fusion.fuse([])
        assert result == []

    def test_fusion_single_engine(self):
        """Test fusion with single engine (pass-through)."""
        fusion = OCRFusionV2()
        single_engine = [
            [SpatialToken("test", 0.90, (0, 0, 50, 20), "tesseract")]
        ]
        result = fusion.fuse(single_engine)
        assert len(result) == 1
        assert result[0].text == "test"

    def test_spatial_clustering(self):
        """Test that spatially distant tokens are not merged."""
        fusion = OCRFusionV2(spatial_eps=10.0)

        # Two tokens far apart
        tokens = [
            [SpatialToken("كسر", 0.90, (10, 20, 50, 40), "tesseract")],
            [SpatialToken("نزيف", 0.90, (500, 500, 550, 520), "easyocr")],
        ]

        result = fusion.fuse(tokens)
        assert len(result) == 2  # Should remain separate

    def test_get_confidence_map(self, mock_ocr_engine_results):
        """Test confidence map DataFrame generation."""
        fusion = OCRFusionV2()
        result = fusion.fuse(mock_ocr_engine_results)
        df = fusion.get_confidence_map(result)

        assert not df.empty
        assert "text" in df.columns
        assert "confidence" in df.columns
        assert "engines" in df.columns
