"""
pdf_extractor.py
Extracts text + word-level bounding boxes from searchable PDFs produced
by ABBYY FineReader 16 or Readiris 23 (both export searchable PDF with
an invisible text layer, but no ALTO/hOCR/XML — this is the workaround).

Requires: pip install pymupdf
"""

import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Any, Union


def extract_pdf_words(pdf_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Extracts every word with its bounding box and page number from a
    searchable PDF (as produced by ABBYY/Readiris OCR export).

    Args:
        pdf_path: Path to the searchable PDF file

    Returns:
        List of dicts, one per word:
            {
                "page": int (0-indexed),
                "text": str,
                "bbox": [x0, y0, x1, y1],  # in PDF points
                "page_width": float,
                "page_height": float
            }
    """
    pdf_path = Path(pdf_path)
    doc = fitz.open(str(pdf_path))

    words = []
    for page_num, page in enumerate(doc):
        page_words = page.get_text("words")
        # get_text("words") returns: (x0, y0, x1, y1, "word", block_no, line_no, word_no)
        for w in page_words:
            x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
            words.append({
                "page": page_num,
                "text": text,
                "bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                "page_width": page.rect.width,
                "page_height": page.rect.height,
            })

    doc.close()
    return words


def extract_pdf_text(pdf_path: Union[str, Path]) -> str:
    """
    Extracts plain text (page-by-page, newline-joined) from a searchable PDF.
    Use this for quick comparisons when bounding boxes aren't needed.

    Args:
        pdf_path: Path to the searchable PDF file

    Returns:
        Full extracted text as a single string
    """
    pdf_path = Path(pdf_path)
    doc = fitz.open(str(pdf_path))

    pages_text = []
    for page in doc:
        pages_text.append(page.get_text("text"))

    doc.close()
    return "\n".join(pages_text)


def extract_pdf_lines(pdf_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Extracts text grouped by line, with bounding boxes.
    Useful for layout-level comparison rather than word-level.

    Args:
        pdf_path: Path to the searchable PDF file

    Returns:
        List of dicts, one per line:
            {
                "page": int,
                "text": str,
                "bbox": [x0, y0, x1, y1]
            }
    """
    pdf_path = Path(pdf_path)
    doc = fitz.open(str(pdf_path))

    lines = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(s["text"] for s in spans)
                if not text.strip():
                    continue
                bbox = line["bbox"]
                lines.append({
                    "page": page_num,
                    "text": text,
                    "bbox": [round(b, 2) for b in bbox],
                })

    doc.close()
    return lines


def is_text_layer_present(pdf_path: Union[str, Path]) -> bool:
    """
    Sanity check: confirms the PDF actually has an extractable text layer
    (i.e. it was OCR'd, not just a raw scanned image PDF).

    Args:
        pdf_path: Path to PDF file

    Returns:
        True if at least one page has extractable text
    """
    text = extract_pdf_text(pdf_path)
    return len(text.strip()) > 0
