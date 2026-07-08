"""
EasyOCR Engine - محرك التعرف الضوئي على النصوص باستخدام EasyOCR
====================================================================

This module wraps EasyOCR for optical character recognition,
with optimized settings for Arabic and English medical documents.

هذه الوحدة تغلف EasyOCR للتعرف الضوئي على النصوص
مع إعدادات محسنة للمستندات الطبية العربية والإنجليزية.
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Arabic + English messages
_MSG_INIT = "جارٍ تهيئة EasyOCR باللغات: {langs} | Initializing EasyOCR with languages: {langs}"
_MSG_INIT_OK = "تم تهيئة EasyOCR بنجاح | EasyOCR initialized successfully"
_MSG_INIT_FAIL = "فشل تهيئة EasyOCR - يرجى تثبيت easyocr | Failed to init EasyOCR - install easyocr"
_MSG_EXTRACTING = "جارٍ استخراج النص باستخدام EasyOCR | Extracting text with EasyOCR"
_MSG_EXTRACTED = "تم استخراج {n} سطر | Extracted {n} lines"
_MSG_EXTRACT_FAIL = "فشل استخراج النص | Text extraction failed"
_MSG_NOT_AVAIL = "EasyOCR غير متاح | EasyOCR not available"
_MSG_CONVERSION = "تحويل BGR إلى RGB | Converting BGR to RGB"


class EasyOCREngine:
    """
    EasyOCR wrapper for Arabic/English medical document OCR.

    محرك EasyOCR للتعرف الضوئي على المستندات الطبية العربية/الإنجليزية.

    Features:
        - Supports Arabic and English by default
        - Automatic BGR to RGB conversion
        - Graceful degradation when EasyOCR is not installed
        - Detailed line-level results with bounding boxes and confidence

    الميزات:
        - يدعم العربية والإنجليزية افتراضياً
        - تحويل تلقائي من BGR إلى RGB
        - تراجع سلس عند عدم توفر EasyOCR
        - نتائج مفصلة على مستوى السطر مع صناديق الحدود والثقة
    """

    def __init__(
        self,
        languages: list[str] | None = None,
        gpu: bool = True,
    ) -> None:
        """
        Initialize EasyOCR reader with specified languages.

        تهيئة قارئ EasyOCR باللغات المحددة.

        Args:
            languages: List of language codes for OCR. Defaults to ['ar', 'en'].
            gpu: Whether to use GPU acceleration. Defaults to True.
        """
        if languages is None:
            languages = ["ar", "en"]

        self.languages = languages
        self.gpu = gpu
        self.reader = None
        self._available = False

        logger.info(_MSG_INIT.format(langs=", ".join(languages)))

        try:
            import easyocr  # type: ignore

            self.reader = easyocr.Reader(
                lang_list=languages,
                gpu=gpu,
                verbose=False,
            )
            self._available = True
            logger.info(_MSG_INIT_OK)

        except ImportError:
            logger.warning(_MSG_INIT_FAIL)
            self._available = False
        except Exception as e:
            logger.error(
                f"خطأ غير متوقع في EasyOCR: {e} | "
                f"Unexpected EasyOCR error: {e}"
            )
            self._available = False

    @property
    def is_available(self) -> bool:
        """Check if EasyOCR reader is available."""
        return self._available

    def extract_text(self, image: np.ndarray) -> dict[str, Any]:
        """
        Extract text from an image using EasyOCR.

        استخراج النص من صورة باستخدام EasyOCR.

        Args:
            image: Input image as numpy array. Supports both BGR (OpenCV)
                   and RGB formats.

        Returns:
            Dictionary containing:
                - text (str): Full extracted text
                - lines (List[Dict]): Individual line results with:
                    - text (str): Detected text
                    - bbox (List[List[int]]): Bounding box coordinates
                    - confidence (float): Detection confidence (0-1)
                - num_lines (int): Number of detected lines
                - engine (str): 'easyocr'
        """
        if not self._available:
            logger.warning(_MSG_NOT_AVAIL)
            return self._empty_result()

        logger.info(_MSG_EXTRACTING)

        try:
            # Convert BGR to RGB if needed (EasyOCR expects RGB)
            processed_image = self._ensure_rgb(image)

            # Run OCR
            raw_results = self.reader.readtext(
                processed_image,
                paragraph=False,
                batch_size=4,
            )

            # Parse results
            lines: list[dict] = []
            for bbox_points, text, confidence in raw_results:
                # bbox_points is [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
                bbox_list = [
                    [int(p[0]), int(p[1])] for p in bbox_points
                ]

                lines.append({
                    "text": text.strip(),
                    "bbox": bbox_list,
                    "confidence": round(float(confidence), 4),
                })

            # Sort lines by vertical then horizontal position (top-to-bottom)
            lines.sort(key=lambda l: (l["bbox"][0][1], l["bbox"][0][0]))

            # Build full text
            full_text = "\n".join(
                line["text"] for line in lines if line["text"]
            )

            result = {
                "text": full_text,
                "lines": lines,
                "num_lines": len(lines),
                "engine": "easyocr",
            }

            logger.info(_MSG_EXTRACTED.format(n=len(lines)))
            return result

        except Exception as e:
            logger.error(
                f"خطأ في استخراج النص: {e} | Text extraction error: {e}",
                exc_info=True,
            )
            return self._empty_result()

    def extract_text_simple(self, image: np.ndarray) -> str:
        """
        Extract text and return only the text string.

        استخراج النص وإرجاع النص فقط.

        This is a convenience method for cases where only the raw
        text is needed without metadata.

        طريقة مريحة للحالات التي تحتاج النص الخام فقط.

        Args:
            image: Input image as numpy array.

        Returns:
            Extracted text as a single string, or empty string on failure.
        """
        result = self.extract_text(image)
        return result.get("text", "")

    def _ensure_rgb(self, image: np.ndarray) -> np.ndarray:
        """
        Ensure the image is in RGB format for EasyOCR.

        التأكد من أن الصورة بصيغة RGB لـ EasyOCR.

        EasyOCR can handle both BGR and RGB, but we explicitly convert
        to ensure consistent behavior with OpenCV-loaded images.

        Args:
            image: Input numpy array.

        Returns:
            Image guaranteed to be in RGB format.
        """
        if len(image.shape) == 2:
            # Grayscale - convert to RGB
            logger.debug("تحويل صورة رمادية إلى RGB | Converting grayscale to RGB")
            return np.stack([image] * 3, axis=-1)

        if image.shape[2] == 4:
            # RGBA - drop alpha channel
            logger.debug("تحويل RGBA إلى RGB | Converting RGBA to RGB")
            return image[:, :, :3]

        if image.shape[2] == 3:
            # Check if likely BGR (dominant blue channel) vs RGB
            # Heuristic: if blue channel average > red, likely BGR
            b_avg = float(np.mean(image[:, :, 0]))
            r_avg = float(np.mean(image[:, :, 2]))

            if b_avg > r_avg * 1.2:
                logger.debug(_MSG_CONVERSION)
                return image[:, :, ::-1]

        return image

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        """Return an empty extraction result."""
        return {
            "text": "",
            "lines": [],
            "num_lines": 0,
            "engine": "easyocr",
        }
