"""
cli.py
Command-line interface for ocr_groundtruth.

Usage:
    ocr-groundtruth build-one --abbyy abbyy/0001.pdf --readiris readiris/0001.pdf --id 0001
    ocr-groundtruth build-batch --abbyy-dir abbyy/ --readiris-dir readiris/ --output ./gt/
    ocr-groundtruth evaluate --ground-truth gt/0001.json --engine-output tesseract/0001.txt
"""

import click
import json
from pathlib import Path

from .groundtruth_builder import build_ground_truth_record, build_dataset_from_folder
from .evaluate import evaluate_engine_output, compare_engines


@click.group()
@click.version_option("1.0.0")
def cli():
    """ocr-groundtruth: Build verified OCR ground truth from ABBYY + Readiris."""
    pass


@cli.command("build-one")
@click.option("--abbyy", "abbyy_pdf", type=click.Path(exists=True), default=None,
              help="Path to ABBYY-exported searchable PDF")
@click.option("--readiris", "readiris_pdf", type=click.Path(exists=True), default=None,
              help="Path to Readiris-exported searchable PDF")
@click.option("--id", "image_id", required=True, help="Document identifier")
@click.option("--output", "-o", default=None, help="Output JSON path (default: <id>.json)")
def build_one(abbyy_pdf, readiris_pdf, image_id, output):
    """Build a single ground-truth record from ABBYY and/or Readiris PDFs."""

    if not abbyy_pdf and not readiris_pdf:
        click.echo("Error: provide at least --abbyy or --readiris", err=True)
        raise click.Abort()

    record = build_ground_truth_record(
        image_id=image_id,
        abbyy_pdf=abbyy_pdf,
        readiris_pdf=readiris_pdf,
    )

    out_path = Path(output) if output else Path(f"{image_id}.json")
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    click.echo(f"✓ Saved: {out_path}")
    click.echo(f"  Agreement rate: {record['stats']['agreement_rate']}")
    click.echo(f"  Conflicts: {record['stats']['conflicts']}")
    click.echo(f"  Review needed: {record['review_needed']}")


@cli.command("build-batch")
@click.option("--abbyy-dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="Folder of ABBYY-exported PDFs")
@click.option("--readiris-dir", type=click.Path(exists=True, file_okay=False), default=None,
              help="Folder of Readiris-exported PDFs")
@click.option("--output", "-o", default="./ground_truth_output", help="Output directory")
def build_batch(abbyy_dir, readiris_dir, output):
    """Build ground-truth records for all matching files in two folders."""

    if not abbyy_dir and not readiris_dir:
        click.echo("Error: provide at least --abbyy-dir or --readiris-dir", err=True)
        raise click.Abort()

    build_dataset_from_folder(
        abbyy_dir=abbyy_dir,
        readiris_dir=readiris_dir,
        output_dir=output,
    )


@cli.command("evaluate")
@click.option("--ground-truth", "-g", required=True, type=click.Path(exists=True),
              help="Path to ground-truth JSON record (from build-one/build-batch)")
@click.option("--engine-output", "-e", required=True, type=click.Path(exists=True),
              help="Path to plain text file with your engine's OCR output")
@click.option("--engine-name", "-n", default="my_engine", help="Label for this engine")
def evaluate(ground_truth, engine_output, engine_name):
    """Compute real CER/WER for your engine against a ground-truth record."""

    gt_data = json.loads(Path(ground_truth).read_text(encoding="utf-8"))
    gt_text = gt_data.get("merged_text", "")

    if not gt_text:
        click.echo("Error: ground-truth file has no 'merged_text' field", err=True)
        raise click.Abort()

    engine_text = Path(engine_output).read_text(encoding="utf-8")

    result = evaluate_engine_output(gt_text, engine_text, engine_name)

    click.echo(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cli()
