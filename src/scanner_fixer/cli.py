"""
cli.py
Command-line interface for scanner-fixer.

Usage examples:
    scanner-fixer fix scan.jpg
    scanner-fixer fix scan.jpg --output fixed.jpg --binarize
    scanner-fixer batch ./scans/ --output-dir ./fixed/
    scanner-fixer info scan.jpg
"""

import click
import json
from pathlib import Path
from .pipeline import fix_scan, fix_scan_batch


@click.group()
@click.version_option("1.0.0")
def cli():
    """scanner-fixer: Pre-OCR image normalization for scanned documents."""
    pass


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output file path (default: input_fixed.ext)")
@click.option("--no-crop", is_flag=True, help="Disable border cropping")
@click.option("--no-rotate", is_flag=True, help="Disable 180° rotation correction")
@click.option("--no-deskew", is_flag=True, help="Disable skew correction")
@click.option("--no-enhance", is_flag=True, help="Disable OCR enhancement")
@click.option("--binarize", is_flag=True, help="Convert to black & white (text-only pages)")
@click.option("--deskew-method", default="hough", type=click.Choice(["hough", "projection"]),
              help="Deskew algorithm (default: hough)")
@click.option("--use-tesseract", is_flag=True, help="Use Tesseract OSD for rotation detection")
@click.option("--report", is_flag=True, help="Print processing report as JSON")
def fix(input_path, output, no_crop, no_rotate, no_deskew, no_enhance,
        binarize, deskew_method, use_tesseract, report):
    """Fix a single scanned image."""

    input_path = Path(input_path)

    if output is None:
        output = input_path.parent / f"{input_path.stem}_fixed{input_path.suffix}"

    click.echo(f"Processing: {input_path.name}")

    result = fix_scan(
        input_path=input_path,
        output_path=output,
        do_crop=not no_crop,
        do_rotate=not no_rotate,
        do_deskew=not no_deskew,
        do_enhance=not no_enhance,
        binarize=binarize,
        deskew_method=deskew_method,
        use_tesseract_osd=use_tesseract,
    )

    click.echo(f"✓ Saved: {output}")

    if report:
        click.echo(json.dumps(result["report"], indent=2, ensure_ascii=False))
    else:
        r = result["report"]
        if r.get("rotation_applied_deg"):
            click.echo(f"  Rotation corrected: {r['rotation_applied_deg']}°")
        if r.get("skew_corrected_deg"):
            click.echo(f"  Skew corrected: {r['skew_corrected_deg']}°")
        click.echo(f"  Final size: {r['final_size']}")


@cli.command()
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--output-dir", "-o", default=None, help="Output directory (default: input_dir/fixed)")
@click.option("--ext", default="jpg,png,tif,tiff,bmp", help="Comma-separated file extensions")
@click.option("--binarize", is_flag=True, help="Convert to black & white")
@click.option("--suffix", default="_fixed", help="Suffix added to output filenames")
def batch(input_dir, output_dir, ext, binarize, suffix):
    """Process all images in a directory."""

    input_dir = Path(input_dir)

    if output_dir is None:
        output_dir = input_dir / "fixed"

    extensions = [f".{e.strip().lstrip('.')}" for e in ext.split(",")]
    paths = [
        p for p in sorted(input_dir.iterdir())
        if p.suffix.lower() in extensions
    ]

    if not paths:
        click.echo(f"No images found in {input_dir}")
        return

    click.echo(f"Found {len(paths)} images → {output_dir}")

    results = fix_scan_batch(
        input_paths=paths,
        output_dir=output_dir,
        suffix=suffix,
        binarize=binarize,
    )

    ok = sum(1 for r in results if r.get("status") == "ok")
    errors = len(results) - ok
    click.echo(f"\nDone: {ok} OK, {errors} errors")


@cli.command()
@click.argument("input_path", type=click.Path(exists=True))
def info(input_path):
    """Show image info and estimated DPI without processing."""
    import cv2
    from .enhance import get_estimated_dpi

    img = cv2.imread(str(input_path))
    if img is None:
        click.echo(f"Error: Cannot read {input_path}")
        return

    h, w = img.shape[:2]
    channels = img.shape[2] if len(img.shape) == 3 else 1
    dpi = get_estimated_dpi(img)

    click.echo(f"File:     {input_path}")
    click.echo(f"Size:     {w} x {h} px")
    click.echo(f"Channels: {channels} ({'color' if channels == 3 else 'grayscale'})")
    click.echo(f"Est. DPI: {dpi or 'unknown'}")


if __name__ == "__main__":
    cli()
