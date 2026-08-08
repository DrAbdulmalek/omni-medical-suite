"""
PaddleOCR Engine
=================

Wraps ``paddleocr.PaddleOCR`` with Arabic language support, table
recognition mode for medical tables, and layout analysis integration.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Any

import cv2
import numpy as np

from src.engines.base_engine import BBox, ImageInput, OCREngine, OCRResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PaddleOCREngine
# ---------------------------------------------------------------------------

class PaddleOCREngine(OCREngine):
    """PaddleOCR engine with Arabic medical document support.

    Features:

    * Arabic language recognition (``lang="ar"``).
    * Table recognition mode using PP-Structure for medical tables
      (lab results, drug dosage grids).
    * Layout analysis to identify text regions, tables, figures, and
      headers in complex medical reports.
    * Verbose output suppressed (``show_log=False``).

    Parameters
    ----------
    lang : str
        Language code (default ``"ar"``).
    use_angle_cls : bool
        Enable text direction classification (default *True*).
    use_gpu : bool | None
        Use GPU acceleration.  If *None*, auto-detect.
    use_table : bool
        Enable table recognition mode (PP-Structure).
    use_layout : bool
        Enable layout analysis.
    det_model_dir : str | None
        Path to a custom detection model.
    rec_model_dir : str | None
        Path to a custom recognition model.
    cls_model_dir : str | None
        Path to a custom direction classifier model.
    table_model_dir : str | None
        Path to a custom table recognition model.
    table_char_dict_path : str | None
        Character dictionary for table cell recognition.
    layout_model_dir : str | None
        Path to a custom layout analysis model.
    show_log : bool
        Show PaddleOCR internal logging (default *False*).
    det_db_thresh : float
        Binarisation threshold for text detection.
    det_db_box_thresh : float
        Bounding box confidence threshold for text detection.
    det_db_unclip_ratio : float
        Unclip ratio for expanding detected text boxes.
    rec_batch_num : int
        Batch size for the recognition model.
    max_text_length : int
        Maximum text length for recognition.
    use_space_char : bool
        Recognise spaces between words.
    drop_score : float
        Minimum recognition confidence to keep a result.
    """

    def __init__(
        self,
        lang: str = "ar",
        use_angle_cls: bool = True,
        use_gpu: bool | None = None,
        use_table: bool = False,
        use_layout: bool = False,
        det_model_dir: str | None = None,
        rec_model_dir: str | None = None,
        cls_model_dir: str | None = None,
        table_model_dir: str | None = None,
        table_char_dict_path: str | None = None,
        layout_model_dir: str | None = None,
        show_log: bool = False,
        det_db_thresh: float = 0.3,
        det_db_box_thresh: float = 0.5,
        det_db_unclip_ratio: float = 1.6,
        rec_batch_num: int = 6,
        max_text_length: int = 25,
        use_space_char: bool = True,
        drop_score: float = 0.5,
    ) -> None:
        super().__init__(engine_name="paddleocr")
        self._lang = lang
        self._use_angle_cls = use_angle_cls
        self._use_gpu = use_gpu
        self._use_table = use_table
        self._use_layout = use_layout
        self._show_log = show_log
        self._det_db_thresh = det_db_thresh
        self._det_db_box_thresh = det_db_box_thresh
        self._det_db_unclip_ratio = det_db_unclip_ratio
        self._rec_batch_num = rec_batch_num
        self._max_text_length = max_text_length
        self._use_space_char = use_space_char
        self._drop_score = drop_score

        # Model paths
        self._det_model_dir = det_model_dir
        self._rec_model_dir = rec_model_dir
        self._cls_model_dir = cls_model_dir
        self._table_model_dir = table_model_dir
        self._table_char_dict_path = table_char_dict_path
        self._layout_model_dir = layout_model_dir

        # Lazy-loaded instances
        self._ocr: Any = None
        self._table_ocr: Any = None
        self._layout_analyzer: Any = None

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _detect_gpu(self) -> bool:
        """Auto-detect GPU availability."""
        try:
            import paddle
            return paddle.device.is_compiled_with_cuda()
        except ImportError:
            return False

    def _init_ocr(self) -> Any:
        """Lazy-initialise the standard PaddleOCR instance."""
        if self._ocr is not None:
            return self._ocr

        from paddleocr import PaddleOCR

        gpu = self._use_gpu if self._use_gpu is not None else self._detect_gpu()

        kwargs: dict[str, Any] = {
            "use_angle_cls": self._use_angle_cls,
            "lang": self._lang,
            "use_gpu": gpu,
            "show_log": self._show_log,
            "det_db_thresh": self._det_db_thresh,
            "det_db_box_thresh": self._det_db_box_thresh,
            "det_db_unclip_ratio": self._det_db_unclip_ratio,
            "rec_batch_num": self._rec_batch_num,
            "max_text_length": self._max_text_length,
            "use_space_char": self._use_space_char,
            "drop_score": self._drop_score,
        }
        for key, path in [
            ("det_model_dir", self._det_model_dir),
            ("rec_model_dir", self._rec_model_dir),
            ("cls_model_dir", self._cls_model_dir),
        ]:
            if path is not None:
                kwargs[key] = path

        self._logger.info(
            "Initialising PaddleOCR (lang=%s, gpu=%s, table=%s, layout=%s).",
            self._lang, gpu, self._use_table, self._use_layout,
        )
        self._ocr = PaddleOCR(**kwargs)
        self._use_gpu = gpu
        return self._ocr

    def _init_table_ocr(self) -> Any:
        """Lazy-initialise PP-Structure for table recognition."""
        if self._table_ocr is not None:
            return self._table_ocr

        from paddleocr import PPStructure

        gpu = self._use_gpu if self._use_gpu is not None else self._detect_gpu()

        kwargs: dict[str, Any] = {
            "use_gpu": gpu,
            "show_log": self._show_log,
            "lang": self._lang,
            "table": True,
            "ocr": True,
        }
        if self._table_model_dir is not None:
            kwargs["table_model_dir"] = self._table_model_dir
        if self._table_char_dict_path is not None:
            kwargs["table_char_dict_path"] = self._table_char_dict_path

        self._logger.info("Initialising PP-Structure for table recognition.")
        self._table_ocr = PPStructure(**kwargs)
        return self._table_ocr

    def _init_layout_analyzer(self) -> Any:
        """Lazy-initialise PP-Structure for layout analysis."""
        if self._layout_analyzer is not None:
            return self._layout_analyzer

        from paddleocr import PPStructure

        gpu = self._use_gpu if self._use_gpu is not None else self._detect_gpu()

        kwargs: dict[str, Any] = {
            "use_gpu": gpu,
            "show_log": self._show_log,
            "lang": self._lang,
            "layout": True,
            "ocr": True,
        }
        if self._layout_model_dir is not None:
            kwargs["layout_model_dir"] = self._layout_model_dir

        self._logger.info("Initialising PP-Structure for layout analysis.")
        self._layout_analyzer = PPStructure(**kwargs)
        return self._layout_analyzer

    def _check_availability(self) -> None:
        """Verify PaddleOCR is importable and initialises."""
        from paddleocr import PaddleOCR  # noqa: F401
        self._init_ocr()
        self._logger.info("PaddleOCR ready (lang=%s).", self._lang)

    # ------------------------------------------------------------------
    # Core OCR
    # ------------------------------------------------------------------

    def ocr(self, image: ImageInput) -> OCRResult:
        """Run PaddleOCR on a single image.

        If ``use_table=True``, table regions are recognised with
        PP-Structure and their cells are concatenated into the text
        output.

        Parameters
        ----------
        image : ImageInput
            File path, numpy array, or PIL Image.

        Returns
        -------
        OCRResult
        """
        validated = self.validate_image(image) if not isinstance(image, np.ndarray) else image
        preprocessed = self.preprocess(validated)

        # Ensure BGR (PaddleOCR expects BGR numpy)
        bgr = self._ensure_bgr(preprocessed)

        if self._use_table:
            return self._ocr_with_tables(bgr)
        elif self._use_layout:
            return self._ocr_with_layout(bgr)
        else:
            return self._ocr_standard(bgr)

    def ocr_batch(self, images: Sequence[ImageInput]) -> list[OCRResult]:
        """Run PaddleOCR on a batch of images sequentially.

        Parameters
        ----------
        images : sequence of ImageInput

        Returns
        -------
        list[OCRResult]
        """
        results: list[OCRResult] = []
        for idx, img in enumerate(images):
            self._logger.debug(
                "PaddleOCR batch: image %d/%d.", idx + 1, len(images),
            )
            results.append(self.ocr(img))
        return results

    # ------------------------------------------------------------------
    # OCR modes
    # ------------------------------------------------------------------

    def _ocr_standard(self, image: np.ndarray) -> OCRResult:
        """Standard text detection + recognition."""
        ocr = self._init_ocr()

        t0 = time.perf_counter()
        raw_result = ocr.ocr(image, cls=self._use_angle_cls)
        inference_time = time.perf_counter() - t0

        return self._parse_standard_result(raw_result, inference_time)

    def _ocr_with_tables(self, image: np.ndarray) -> OCRResult:
        """Table recognition mode using PP-Structure."""
        table_ocr = self._init_table_ocr()

        t0 = time.perf_counter()
        raw_result = table_ocr(image)
        inference_time = time.perf_counter() - t0

        return self._parse_structure_result(raw_result, inference_time)

    def _ocr_with_layout(self, image: np.ndarray) -> OCRResult:
        """Layout analysis mode using PP-Structure."""
        layout_analyzer = self._init_layout_analyzer()

        t0 = time.perf_counter()
        raw_result = layout_analyzer(image)
        inference_time = time.perf_counter() - t0

        return self._parse_structure_result(raw_result, inference_time)

    # ------------------------------------------------------------------
    # Result parsing
    # ------------------------------------------------------------------

    def _parse_standard_result(
        self,
        raw_result: Any,
        inference_time: float,
    ) -> OCRResult:
        """Parse standard PaddleOCR output into an :class:`OCRResult`.

        PaddleOCR returns a nested list structure:
        ``[[[bbox_pts, (text, confidence)], ...], ...]``
        where the outer list is pages.
        """
        lines_text: list[str] = []
        line_confs: list[float] = []
        line_bboxes: list[BBox] = []
        word_level: list[tuple[str, float, BBox]] = []

        if raw_result is None:
            return OCRResult(
                text="", confidence=0.0, bbox=None,
                engine_name=self.engine_name,
                processing_time=inference_time,
            )

        # Handle single-page result (list of detections)
        pages = raw_result if isinstance(raw_result[0], list) else [raw_result]

        for page in pages:
            if page is None:
                continue
            for line in page:
                bbox_pts, (text, conf) = line[0], line[1]
                text = text.strip()
                if not text:
                    continue
                conf = float(conf)
                if conf < self._drop_score:
                    continue

                pts = np.array(bbox_pts, dtype=np.float64)
                bbox = BBox(
                    x_min=float(pts[:, 0].min()),
                    y_min=float(pts[:, 1].min()),
                    x_max=float(pts[:, 0].max()),
                    y_max=float(pts[:, 1].max()),
                )

                lines_text.append(text)
                line_confs.append(conf)
                line_bboxes.append(bbox)
                word_level.append((text, conf, bbox))

        if not lines_text:
            return OCRResult(
                text="", confidence=0.0, bbox=None,
                engine_name=self.engine_name,
                processing_time=inference_time,
            )

        full_text = "\n".join(lines_text)
        avg_conf = sum(line_confs) / len(line_confs)
        overall_bbox = BBox(
            x_min=min(b.x_min for b in line_bboxes),
            y_min=min(b.y_min for b in line_bboxes),
            x_max=max(b.x_max for b in line_bboxes),
            y_max=max(b.y_max for b in line_bboxes),
        )

        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            bbox=overall_bbox,
            engine_name=self.engine_name,
            processing_time=inference_time,
            word_level=word_level,
            metadata={
                "lang": self._lang,
                "gpu": self._use_gpu,
                "mode": "standard",
                "line_count": len(lines_text),
            },
        )

    def _parse_structure_result(
        self,
        raw_result: Any,
        inference_time: float,
    ) -> OCRResult:
        """Parse PP-Structure (table/layout) output.

        PP-Structure returns a list of dicts with keys like
        ``type``, ``bbox``, ``res``, ``text``.
        """
        lines_text: list[str] = []
        line_confs: list[float] = []
        line_bboxes: list[BBox] = []
        word_level: list[tuple[str, float, BBox]] = []

        if raw_result is None:
            return OCRResult(
                text="", confidence=0.0, bbox=None,
                engine_name=self.engine_name,
                processing_time=inference_time,
            )

        for region in raw_result:
            region_type = region.get("type", "text")
            bbox_pts = region.get("bbox", None)

            # Extract text from the region
            text = ""
            confidence = 0.0

            if region_type == "table":
                # Table result has an HTML representation
                html = region.get("res", {}).get("html", "")
                if html:
                    text = self._html_table_to_text(html)
                    confidence = 0.85  # structural recognition confidence
            else:
                # Text region: res is a list of (text, confidence)
                res = region.get("res", [])
                if isinstance(res, list):
                    text_parts = []
                    confs = []
                    for item in res:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            t, c = item[0], float(item[1])
                            if t.strip():
                                text_parts.append(t.strip())
                                confs.append(c)
                    text = " ".join(text_parts)
                    confidence = sum(confs) / len(confs) if confs else 0.0
                elif isinstance(res, str):
                    text = res.strip()
                    confidence = 0.8

            text = text.strip()
            if not text:
                continue

            if bbox_pts is not None:
                pts = np.array(bbox_pts, dtype=np.float64)
                if pts.ndim == 1 and len(pts) == 4:
                    # (x, y, w, h) format
                    bbox = BBox(
                        x_min=float(pts[0]),
                        y_min=float(pts[1]),
                        x_max=float(pts[0] + pts[2]),
                        y_max=float(pts[1] + pts[3]),
                    )
                elif pts.ndim == 2 and pts.shape[0] >= 4:
                    bbox = BBox(
                        x_min=float(pts[:, 0].min()),
                        y_min=float(pts[:, 1].min()),
                        x_max=float(pts[:, 0].max()),
                        y_max=float(pts[:, 1].max()),
                    )
                else:
                    bbox = None
            else:
                bbox = None

            lines_text.append(text)
            line_confs.append(confidence)
            if bbox is not None:
                line_bboxes.append(bbox)
                word_level.append((text, confidence, bbox))

        if not lines_text:
            return OCRResult(
                text="", confidence=0.0, bbox=None,
                engine_name=self.engine_name,
                processing_time=inference_time,
            )

        full_text = "\n".join(lines_text)
        avg_conf = sum(line_confs) / len(line_confs)

        overall_bbox = None
        if line_bboxes:
            overall_bbox = BBox(
                x_min=min(b.x_min for b in line_bboxes),
                y_min=min(b.y_min for b in line_bboxes),
                x_max=max(b.x_max for b in line_bboxes),
                y_max=max(b.y_max for b in line_bboxes),
            )

        mode = "table" if self._use_table else "layout" if self._use_layout else "standard"

        return OCRResult(
            text=full_text,
            confidence=avg_conf,
            bbox=overall_bbox,
            engine_name=self.engine_name,
            processing_time=inference_time,
            word_level=word_level if word_level else None,
            metadata={
                "lang": self._lang,
                "gpu": self._use_gpu,
                "mode": mode,
                "region_count": len(raw_result),
            },
        )

    # ------------------------------------------------------------------
    # Table HTML to plain text
    # ------------------------------------------------------------------

    @staticmethod
    def _html_table_to_text(html: str) -> str:
        """Convert a simple HTML table to tab-separated plain text.

        Parameters
        ----------
        html : str
            HTML table string from PP-Structure.

        Returns
        -------
        str
            Plain text with rows separated by newlines and cells by
            tabs.
        """
        try:
            from html.parser import HTMLParser

            class _TableParser(HTMLParser):
                def __init__(self) -> None:
                    super().__init__()
                    self.in_cell = False
                    self.in_row = False
                    self.cells: list[str] = []
                    self.rows: list[str] = []

                def handle_starttag(self, tag: str, attrs: Any) -> None:
                    if tag == "td" or tag == "th":
                        self.in_cell = True
                        self.cells.append("")
                    elif tag == "tr":
                        self.in_row = True
                        self.cells = []

                def handle_endtag(self, tag: str) -> None:
                    if tag == "td" or tag == "th":
                        self.in_cell = False
                    elif tag == "tr":
                        self.in_row = False
                        if self.cells:
                            self.rows.append("\t".join(self.cells))

                def handle_data(self, data: str) -> None:
                    if self.in_cell and self.cells:
                        self.cells[-1] += data.strip()

            parser = _TableParser()
            parser.feed(html)
            return "\n".join(parser.rows)

        except Exception:
            # Fallback: strip tags and return raw text
            import re
            return re.sub(r"<[^>]+>", " ", html).strip()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_bgr(image: np.ndarray) -> np.ndarray:
        """Ensure image is BGR uint8."""
        if image.ndim == 2:
            return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        if image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)
        return image

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Release PaddleOCR resources and GPU memory."""
        try:
            import paddle
            if paddle.device.is_compiled_with_cuda():
                paddle.device.cuda.empty_cache()
        except ImportError:
            pass

        self._ocr = None
        self._table_ocr = None
        self._layout_analyzer = None
        super().close()
