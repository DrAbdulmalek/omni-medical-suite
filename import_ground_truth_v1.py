#!/usr/bin/env python3
"""
import_ground_truth.py — Import Word/RTF/PDF as Ground Truth for OCR Training
================================================================================
Imports output files from ABBYY FineReader, ReadIRIS, and PDF Grabber
as high-quality ground truth for training and benchmarking OCR systems.

Supported formats:
    - .docx (ABBYY FineReader, ReadIRIS)
    - .rtf   (ReadIRIS)
    - .txt   (Plain text export)
    - .pdf   (PDF Grabber — with font/glyph extraction)
    - .html  (ABBYY structured export)

Usage:
    python import_ground_truth.py abbyy_output.docx --output gt_abbyy.txt
    python import_ground_truth.py readiris_output.rtf --output gt_readiris.txt
    python import_ground_truth.py document.pdf --mode font-extract --output fonts.json
    python import_ground_truth.py abbyy.docx readiris.rtf --merge --output merged_gt.txt

Author: Dr. Abdulmalek
Version: 1.0.0
Date: 2026-06-04
"""

import json
import re
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class GroundTruthEntry:
    """A single ground truth entry with metadata."""
    text: str
    source: str  # "abbyy", "readiris", "pdf_grabber", "manual"
    page_number: int = 1
    line_number: int = 0
    confidence: float = 1.0  # GT assumed perfect
    font_name: str = ""
    font_size: float = 0.0
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)
    is_bold: bool = False
    is_italic: bool = False
    is_rtl: bool = True  # Arabic default
    original_file: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


class DocumentImporter:
    """Base class for importing documents as ground truth."""

    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.entries: List[GroundTruthEntry] = []

    def import_document(self) -> List[GroundTruthEntry]:
        """Import document and return list of entries."""
        raise NotImplementedError

    def save_as_text(self, output_path: str):
        """Save all entries as plain text file."""
        lines = []
        for entry in self.entries:
            lines.append(entry.text)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        logger.info(f"Saved {len(lines)} lines to {output_path}")

    def save_as_json(self, output_path: str):
        """Save all entries with metadata as JSON."""
        data = {
            "source": self.file_path.name,
            "imported_at": datetime.now().isoformat(),
            "total_entries": len(self.entries),
            "entries": [e.to_dict() for e in self.entries]
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved structured data to {output_path}")


class DocxImporter(DocumentImporter):
    """Import .docx files (from ABBYY FineReader or ReadIRIS)."""

    def import_document(self) -> List[GroundTruthEntry]:
        try:
            from docx import Document
        except ImportError:
            logger.error("python-docx not installed. Run: pip install python-docx")
            return []

        doc = Document(str(self.file_path))
        line_num = 0

        for para in doc.paragraphs:
            if not para.text.strip():
                continue

            # Extract font info from first run
            font_name = ""
            font_size = 0.0
            is_bold = False
            is_italic = False

            if para.runs:
                run = para.runs[0]
                if run.font.name:
                    font_name = run.font.name
                if run.font.size:
                    font_size = run.font.size.pt if hasattr(run.font.size, 'pt') else float(run.font.size) / 12700
                is_bold = run.bold or False
                is_italic = run.italic or False

            entry = GroundTruthEntry(
                text=para.text.strip(),
                source="abbyy" if "abbyy" in self.file_path.name.lower() else "readiris",
                line_number=line_num,
                font_name=font_name,
                font_size=font_size,
                is_bold=is_bold,
                is_italic=is_italic,
                original_file=str(self.file_path)
            )
            self.entries.append(entry)
            line_num += 1

        logger.info(f"Imported {len(self.entries)} paragraphs from {self.file_path}")
        return self.entries


class RtfImporter(DocumentImporter):
    """Import .rtf files (from ReadIRIS)."""

    def import_document(self) -> List[GroundTruthEntry]:
        try:
            from striprtf.striprtf import rtf_to_text
        except ImportError:
            logger.error("striprtf not installed. Run: pip install striprtf")
            # Fallback: manual RTF parsing
            return self._manual_rtf_parse()

        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            rtf_content = f.read()

        text = rtf_to_text(rtf_content)
        lines = [line.strip() for line in text.split('\n') if line.strip()]

        for i, line in enumerate(lines):
            entry = GroundTruthEntry(
                text=line,
                source="readiris",
                line_number=i,
                original_file=str(self.file_path)
            )
            self.entries.append(entry)

        logger.info(f"Imported {len(self.entries)} lines from RTF: {self.file_path}")
        return self.entries

    def _manual_rtf_parse(self) -> List[GroundTruthEntry]:
        """Fallback RTF parser without striprtf."""
        with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Remove RTF control words
        text = re.sub(r'\[a-z]+\d*\s?', '', content)
        text = re.sub(r'[{}]', '', text)
        text = re.sub(r'\\', '\', text)

        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for i, line in enumerate(lines):
            self.entries.append(GroundTruthEntry(
                text=line, source="readiris", line_number=i,
                original_file=str(self.file_path)
            ))
        return self.entries


class TxtImporter(DocumentImporter):
    """Import plain text files."""

    def import_document(self) -> List[GroundTruthEntry]:
        with open(self.file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]

        for i, line in enumerate(lines):
            self.entries.append(GroundTruthEntry(
                text=line,
                source="manual",
                line_number=i,
                original_file=str(self.file_path)
            ))
        return self.entries


class HtmlImporter(DocumentImporter):
    """Import ABBYY HTML structured export."""

    def import_document(self) -> List[GroundTruthEntry]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("beautifulsoup4 not installed. Run: pip install beautifulsoup4")
            return []

        with open(self.file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')

        # ABBYY HTML usually has <p> or <span> with class="ocr"
        elements = soup.find_all(['p', 'span', 'div'])
        line_num = 0

        for elem in elements:
            text = elem.get_text().strip()
            if not text:
                continue

            # Try to extract bbox from style or attributes
            bbox = (0, 0, 0, 0)
            style = elem.get('style', '')
            bbox_match = re.search(r'left:(\d+)px;top:(\d+)px;width:(\d+)px;height:(\d+)px', style)
            if bbox_match:
                bbox = tuple(int(x) for x in bbox_match.groups())

            entry = GroundTruthEntry(
                text=text,
                source="abbyy_html",
                line_number=line_num,
                bbox=bbox,
                original_file=str(self.file_path)
            )
            self.entries.append(entry)
            line_num += 1

        return self.entries


class PdfFontExtractor:
    """Extract font and glyph information from PDF (PDF Grabber output)."""

    def __init__(self, pdf_path: str):
        self.pdf_path = Path(pdf_path)
        self.fonts: Dict[str, Any] = {}
        self.glyphs: List[Dict] = []

    def extract_fonts(self) -> Dict[str, Any]:
        """Extract font metadata from PDF."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF not installed. Run: pip install PyMuPDF")
            return {}

        doc = fitz.open(str(self.pdf_path))
        font_data = {}

        for page_num in range(len(doc)):
            page = doc[page_num]
            page_fonts = page.get_fonts()

            for font in page_fonts:
                # font = (xref, ext, type, basefont, encoding, name)
                font_name = font[3] if len(font) > 3 else "unknown"
                font_type = font[2] if len(font) > 2 else "unknown"

                if font_name not in font_data:
                    font_data[font_name] = {
                        "type": font_type,
                        "pages": [],
                        "glyphs": []
                    }
                font_data[font_name]["pages"].append(page_num + 1)

        self.fonts = font_data
        doc.close()
        logger.info(f"Extracted {len(font_data)} fonts from {self.pdf_path}")
        return font_data

    def extract_glyphs(self) -> List[Dict]:
        """Extract individual character glyphs with positions."""
        try:
            import fitz
        except ImportError:
            return []

        doc = fitz.open(str(self.pdf_path))
        glyphs = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            text_dict = page.get_text("dict")

            for block in text_dict["blocks"]:
                if "lines" not in block:
                    continue
                for line in block["lines"]:
                    for span in line["spans"]:
                        for char in span.get("chars", []):
                            glyphs.append({
                                "char": char["c"],
                                "x": char["origin"][0],
                                "y": char["origin"][1],
                                "width": char["bbox"][2] - char["bbox"][0],
                                "height": char["bbox"][3] - char["bbox"][1],
                                "font": span["font"],
                                "size": span["size"],
                                "flags": span["flags"],
                                "page": page_num + 1
                            })

        self.glyphs = glyphs
        doc.close()
        logger.info(f"Extracted {len(glyphs)} glyphs from {self.pdf_path}")
        return glyphs

    def save_font_data(self, output_path: str):
        """Save font and glyph data as JSON."""
        data = {
            "pdf_file": str(self.pdf_path),
            "extracted_at": datetime.now().isoformat(),
            "fonts": self.fonts,
            "glyph_count": len(self.glyphs),
            "glyphs": self.glyphs[:1000]  # Limit for file size
        }
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved font data to {output_path}")

    def build_character_map(self) -> Dict[str, List[Dict]]:
        """Build a map of characters to their glyph instances."""
        char_map = {}
        for glyph in self.glyphs:
            char = glyph["char"]
            if char not in char_map:
                char_map[char] = []
            char_map[char].append(glyph)
        return char_map


def merge_ground_truth_sources(sources: List[List[GroundTruthEntry]],
                                strategy: str = "longest") -> List[GroundTruthEntry]:
    """
    Merge multiple ground truth sources into one.

    Strategies:
        longest  — Keep longest text per line (assumes more complete)
        vote     — Majority vote per word
        abbyy    — Prefer ABBYY over others
        readiris — Prefer ReadIRIS over others
    """
    if not sources:
        return []

    if len(sources) == 1:
        return sources[0]

    # Align by line number
    max_lines = max(len(s) for s in sources)
    merged = []

    for i in range(max_lines):
        candidates = []
        for source in sources:
            if i < len(source):
                candidates.append(source[i])

        if not candidates:
            continue

        if strategy == "longest":
            best = max(candidates, key=lambda e: len(e.text))
        elif strategy == "abbyy":
            abbyy = [c for c in candidates if "abbyy" in c.source]
            best = abbyy[0] if abbyy else candidates[0]
        elif strategy == "readiris":
            ri = [c for c in candidates if "readiris" in c.source]
            best = ri[0] if ri else candidates[0]
        else:
            best = candidates[0]

        merged.append(best)

    logger.info(f"Merged {len(sources)} sources into {len(merged)} entries using '{strategy}' strategy")
    return merged


def main():
    parser = argparse.ArgumentParser(
        description="Import Word/RTF/PDF as Ground Truth for OCR Training",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import ABBYY Word output
  python import_ground_truth.py abbyy_output.docx --output gt_abbyy.txt

  # Import ReadIRIS RTF
  python import_ground_truth.py readiris_output.rtf --output gt_readiris.txt

  # Extract fonts from PDF
  python import_ground_truth.py document.pdf --mode font-extract --output fonts.json

  # Merge multiple sources
  python import_ground_truth.py abbyy.docx readiris.rtf --merge --output merged_gt.txt

  # Import as structured JSON
  python import_ground_truth.py abbyy.docx --output gt.json --format json
        """
    )

    parser.add_argument("files", nargs="+", help="Input files (.docx, .rtf, .txt, .html, .pdf)")
    parser.add_argument("--output", "-o", required=True, help="Output file path")
    parser.add_argument("--format", choices=["txt", "json"], default="txt",
                        help="Output format (default: txt)")
    parser.add_argument("--mode", choices=["text", "font-extract"], default="text",
                        help="Operation mode (default: text)")
    parser.add_argument("--merge", action="store_true",
                        help="Merge multiple sources")
    parser.add_argument("--merge-strategy", choices=["longest", "abbyy", "readiris", "vote"],
                        default="longest", help="Merge strategy")
    parser.add_argument("--page", type=int, default=1, help="Page number filter")

    args = parser.parse_args()

    if args.mode == "font-extract":
        # PDF font extraction mode
        for file_path in args.files:
            if not file_path.lower().endswith('.pdf'):
                logger.warning(f"Skipping non-PDF file: {file_path}")
                continue
            extractor = PdfFontExtractor(file_path)
            extractor.extract_fonts()
            extractor.extract_glyphs()
            extractor.save_font_data(args.output)
        return

    # Text import mode
    all_sources = []

    for file_path in args.files:
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            continue

        importer = None
        suffix = path.suffix.lower()

        if suffix == '.docx':
            importer = DocxImporter(file_path)
        elif suffix == '.rtf':
            importer = RtfImporter(file_path)
        elif suffix == '.txt':
            importer = TxtImporter(file_path)
        elif suffix == '.html':
            importer = HtmlImporter(file_path)
        else:
            logger.warning(f"Unsupported format: {suffix}. Trying as text.")
            importer = TxtImporter(file_path)

        entries = importer.import_document()
        all_sources.append(entries)

    # Merge or use first
    if args.merge and len(all_sources) > 1:
        final_entries = merge_ground_truth_sources(all_sources, args.merge_strategy)
    else:
        final_entries = all_sources[0] if all_sources else []

    # Save
    if args.format == "json":
        # Use first importer for saving
        if all_sources:
            importer = DocumentImporter(args.files[0])
            importer.entries = final_entries
            importer.save_as_json(args.output)
    else:
        lines = [e.text for e in final_entries]
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        logger.info(f"Saved {len(lines)} lines to {args.output}")


if __name__ == "__main__":
    main()
