"""
Surya Layout Analyzer - تحليل تخطيط المستندات باستخدام Surya OCR
===================================================================

This module provides document layout analysis capabilities using the
surya-ocr library. It detects text lines, classifies layout elements,
and determines reading order for Arabic and multilingual medical documents.

الوحدة توفر تحليل تخطيط المستندات باستخدام مكتبة surya-ocr
للكشف عن أسطر النص وتصنيف عناصر التخطيط وتحديد ترتيب القراءة.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

logger = logging.getLogger(__name__)

# Arabic + English messages
_MSG_LOADING = "جارٍ تحميل نماذج Surya... | Loading Surya models..."
_MSG_LOADED = "تم تحميل نماذج Surya بنجاح | Surya models loaded successfully"
_MSG_FAILED = "فشل تحميل Surya - سيتم استخدام التراجع | Failed to load Surya - fallback mode"
_MSG_ANALYZING = "جارٍ تحليل تخطيط المستند | Analyzing document layout"
_MSG_DONE = "اكتمل التحليل - {num_lines} سطر تم العثور عليه | Analysis complete - {num_lines} lines found"
_MSG_NOT_AVAILABLE = "Surya غير متاح - يرجى تثبيت surya-ocr | Surya not available - please install surya-ocr"
_MSG_READING_ORDER = "جارٍ تحديد ترتيب القراءة | Determining reading order"
_MSG_CLASSIFY = "تصنيف العنصر: {text[:30]}... | Classifying element: {text[:30]}..."


class SuryaLayoutAnalyzer:
    """
    Document layout analyzer powered by Surya OCR.

    Provides layout analysis, text line detection, OCR recognition,
    and reading order detection for medical documents.

    محلل تخطيط المستندات المدعوم بـ Surya OCR.
    يوفر تحليل التخطيط والكشف عن أسطر النص والتعرف الضوئي
    وتحديد ترتيب القراءة للمستندات الطبية.
    """

    def __init__(self) -> None:
        """
        Initialize Surya layout analyzer by loading detection
        and recognition models.

        تهيئة محلل تخطيط Surya عن طريق تحميل نماذج الكشف والتعرف.
        """
        self.detector = None
        self.recognizer = None
        self.order_detector = None
        self._available = False

        logger.info(_MSG_LOADING)
        try:
            from surya.detection import DetectionPredictor
            from surya.recognition import RecognitionPredictor
            from surya.ordering import OrderPredictor

            self.detector = DetectionPredictor()
            logger.info("تم تحميل نموذج الكشف | Detection model loaded")

            self.recognizer = RecognitionPredictor()
            logger.info("تم تحميل نموذج التعرف | Recognition model loaded")

            self.order_detector = OrderPredictor()
            logger.info("تم تحميل نموذج ترتيب القراءة | Reading order model loaded")

            self._available = True
            logger.info(_MSG_LOADED)

        except ImportError:
            logger.warning(_MSG_NOT_AVAILABLE)
            logger.warning(_MSG_FAILED)
            self._available = False
        except Exception as e:
            logger.error(f"خطأ أثناء تحميل Surya: {e} | Error loading Surya: {e}")
            self._available = False

    @property
    def is_available(self) -> bool:
        """Check if Surya models are loaded and available."""
        return self._available

    def analyze(self, image: np.ndarray) -> Dict[str, Any]:
        """
        Perform full layout analysis on an image.

        Performs text detection, OCR recognition, element classification,
        and reading order detection.

        إجراء تحليل تخطيط كامل على الصورة.
        يشمل الكشف عن النص والتعرف الضوئي وتصنيف العناصر
        وتحديد ترتيب القراءة.

        Args:
            image: Input image as numpy array (BGR or RGB).

        Returns:
            Dictionary containing:
                - full_text (str): Combined text from all detected lines
                - lines (List[Dict]): Each line with text, bbox, confidence,
                  type, and order
                - num_lines (int): Total number of detected lines
                - layout_types (Dict[str, int]): Count of each layout element type
        """
        if not self._available:
            logger.warning(_MSG_NOT_AVAILABLE)
            return self._empty_result()

        logger.info(_MSG_ANALYZING)

        try:
            # Convert BGR to RGB if needed (Surya expects RGB PIL Image)
            pil_image = self._to_pil(image)

            # Step 1: Detect text line bounding boxes
            detections = self.detector([pil_image])
            bboxes = detections[0] if detections else []

            logger.debug(
                f"تم العثور على {len(bboxes)} منطقة كشف "
                f"| Found {len(bboxes)} detection regions"
            )

            if not bboxes:
                logger.info("لم يتم العثور على نص | No text found")
                return self._empty_result()

            # Step 2: Recognize text in each bounding box
            predictions = self.recognizer([pil_image], [bboxes])
            line_results = predictions[0] if predictions else []

            # Step 3: Determine reading order
            order_result = self._get_reading_order_internal(pil_image, bboxes)
            order_map = order_result.get("order_indices", {})

            # Step 4: Build structured lines with classification
            lines: List[Dict] = []
            for idx, (bbox, pred) in enumerate(zip(bboxes, line_results)):
                text = pred.get("text", "")
                confidence = float(pred.get("confidence", 0.0))

                # Normalize bounding box to list format
                bbox_list = self._normalize_bbox(bbox)

                # Classify the element
                element_type = self._classify_element(bbox_list, text)

                # Get reading order position
                order_pos = order_map.get(idx, idx)

                lines.append({
                    "text": text,
                    "bbox": bbox_list,
                    "confidence": round(confidence, 4),
                    "type": element_type,
                    "order": order_pos,
                })

            # Step 5: Sort by reading order
            lines.sort(key=lambda x: x["order"])

            # Step 6: Build full text
            full_text = "\n".join(
                line["text"] for line in lines if line["text"].strip()
            )

            # Step 7: Get layout summary
            layout_types = self._get_layout_summary(lines)

            result = {
                "full_text": full_text,
                "lines": lines,
                "num_lines": len(lines),
                "layout_types": layout_types,
                "engine": "surya",
            }

            logger.info(_MSG_DONE.format(num_lines=len(lines)))
            return result

        except Exception as e:
            logger.error(
                f"خطأ في التحليل: {e} | Analysis error: {e}",
                exc_info=True,
            )
            return self._empty_result()

    def get_reading_order(self, image: np.ndarray) -> List[Dict]:
        """
        Detect text lines and return them in reading order.

        This is a convenience method that returns only ordered text lines
        without full layout classification.

        الكشف عن أسطر النص وإرجاعها بترتيب القراءة.

        Args:
            image: Input image as numpy array.

        Returns:
            List of dictionaries with 'text', 'bbox', 'confidence', 'order'.
        """
        if not self._available:
            logger.warning(_MSG_NOT_AVAILABLE)
            return []

        logger.info(_MSG_READING_ORDER)

        try:
            pil_image = self._to_pil(image)

            # Detect text lines
            detections = self.detector([pil_image])
            bboxes = detections[0] if detections else []

            if not bboxes:
                return []

            # Recognize text
            predictions = self.recognizer([pil_image], [bboxes])
            line_results = predictions[0] if predictions else []

            # Get reading order
            order_result = self._get_reading_order_internal(pil_image, bboxes)
            order_map = order_result.get("order_indices", {})

            ordered_lines = []
            for idx, (bbox, pred) in enumerate(zip(bboxes, line_results)):
                text = pred.get("text", "")
                confidence = float(pred.get("confidence", 0.0))
                bbox_list = self._normalize_bbox(bbox)
                order_pos = order_map.get(idx, idx)

                ordered_lines.append({
                    "text": text,
                    "bbox": bbox_list,
                    "confidence": round(confidence, 4),
                    "order": order_pos,
                })

            # Sort by reading order
            ordered_lines.sort(key=lambda x: x["order"])

            logger.info(
                f"تم ترتيب {len(ordered_lines)} سطر | "
                f"Ordered {len(ordered_lines)} lines"
            )
            return ordered_lines

        except Exception as e:
            logger.error(
                f"خطأ في ترتيب القراءة: {e} | Reading order error: {e}"
            )
            return []

    def _classify_element(
        self, bbox: List, text: str
    ) -> str:
        """
        Classify a layout element based on its bounding box and text content.

        تصنيف عنصر التخطيط بناءً على موقعه ومحتواه النصي.

        Classification rules:
            - figure: Very short text or empty with large bounding box
            - header: Short text (≤ 40 chars) in upper 20% of page
            - paragraph: Longer text blocks
            - text_line: Default for standard text lines

        Args:
            bbox: Bounding box as [x1, y1, x2, y2].
            text: Extracted text content.

        Returns:
            Element type string: 'text_line', 'figure', 'header', 'paragraph'.
        """
        text_stripped = text.strip()
        text_length = len(text_stripped)

        # Calculate bounding box area and dimensions
        if len(bbox) >= 4:
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            area = width * height
        else:
            width, height, area = 0, 0, 0

        # Rule 1: Figure detection - large area with little or no text
        if text_length < 5 and area > 10000:
            logger.debug(f"تصنيف: شكل | Classified: figure (area={area})")
            return "figure"

        # Rule 2: Header detection - short text in upper portion
        if text_length <= 40 and text_length > 0 and height > 0:
            # Assume typical page height of ~1000 pixels for relative positioning
            relative_y = bbox[1] / max(bbox[3], 1)
            if relative_y < 0.20 or bbox[1] < 100:
                logger.debug(
                    f"تصنيف: عنوان | Classified: header "
                    f"(y={bbox[1]}, len={text_length})"
                )
                return "header"

        # Rule 3: Paragraph detection - longer text blocks
        if text_length > 100:
            logger.debug(
                f"تصنيف: فقرة | Classified: paragraph (len={text_length})"
            )
            return "paragraph"

        # Rule 4: Default - standard text line
        logger.debug(
            f"تصنيف: سطر نص | Classified: text_line (len={text_length})"
        )
        return "text_line"

    def _get_layout_summary(self, lines: List[Dict]) -> Dict[str, int]:
        """
        Count the occurrences of each layout element type.

        عد أنواع عناصر التخطيط المكتشفة.

        Args:
            lines: List of detected line dictionaries with 'type' field.

        Returns:
            Dictionary mapping element type to count.
        """
        summary: Dict[str, int] = {}
        for line in lines:
            elem_type = line.get("type", "unknown")
            summary[elem_type] = summary.get(elem_type, 0) + 1

        logger.debug(
            f"ملخص التخطيط: {summary} | Layout summary: {summary}"
        )
        return summary

    def _get_reading_order_internal(
        self, pil_image, bboxes: List
    ) -> Dict[str, Any]:
        """
        Internal method to get reading order from Surya order predictor.

        طريقة داخلية لتحديد ترتيب القراءة.

        Args:
            pil_image: PIL Image object.
            bboxes: List of bounding boxes.

        Returns:
            Dictionary with 'order_indices' mapping original index to order.
        """
        try:
            # Surya ordering expects specific format
            order_predictions = self.order_detector([pil_image], [bboxes])
            order_indices = order_predictions[0] if order_predictions else []

            # Build order map: original_index -> position
            order_map: Dict[int, int] = {}
            for position, original_idx in enumerate(order_indices):
                order_map[original_idx] = position

            return {"order_indices": order_map}

        except Exception as e:
            logger.warning(
                f"فشل تحديد الترتيب، استخدام الترتيب الافتراضي "
                f"| Order detection failed, using default order: {e}"
            )
            # Fallback: use original order
            return {"order_indices": {i: i for i in range(len(bboxes))}}

    @staticmethod
    def _to_pil(image: np.ndarray):
        """
        Convert numpy array to PIL Image.

        تحويل مصفوفة numpy إلى صورة PIL.

        Args:
            image: numpy array (BGR or RGB).

        Returns:
            PIL Image in RGB format.
        """
        from PIL import Image

        if len(image.shape) == 2:
            # Grayscale to RGB
            pil_image = Image.fromarray(image, mode="L").convert("RGB")
        elif image.shape[2] == 4:
            # RGBA to RGB
            pil_image = Image.fromarray(image, mode="RGBA").convert("RGB")
        elif image.shape[2] == 3:
            # Assume BGR (OpenCV default), convert to RGB
            rgb_image = image[:, :, ::-1]
            pil_image = Image.fromarray(rgb_image)
        else:
            pil_image = Image.fromarray(image)

        return pil_image

    @staticmethod
    def _normalize_bbox(bbox) -> List[float]:
        """
        Normalize bounding box to a consistent [x1, y1, x2, y2] format.

        توحيد صندوق الحدود إلى تنسيق موحد.

        Args:
            bbox: Bounding box in various possible formats.

        Returns:
            List of 4 floats: [x_min, y_min, x_max, y_max].
        """
        try:
            # If it's a list of points [[x1,y1],[x2,y2],...]
            if isinstance(bbox, (list, tuple)):
                flat = []
                for item in bbox:
                    if isinstance(item, (list, tuple)):
                        flat.extend([float(v) for v in item])
                    else:
                        flat.append(float(item))

                if len(flat) >= 4:
                    xs = [flat[i] for i in range(0, len(flat), 2)]
                    ys = [flat[i + 1] for i in range(1, len(flat), 2)]
                    return [
                        round(min(xs), 2),
                        round(min(ys), 2),
                        round(max(xs), 2),
                        round(max(ys), 2),
                    ]

            # If it's a dict with keys
            if isinstance(bbox, dict):
                x1 = float(bbox.get("x1", bbox.get("left", 0)))
                y1 = float(bbox.get("y1", bbox.get("top", 0)))
                x2 = float(bbox.get("x2", bbox.get("right", 0)))
                y2 = float(bbox.get("y2", bbox.get("bottom", 0)))
                return [round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)]

        except (TypeError, ValueError, IndexError) as e:
            logger.warning(f"تعذر توحيد الصندوق: {e} | Could not normalize bbox: {e}")

        return [0.0, 0.0, 0.0, 0.0]

    @staticmethod
    def _empty_result() -> Dict[str, Any]:
        """Return an empty analysis result."""
        return {
            "full_text": "",
            "lines": [],
            "num_lines": 0,
            "layout_types": {},
            "engine": "surya",
        }