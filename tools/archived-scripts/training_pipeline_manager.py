#!/usr/bin/env python3
"""
training_pipeline_manager.py — Complete OCR Training Pipeline Manager
=======================================================================
Manages the full workflow from importing ground truth to generating
training data for model fine-tuning (TrOCR, Tesseract, etc.).

Workflow:
    1. Import GT (ABBYY/ReadIRIS/PDF Grabber)
    2. Run OCR with multiple engines
    3. Compare and generate error analysis
    4. Create training pairs
    5. Export for model fine-tuning

Usage:
    python training_pipeline_manager.py --config pipeline_config.json
    python training_pipeline_manager.py --gt abbyy.docx --image doc.jpg --run-all

Author: Dr. Abdulmalek
Version: 1.0.0
Date: 2026-06-04
"""

import json
import os
import sys
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the training pipeline."""
    gt_source: str = ""           # Path to ground truth file
    image_path: str = ""         # Path to scanned image
    ocr_engines: List[str] = None
    output_dir: str = "training_output"
    fusion_strategy: str = "hybrid"
    medical_dict: str = "arabic_medical_dict.json"
    font_data: str = ""
    generate_visualizations: bool = True
    export_format: str = "json"  # json, csv, lmdb (for TrOCR)

    def __post_init__(self):
        if self.ocr_engines is None:
            self.ocr_engines = ["tesseract", "easyocr", "paddleocr"]


class TrainingPipeline:
    """Main pipeline orchestrator."""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.results = {}

    def run(self):
        """Execute the full pipeline."""
        logger.info("=" * 70)
        logger.info("🚀 Starting OCR Training Pipeline")
        logger.info("=" * 70)

        # Step 1: Import Ground Truth
        self.step1_import_gt()

        # Step 2: Run OCR Engines
        self.step2_run_ocr()

        # Step 3: Fuse Results
        self.step3_fusion()

        # Step 4: Compare with GT
        self.step4_compare()

        # Step 5: Generate Training Data
        self.step5_generate_training()

        # Step 6: Export
        self.step6_export()

        logger.info("\n" + "=" * 70)
        logger.info("✅ Pipeline Complete!")
        logger.info(f"📁 Output directory: {self.output_dir}")
        logger.info("=" * 70)

    def step1_import_gt(self):
        """Import ground truth from external source."""
        logger.info("\n📖 Step 1: Importing Ground Truth")

        if not self.config.gt_source:
            logger.warning("No GT source provided. Skipping.")
            return

        gt_path = Path(self.config.gt_source)
        output_txt = self.output_dir / "ground_truth.txt"
        output_json = self.output_dir / "ground_truth.json"

        # Use import_ground_truth.py
        cmd = [
            sys.executable, "import_ground_truth.py",
            str(gt_path),
            "--output", str(output_json),
            "--format", "json"
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"✅ GT imported: {output_json}")
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ GT import failed: {e.stderr}")

    def step2_run_ocr(self):
        """Run multiple OCR engines."""
        logger.info("\n🔍 Step 2: Running OCR Engines")

        if not self.config.image_path:
            logger.warning("No image provided. Skipping OCR.")
            return

        for engine in self.config.ocr_engines:
            output_file = self.output_dir / f"ocr_{engine}.json"
            logger.info(f"  Running {engine}...")

            # This would call actual OCR engines
            # For now, create placeholder
            placeholder = {
                "engine": engine,
                "image": self.config.image_path,
                "text": "",  # Would contain actual OCR output
                "timestamp": datetime.now().isoformat()
            }

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(placeholder, f, ensure_ascii=False, indent=2)

            logger.info(f"  💾 {engine} output: {output_file}")

    def step3_fusion(self):
        """Fuse OCR results from multiple engines."""
        logger.info("\n⚖️  Step 3: Fusing OCR Results")

        # This would use ocr_fusion_engine.py
        logger.info(f"  Strategy: {self.config.fusion_strategy}")
        logger.info("  (Fusion results would be generated here)")

    def step4_compare(self):
        """Compare OCR with ground truth."""
        logger.info("\n📊 Step 4: Comparing with Ground Truth")

        gt_file = self.output_dir / "ground_truth.txt"
        if not gt_file.exists():
            logger.warning("No GT file found. Skipping comparison.")
            return

        # Run comparison for each engine
        for engine in self.config.ocr_engines:
            ocr_file = self.output_dir / f"ocr_{engine}.txt"
            if not ocr_file.exists():
                continue

            report_file = self.output_dir / f"report_{engine}.json"

            cmd = [
                sys.executable, "gt_comparison_engine.py",
                "--gt", str(gt_file),
                "--ocr", str(ocr_file),
                "--output", str(report_file),
                "--generate-dict",
                "--generate-training"
            ]

            try:
                subprocess.run(cmd, check=True, capture_output=True, text=True)
                logger.info(f"  ✅ {engine} comparison: {report_file}")
            except subprocess.CalledProcessError as e:
                logger.error(f"  ❌ {engine} comparison failed: {e.stderr}")

    def step5_generate_training(self):
        """Generate training data from comparisons."""
        logger.info("\n🎓 Step 5: Generating Training Data")

        training_pairs = []

        # Collect training data from all comparisons
        for engine in self.config.ocr_engines:
            train_file = self.output_dir / f"report_{engine}_training.json"
            if train_file.exists():
                with open(train_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    training_pairs.extend(data)

        # Deduplicate
        seen = set()
        unique_pairs = []
        for pair in training_pairs:
            key = f"{pair.get('input', '')} -> {pair.get('target', '')}"
            if key not in seen:
                seen.add(key)
                unique_pairs.append(pair)

        # Save
        train_output = self.output_dir / "training_pairs.json"
        with open(train_output, 'w', encoding='utf-8') as f:
            json.dump({
                "total_pairs": len(unique_pairs),
                "generated_at": datetime.now().isoformat(),
                "pairs": unique_pairs
            }, f, ensure_ascii=False, indent=2)

        logger.info(f"  ✅ {len(unique_pairs)} unique training pairs")

    def step6_export(self):
        """Export training data in desired format."""
        logger.info("\n💾 Step 6: Exporting Training Data")

        train_file = self.output_dir / "training_pairs.json"
        if not train_file.exists():
            logger.warning("No training data to export.")
            return

        with open(train_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if self.config.export_format == "csv":
            import csv
            csv_file = self.output_dir / "training_pairs.csv"
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["input", "target", "cer", "error_types"])
                writer.writeheader()
                for pair in data["pairs"]:
                    writer.writerow({
                        "input": pair.get("input", ""),
                        "target": pair.get("target", ""),
                        "cer": pair.get("cer", 0),
                        "error_types": ",".join(pair.get("error_types", []))
                    })
            logger.info(f"  💾 CSV export: {csv_file}")

        elif self.config.export_format == "lmdb":
            # For TrOCR fine-tuning
            logger.info("  📦 LMDB format (for TrOCR) — requires additional setup")

        logger.info(f"  📁 All outputs in: {self.output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="OCR Training Pipeline Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline
  python training_pipeline_manager.py --gt abbyy.docx --image doc.jpg --run-all

  # With config file
  python training_pipeline_manager.py --config pipeline.json

  # Export existing data
  python training_pipeline_manager.py --export training_pairs.json --format csv
        """
    )

    parser.add_argument("--config", help="Pipeline configuration JSON file")
    parser.add_argument("--gt", help="Ground truth file (.docx, .rtf, .txt)")
    parser.add_argument("--image", help="Scanned image file")
    parser.add_argument("--engines", nargs="+", default=["tesseract", "easyocr", "paddleocr"],
                        help="OCR engines to use")
    parser.add_argument("--output-dir", default="training_output", help="Output directory")
    parser.add_argument("--run-all", action="store_true", help="Run complete pipeline")
    parser.add_argument("--export", help="Export existing training data")
    parser.add_argument("--format", choices=["json", "csv", "lmdb"], default="json",
                        help="Export format")

    args = parser.parse_args()

    # Load config
    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        config = PipelineConfig(**config_data)
    else:
        config = PipelineConfig(
            gt_source=args.gt or "",
            image_path=args.image or "",
            ocr_engines=args.engines,
            output_dir=args.output_dir,
            export_format=args.format
        )

    if args.run_all:
        pipeline = TrainingPipeline(config)
        pipeline.run()
    elif args.export:
        # Just export existing data
        config.export_format = args.format
        pipeline = TrainingPipeline(config)
        pipeline.step6_export()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
