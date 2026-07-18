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
import re
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
# Engine registry (optional — used for runtime-aware engine selection)
# ---------------------------------------------------------------------------
try:
    from packages.core.engine_registry import EngineRegistry  # type: ignore
    _HAS_ENGINE_REGISTRY = True
except ImportError:
    _HAS_ENGINE_REGISTRY = False
    logger.debug("packages.core.engine_registry not available — falling back to "
                 "manual engine checks")


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

# Auto-tune search space (Tesseract PSM × DPI). Lifted verbatim from the
# legacy scripts/pdf_ocr_processor.py so existing CLI behaviour is preserved.
PSM_MODES: list[int] = [3, 4, 6, 11]
DPI_OPTIONS: list[int] = [200, 300, 400]

# Glossary extraction patterns (Arabic-Latin bilingual pairs).
GLOSSARY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r'(.+?)\s*[=ـ]\s*(.+?)$'),           # العربية = English
    re.compile(r'(.+?)\s*[-–—]\s*(.+?)$'),            # العربية - English
    re.compile(r'(.+?)\s*[:：]\s*(.+?)$'),             # العربية : English
    re.compile(r'(.+?)\t+(.+?)$'),                     # العربية\tEnglish
]

# Mapping from PDFOCRProcessor engine names (lowercase) to EngineRegistry
# adapter names (capitalized). Used to bridge the two naming conventions
# when delegating engine availability checks to EngineRegistry.
_REGISTRY_NAME_MAP: dict[str, str] = {
    "tesseract": "Tesseract",
    "paddleocr": "PaddleOCR",
    "easyocr": "EasyOCR",
}

# Reverse map for fallback ordering: when the requested engine is unavailable,
# we walk the registry's available list in this preferred order (matches the
# previous hard-coded fallback chain to preserve backwards behaviour).
_FALLBACK_PREFERENCE: list[str] = ["tesseract", "paddleocr", "easyocr"]


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
        auto_tune: bool = False,
        extract_glossary: bool = False,
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
            auto_tune: When True, run a PSM × DPI search on the first page
                of each PDF and pick the configuration that yields the
                highest-quality OCR text (longest, most-Arabic, most
                consistent). Only effective when ``ocr_engine`` resolves
                to Tesseract. Previously this lived only in
                ``scripts/pdf_ocr_processor.py``; it has been moved here
                so the CLI can become a thin wrapper.
            extract_glossary: When True, scan OCR text for bilingual
                Arabic-English glossary entries (patterns like
                ``عربي = English``, ``عربي - English``, ``عربي : English``,
                ``عربi\\tEnglish``) and attach them to each page result
                under the ``glossary_entries`` key. Also see
                ``export_glossary()``.
        """
        self.dpi = dpi
        self.ocr_engine = ocr_engine
        self.normalize_images = normalize_images
        self.fix_rtl = fix_rtl
        self.extract_fields = extract_fields
        self.language = language
        self.tesseract_config = tesseract_config
        self.default_password = password
        self.auto_tune = auto_tune
        self.extract_glossary = extract_glossary

        # Best PSM/DPI config found by ``_auto_tune_psm_dpi``. Updated lazily.
        self.best_config: dict[str, Any] = {
            "psm": 6,
            "dpi": dpi,
            "language": language,
        }

        # Accumulated glossary entries across all processed pages/PDFs.
        # Each entry: {"term_arabic": str, "term_english": str, "source": str}
        self.combined_glossary: list[dict[str, str]] = []

        # Lazy-initialized OCR engine instances
        self._paddle_reader: Any = None
        self._easy_reader: Any = None
        self._rtl_fixer: Any = None
        self._field_extractor: Any = None

        # EngineRegistry — probed lazily on first OCR call so that import-time
        # failures of packages.core don't break scanner_fixer. When the
        # registry is unavailable we transparently fall back to the legacy
        # _HAS_TESSERACT / _HAS_PADDLEOCR / _HAS_EASYOCR flags.
        self._engine_registry: Any = None
        self._registry_probed: bool = False

        # Validate engine availability (use registry if possible, else flags)
        self._warn_if_engine_unavailable(ocr_engine)

        # At least one PDF library is needed
        if not _HAS_FITZ and not _HAS_PDF2IMAGE:
            raise RuntimeError(
                "No PDF library available. Install PyMuPDF or pdf2image:\n"
                "  pip install PyMuPDF\n"
                "  pip install pdf2image  # also requires poppler-utils"
            )

    # ------------------------------------------------------------------
    # EngineRegistry integration
    # ------------------------------------------------------------------
    def _ensure_registry(self) -> Any:
        """Lazily probe the EngineRegistry once and cache the result.

        Returns the registry instance, or ``None`` if it's unavailable.
        Subsequent calls are O(1).
        """
        if self._registry_probed:
            return self._engine_registry
        self._registry_probed = True

        if not _HAS_ENGINE_REGISTRY:
            return None

        try:
            self._engine_registry = EngineRegistry()
            self._engine_registry.discover()
            logger.debug(
                "EngineRegistry probed — available: %s",
                self._engine_registry.available_engine_names(),
            )
        except Exception as exc:
            logger.debug("EngineRegistry probe failed: %s", exc)
            self._engine_registry = None
        return self._engine_registry

    def _is_engine_available(self, engine_name: str) -> bool:
        """Check engine availability, preferring EngineRegistry over flags.

        Falls back to the legacy ``_HAS_*`` module-level flags when the
        registry is unavailable. This keeps backwards compatibility for
        environments where ``packages.core`` is not installed.
        """
        registry = self._ensure_registry()
        if registry is not None:
            registry_name = _REGISTRY_NAME_MAP.get(engine_name.lower())
            if registry_name is None:
                # Non-OCR engines (fitz, pdfplumber) — defer to flags
                return engine_name.lower() in ("fitz",) and _HAS_FITZ \
                    or engine_name.lower() == "pdfplumber" and _HAS_PDFPLUMBER
            info = registry.get_info(registry_name)
            return bool(info and info.available and info.healthy)

        # Legacy flag fallback
        return {
            "tesseract": _HAS_TESSERACT,
            "paddleocr": _HAS_PADDLEOCR,
            "easyocr": _HAS_EASYOCR,
            "fitz": _HAS_FITZ,
            "pdfplumber": _HAS_PDFPLUMBER,
        }.get(engine_name.lower(), False)

    def _warn_if_engine_unavailable(self, engine_name: str) -> None:
        """Warn at construction time if the requested engine is not usable.

        Mirrors the previous hard-coded warnings so logs stay informative.
        """
        if engine_name.lower() in ("fitz", "pdfplumber"):
            return  # these are text-extraction engines; not OCR
        if not self._is_engine_available(engine_name):
            logger.warning(
                "%s not available via EngineRegistry — will fall back at OCR time",
                engine_name,
            )

    def _pick_fallback_engine(self) -> Optional[str]:
        """Pick the best available fallback engine.

        Order of preference (preserves previous behaviour):
          1. Walk ``_FALLBACK_PREFERENCE`` and return first available.
          2. If none of those are available, ask the registry for *any*
             healthy engine within a 4 GB RAM budget.
          3. Return ``None`` if nothing is available.
        """
        for name in _FALLBACK_PREFERENCE:
            if self._is_engine_available(name):
                return name

        registry = self._ensure_registry()
        if registry is not None:
            try:
                healthy = registry.available_engine_names()
                # Filter by RAM budget (default 4 GB — same as PaddleOCR)
                within_budget = registry.filter_by_ram(healthy, 4.0)
                for h in within_budget:
                    # Reverse-map registry name back to our engine name
                    for eng, reg_name in _REGISTRY_NAME_MAP.items():
                        if reg_name == h:
                            return eng
            except Exception as exc:
                logger.debug("Registry fallback lookup failed: %s", exc)
        return None

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

        # Optional: auto-tune PSM × DPI on the first page (Tesseract only).
        # The chosen config is stored in self.best_config and re-used for
        # every subsequent page in this PDF (and any future PDFs until the
        # user constructs a new PDFOCRProcessor or calls _auto_tune again).
        if self.auto_tune and total > 0:
            self._auto_tune_psm_dpi(page_images[0][1])
            logger.info(
                "Auto-tune picked PSM=%s, DPI=%s (score=%.3f)",
                self.best_config.get("psm"),
                self.best_config.get("dpi"),
                self.best_config.get("auto_tune_score", 0.0),
            )

        # Step 2: Process each page
        results: list[dict[str, Any]] = []

        # When auto_tune is on, we update the tesseract_config to use the
        # tuned PSM. This is read by _ocr_tesseract.
        if self.auto_tune:
            tuned_psm = self.best_config.get("psm", 6)
            tuned_dpi = self.best_config.get("dpi", self.dpi)
            self.tesseract_config = f"--psm {tuned_psm} --dpi {tuned_dpi}"

        # Source label for glossary extraction
        source_label = (
            Path(pdf_source).name if isinstance(pdf_source, (str, Path)) else "bytes"
        )

        for idx, (page_num, pil_image) in enumerate(page_images):
            if progress_callback:
                progress_callback(idx + 1, total, f"صفحة {page_num + 1}")

            page_result = self._process_page(page_num, pil_image)

            # Optional: extract bilingual glossary entries from this page's text
            if self.extract_glossary and page_result.get("text"):
                entries = self._extract_glossary_entries(
                    page_result["text"], source=source_label
                )
                page_result["glossary_entries"] = entries
                self.combined_glossary.extend(entries)

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
            "page_num", "text", "ocr_engine", "ocr_engine_used", "confidence",
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
            "ocr_engine_used": None,  # actually-used engine (may differ from ocr_engine after fallback)
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

            # Step 2: OCR (records which engine was actually used)
            text, confidence, used_engine = self._run_ocr_with_tracking(bgr)
            result["text"] = text
            result["confidence"] = confidence
            result["ocr_engine_used"] = used_engine

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
    def _run_ocr_with_tracking(self, bgr: np.ndarray) -> tuple[str, float, Optional[str]]:
        """Run OCR and report which engine was actually used.

        Wraps ``_run_ocr`` so that callers (e.g. ``_process_page``) can
        record the *actually-used* engine in the result dict, which may
        differ from ``self.ocr_engine`` when a fallback was triggered.
        """
        engine = self.ocr_engine.lower()

        # Text-extraction engines short-circuit (no real OCR happens).
        # Inline the warning instead of calling _run_ocr to avoid infinite
        # recursion (_run_ocr delegates back to this method).
        if engine in ("fitz", "pdfplumber"):
            logger.warning(
                "%s is a text-extraction engine, not image OCR. "
                "Use process_pdf() which handles text extraction separately.",
                engine,
            )
            return "", 0.0, engine

        if self._is_engine_available(engine):
            text, conf = self._dispatch_ocr(engine, bgr)
            return text, conf, engine

        fallback = self._pick_fallback_engine()
        if fallback is None:
            logger.error("No OCR engine available (requested=%s)", engine)
            return "", 0.0, None

        if fallback != engine:
            logger.info(
                "Primary OCR engine %s unavailable — falling back to %s",
                engine, fallback,
            )
        text, conf = self._dispatch_ocr(fallback, bgr)
        return text, conf, fallback

    def _run_ocr(self, bgr: np.ndarray) -> tuple[str, float]:
        """Run OCR on a BGR image using the configured engine.

        Engine selection flow (unified with ``packages.core.engine_registry``):

        1. If the user-requested engine (``self.ocr_engine``) is reported
           available by the registry (or by the legacy ``_HAS_*`` flags when
           the registry is missing), use it directly.
        2. Otherwise, ask ``_pick_fallback_engine()`` to choose the best
           available engine, respecting the previous hard-coded preference
           order (tesseract → paddleocr → easyocr) plus a RAM budget.
        3. If no engine is available at all, return ("", 0.0).

        Returns:
            (text, confidence) — confidence is 0.0-1.0

        Note: this method preserves its original (text, conf) signature for
        backwards compatibility. ``_process_page`` calls
        ``_run_ocr_with_tracking`` instead to also learn which engine was
        actually used after a potential fallback.
        """
        text, conf, _used = self._run_ocr_with_tracking(bgr)
        return text, conf

    def _dispatch_ocr(self, engine: str, bgr: np.ndarray) -> tuple[str, float]:
        """Dispatch to the per-engine OCR method.

        Centralises the engine → method mapping so ``_run_ocr`` stays
        readable and the fallback path can reuse the same dispatch.
        """
        if engine == "tesseract":
            return self._ocr_tesseract(bgr)
        if engine == "paddleocr":
            return self._ocr_paddle(bgr)
        if engine == "easyocr":
            return self._ocr_easy(bgr)
        logger.error("Unknown OCR engine: %s", engine)
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
        """Run PaddleOCR on BGR image.

        Note: ``device="cpu"`` is required for PaddlePaddle 3.x compatibility
        (the old ``use_gpu=False`` flag was removed in 3.x). This mirrors the
        fix applied in ``hf-space/app.py`` (commit a379f26).
        ``show_log=False`` is still supported by PaddleOCR 2.7.x and 3.x;
        we keep it to silence the noisy paddlepaddle startup banner.

        The ``PaddleOCR`` class is imported lazily inside this method so
        that tests can patch ``sys.modules['paddleocr']`` with a mock
        without needing the real package installed.
        """
        if self._paddle_reader is None:
            # Lazy import — don't rely on the module-level PaddleOCR name,
            # which may be unbound when the package isn't installed.
            from paddleocr import PaddleOCR  # type: ignore
            self._paddle_reader = PaddleOCR(
                use_angle_cls=True,
                lang="ar",  # Arabic
                show_log=False,
                device="cpu",  # PaddlePaddle 3.x compat (was implicit before)
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

    # ------------------------------------------------------------------
    # Auto-tuning (Tesseract PSM × DPI search)
    # ------------------------------------------------------------------
    def _auto_tune_psm_dpi(self, pil_image: Image.Image) -> None:
        """Search PSM × DPI space on a sample image and pick the best config.

        Lifted from ``scripts/pdf_ocr_processor.py`` (now removed) and
        preserved verbatim in scoring logic so existing CLI behaviour is
        unchanged. Updates ``self.best_config`` in place.

        Only effective when Tesseract is the OCR engine — for other engines
        this is a no-op (the DPI search still runs but has no effect on
        engine selection, since PaddleOCR/EasyOCR ignore ``tesseract_config``).

        Scoring criteria (weighted):
          - Text length (longer is better, capped at 2000 chars)        30%
          - Arabic character ratio vs Latin                              25%
          - Word count (more is better, capped at 200)                  25%
          - Line-length consistency (lower variance is better)          20%
        """
        if not _HAS_TESSERACT:
            logger.debug("auto_tune: pytesseract not installed — skipping")
            return

        best_score = -1.0
        best_psm = 6
        best_dpi = self.dpi
        original_w, original_h = pil_image.size

        for psm in PSM_MODES:
            for dpi in DPI_OPTIONS:
                try:
                    scale = dpi / 300
                    new_w = max(1, int(original_w * scale))
                    new_h = max(1, int(original_h * scale))
                    resized = pil_image.resize((new_w, new_h), Image.LANCZOS)

                    text = pytesseract.image_to_string(
                        resized,
                        lang=self.language,
                        config=f"--psm {psm}",
                    )
                    score = self._evaluate_ocr_text(text)
                    logger.debug(
                        "auto_tune: PSM=%s DPI=%s -> score=%.3f len=%d words=%d",
                        psm, dpi, score, len(text), len(text.split()),
                    )
                    if score > best_score:
                        best_score = score
                        best_psm = psm
                        best_dpi = dpi
                except Exception as exc:
                    logger.debug("auto_tune: PSM=%s DPI=%s failed: %s", psm, dpi, exc)
                    continue

        self.best_config = {
            "psm": best_psm,
            "dpi": best_dpi,
            "language": self.language,
            "auto_tune_score": round(best_score, 3),
        }

    @staticmethod
    def _evaluate_ocr_text(text: str) -> float:
        """Score OCR text quality (0.0-1.0). Used by ``_auto_tune_psm_dpi``.

        Publicised from the legacy script verbatim so scoring is reproducible.
        """
        if not text.strip():
            return 0.0

        # Length score (normalize to 0-1, cap at 2000 chars)
        length_score = min(len(text) / 2000, 1.0)

        # Arabic character ratio
        arabic_chars = len(re.findall(r'[\u0600-\u06FF]', text))
        total_alpha = len(re.findall(r'[a-zA-Z\u0600-\u06FF]', text))
        arabic_ratio = arabic_chars / max(total_alpha, 1)

        # Word count score
        words = text.split()
        word_score = min(len(words) / 200, 1.0)

        # Consistency: variance of line lengths (lower = more consistent)
        lines = [ln for ln in text.split("\n") if ln.strip()]
        if lines:
            line_lengths = [len(ln) for ln in lines]
            avg_len = sum(line_lengths) / len(line_lengths)
            variance = sum((ln - avg_len) ** 2 for ln in line_lengths) / len(line_lengths)
            consistency = 1.0 / (1.0 + variance / 1000)
        else:
            consistency = 0.0

        return (
            0.30 * length_score
            + 0.25 * arabic_ratio
            + 0.25 * word_score
            + 0.20 * consistency
        )

    # ------------------------------------------------------------------
    # Glossary extraction
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_glossary_entries(
        text: str,
        source: str = "unknown",
    ) -> list[dict[str, str]]:
        """Extract bilingual Arabic-English glossary entries from OCR text.

        Recognised patterns (one per line, first match wins):
          - ``العربية = English``
          - ``العربية - English``
          - ``العربية : English``
          - ``العربية\\tEnglish``

        Returns a list of dicts with keys:
          - ``term_arabic``
          - ``term_english``
          - ``source``
        """
        entries: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()

        for line in text.split("\n"):
            line = line.strip()
            if not line or len(line) < 3:
                continue

            for pattern in GLOSSARY_PATTERNS:
                match = pattern.match(line)
                if not match:
                    continue

                left = match.group(1).strip()
                right = match.group(2).strip()

                has_arabic_left = bool(re.search(r'[\u0600-\u06FF]', left))
                has_arabic_right = bool(re.search(r'[\u0600-\u06FF]', right))
                has_english_left = bool(re.search(r'[a-zA-Z]', left))
                has_english_right = bool(re.search(r'[a-zA-Z]', right))

                # Must have one Arabic and one English side
                if has_arabic_left and has_english_right:
                    term_ar, term_en = left, right
                elif has_arabic_right and has_english_left:
                    term_ar, term_en = right, left
                else:
                    continue

                # Strip leading/trailing separators
                term_ar = re.sub(r'^[\s\-=:]+|[\s\-=:]+$', '', term_ar)
                term_en = re.sub(r'^[\s\-=:]+|[\s\-=:]+$', '', term_en)

                if len(term_ar) < 2 or len(term_en) < 2:
                    continue

                key = (term_ar, term_en)
                if key in seen:
                    continue
                seen.add(key)
                entries.append({
                    "term_arabic": term_ar,
                    "term_english": term_en,
                    "source": source,
                })
                break  # don't double-match the same line

        return entries

    def export_glossary(
        self,
        output_path: str | Path,
        fmt: Optional[str] = None,
    ) -> str:
        """Export ``self.combined_glossary`` to CSV or JSON.

        Args:
            output_path: Destination file path. If ``fmt`` is None, the
                format is inferred from the file extension (``.csv`` or
                ``.json``).
            fmt: Force format. One of ``"csv"`` or ``"json"``.

        Returns:
            Absolute path to the written file.
        """
        output_path = Path(output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if fmt is None:
            fmt = "csv" if output_path.suffix.lower() == ".csv" else "json"

        if fmt == "csv":
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["term_arabic", "term_english", "source"],
                )
                writer.writeheader()
                writer.writerows(self.combined_glossary)
        elif fmt == "json":
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(
                    self.combined_glossary, f,
                    ensure_ascii=False, indent=2, default=str,
                )
        else:
            raise ValueError(f"Unsupported glossary format: {fmt!r}")

        logger.info(
            "Glossary exported: %s (%d entries, %s)",
            output_path, len(self.combined_glossary), fmt,
        )
        return str(output_path)


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
    parser.add_argument("--auto-tune", action="store_true",
                        help="Search PSM × DPI on first page and use the best config")
    parser.add_argument("--extract-glossary", action="store_true",
                        help="Extract bilingual Arabic-English glossary entries")
    parser.add_argument("--glossary-output", default=None,
                        help="Output path for glossary (.csv or .json). "
                             "Default: <input-stem>_glossary.csv next to --output")
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
        auto_tune=args.auto_tune,
        extract_glossary=args.extract_glossary,
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
    if args.auto_tune:
        print(f"  Auto-tune: PSM={proc.best_config.get('psm')}, "
              f"DPI={proc.best_config.get('dpi')}, "
              f"score={proc.best_config.get('auto_tune_score', 0.0):.3f}")
    print()

    for r in results:
        pn = r["page_num"]
        text_preview = r["text"][:100].replace("\n", " ") if r["text"] else "(empty)"
        conf = r.get("confidence", 0)
        norm = "✓" if r.get("normalized") else "✗"
        used = r.get("ocr_engine_used") or r.get("ocr_engine", "?")
        err = r.get("error", "")
        glossary_count = len(r.get("glossary_entries", []))
        extra = f" glossary={glossary_count}" if args.extract_glossary else ""
        print(f"  Page {pn}: engine={used} conf={conf:.0%} norm={norm}{extra} | {text_preview}...")
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

    # Glossary export
    if args.extract_glossary and proc.combined_glossary:
        if args.glossary_output:
            glossary_path = args.glossary_output
        else:
            # Default: next to results file (or input stem)
            base = Path(args.output).parent if args.output else input_path.parent
            stem = input_path.stem
            glossary_path = base / f"{stem}_glossary.csv"
        gp = proc.export_glossary(glossary_path)
        print(f"  Glossary exported to: {gp} ({len(proc.combined_glossary)} entries)")



if __name__ == "__main__":
    main()
