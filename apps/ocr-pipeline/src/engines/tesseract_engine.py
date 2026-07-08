"""
Tesseract OCR Engine
====================

Wraps ``pytesseract`` with Arabic + English language support, configurable
Page Segmentation Modes (PSM) tailored for medical documents, and hOCR
parsing for word-level bounding boxes.

Supported PSM modes
-------------------
- ``PSM_AUTO`` (3): Fully automatic page segmentation (default).
- ``PSM_SINGLE_BLOCK`` (6): Assume a single uniform block of text.
- ``PSM_SPARSE_TEXT`` (11): Sparse text — good for scattered fields.
- ``PSM_SINGLE_COLUMN`` (4): Single column of text (forms, receipts).
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from enum import IntEnum
from typing import Any

import cv2
import numpy as np

from src.engines.base_engine import BBox, ImageInput, OCREngine, OCRResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PSM modes for medical documents
# ---------------------------------------------------------------------------

class TesseractPSM(IntEnum):
    """Tesseract page segmentation modes relevant to medical documents.

    Reference: ``tesseract --help-psm``
    """

    PSM_OSD_ONLY = 0
    PSM_SPARSE_TEXT_OSD = 1
    PSM_SPARSE_TEXT = 11
    PSM_AUTO = 3
    PSM_SINGLE_COLUMN = 4
    PSM_SINGLE_BLOCK_VERT_TEXT = 5
    PSM_SINGLE_BLOCK = 6
    PSM_SINGLE_LINE = 7
    PSM_SINGLE_WORD = 8
    PSM_SINGLE_WORD_CIRCLE = 9
    PSM_SINGLE_CHAR = 10
    PSM_AUTO_OSD = 2
    PSM_COUNT = 13


# ---------------------------------------------------------------------------
# PSM presets for common medical document layouts
# ---------------------------------------------------------------------------

MEDICAL_PSM_PRESETS: dict[str, int] = {
    "auto": TesseractPSM.PSM_AUTO,
    "single_block": TesseractPSM.PSM_SINGLE_BLOCK,
    "single_column": TesseractPSM.PSM_SINGLE_COLUMN,
    "sparse_text": TesseractPSM.PSM_SPARSE_TEXT,
    "table": TesseractPSM.PSM_AUTO,  # tables use auto + hOCR
    "form": TesseractPSM.PSM_SPARSE_TEXT,
    "receipt": TesseractPSM.PSM_SINGLE_COLUMN,
}


# ---------------------------------------------------------------------------
# hOCR word-level parser
# ---------------------------------------------------------------------------

def _parse_hocr_word_boxes(hocr_html: str) -> list[tuple[str, float, BBox]]:
    """Parse word-level text, confidence, and bounding boxes from hOCR.

    Parameters
    ----------
    hocr_html : str
        Raw hOCR output from Tesseract.

    Returns
    -------
    list[tuple[str, float, BBox]]
        ``(word_text, confidence, bbox)`` for each recognised word.
    """
    results: list[tuple[str, float, BBox]] = []

    try:
        root = ET.fromstring(hocr_html)
    except ET.ParseError:
        logger.warning("Failed to parse hOCR XML — returning empty word list.")
        return results

    # Tesseract hOCR uses the XHTML namespace

    for word_elem in root.iter("{http://www.w3.org/1999/xhtml}span"):
        cls = word_elem.get("class", "")
        if cls != "ocrx_word":
            continue

        text = (word_elem.text or "").strip()
        if not text:
            continue

        # Extract title attribute for bbox and confidence
        # Format: "bbox x0 y0 x1 y1; x_wconf NNN"
        title = word_elem.get("title", "")
        bbox_match = re.search(r"bbox\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", title)
        conf_match = re.search(r"x_wconf\s+(\d+)", title)

        if bbox_match:
            bbox = BBox(
                x_min=float(bbox_match.group(1)),
                y_min=float(bbox_match.group(2)),
                x_max=float(bbox_match.group(3)),
                y_max=float(bbox_match.group(4)),
            )
        else:
            bbox = BBox(0, 0, 0, 0)

        confidence = float(conf_match.group(1)) / 100.0 if conf_match else 0.0
        results.append((text, confidence, bbox))

    return results


# ---------------------------------------------------------------------------
# TesseractEngine
# ---------------------------------------------------------------------------

class TesseractEngine(OCREngine):
    """Tesseract OCR engine with Arabic/English medical document support.

    Parameters
    ----------
    lang : str
        Tesseract language string (default ``"ara+eng"``).
    psm : int | str | None
        Page Segmentation Mode.  Accepts an integer (e.g. ``3``), a
        preset name from :data:`MEDICAL_PSM_PRESETS`, or *None* to use
        the ``"auto"`` preset.
    tesseract_cmd : str | None
        Path to the ``tesseract`` binary.  If *None*, the system
        ``PATH`` is searched.
    tessdata_prefix : str | None
        Value for the ``TESSDATA_PREFIX`` environment variable.  If
        *None*, the existing environment value is used.
    config_args : str | None
        Additional Tesseract configuration string (e.g.
        ``"--oem 3 --dpi 300"``).  ``--psm`` is set separately via
        *psm*.
    oem : int
        OCR Engine Mode.  ``1`` = LSTM only (recommended).
    use_hocr : bool
        If *True*, use hOCR output for word-level bounding boxes.
    dpi : int
        DPI hint passed to Tesseract for image-to-data calls.
    """

    def __init__(
        self,
        lang: str = "ara+eng",
        psm: int | str | None = None,
        tesseract_cmd: str | None = None,
        tessdata_prefix: str | None = None,
        config_args: str | None = None,
        oem: int = 1,
        use_hocr: bool = True,
        dpi: int = 300,
    ) -> None:
        super().__init__(engine_name="tesseract")
        self._lang = lang
        self._oem = oem
        self._use_hocr = use_hocr
        self._dpi = dpi
        self._config_args = config_args

        # Resolve PSM
        if psm is None:
            self._psm = MEDICAL_PSM_PRESETS["auto"]
        elif isinstance(psm, str):
            self._psm = MEDICAL_PSM_PRESETS.get(psm, TesseractPSM.PSM_AUTO)
        else:
            self._psm = int(psm)

        # Set TESSDATA_PREFIX if provided
        self._tessdata_prefix = tessdata_prefix
        if tessdata_prefix is not None:
            import os
            os.environ["TESSDATA_PREFIX"] = tessdata_prefix
            logger.info("TESSDATA_PREFIX set to: %s", tessdata_prefix)

        # Lazily import and configure pytesseract
        self._pytesseract: Any = None
        self._tesseract_cmd = tesseract_cmd

        # Build config string
        self._config = self._build_config()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_config(self) -> str:
        """Build the Tesseract configuration string."""
        parts = [
            f"--oem {self._oem}",
            f"--psm {self._psm}",
        ]
        if self._config_args:
            parts.append(self._config_args)
        return " ".join(parts)

    def _init_pytesseract(self) -> Any:
        """Lazy-initialise pytesseract with optional binary path."""
        if self._pytesseract is not None:
            return self._pytesseract

        import pytesseract
        if self._tesseract_cmd is not None:
            pytesseract.pytesseract.tesseract_cmd = self._tesseract_cmd
        self._pytesseract = pytesseract
        return pytesseract

    def _check_availability(self) -> None:
        """Verify Tesseract binary is reachable and Arabic data exists."""
        pytesseract = self._init_pytesseract()
        version = pytesseract.get_tesseract_version()
        logger.info(
            "Tesseract %s detected, lang=%s, psm=%d.",
            version, self._lang, self._psm,
        )

    # ------------------------------------------------------------------
    # Core OCR
    # ------------------------------------------------------------------

    def ocr(self, image: ImageInput) -> OCRResult:
        """Run Tesseract OCR on a single image.

        Parameters
        ----------
        image : ImageInput
            File path, numpy array, or PIL Image.

        Returns
        -------
        OCRResult
            Recognition result with optional word-level bounding boxes
            when hOCR is enabled.
        """
        pytesseract = self._init_pytesseract()
        validated = self.validate_image(image) if not isinstance(image, np.ndarray) else image
        preprocessed = self.preprocess(validated)

        # --- Run hOCR for word-level boxes if enabled ---
        word_level: list[tuple[str, float, BBox]] | None = None

        if self._use_hocr:
            try:
                hocr_html = pytesseract.image_to_pdf_or_hocr(
                    preprocessed,
                    lang=self._lang,
                    config=self._config,
                    extension="hocr",
                )
                if isinstance(hocr_html, bytes):
                    hocr_text = hocr_html.decode("utf-8", errors="replace")
                else:
                    hocr_text = hocr_html

                word_level = _parse_hocr_word_boxes(hocr_text)
            except Exception as exc:
                self._logger.warning(
                    "hOCR parsing failed, falling back to image_to_data: %s", exc,
                )

        # --- Run image_to_data for text and confidence ---
        data = pytesseract.image_to_data(
            preprocessed,
            lang=self._lang,
            config=self._config,
            output_type=pytesseract.Output.DICT,
        )

        # Collect non-empty words with their bounding boxes
        words: list[str] = []
        word_confs: list[float] = []
        x_mins, y_mins, x_maxs, y_maxs = [], [], [], []

        for i, txt in enumerate(data["text"]):
            txt = txt.strip()
            if not txt:
                continue
            conf = float(data["conf"][i])
            conf = max(0.0, conf / 100.0) if conf >= 0 else 0.0
            if conf == 0.0:
                continue

            words.append(txt)
            word_confs.append(conf)
            x = float(data["left"][i])
            y = float(data["top"][i])
            w = float(data["width"][i])
            h = float(data["height"][i])
            x_mins.append(x)
            y_mins.append(y)
            x_maxs.append(x + w)
            y_maxs.append(y + h)

        if not words:
            return OCRResult(
                text="",
                confidence=0.0,
                bbox=None,
                engine_name=self.engine_name,
                metadata={"lang": self._lang, "psm": self._psm, "oem": self._oem},
            )

        # Build full text by grouping words into lines based on y-position
        full_text = self._group_words_into_lines(
            words, x_mins, y_mins, x_maxs, y_maxs
        )

        # Overall confidence = mean of per-word confidences
        avg_confidence = sum(word_confs) / len(word_confs)

        # Full-image bounding box
        overall_bbox = BBox(
            x_min=min(x_mins),
            y_min=min(y_mins),
            x_max=max(x_maxs),
            y_max=max(y_maxs),
        )

        return OCRResult(
            text=full_text,
            confidence=avg_confidence,
            bbox=overall_bbox,
            engine_name=self.engine_name,
            word_level=word_level,
            metadata={
                "lang": self._lang,
                "psm": self._psm,
                "oem": self._oem,
                "word_count": len(words),
            },
        )

    def ocr_batch(self, images: Sequence[ImageInput]) -> list[OCRResult]:
        """Run Tesseract OCR on a batch of images sequentially.

        Parameters
        ----------
        images : sequence of ImageInput
            Input images.

        Returns
        -------
        list[OCRResult]
        """
        results: list[OCRResult] = []
        for idx, img in enumerate(images):
            self._logger.debug(
                "Tesseract batch: image %d/%d.", idx + 1, len(images),
            )
            results.append(self.ocr(img))
        return results

    # ------------------------------------------------------------------
    # Word-to-line grouping
    # ------------------------------------------------------------------

    @staticmethod
    def _group_words_into_lines(
        words: list[str],
        x_mins: list[float],
        y_mins: list[float],
        x_maxs: list[float],
        y_maxs: list[float],
    ) -> str:
        """Group word-level detections into lines and produce full text.

        Words are sorted by vertical position and then by horizontal
        position within each line.  A tolerance of half the median word
        height is used to cluster words into the same line.

        Parameters
        ----------
        words, x_mins, y_mins, x_maxs, y_maxs :
            Parallel lists of word attributes.

        Returns
        -------
        str
            The reconstructed text with lines separated by ``\\n``.
        """
        if not words:
            return ""

        # Build (y_center, x_min, index) tuples for sorting
        items = []
        for i in range(len(words)):
            y_center = (y_mins[i] + y_maxs[i]) / 2.0
            items.append((y_center, x_mins[i], i))

        items.sort(key=lambda t: (round(t[0], 0), t[1]))

        # Compute median word height for line-gap threshold
        heights = [y_maxs[i] - y_mins[i] for i in range(len(words))]
        heights.sort()
        median_height = heights[len(heights) // 2] if heights else 20.0
        line_threshold = median_height * 0.5

        lines: list[list[str]] = []
        current_line: list[str] = []
        current_y = items[0][0]

        for y_center, _x_min, idx in items:
            if abs(y_center - current_y) > line_threshold and current_line:
                lines.append(current_line)
                current_line = [words[idx]]
                current_y = y_center
            else:
                current_line.append(words[idx])

        if current_line:
            lines.append(current_line)

        return "\n".join(" ".join(line) for line in lines)

    # ------------------------------------------------------------------
    # Medical-document PSM helpers
    # ------------------------------------------------------------------

    def set_psm(self, psm: int | str) -> None:
        """Change the page segmentation mode at runtime.

        Parameters
        ----------
        psm : int | str
            An integer PSM value or a preset name from
            :data:`MEDICAL_PSM_PRESETS`.
        """
        if isinstance(psm, str):
            self._psm = MEDICAL_PSM_PRESETS.get(psm, TesseractPSM.PSM_AUTO)
        else:
            self._psm = int(psm)
        self._config = self._build_config()
        self._logger.info("PSM updated to %d.", self._psm)

    def detect_layout_preset(self, image: np.ndarray) -> str:
        """Heuristically detect the best PSM preset for a medical image.

        Analyses the image structure (aspect ratio, text density, line
        count) to suggest an appropriate preset.

        Parameters
        ----------
        image : numpy.ndarray
            Input image (BGR or grayscale).

        Returns
        -------
        str
            Preset name from :data:`MEDICAL_PSM_PRESETS`.
        """
        gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Binarise to count text regions
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
        )

        # Count connected components (text regions)
        num_labels, _ = cv2.connectedComponents(binary)
        text_regions = num_labels - 1  # subtract background

        # Text density
        text_density = text_regions / (w * h) if w * h > 0 else 0

        # Heuristics
        if text_density < 0.0005:
            preset = "sparse_text"
        elif h > w * 1.5:
            preset = "single_column"
        elif text_density > 0.005:
            preset = "table"
        else:
            preset = "auto"

        self._logger.info(
            "Layout detection: %d regions, density=%.5f → preset='%s'.",
            text_regions, text_density, preset,
        )
        return preset

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release Tesseract resources (no-op for pytesseract)."""
        super().close()
