#!/usr/bin/env python3
"""
scanner_fixer.pdf_ocr_processor
================================

Full PDF → image → normalize → OCR pipeline for scanned medical documents.

Combines:
  - PDF-to-image conversion (PyMuPDF / pdf2image fallback)
  - scanner_fixer normalization (deskew + crop + enhance)
  - Multi-engine OCR (Tesseract + PaddleOCR + EasyOCR)
  - Arabic RTL text fixing
  - Medical field extraction
  - Batch multi-page processing with progress tracking
  - JSON/CSV report export

Usage:
    from scanner_fixer.pdf_ocr_processor import PDFOCRProcessor

    proc = PDFOCRProcessor(dpi=300, ocr_engine="tesseract")
    results = proc.process_pdf("medical_report.pdf")
    for page in results:
        print(page["page_num"], page["text"][:80])

    # Export
    proc.export_results(results, "output.json")
    proc.export_results(results, "output.csv")
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency flags
# ---------------------------------------------------------------------------
_HAS_FITZ = False
_HAS_PDF2IMAGE = False
_HAS_PDFPLUMBER = False
_HAS_TESSERACT = False
_HAS_PADDLEOCR = False
_HAS_EASYOCR = False
_HAS_IMAGEHASH = False

try:
    import fitz  # PyMuPDF
    _HAS_FITZ = True
except ImportError:
    pass

try:
    from pdf2image import convert_from_path  # type: ignore
    _HAS_PDF2IMAGE = True
except ImportError:
    pass

try:
    import pdfplumber  # type: ignore
    _HAS_PDFPLUMBER = True
except ImportError:
    pass

try:
    import pytesseract  # type: ignore
    _HAS_TESSERACT = True
except ImportError:
    pass

try:
    from paddleocr import PaddleOCR  # type: ignore
    _HAS_PADDLEOCR = True
except ImportError:
    pass

try:
    import easyocr  # type: ignore
    _HAS_EASYOCR = True
except ImportError:
    pass

try:
    import imagehash  # type: ignore
    _HAS_IMAGEHASH = True
except ImportError:
    pass

# ---------------------------------------------------------------------------
# scanner_fixer imports (with fallback)
# ---------------------------------------------------------------------------
try:
    from scanner_fixer.pipeline import fix_scan
    from scanner_fixer.normalize import normalize_scanned_image
    from scanner_fixer.deskew import detect_skew_angle
    from scanner_fixer.crop import auto_crop
    from scanner_fixer.enhance import enhance_for_ocr
    from scanner_fixer.dedup import compute_image_phash

    _HAS_SCANNER_FIXER = True
except ImportError:
    _HAS_SCANNER_FIXER = False
    logger.debug("scanner_fixer not available — image normalization disabled")

# ---------------------------------------------------------------------------
# RTL / field extraction (optional)
# ---------------------------------------------------------------------------
try:
    from src.ocr.rtl_utils import ArabicRTLFixer  # type: ignore
    _HAS_RTL_FIXER = True
except ImportError:
    _HAS_RTL_FIXER = False

try:
    from src.ocr.field_extractor import ArabicMedicalFieldExtractor  # type: ignore
    _HAS_FIELD_EXTRACTOR = True
except ImportError:
    _HAS_FIELD_EXTRACTOR = False


# ---------------------------------------------------------------------------
# Engine constants
# ---------------------------------------------------------------------------
OCR_ENGINES = {
    "tesseract": "Tesseract OCR (open-source, best for structured text)",
    "paddleocr": "PaddleOCR (good for Chinese/Arabic mixed documents)",
    "easyocr": "EasyOCR (good for handwriting and multilingual)",
    "fitz": "PyMuPDF built-in text extraction (fast, no image OCR)",
    "pdfplumber": "pdfplumber text extraction (good for tables)",
}

SUPPORTED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


# ---------------------------------------------------------------------------
# Helper: PIL ↔ numpy
# ---------------------------------------------------------------------------
def _pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
    """Convert PIL Image to BGR numpy array (OpenCV format)."""
    return cv2.cvtColor(np.array(pil_img.convert("RGB")), cv2.COLOR_RGB2BGR)


def _cv2_to_pil(bgr: np.ndarray) -> Image.Image:
    """Convert BGR numpy array to PIL Image."""
    return Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


# ===========================================================================
# PDFOCRProcessor
# ===========================================================================
class PDFOCRProcessor:
    """
    Full PDF → image → normalize → OCR pipeline.

    Steps per page:
        1. PDF page → image (PyMuPDF or pdf2image)
        2. Image normalization (scanner_fixer pipeline: deskew + crop + enhance)
        3. OCR text extraction (Tesseract / PaddleOCR / EasyOCR)
        4. RTL Arabic text fixing (optional)
        5. Medical field extraction (optional)
        6. Perceptual hash computation (for dedup)

    Example:
        >>> proc = PDFOCRProcessor(dpi=300, ocr_engine="tesseract")
        >>> results = proc.process_pdf("report.pdf", pages=[0, 1])
        >>> proc.export_results(results, "report.json")
    """

    def __init__(
        self,
        dpi: int = 300,
        ocr_engine: str = "tesseract",
        normalize_images: bool = True,
        fix_rtl: bool = True,
        extract_fields: bool = False,
        language: str = "ara+eng",
        tesseract_config: str = "--psm 6",
        password: Optional[str] = None,
    ) -> None:
        """
        Initialize the PDF OCR processor.

        Args:
            dpi: Resolution for PDF → image conversion (default 300).
            ocr_engine: Primary OCR engine. One of: "tesseract", "paddleocr",
                        "easyocr", "fitz", "pdfplumber".
            normalize_images: Run scanner_fixer normalization before OCR.
            fix_rtl: Apply Arabic RTL text fixing after OCR.
            extract_fields: Extract medical fields from OCR text.
            language: Language for OCR engines (tesseract: "ara+eng").
            tesseract_config: Tesseract config string.
            password: Default password for encrypted PDFs.
        """
        self.dpi = dpi
        self.ocr_engine = ocr_engine
        self.normalize_images = normalize_images
        self.fix_rtl = fix_rtl
        self.extract_fields = extract_fields
        self.language = language
        self.tesseract_config = tesseract_config
        self.default_password = password

        # Lazy-initialized OCR engine instances
        self._paddle_reader: Any = None
        self._easy_reader: Any = None
        self._rtl_fixer: Any = None
        self._field_extractor: Any = None

        # Validate engine availability
        if ocr_engine == "tesseract" and not _HAS_TESSERACT:
            logger.warning("pytesseract not installed — Tesseract OCR unavailable")
        if ocr_engine == "paddleocr" and not _HAS_PADDLEOCR:
            logger.warning("paddleocr not installed — PaddleOCR unavailable")
        if ocr_engine == "easyocr" and not _HAS_EASYOCR:
            logger.warning("easyocr not installed — EasyOCR unavailable")

        # At least one PDF library is needed
        if not _HAS_FITZ and not _HAS_PDF2IMAGE:
            raise RuntimeError(
                "No PDF library available. Install PyMuPDF or pdf2image:\n"
                "  pip install PyMuPDF\n"
                "  pip install pdf2image  # also requires poppler-utils"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def process_pdf(
        self,
        pdf_source: str | bytes | Path,
        pages: Optional[list[int]] = None,
        password: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int, str], Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Process a PDF file: convert pages to images, normalize, and run OCR.

        Args:
            pdf_source: Path to PDF file, or raw bytes.
            pages: List of page numbers (0-indexed). None = all pages.
            password: Password for encrypted PDFs.
            progress_callback: Called as (current, total, status_message).

        Returns:
            List of dicts, one per page, with keys:
                page_num, text, ocr_engine, confidence,
                normalized (bool), skew_angle, phash,
                fields (if extract_fields=True),
                processing_time_ms, error
        """
        start_total = time.perf_counter()
        pwd = password or self.default_password

        # Step 1: Convert PDF pages to images
        page_images = self._pdf_to_images(pdf_source, pages, pwd)
        total = len(page_images)

        if total == 0:
            logger.warning("No pages extracted from PDF")
            return []

        logger.info("Processing %d pages from PDF (engine=%s, normalize=%s)",
                     total, self.ocr_engine, self.normalize_images)

        # Step 2: Process each page
        results: list[dict[str, Any]] = []

        for idx, (page_num, pil_image) in enumerate(page_images):
            if progress_callback:
                progress_callback(idx + 1, total, f"صفحة {page_num + 1}")

            page_result = self._process_page(page_num, pil_image)
            results.append(page_result)

        elapsed = (time.perf_counter() - start_total) * 1000
        logger.info("PDF processing complete: %d pages in %.0f ms", total, elapsed)

        return results

    def process_image(
        self,
        image_source: str | Path | np.ndarray | Image.Image,
    ) -> dict[str, Any]:
        """
        Process a single image (not from PDF) through the pipeline.

        Args:
            image_source: Path to image file, numpy array (BGR), or PIL Image.

        Returns:
            Same dict format as process_pdf page results.
        """
        # Load image
        if isinstance(image_source, (str, Path)):
            bgr = cv2.imread(str(image_source))
            if bgr is None:
                raise ValueError(f"Cannot read image: {image_source}")
            pil_image = _cv2_to_pil(bgr)
        elif isinstance(image_source, np.ndarray):
            if len(image_source.shape) == 2:
                bgr = cv2.cvtColor(image_source, cv2.COLOR_GRAY2BGR)
            else:
                bgr = image_source
            pil_image = _cv2_to_pil(bgr)
        elif isinstance(image_source, Image.Image):
            pil_image = image_source
        else:
            raise TypeError(f"Unsupported image type: {type(image_source)}")

        return self._process_page(0, pil_image)

    @staticmethod
    def export_results(
        results: list[dict[str, Any]],
        output_path: str | Path,
    ) -> str:
        """
        Export OCR results to JSON or CSV.

        Args:
            results: Output from process_pdf or process_image.
            output_path: Path for output file (.json or .csv).

        Returns:
            Absolute path to the written file.
        """
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if output_path.suffix.lower() == ".csv":
            return PDFOCRProcessor._export_csv(results, output_path)
        else:
            return PDFOCRProcessor._export_json(results, output_path)

    @staticmethod
    def _export_json(results: list[dict[str, Any]], path: Path) -> str:
        """Export results to JSON."""
        # Convert non-serializable values
        clean = []
        for r in results:
            item = {}
            for k, v in r.items():
                if isinstance(v, (np.ndarray, Image.Image)):
                    item[k] = f"<{type(v).__name__}>"
                elif isinstance(v, bytes):
                    item[k] = f"<bytes len={len(v)}>"
                else:
                    item[k] = v
            clean.append(item)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, indent=2, default=str)

        logger.info("JSON results exported to %s", path)
        return str(path)

    @staticmethod
    def _export_csv(results: list[dict[str, Any]], path: Path) -> str:
        """Export results to CSV (text and metadata only)."""
        fieldnames = [
            "page_num", "text", "ocr_engine", "confidence",
            "normalized", "skew_angle", "phash",
            "processing_time_ms", "error",
        ]
        # Add field extraction columns if present
        if results and "fields" in results[0]:
            fieldnames.append("fields")

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in results:
                row = {}
                for k in fieldnames:
                    val = r.get(k, "")
                    if isinstance(val, dict):
                        val = json.dumps(val, ensure_ascii=False)
                    row[k] = val
                writer.writerow(row)

        logger.info("CSV results exported to %s", path)
        return str(path)

    def get_page_count(
        self,
        pdf_source: str | bytes | Path,
        password: Optional[str] = None,
    ) -> int:
        """Return the number of pages in a PDF file."""
        pwd = password or self.default_password

        if _HAS_FITZ:
            doc = self._open_fitz(pdf_source, pwd)
            count = len(doc)
            doc.close()
            return count
        elif _HAS_PDF2IMAGE:
            # pdf2image doesn't have a fast page count method
            # We'd have to convert all pages just to count — use PyMuPDF instead
            raise RuntimeError(
                "Page counting requires PyMuPDF. Install: pip install PyMuPDF"
            )
        else:
            raise RuntimeError("No PDF library available")

    # ------------------------------------------------------------------
    # PDF → Image conversion
    # ------------------------------------------------------------------
    def _pdf_to_images(
        self,
        pdf_source: str | bytes | Path,
        pages: Optional[list[int]],
        password: Optional[str],
    ) -> list[tuple[int, Image.Image]]:
        """Convert PDF pages to PIL Images. Returns list of (page_num, pil_image)."""
        if _HAS_FITZ:
            return self._pdf_to_images_fitz(pdf_source, pages, password)
        elif _HAS_PDF2IMAGE:
            return self._pdf_to_images_pdf2image(pdf_source, pages)
        else:
            raise RuntimeError("No PDF library available for image conversion")

    def _pdf_to_images_fitz(
        self,
        pdf_source: str | bytes | Path,
        pages: Optional[list[int]],
        password: Optional[str],
    ) -> list[tuple[int, Image.Image]]:
        """Convert PDF pages using PyMuPDF (fitz)."""
        import fitz

        doc = self._open_fitz(pdf_source, password)
        total_pages = len(doc)
        target_pages = pages if pages is not None else list(range(total_pages))
        target_pages = [p for p in target_pages if 0 <= p < total_pages]

        result: list[tuple[int, Image.Image]] = []
        mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)

        for page_num in target_pages:
            page = doc[page_num]
            pix = page.get_pixmap(matrix=mat)
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.h, pix.w, pix.n
            )
            if pix.n == 4:
                pil_img = Image.fromarray(img_array[:, :, :3], mode="RGB")
            elif pix.n == 1:
                pil_img = Image.fromarray(img_array[:, :, 0], mode="L").convert("RGB")
            else:
                pil_img = Image.fromarray(img_array, mode="RGB")
            result.append((page_num, pil_img))

        doc.close()
        logger.debug("Extracted %d pages via PyMuPDF", len(result))
        return result

    def _pdf_to_images_pdf2image(
        self,
        pdf_source: str | bytes | Path,
        pages: Optional[list[int]],
    ) -> list[tuple[int, Image.Image]]:
        """Convert PDF pages using pdf2image (poppler backend)."""
        path_str = str(pdf_source)
        if not Path(path_str).exists():
            raise FileNotFoundError(f"PDF not found: {path_str}")

        first_page = None
        last_page = None
        if pages is not None:
            first_page = min(pages) + 1  # pdf2image is 1-indexed
            last_page = max(pages) + 1

        pil_images = convert_from_path(
            path_str,
            dpi=self.dpi,
            first_page=first_page,
            last_page=last_page,
        )

        result: list[tuple[int, Image.Image]] = []
        # Map back to 0-indexed page numbers
        if pages is not None:
            for i, page_num in enumerate(sorted(pages)):
                if i < len(pil_images):
                    result.append((page_num, pil_images[i]))
        else:
            for i, img in enumerate(pil_images):
                result.append((i, img))

        logger.debug("Extracted %d pages via pdf2image", len(result))
        return result

    def _open_fitz(
        self,
        pdf_source: str | bytes | Path,
        password: Optional[str],
    ) -> Any:
        """Open a PDF document with PyMuPDF."""
        import fitz

        if isinstance(pdf_source, (str, Path)):
            path_str = str(pdf_source)
            if not Path(path_str).exists():
                raise FileNotFoundError(f"PDF not found: {path_str}")
            doc = fitz.open(path_str)
        elif isinstance(pdf_source, bytes):
            doc = fitz.open(stream=pdf_source, filetype="pdf")
        else:
            raise TypeError(f"Unsupported pdf_source type: {type(pdf_source)}")

        if doc.is_encrypted:
            if password and doc.authenticate(password):
                pass
            elif self.default_password and doc.authenticate(self.default_password):
                pass
            else:
                doc.close()
                raise PermissionError("PDF is encrypted and no valid password provided")

        return doc

    # ------------------------------------------------------------------
    # Per-page processing
    # ------------------------------------------------------------------
    def _process_page(
        self,
        page_num: int,
        pil_image: Image.Image,
    ) -> dict[str, Any]:
        """Process a single page image through the full pipeline."""
        start = time.perf_counter()

        result: dict[str, Any] = {
            "page_num": page_num,
            "text": "",
            "ocr_engine": self.ocr_engine,
            "confidence": 0.0,
            "normalized": False,
            "skew_angle": None,
            "phash": None,
            "processing_time_ms": 0.0,
            "error": "",
        }

        try:
            bgr = _pil_to_cv2(pil_image)

            # Step 1: Normalize with scanner_fixer
            if self.normalize_images and _HAS_SCANNER_FIXER:
                bgr, meta = self._normalize_image(bgr)
                result["normalized"] = True
                result["skew_angle"] = meta.get("skew_angle")
            elif self.normalize_images and not _HAS_SCANNER_FIXER:
                logger.debug("scanner_fixer unavailable — skipping normalization")

            # Step 2: OCR
            text, confidence = self._run_ocr(bgr)
            result["text"] = text
            result["confidence"] = confidence

            # Step 3: RTL fix
            if self.fix_rtl and _HAS_RTL_FIXER and text:
                result["text"] = self._fix_rtl_text(text)

            # Step 4: Field extraction
            if self.extract_fields and _HAS_FIELD_EXTRACTOR and text:
                result["fields"] = self._extract_fields(result["text"])

            # Step 5: Perceptual hash
            if _HAS_IMAGEHASH and _HAS_SCANNER_FIXER:
                try:
                    phash = compute_image_phash(bgr)
                    result["phash"] = str(phash)
                except Exception:
                    pass

        except Exception as exc:
            result["error"] = str(exc)
            logger.error("Error processing page %d: %s", page_num, exc)

        result["processing_time_ms"] = round((time.perf_counter() - start) * 1000, 2)
        return result

    # ------------------------------------------------------------------
    # Image normalization
    # ------------------------------------------------------------------
    def _normalize_image(self, bgr: np.ndarray) -> tuple[np.ndarray, dict[str, Any]]:
        """
        Normalize image using scanner_fixer pipeline.

        Returns:
            (normalized_bgr, metadata_dict)
        """
        meta: dict[str, Any] = {}

        # Detect skew angle first (for reporting)
        if _HAS_SCANNER_FIXER:
            try:
                angle, angle_meta = detect_skew_angle(bgr)
                meta["skew_angle"] = angle
                meta["skew_uncertain"] = angle_meta.get("uncertain", False)
            except Exception:
                pass

        # Run full pipeline
        try:
            pipeline_result = fix_scan(
                bgr,
                do_crop=True,
                do_deskew=True,
                do_rotate=False,
                do_enhance=True,
                binarize=False,
                crop_padding=10,
            )
            normalized = pipeline_result["image"]
            meta.update(pipeline_result.get("report", {}))
            return normalized, meta
        except Exception as exc:
            logger.warning("scanner_fixer pipeline failed, using basic normalize: %s", exc)
            # Fallback: basic normalization
            try:
                normalized = normalize_scanned_image(bgr)
                return normalized, meta
            except Exception:
                logger.warning("Basic normalization also failed, using original image")
                return bgr, meta

    # ------------------------------------------------------------------
    # OCR engines
    # ------------------------------------------------------------------
    def _run_ocr(self, bgr: np.ndarray) -> tuple[str, float]:
        """
        Run OCR on a BGR image using the configured engine.

        Returns:
            (text, confidence) — confidence is 0.0-1.0
        """
        engine = self.ocr_engine.lower()

        if engine == "tesseract" and _HAS_TESSERACT:
            return self._ocr_tesseract(bgr)
        elif engine == "paddleocr" and _HAS_PADDLEOCR:
            return self._ocr_paddle(bgr)
        elif engine == "easyocr" and _HAS_EASYOCR:
            return self._ocr_easy(bgr)
        elif engine in ("fitz", "pdfplumber"):
            # These engines extract text directly — no image OCR
            logger.warning(
                "%s is a text-extraction engine, not image OCR. "
                "Use process_pdf() which handles text extraction separately.",
                engine,
            )
            return "", 0.0
        else:
            # Fallback chain: tesseract → paddleocr → easyocr
            if _HAS_TESSERACT:
                logger.info("Primary OCR unavailable, falling back to Tesseract")
                return self._ocr_tesseract(bgr)
            elif _HAS_PADDLEOCR:
                logger.info("Primary OCR unavailable, falling back to PaddleOCR")
                return self._ocr_paddle(bgr)
            elif _HAS_EASYOCR:
                logger.info("Primary OCR unavailable, falling back to EasyOCR")
                return self._ocr_easy(bgr)
            else:
                logger.error("No OCR engine available")
                return "", 0.0

    def _ocr_tesseract(self, bgr: np.ndarray) -> tuple[str, float]:
        """Run Tesseract OCR on BGR image."""
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)

        # Get text
        text = pytesseract.image_to_string(
            pil_img,
            lang=self.language,
            config=self.tesseract_config,
        )

        # Get confidence
        try:
            data = pytesseract.image_to_data(
                pil_img,
                lang=self.language,
                config=self.tesseract_config,
                output_type=pytesseract.Output.DICT,
            )
            confidences = [
                int(c) for c in data["conf"] if int(c) > 0
            ]
            avg_conf = sum(confidences) / len(confidences) / 100.0 if confidences else 0.0
        except Exception:
            avg_conf = 0.0

        return text.strip(), round(avg_conf, 3)

    def _ocr_paddle(self, bgr: np.ndarray) -> tuple[str, float]:
        """Run PaddleOCR on BGR image."""
        if self._paddle_reader is None:
            self._paddle_reader = PaddleOCR(
                use_angle_cls=True,
                lang="ar",  # Arabic
                show_log=False,
            )

        result = self._paddle_reader.ocr(bgr, cls=True)

        if not result or not result[0]:
            return "", 0.0

        texts = []
        confidences = []
        for line in result[0]:
            if line and len(line) >= 2:
                text = line[1][0] if isinstance(line[1], (list, tuple)) else str(line[1])
                conf = line[1][1] if isinstance(line[1], (list, tuple)) and len(line[1]) > 1 else 0.0
                texts.append(str(text))
                confidences.append(float(conf))

        full_text = " ".join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return full_text.strip(), round(avg_conf, 3)

    def _ocr_easy(self, bgr: np.ndarray) -> tuple[str, float]:
        """Run EasyOCR on BGR image."""
        if self._easy_reader is None:
            lang_list = ["ar", "en"]  # Arabic + English
            self._easy_reader = easyocr.Reader(lang_list, gpu=False)

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        results = self._easy_reader.readtext(rgb)

        if not results:
            return "", 0.0

        texts = []
        confidences = []
        for detection in results:
            _, text, conf = detection
            texts.append(text)
            confidences.append(conf)

        full_text = " ".join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        return full_text.strip(), round(avg_conf, 3)

    # ------------------------------------------------------------------
    # RTL fixing
    # ------------------------------------------------------------------
    def _fix_rtl_text(self, text: str) -> str:
        """Apply Arabic RTL text fixing."""
        if self._rtl_fixer is None:
            self._rtl_fixer = ArabicRTLFixer()
        try:
            return self._rtl_fixer.fix_text(text)
        except Exception as exc:
            logger.warning("RTL fixing failed: %s", exc)
            return text

    # ------------------------------------------------------------------
    # Field extraction
    # ------------------------------------------------------------------
    def _extract_fields(self, text: str) -> dict[str, Any]:
        """Extract medical fields from OCR text."""
        if self._field_extractor is None:
            self._field_extractor = ArabicMedicalFieldExtractor()
        try:
            fields = self._field_extractor.extract_fields(text)
            return fields.to_dict() if hasattr(fields, "to_dict") else dict(fields)
        except Exception as exc:
            logger.warning("Field extraction failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # Text extraction (non-OCR) — useful as supplement
    # ------------------------------------------------------------------
    def extract_text_direct(
        self,
        pdf_source: str | bytes | Path,
        pages: Optional[list[int]] = None,
        password: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Extract text directly from PDF without OCR (uses PyMuPDF/pdfplumber).

        Useful for digitally-created PDFs where OCR is unnecessary.

        Returns:
            List of dicts with keys: page_num, text, tables
        """
        pwd = password or self.default_password
        results: list[dict[str, Any]] = []

        if _HAS_FITZ:
            doc = self._open_fitz(pdf_source, pwd)
            total = len(doc)
            target = pages if pages is not None else list(range(total))
            for pn in target:
                if 0 <= pn < total:
                    page = doc[pn]
                    text = page.get_text("text").strip()
                    results.append({"page_num": pn, "text": text, "tables": []})
            doc.close()

        # Supplement with pdfplumber for tables
        if _HAS_PDFPLUMBER:
            try:
                if isinstance(pdf_source, (str, Path)):
                    pdf = pdfplumber.open(str(pdf_source))
                    for r in results:
                        pn = r["page_num"]
                        if pn < len(pdf.pages):
                            page = pdf.pages[pn]
                            tables = page.extract_tables() or []
                            r["tables"] = tables
                            if not r["text"].strip():
                                r["text"] = (page.extract_text() or "").strip()
                    pdf.close()
            except Exception as exc:
                logger.warning("pdfplumber supplement failed: %s", exc)

        return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """CLI entry point for pdf_ocr_processor."""
    import argparse

    parser = argparse.ArgumentParser(
        description="PDF OCR Processor — scanned medical document pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  %(prog)s report.pdf --engine tesseract --output results.json
  %(prog)s report.pdf --engine paddleocr --pages 0 1 2 --output results.csv
  %(prog)s scanned_image.png --output ocr_result.json
        """,
    )
    parser.add_argument("input", help="PDF file or image path")
    parser.add_argument("--engine", "-e", default="tesseract",
                        choices=list(OCR_ENGINES.keys()),
                        help="OCR engine (default: tesseract)")
    parser.add_argument("--dpi", type=int, default=300,
                        help="DPI for PDF→image conversion (default: 300)")
    parser.add_argument("--pages", type=int, nargs="*",
                        help="Page numbers (0-indexed). Default: all pages")
    parser.add_argument("--output", "-o", default=None,
                        help="Output file path (.json or .csv)")
    parser.add_argument("--no-normalize", action="store_true",
                        help="Skip image normalization")
    parser.add_argument("--no-rtl", action="store_true",
                        help="Skip Arabic RTL fixing")
    parser.add_argument("--fields", action="store_true",
                        help="Extract medical fields")
    parser.add_argument("--password", default=None,
                        help="Password for encrypted PDFs")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    proc = PDFOCRProcessor(
        dpi=args.dpi,
        ocr_engine=args.engine,
        normalize_images=not args.no_normalize,
        fix_rtl=not args.no_rtl,
        extract_fields=args.fields,
        password=args.password,
    )

    input_path = Path(args.input)

    # Detect input type
    if input_path.suffix.lower() == ".pdf":
        results = proc.process_pdf(
            str(input_path),
            pages=args.pages,
            password=args.password,
        )
    elif input_path.suffix.lower() in SUPPORTED_IMAGE_EXT:
        results = [proc.process_image(str(input_path))]
    else:
        print(f"Error: Unsupported file type: {input_path.suffix}")
        return

    # Print summary
    print(f"\n{'='*60}")
    print(f"  PDF OCR Processor Results")
    print(f"{'='*60}")
    print(f"  Input:  {input_path.name}")
    print(f"  Engine: {args.engine}")
    print(f"  Pages:  {len(results)}")
    print()

    for r in results:
        pn = r["page_num"]
        text_preview = r["text"][:100].replace("\n", " ") if r["text"] else "(empty)"
        conf = r.get("confidence", 0)
        norm = "✓" if r.get("normalized") else "✗"
        err = r.get("error", "")
        print(f"  Page {pn}: conf={conf:.0%} norm={norm} | {text_preview}...")
        if err:
            print(f"    ⚠ Error: {err}")

    # Export
    if args.output:
        out_path = proc.export_results(results, args.output)
        print(f"\n  Results exported to: {out_path}")
    else:
        # Default: print JSON to stdout
        print("\n" + json.dumps(
            [{k: v for k, v in r.items() if k != "page_image"} for r in results],
            ensure_ascii=False, indent=2, default=str,
        ))


if __name__ == "__main__":
    main()
