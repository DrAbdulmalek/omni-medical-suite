"""
PaddleOCR Engine - محرك PaddleOCR المحسّن للنصوص العربية
============================================================

This module wraps PaddleOCR with Arabic-optimized settings, inspired by
PaddleOCR_Handwritten_Arabic. It includes tuned detection parameters
and support for custom handwriting models.

هذه الوحدة تغلف PaddleOCR بإعدادات محسنة للنصوص العربية،
مستوحاة من PaddleOCR_Handwritten_Arabic. تشمل معلمات كشف مضبوطة
ودعم نماذج الخط العربي المخصصة.
"""

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Arabic + English messages
_MSG_INIT = "جارٍ تهيئة PaddleOCR - اللغة: {lang} | Initializing PaddleOCR - lang: {lang}"
_MSG_INIT_OK = "تم تهيئة PaddleOCR بنجاح | PaddleOCR initialized successfully"
_MSG_INIT_FAIL = "فشل تهيئة PaddleOCR - يرجى تثبيت paddleocr | Failed to init PaddleOCR - install paddleocr"
_MSG_CUSTOM_MODEL = "تم العثور على نموذج مخصص في {path} | Custom model found at {path}"
_MSG_NO_CUSTOM = "لا يوجد نموذج مخصص، استخدام النموذج الافتراضي | No custom model, using default"
_MSG_EXTRACTING = "جارٍ استخراج النص باستخدام PaddleOCR | Extracting text with PaddleOCR"
_MSG_EXTRACTED = "تم استخراج {n} سطر | Extracted {n} lines"
_MSG_EXTRACT_FAIL = "فشل استخراج النص: {err} | Text extraction failed: {err}"
_MSG_NOT_AVAIL = "PaddleOCR غير متاح | PaddleOCR not available"

# Default Arabic-optimized parameters
# المعلمات الافتراضية المحسنة للعربية
DEFAULT_PARAMS = {
    "det_db_thresh": 0.3,
    "det_db_box_thresh": 0.5,
    "det_db_unclip_ratio": 1.8,
    "max_text_length": 800,
    "use_mp": True,
    "use_angle_cls": False,
    "lang": "ar",
    "show_log": False,
    "use_gpu": True,
    "enable_mkldnn": True,
}

# Custom model path relative to project root
CUSTOM_MODEL_DIR = "models/paddle_handwriting"


class PaddleOCREngine:
    """
    PaddleOCR wrapper with Arabic-optimized detection parameters.

    محرك PaddleOCR مغلف بإعدادات كشف محسنة للنصوص العربية.

    Key optimizations for Arabic/medical documents:
        - Lower detection threshold (0.3) to catch faint text
        - Higher unclip ratio (1.8) for better bounding boxes
        - Extended max text length (800) for long medical terms
        - Multi-process support enabled by default
        - Optional custom handwriting model loading

    التحسينات الرئيسية للمستندات العربية/الطبية:
        - عتبة كشف منخفضة (0.3) لالتقاط النصوص الخافتة
        - نسبة فك قص أعلى (1.8) لصناديق حدود أفضل
        - طول نص أقصى ممتد (800) للمصطلحات الطبية الطويلة
        - دعم المعالجة المتعددة مفعّل افتراضياً
        - تحميل نموذج خط مخصص اختياري
    """

    def __init__(
        self,
        lang: str = "ar",
        use_gpu: bool = True,
        det_db_thresh: float = 0.3,
        det_db_box_thresh: float = 0.5,
        det_db_unclip_ratio: float = 1.8,
        max_text_length: int = 800,
        use_mp: bool = True,
    ) -> None:
        """
        Initialize PaddleOCR with Arabic-optimized settings.

        تهيئة PaddleOCR بإعدادات محسنة للعربية.

        Args:
            lang: OCR language code. Defaults to 'ar'.
            use_gpu: Enable GPU acceleration. Defaults to True.
            det_db_thresh: DB detection threshold. Lower = more detections.
            det_db_box_thresh: DB box threshold. Controls box confidence.
            det_db_unclip_ratio: Unclip ratio for bounding box expansion.
            max_text_length: Maximum text length per detection.
            use_mp: Enable multi-process for speed.
        """
        self.lang = lang
        self.ocr_engine = None
        self._available = False
        self._params = {
            "det_db_thresh": det_db_thresh,
            "det_db_box_thresh": det_db_box_thresh,
            "det_db_unclip_ratio": det_db_unclip_ratio,
            "max_text_length": max_text_length,
            "use_mp": use_mp,
            "use_angle_cls": False,
            "lang": lang,
            "show_log": False,
            "use_gpu": use_gpu,
            "enable_mkldnn": True,
        }

        logger.info(_MSG_INIT.format(lang=lang))

        try:
            # Check for custom model directory
            custom_dir = self._find_custom_model_dir()
            custom_config = {}

            if custom_dir is not None:
                det_model = os.path.join(custom_dir, "det")
                rec_model = os.path.join(custom_dir, "rec")
                cls_model = os.path.join(custom_dir, "cls")

                if os.path.isdir(det_model):
                    custom_config["det_model_dir"] = det_model
                    logger.info(_MSG_CUSTOM_MODEL.format(path=det_model))

                if os.path.isdir(rec_model):
                    custom_config["rec_model_dir"] = rec_model
                    logger.info(_MSG_CUSTOM_MODEL.format(path=rec_model))

                if os.path.isdir(cls_model):
                    custom_config["cls_model_dir"] = cls_model

            # Merge custom config with default params
            init_params = {**self._params, **custom_config}

            from paddleocr import PaddleOCR  # type: ignore

            self.ocr_engine = PaddleOCR(**init_params)
            self._available = True
            logger.info(_MSG_INIT_OK)

            if not custom_config:
                logger.debug(_MSG_NO_CUSTOM)

        except ImportError:
            logger.warning(_MSG_INIT_FAIL)
            self._available = False
        except Exception as e:
            logger.error(
                f"خطأ غير متوقع في PaddleOCR: {e} | "
                f"Unexpected PaddleOCR error: {e}",
                exc_info=True,
            )
            self._available = False

    @property
    def is_available(self) -> bool:
        """Check if PaddleOCR engine is available."""
        return self._available

    def extract_text(self, image: np.ndarray) -> dict[str, Any]:
        """
        Extract text from an image using PaddleOCR.

        استخراج النص من صورة باستخدام PaddleOCR.

        Handles both BGR and RGB input images. The image is converted
        to the format expected by PaddleOCR before processing.

        Args:
            image: Input image as numpy array (BGR or RGB).

        Returns:
            Dictionary containing:
                - text (str): Full extracted text
                - lines (List[Dict]): Individual line results with:
                    - text (str): Detected text
                    - bbox (List[List[int]]): Bounding box as
                      [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                    - confidence (float): Average confidence (0-1)
                - num_lines (int): Total number of detected lines
                - engine (str): 'paddleocr'
        """
        if not self._available:
            logger.warning(_MSG_NOT_AVAIL)
            return self._empty_result()

        logger.info(_MSG_EXTRACTING)

        try:
            # Convert image to RGB (PaddleOCR works best with RGB)
            rgb_image = self._ensure_rgb(image)

            # Run OCR - PaddleOCR returns list of results per image
            raw_results = self.ocr_engine.ocr(rgb_image, cls=False)

            if not raw_results or raw_results[0] is None:
                logger.info("لم يتم العثور على نص | No text found")
                return self._empty_result()

            lines: list[dict] = []
            for item in raw_results[0]:
                # PaddleOCR format: [bbox, (text, confidence)]
                bbox_points = item[0]
                text_info = item[1]

                text = text_info[0].strip() if text_info[0] else ""
                confidence = float(text_info[1]) if len(text_info) > 1 else 0.0

                # Normalize bounding box to integer coordinates
                bbox_list = [
                    [round(p[0]), round(p[1])] for p in bbox_points
                ]

                lines.append({
                    "text": text,
                    "bbox": bbox_list,
                    "confidence": round(confidence, 4),
                })

            # Sort by vertical position (top to bottom), then horizontal
            lines.sort(key=lambda l: (l["bbox"][0][1], l["bbox"][0][0]))

            # Build full text
            full_text = "\n".join(
                line["text"] for line in lines if line["text"]
            )

            result = {
                "text": full_text,
                "lines": lines,
                "num_lines": len(lines),
                "engine": "paddleocr",
            }

            logger.info(_MSG_EXTRACTED.format(n=len(lines)))
            return result

        except Exception as e:
            logger.error(
                _MSG_EXTRACT_FAIL.format(err=e),
                exc_info=True,
            )
            return self._empty_result()

    def _find_custom_model_dir(self) -> str | None:
        """
        Search for a custom PaddleOCR model directory.

        البحث عن دليل نموذج PaddleOCR المخصص.

        Checks multiple possible locations:
            1. models/paddle_handwriting/ relative to CWD
            2. models/paddle_handwriting/ relative to this file
            3. An absolute path if it exists

        Returns:
            Path to the custom model directory, or None if not found.
        """
        search_paths = [
            Path(CUSTOM_MODEL_DIR).resolve(),
            Path(__file__).parent.parent.parent / CUSTOM_MODEL_DIR,
            Path.cwd() / CUSTOM_MODEL_DIR,
        ]

        for path in search_paths:
            if path.is_dir():
                logger.debug(
                    f"العثور على دليل النموذج: {path} | "
                    f"Found model directory: {path}"
                )
                return str(path)

        return None

    @staticmethod
    def _ensure_rgb(image: np.ndarray) -> np.ndarray:
        """
        Convert image to RGB format if needed.

        تحويل الصورة إلى صيغة RGB عند الحاجة.

        Args:
            image: Input numpy array.

        Returns:
            RGB image as numpy array.
        """
        if len(image.shape) == 2:
            # Grayscale to RGB
            return np.stack([image] * 3, axis=-1)

        if image.shape[2] == 4:
            # RGBA to RGB
            return image[:, :, :3]

        if image.shape[2] == 3:
            # Check if BGR (OpenCV default)
            b_avg = float(np.mean(image[:, :, 0]))
            r_avg = float(np.mean(image[:, :, 2]))

            if b_avg > r_avg * 1.15:
                return image[:, :, ::-1]

        return image

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        """Return an empty extraction result."""
        return {
            "text": "",
            "lines": [],
            "num_lines": 0,
            "engine": "paddleocr",
        }
