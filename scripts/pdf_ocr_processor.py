#!/usr/bin/env python3
"""
pdf_ocr_processor.py — thin CLI wrapper around scanner_fixer.PDFOCRProcessor
══════════════════════════════════════════════════════════════════════════════

Historical note
---------------
This file used to be an 868-line independent reimplementation of the PDF →
image → OCR pipeline, duplicating logic that already lived in
``packages/scanner_fixer/src/scanner_fixer/pdf_ocr_processor.py``. It was
refactored into a thin wrapper so that:

  1. All OCR / normalization / fallback logic lives in exactly one place
     (the library class), and is exercised by the test suite there.
  2. The unique features that *did* live only in the script — auto-tuning
     of Tesseract PSM × DPI, and bilingual glossary extraction — have been
     moved into the library class as ``auto_tune=True`` and
     ``extract_glossary=True`` options, so they're now programmatically
     accessible too.
  3. CLI behaviour is preserved: ``python3 scripts/pdf_ocr_processor.py
     --auto-tune --engine tesseract`` produces the same functional output
     as before the refactor.

Usage
-----
    python3 scripts/pdf_ocr_processor.py
    python3 scripts/pdf_ocr_processor.py --input data/report.pdf --output ~/output/
    python3 scripts/pdf_ocr_processor.py --auto-tune --engine tesseract
    python3 scripts/pdf_ocr_processor.py --input report.pdf --extract-glossary

The script defers all heavy lifting to ``PDFOCRProcessor``. It only handles
argument parsing, directory walking, and Markdown log generation.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# ── Project path bootstrap ────────────────────────────────────────────────
# The library lives under packages/scanner_fixer/src. Add it to sys.path
# so this script can be run from anywhere without installing the package.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "scanner_fixer" / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "packages" / "core"))
sys.path.insert(0, str(PROJECT_ROOT))  # so packages.core.engine_registry imports work

# ── Library import ────────────────────────────────────────────────────────
from scanner_fixer.pdf_ocr_processor import (  # noqa: E402
    OCR_ENGINES,
    PDFOCRProcessor,
    SUPPORTED_IMAGE_EXT,
)

logger = logging.getLogger("pdf_ocr_processor")

# ── Optional: advanced logger integration (kept from the old script) ─────
_ADVANCED_LOGGER_AVAILABLE = False
_feedback_collector = None

try:
    from scripts.advanced_logger import get_feedback_collector  # type: ignore
    _feedback_collector = get_feedback_collector()
    _ADVANCED_LOGGER_AVAILABLE = True
except ImportError:
    pass


def log_ocr_result(
    file_name: str,
    pages: int,
    entries: int,
    config: dict,
    source: str = "pdf_ocr_processor",
) -> None:
    """Log an OCR result to the advanced logger (no-op if unavailable)."""
    if not _ADVANCED_LOGGER_AVAILABLE or _feedback_collector is None:
        return

    try:
        import json
        entry = {
            "timestamp": datetime.now().isoformat(),
            "action": "ocr_processed",
            "details": {
                "file": file_name,
                "pages": pages,
                "entries_found": entries,
                "config": config,
                "source": source,
            },
        }
        log_file = (
            Path("logs/user_actions")
            / f"actions_{datetime.now().strftime('%Y%m%d')}.jsonl"
        )
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info(f"OCR logged: {file_name} ({pages} pages, {entries} entries)")
    except Exception as exc:
        logger.debug(f"Advanced logging failed: {exc}")


def process_single_file(
    processor: PDFOCRProcessor,
    input_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Process one PDF or image file using the library processor.

    Mirrors the per-file behaviour of the old script: writes a .txt/.csv/.json
    next to the file in ``output_dir``, and returns a summary dict.
    """
    input_path = Path(input_path)
    suffix = input_path.suffix.lower()

    if suffix == ".pdf":
        results = processor.process_pdf(str(input_path))
    elif suffix in SUPPORTED_IMAGE_EXT:
        results = [processor.process_image(str(input_path))]
    else:
        logger.warning(f"Skipping unsupported file: {input_path}")
        return {
            "file": input_path.name,
            "file_path": str(input_path),
            "error": f"unsupported extension: {suffix}",
        }

    # Aggregate text
    all_text = ""
    total_glossary = 0
    for r in results:
        all_text += f"\n--- صفحة {r['page_num'] + 1} ---\n{r.get('text', '')}\n"
        total_glossary += len(r.get("glossary_entries", []))

    # Write per-file outputs (matches old script naming)
    stem = input_path.stem
    txt_path = output_dir / f"{stem}.txt"
    txt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(all_text)

    # Use the library's JSON/CSV exporter for the structured results
    processor.export_results(results, output_dir / f"{stem}.json")

    # Glossary per-file (only if extraction enabled)
    if processor.extract_glossary and processor.combined_glossary:
        file_entries = [
            e for e in processor.combined_glossary
            if e.get("source", "").startswith(input_path.name)
        ]
        if file_entries:
            import csv
            csv_path = output_dir / f"{stem}.csv"
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["term_arabic", "term_english", "source"],
                )
                writer.writeheader()
                writer.writerows(file_entries)

    file_result = {
        "file": input_path.name,
        "file_path": str(input_path),
        "pages": len(results),
        "entries_found": total_glossary,
        "best_config": getattr(processor, "best_config", {}).copy(),
        "error": "",
    }

    log_ocr_result(
        file_name=input_path.name,
        pages=len(results),
        entries=total_glossary,
        config=getattr(processor, "best_config", {}).copy(),
        source="pdf_ocr_processor",
    )

    return file_result


def process_directory(
    processor: PDFOCRProcessor,
    input_dir: Path,
    output_dir: Path,
) -> list[dict[str, Any]]:
    """Process every PDF in ``input_dir`` sequentially."""
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise FileNotFoundError(f"المجلد غير موجود: {input_dir}")

    pdf_files = sorted(input_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"لا توجد ملفات PDF في: {input_dir}")
        return []

    logger.info(f"وجد {len(pdf_files)} ملف PDF في {input_dir}")
    all_results: list[dict[str, Any]] = []

    for pdf_path in pdf_files:
        try:
            result = process_single_file(processor, pdf_path, output_dir)
            all_results.append(result)
        except Exception as exc:
            logger.error(f"فشل في معالجة {pdf_path.name}: {exc}")
            all_results.append({
                "file": pdf_path.name,
                "file_path": str(pdf_path),
                "error": str(exc),
            })

    # Save combined glossary across all files
    if processor.extract_glossary and processor.combined_glossary:
        processor.export_glossary(output_dir / "combined_glossary.csv")
        processor.export_glossary(output_dir / "combined_glossary.json")

    return all_results


def generate_processing_log(
    processor: PDFOCRProcessor,
    results: list[dict[str, Any]],
    output_dir: Path,
) -> Path:
    """Generate a Markdown processing log (matches the old script's report)."""
    log_path = output_dir / "OCR_PROCESSING_LOG.md"
    lines = [
        "# سجل معالجة OCR",
        f"\n**التاريخ:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**الإعداد المستخدم:** PSM={processor.best_config.get('psm')}, "
        f"DPI={processor.best_config.get('dpi')}, "
        f"lang={processor.best_config.get('language')}",
        f"**المعالجة المسبقة:** {'scanner_fixer' if processor.normalize_images else 'معطّلة'}",
        f"**Auto-tune:** {'مفعّل' if processor.auto_tune else 'معطّل'}",
        f"**استخراج المسارد:** {'مفعّل' if processor.extract_glossary else 'معطّل'}",
        "",
        "## الملفات المعالجة",
        "",
        "| الملف | الصفحات | المسارد | الحالة |",
        "|---|---|---|---|",
    ]
    for r in results:
        status = "✅" if not r.get("error") else f"❌ {r.get('error', '')[:30]}"
        lines.append(
            f"| {r.get('file', '?')} | {r.get('pages', 0)} | "
            f"{r.get('entries_found', 0)} | {status} |"
        )

    lines.extend([
        "",
        "## إجمالي المسارد",
        f"- **إجمالي المُدخلات:** {len(processor.combined_glossary)}",
        f"- **ملفات PDF:** {len(results)}",
    ])

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"تقرير المعالجة: {log_path}")
    return log_path


# ===========================================================================
# CLI
# ===========================================================================
def main() -> None:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="PDF OCR Processor — thin CLI wrapper around "
                    "scanner_fixer.PDFOCRProcessor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
أمثلة:
  %(prog)s                                    # معالجة كل PDF في data/
  %(prog)s --input report.pdf                 # ملف واحد
  %(prog)s --input ./pdfs/ --auto-tune        # مع ضبط تلقائي
  %(prog)s --input report.pdf --no-normalize  # بدون معالجة مسبقة
  %(prog)s --input report.pdf --extract-glossary --auto-tune
        """,
    )
    parser.add_argument(
        "--input", "-i",
        default="data/",
        help="مسار ملف PDF أو مجلد (افتراضي: data/)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="مجلد الإخراج (افتراضي: ~/glossaries_output)",
    )
    parser.add_argument(
        "--engine", "-e",
        default="tesseract",
        choices=list(OCR_ENGINES.keys()),
        help="OCR engine (افتراضي: tesseract)",
    )
    parser.add_argument(
        "--language", "-l",
        default="ara+eng",
        help="لغة OCR (افتراضي: ara+eng)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="DPI for PDF→image conversion (افتراضي: 300)",
    )
    parser.add_argument(
        "--no-auto-tune",
        action="store_true",
        help="تعطيل الضبط التلقائي (ملاحظة: auto-tune معطّل افتراضياً)",
    )
    parser.add_argument(
        "--auto-tune",
        action="store_true",
        help="تفعيل الضبط التلقائي لـ PSM و DPI",
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="تعطيل المعالجة المسبقة للصور",
    )
    parser.add_argument(
        "--extract-glossary",
        action="store_true",
        help="استخراج المسارد الثنائية اللغة",
    )
    parser.add_argument(
        "--psm",
        type=int,
        default=None,
        help="PSM mode يدوي (3, 4, 6, 11) — يتجاوز auto-tune",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="تسجيل مفصّل",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # ── Banner ────────────────────────────────────────────────────────────
    print("═══════════════════════════════════════════════════")
    print("  PDF OCR Processor — معالج PDF OCR الطبي")
    print("  (thin CLI wrapper around scanner_fixer.PDFOCRProcessor)")
    print("═══════════════════════════════════════════════════")
    print()

    # ── Build the library processor ───────────────────────────────────────
    # Note: we always set auto_tune explicitly (default off unless --auto-tune)
    auto_tune = args.auto_tune and not args.no_auto_tune

    processor = PDFOCRProcessor(
        dpi=args.dpi,
        ocr_engine=args.engine,
        normalize_images=not args.no_normalize,
        language=args.language,
        auto_tune=auto_tune,
        extract_glossary=args.extract_glossary,
    )

    # Manual PSM override (overrides auto-tune if both set)
    if args.psm is not None:
        processor.best_config["psm"] = args.psm
        processor.auto_tune = False
        # Also update the tesseract_config string the library uses
        processor.tesseract_config = f"--psm {args.psm} --dpi {args.dpi}"

    # ── Resolve output dir ────────────────────────────────────────────────
    import os
    output_dir = Path(args.output) if args.output else Path(
        os.path.expanduser("~/glossaries_output")
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Process input ─────────────────────────────────────────────────────
    input_path = Path(args.input)

    if input_path.is_file() and (
        input_path.suffix.lower() == ".pdf"
        or input_path.suffix.lower() in SUPPORTED_IMAGE_EXT
    ):
        results = [process_single_file(processor, input_path, output_dir)]
    elif input_path.is_dir():
        results = process_directory(processor, input_path, output_dir)
    else:
        print(f"❌ المسار غير صالح: {input_path}")
        print("   استخدم: --input <file.pdf> أو --input <directory/>")
        sys.exit(1)

    # ── Generate Markdown processing log ──────────────────────────────────
    generate_processing_log(processor, results, output_dir)

    # ── Summary ───────────────────────────────────────────────────────────
    print()
    print("═══════════════════════════════════════════════════")
    print("  ✅ اكتملت المعالجة!")
    print("═══════════════════════════════════════════════════")
    print(f"  📁 الإخراج: {output_dir}")
    print(f"  📄 ملفات: {len(results)}")
    print(f"  📖 مسارد: {len(processor.combined_glossary)} مُدخلة")
    print(f"  ⚙️  الإعداد: PSM={processor.best_config.get('psm')}, "
          f"DPI={processor.best_config.get('dpi')}")
    print()
    print("  الملفات:")
    for p in sorted(output_dir.iterdir())[:20]:
        if p.is_file():
            size = p.stat().st_size
            print(f"    {p.name} ({size:,} bytes)")


if __name__ == "__main__":
    main()
