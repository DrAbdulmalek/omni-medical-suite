# -*- coding: utf-8 -*-
"""Tests for the data collection pipeline.

Run with::

    pytest tests/test_data_collection.py -v
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


class TestSyntheticArabicGenerator:
    """Tests for synthetic Arabic medical image generation."""

    @pytest.fixture()
    def generator(self, tmp_path):
        from services.ocr.data_collection.pipeline import SyntheticArabicGenerator
        return SyntheticArabicGenerator(
            output_dir=str(tmp_path / "synthetic"),
        )

    def test_generate_prescription(self, generator, tmp_path):
        """Generate a prescription image and verify output."""
        img_path, text = generator.generate_prescription_template()
        assert os.path.exists(img_path)
        assert len(text) > 10
        assert Path(img_path).suffix == ".png"

    def test_generate_clinical_note(self, generator):
        """Generate a clinical note image."""
        img_path, text = generator.generate_clinical_note()
        assert os.path.exists(img_path)
        assert len(text) > 10

    def test_generate_random_medical_text(self, generator):
        """Generate a random medical text image."""
        img_path, text = generator.generate_random_medical_text()
        assert os.path.exists(img_path)
        assert len(text) > 5

    def test_generate_batch(self, generator):
        """Generate a batch of images."""
        results = generator.generate_batch(count=10, style="mixed")
        assert len(results) >= 5  # Allow some failures.
        for img_path, text in results:
            assert os.path.exists(img_path)


class TestMedicalImageProcessor:
    """Tests for the medical image processor."""

    @pytest.fixture()
    def processor(self):
        from services.ocr.data_collection.pipeline import MedicalImageProcessor
        return MedicalImageProcessor(target_width=128, target_height=128)

    @pytest.fixture()
    def sample_image(self, tmp_path):
        """Create a simple test image."""
        from PIL import Image
        path = tmp_path / "test_input.png"
        img = Image.new("L", (256, 256), 200)
        # Draw a white rectangle on grey background.
        from PIL import ImageDraw
        draw = ImageDraw.Draw(img)
        draw.rectangle([50, 50, 200, 200], fill=50)
        img.save(str(path))
        return str(path)

    def test_process_single(self, processor, sample_image, tmp_path):
        """Process a single image."""
        out_dir = str(tmp_path / "processed")
        out_path, metadata = processor.process(
            sample_image, output_dir=out_dir, augment=False
        )
        assert os.path.exists(out_path)
        assert "processed_size" in metadata
        assert metadata["format"] == "PNG"

    def test_process_batch(self, processor, sample_image, tmp_path):
        """Process a batch of images from a directory."""
        # Copy sample image multiple times.
        input_dir = tmp_path / "batch_input"
        input_dir.mkdir()
        for i in range(3):
            import shutil
            shutil.copy(sample_image, input_dir / f"img_{i}.png")

        out_dir = str(tmp_path / "batch_output")
        results = processor.process_batch(str(input_dir), out_dir)
        # Batch processing tolerates individual failures gracefully.
        assert len(results) >= 2
        for out_path, meta in results:
            assert os.path.exists(out_path)


class testDataQualityAssurance:
    """Tests for the data quality assurance module."""

    @pytest.fixture()
    def qa(self, tmp_path):
        from services.ocr.data_collection.pipeline import DataQualityAssurance
        return DataQualityAssurance(data_dir=str(tmp_path), min_quality=0.0)

    @pytest.fixture()
    def sample_data(self, tmp_path):
        """Create a small dataset with manifest for QA testing."""
        from PIL import Image, ImageDraw
        import json

        data_dir = tmp_path / "samples"
        img_dir = data_dir / "images"
        img_dir.mkdir(parents=True)
        label_dir = data_dir / "labels"
        label_dir.mkdir(parents=True)

        records = []
        for i in range(5):
            img = Image.new("L", (200, 200), 230)
            draw = ImageDraw.Draw(img)
            draw.text((20, 20), f"Sample {i}", fill=30)
            img_path = img_dir / f"sample_{i}.png"
            img.save(str(img_path))

            text = f"نص عربي تجريبي رقم {i}"
            label_path = label_dir / f"sample_{i}.txt"
            with open(label_path, "w", encoding="utf-8") as f:
                f.write(text)

            records.append({
                "id": f"sample_{i}",
                "image_path": str(img_path),
                "text_label": text,
                "image_hash": f"hash_{i}",
            })

        manifest_path = data_dir / "manifest.jsonl"
        with open(manifest_path, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        return str(data_dir)

    def test_full_assessment(self, qa, sample_data):
        """Run full quality assessment on sample data."""
        report = qa.run_full_assessment()
        assert report.total_samples == 5
        assert report.passed > 0
        assert report.avg_quality_score >= 0.0

    def test_report_summary(self, qa, sample_data):
        """Report summary is a non-empty string."""
        report = qa.run_full_assessment()
        summary = report.summary()
        assert isinstance(summary, str)
        assert len(summary) > 50
        assert "Total samples" in summary
