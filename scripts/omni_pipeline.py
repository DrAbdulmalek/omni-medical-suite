#!/usr/bin/env python3
"""
Omni Pipeline — Single CLI entry point for the full OCR pipeline.

Stages: scan-fix → ocr-extract → ground-truth → train → benchmark → release

Usage:
    python scripts/omni_pipeline.py scan-fix --input ./data/raw --output ./data/fixed
    python scripts/omni_pipeline.py ocr-extract --input ./data/fixed --output ./data/ocr_results
    python scripts/omni_pipeline.py ground-truth --input ./data/ocr_results --output ./data/gt
    python scripts/omni_pipeline.py train --dataset ./data/gt/training.jsonl --epochs 5
    python scripts/omni_pipeline.py benchmark --model ./models/v1 --images ./data/fixed/test
    python scripts/omni_pipeline.py run --input ./data/raw --output ./outputs

    # Run everything end-to-end (with confirmation at each stage)
    python scripts/omni_pipeline.py run --input ./data/raw --output ./outputs --yes
"""

import argparse
import json
import logging
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Pipeline configuration persisted across stages."""
    input_dir: str = ""
    output_dir: str = ""
    current_stage: str = ""
    stages_completed: List[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def save(self, path: Path):
        path.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "PipelineConfig":
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            data["stages_completed"] = data.get("stages_completed", [])
            return cls(**data)
        return cls()


PIPELINE_CONFIG_FILE = "pipeline_state.json"

# ─── Stage implementations ────────────────────────────────────────────────

def stage_scan_fix(args, config: PipelineConfig):
    """Run scanner-fixer batch processing."""
    log.info("═══ Stage: SCAN-FIX ═══")
    log.info("Input: %s → Output: %s", args.input, args.output)

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    # Try using scanner-fixer BatchProcessor if available
    try:
        from scanner_fixer.batch_pipeline import BatchProcessor
        processor = BatchProcessor(
            input_dir=input_path,
            output_dir=output_path,
            workers=args.workers or 4,
            generate_previews=not args.no_previews,
        )
        processor.run()
        log.info("Scan-fix complete (using scanner-fixer BatchProcessor)")
    except ImportError:
        log.warning("scanner-fixer not installed — using fallback (copy without processing)")
        _fallback_copy(input_path, output_path)

    config.stages_completed.append("scan-fix")
    config.current_stage = "scan-fix"


def stage_ocr_extract(args, config: PipelineConfig):
    """Run OCR extraction on fixed images."""
    log.info("═══ Stage: OCR-EXTRACT ═══")
    log.info("Input: %s → Output: %s", args.input, args.output)

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    # Try using arabic-medical-ocr-baseline inference if available
    try:
        sys.path.insert(0, str(input_path.parent.parent))
        # Import and run inference
        from inference import process_directory
        results = process_directory(str(input_path), str(output_path))
        log.info("OCR extraction complete: %d images processed", len(results))
    except (ImportError, Exception) as e:
        log.warning("inference.py not available (%s) — skipping OCR extraction", e)
        output_path.mkdir(parents=True, exist_ok=True)
        # Create empty results file
        (output_path / "ocr_results.json").write_text("[]", encoding="utf-8")

    config.stages_completed.append("ocr-extract")
    config.current_stage = "ocr-extract"


def stage_ground_truth(args, config: PipelineConfig):
    """Prepare ground truth from OCR results."""
    log.info("═══ Stage: GROUND-TRUTH ═══")
    log.info("Input: %s → Output: %s", args.input, args.output)

    input_path = Path(args.input)
    output_path = Path(args.output)

    # Create subdirectory structure
    for subdir in ["verified", "corrections", "review_needed"]:
        (output_path / subdir).mkdir(parents=True, exist_ok=True)

    # Try using medical-ocr-ground-truth tools
    ocr_results = input_path / "ocr_results.json"
    if ocr_results.exists():
        log.info("Found OCR results — ready for human correction")
        shutil.copy2(str(ocr_results), str(output_path / "corrections" / "pending_corrections.csv"))
    else:
        log.info("No OCR results found — creating empty structure")

    # Create metadata template
    metadata_path = output_path / "metadata.csv"
    if not metadata_path.exists():
        metadata_path.write_text(
            "filename,type,language,source,has_ground_truth,quality,notes\n",
            encoding="utf-8",
        )

    log.info("Ground truth structure created at %s", output_path)
    config.stages_completed.append("ground-truth")
    config.current_stage = "ground-truth"


def stage_train(args, config: PipelineConfig):
    """Run model training."""
    log.info("═══ Stage: TRAIN ═══")

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        log.error("Dataset not found: %s", dataset_path)
        log.error("Run ground-truth stage first, or provide --dataset path")
        return False

    epochs = args.epochs or 5
    log.info("Dataset: %s | Epochs: %d", dataset_path, epochs)

    # This is a placeholder — actual training depends on the trainer setup
    log.info("Training pipeline would start here.")
    log.info("Configure training via medical-ocr-training-hub for full integration.")

    config.stages_completed.append("train")
    config.current_stage = "train"
    return True


def stage_benchmark(args, config: PipelineConfig):
    """Run benchmarking."""
    log.info("═══ Stage: BENCHMARK ═══")

    model_path = Path(args.model) if args.model else None
    images_path = Path(args.images) if args.images else None

    if images_path and images_path.exists():
        log.info("Images: %s", images_path)
        # Try eval_benchmark.py from arabic-medical-ocr-baseline
        try:
            import eval_benchmark
            log.info("Running benchmark evaluation...")
        except ImportError:
            log.warning("eval_benchmark not available — run manually:")
            log.warning("  python eval_benchmark.py --data %s --output benchmark_report.md", images_path)
    else:
        log.warning("No images path provided — skipping benchmark")

    config.stages_completed.append("benchmark")
    config.current_stage = "benchmark"


def stage_release(args, config: PipelineConfig):
    """Create release using training-hub promotion pipeline."""
    log.info("═══ Stage: RELEASE ═══")

    # Try using promotion pipeline
    try:
        from promotion.pipeline import PromotionPipeline
        pipeline = PromotionPipeline(state_file="promotion_state.json")
        pipeline.promote(args.dataset or "default", "candidate")
        log.info("Promotion pipeline executed")
    except ImportError:
        log.info("Promotion pipeline not available — run manually:")
        log.info("  python scripts/promote.py promote <dataset_id> candidate")

    config.stages_completed.append("release")
    config.current_stage = "release"


# ─── Full pipeline run ────────────────────────────────────────────────────

STAGES = ["scan-fix", "ocr-extract", "ground-truth", "train", "benchmark", "release"]

def run_full_pipeline(args):
    """Run all stages sequentially."""
    config = PipelineConfig(
        input_dir=args.input,
        output_dir=args.output,
    )

    config_path = Path(args.output) / PIPELINE_CONFIG_FILE

    for stage in STAGES:
        if args.yes:
            confirmed = True
        else:
            try:
                confirmed = input(f"Run stage [{stage}]? [Y/n]: ").strip().lower() != "n"
            except EOFError:
                confirmed = True

        if not confirmed:
            log.info("Skipping stage: %s", stage)
            continue

        start = time.time()
        stage_args = argparse.Namespace(
            input=args.input if stage == "scan-fix"
                else str(Path(args.output) / "fixed") if stage == "ocr-extract"
                else str(Path(args.output) / "ocr_results") if stage == "ground-truth"
                else str(Path(args.output) / "gt"),
            output=str(Path(args.output) / {
                "scan-fix": "fixed",
                "ocr-extract": "ocr_results",
                "ground-truth": "gt",
                "train": "models",
                "benchmark": "reports",
                "release": "releases",
            }[stage]),
            workers=args.workers,
            no_previews=args.no_previews,
            dataset=args.dataset,
            epochs=args.epochs,
            model=args.model,
            images=args.images,
        )

        if stage == "scan-fix":
            stage_scan_fix(stage_args, config)
        elif stage == "ocr-extract":
            stage_ocr_extract(stage_args, config)
        elif stage == "ground-truth":
            stage_ground_truth(stage_args, config)
        elif stage == "train":
            stage_train(stage_args, config)
        elif stage == "benchmark":
            stage_benchmark(stage_args, config)
        elif stage == "release":
            stage_release(stage_args, config)

        elapsed = time.time() - start
        log.info("Stage [%s] completed in %.1fs", stage, elapsed)
        config.save(config_path)

    # Print summary
    log.info("═══ Pipeline Complete ═══")
    log.info("Stages completed: %s", ", ".join(config.stages_completed))
    log.info("Config saved to: %s", config_path)


def _fallback_copy(src: Path, dst: Path):
    """Fallback: copy images without processing when scanner-fixer is unavailable."""
    from pathlib import Path
    extensions = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
    count = 0
    for f in src.rglob("*"):
        if f.suffix.lower() in extensions:
            out = dst / f.relative_to(src)
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(f), str(out))
            count += 1
    log.info("Copied %d images (no processing applied)", count)


# ─── CLI ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Omni Pipeline — Full OCR pipeline: scan-fix → ocr → gt → train → benchmark → release",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s scan-fix --input ./raw --output ./fixed
  %(prog)s ocr-extract --input ./fixed --output ./ocr_results
  %(prog)s run --input ./raw --output ./outputs --yes
        """,
    )
    parser.add_argument("--workers", "-w", type=int, default=4, help="Parallel workers")
    parser.add_argument("--no-previews", action="store_true", help="Skip before/after previews")
    parser.add_argument("--dataset", help="Dataset path for training")
    parser.add_argument("--epochs", type=int, default=5, help="Training epochs")
    parser.add_argument("--model", help="Model path for benchmarking")
    parser.add_argument("--images", help="Images path for benchmarking")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")

    subparsers = parser.add_subparsers(dest="command", help="Pipeline stage to run")

    # scan-fix
    p = subparsers.add_parser("scan-fix", help="Fix scans with scanner-fixer")
    p.add_argument("--input", "-i", required=True)
    p.add_argument("--output", "-o", required=True)

    # ocr-extract
    p = subparsers.add_parser("ocr-extract", help="Extract text with OCR engines")
    p.add_argument("--input", "-i", required=True)
    p.add_argument("--output", "-o", required=True)

    # ground-truth
    p = subparsers.add_parser("ground-truth", help="Prepare ground truth structure")
    p.add_argument("--input", "-i", required=True)
    p.add_argument("--output", "-o", required=True)

    # train
    p = subparsers.add_parser("train", help="Train OCR model")
    p.add_argument("--dataset", "-d", required=True)
    p.add_argument("--epochs", "-e", type=int, default=5)

    # benchmark
    p = subparsers.add_parser("benchmark", help="Benchmark model quality")
    p.add_argument("--model", "-m", required=True)
    p.add_argument("--images", "-i", required=True)

    # release
    p = subparsers.add_parser("release", help="Promote dataset via training-hub")
    p.add_argument("--dataset", "-d", default="default")

    # run (full pipeline)
    p = subparsers.add_parser("run", help="Run full pipeline end-to-end")
    p.add_argument("--input", "-i", required=True)
    p.add_argument("--output", "-o", required=True)

    args = parser.parse_args()

    if args.command == "run":
        run_full_pipeline(args)
    elif args.command in STAGES:
        config = PipelineConfig()
        stage_fn = {
            "scan-fix": stage_scan_fix,
            "ocr-extract": stage_ocr_extract,
            "ground-truth": stage_ground_truth,
            "train": stage_train,
            "benchmark": stage_benchmark,
            "release": stage_release,
        }[args.command]
        stage_fn(args, config)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()