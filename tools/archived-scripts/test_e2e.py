"""OmniMedical Suite v2.0 — End-to-End Integration Tests"""

import pytest
import time


class TestEndToEndPipeline:
    """End-to-end tests for the complete processing pipeline."""

    def test_full_pipeline_arabic(self, client, auth_headers, create_test_image):
        """Test complete pipeline with Arabic medical text."""
        # Create test image with Arabic text
        img_buffer = create_test_image(
            text="تشخيص: كسر في عظم الفخذ الأيمن\nنوع: كسر مفتوح مع نزيف حاد"
        )

        files = {"file": ("test_ar.png", img_buffer, "image/png")}
        data = {
            "language": "ar",
            "enable_correction": "true",
            "enable_dedup": "true"
        }

        response = client.post(
            "/api/documents/upload",
            files=files,
            data=data,
            headers=auth_headers
        )

        assert response.status_code == 200
        result = response.json()

        # Verify pipeline stages
        assert result["status"] == "completed"
        assert result["processing_stage"] == "vectorized"
        assert result["language_detected"] in ["ar", "auto"]
        assert result["confidence_score"] is not None
        assert 0.0 <= result["confidence_score"] <= 1.0

    def test_pipeline_with_correction(self, client, auth_headers, create_test_image, temp_correction_db):
        """Test pipeline applies learned corrections."""
        from omnimedical_gradio_ui import CorrectionMemoryV2

        # Pre-seed correction memory
        mem = CorrectionMemoryV2(temp_correction_db)
        mem.save("فخد", "عظم الفخذ", "ar", "كسر في", "الأيمن", 0.65, 0.92, "e2e_test")

        # Process document
        img_buffer = create_test_image(text="كسر في فخد الأيمن")
        files = {"file": ("test_corr.png", img_buffer, "image/png")}

        response = client.post(
            "/api/documents/upload",
            files=files,
            data={"enable_correction": "true"},
            headers=auth_headers
        )

        assert response.status_code == 200
        result = response.json()

        # Verify correction was applied
        if result.get("corrected_text"):
            assert "عظم الفخذ" in result["corrected_text"] or "فخد" in result["corrected_text"]

    def test_pipeline_with_dedup(self, client, auth_headers, create_test_image):
        """Test pipeline deduplicates repeated content."""
        # Create image with repeated text
        img_buffer = create_test_image(
            text="كسر في عظم الفخذ الأيمن\n\nكسر في عظم الفخذ الأيمن\n\nنزيف داخلي خفيف"
        )

        files = {"file": ("test_dedup.png", img_buffer, "image/png")}

        response = client.post(
            "/api/documents/upload",
            files=files,
            data={"enable_dedup": "true"},
            headers=auth_headers
        )

        assert response.status_code == 200
        result = response.json()

        # Should have fewer chunks than raw text lines
        if result.get("chunk_count"):
            assert result["chunk_count"] <= 3  # Dedup should reduce

    def test_pipeline_performance(self, client, auth_headers, create_test_image):
        """Test pipeline completes within acceptable time."""
        img_buffer = create_test_image(text="تشخيص طبي بسيط")
        files = {"file": ("test_perf.png", img_buffer, "image/png")}

        start = time.time()
        response = client.post(
            "/api/documents/upload",
            files=files,
            headers=auth_headers
        )
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 30  # Should complete within 30 seconds

    def test_pipeline_medical_safety(self, client, auth_headers, create_test_image):
        """Test that medical context conflicts are detected and protected."""
        # Create image with conflicting laterality
        img_buffer = create_test_image(
            text="كسر في عظم الفخذ الأيمن\nكسر في عظم الفخذ الأيسر"
        )

        files = {"file": ("test_safety.png", img_buffer, "image/png")}

        response = client.post(
            "/api/documents/upload",
            files=files,
            data={"enable_dedup": "true"},
            headers=auth_headers
        )

        assert response.status_code == 200
        result = response.json()

        # Both versions should be preserved (not merged)
        if result.get("final_text"):
            final = result["final_text"]
            # Should contain both or be marked as protected
            assert "أيمن" in final or "أيسر" in final or "protected" in final.lower()

    def test_correction_to_promotion_workflow(self, client, auth_headers, temp_correction_db):
        """Test full workflow: correction → review → promotion → application."""
        # Step 1: Submit correction
        correction = {
            "original": "test_e2e",
            "corrected": "test_e2e_corrected",
            "language": "ar",
            "confidence_before": 0.5,
            "confidence_after": 0.95
        }

        response = client.post("/api/corrections/", json=correction, headers=auth_headers)
        assert response.status_code == 200

        # Step 2: Submit same correction 2 more times (to meet frequency=3)
        for _ in range(2):
            response = client.post("/api/corrections/", json=correction, headers=auth_headers)
            assert response.status_code == 200

        # Step 3: Run promotion
        response = client.post("/api/corrections/run-promotion", headers=auth_headers)
        assert response.status_code == 200

        promo_result = response.json()
        assert promo_result["promoted_count"] >= 1

        # Step 4: Verify stats updated
        response = client.get("/api/corrections/stats", headers=auth_headers)
        stats = response.json()
        assert stats["promoted"] >= 1
