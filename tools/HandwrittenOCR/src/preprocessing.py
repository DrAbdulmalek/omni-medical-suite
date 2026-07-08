"""
HandwrittenOCR - معالجة الصور المسبقة v4.0
==============================================
تحسين الصور قبل التعرف مع:
- تسوية الميل (Deskewing) مع borderMode=BORDER_REPLICATE
- CLAHE + Denoising + Thresholding (OTSU + Adaptive)
- تجزئة ذكية: EasyOCR أولاً + IoU matching + الكنتورات كبديل
- مُحصّن: crops من img_bgr الأصلية (ليس من الصورة الثنائية)
"""


import cv2
import numpy as np

from config import Config


def deskew(gray: np.ndarray, config: Config = None) -> np.ndarray:
    """
    تسوية ميل النص باستخدام minAreaRect.
    - يستخدم borderMode=BORDER_REPLICATE (تصحيح #5)
    - حد أدنى 50 نقطة (من الكود الجديد)
    """
    coords = np.column_stack(np.where(gray < 250))
    if len(coords) < 50:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if abs(angle) < 0.3:
        return gray
    h, w = gray.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    return cv2.warpAffine(
        gray, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,  # تصحيح #5
    )


def preprocess_image(
    img_bgr: np.ndarray,
    config: Config = None,
    adaptive: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """
    تحسين الصورة للتعرف على النصوص.

    Returns:
        tuple: (binary_image, enhanced_gray)
    """
    if config is None:
        config = Config()

    gray = (
        cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        if img_bgr.ndim == 3
        else img_bgr.copy()
    )

    if config.enable_deskew:
        gray = deskew(gray, config)

    gray = cv2.createCLAHE(
        clipLimit=config.clahe_clip,
        tileGridSize=config.clahe_tile,
    ).apply(gray)

    gray = cv2.fastNlMeansDenoising(gray, h=config.denoise_h)

    if adaptive:
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, 31, 11,
        )
    else:
        _, binary = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )

    return binary, gray


def compute_iou(b1, b2) -> float:
    """حساب نسبة التداخل بين مستطيلين"""
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    xi1, yi1 = max(x1, x2), max(y1, y2)
    xi2, yi2 = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
    inter = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    union = w1 * h1 + w2 * h2 - inter
    return inter / union if union > 0 else 0


def smart_segmentation(
    img_bgr: np.ndarray,
    binary: np.ndarray,
    easyocr_detections: list | None = None,
    config: Config = None,
) -> list[tuple[int, int, int, int]]:
    """
    تجزئة ذكية: EasyOCR أولاً + IoU matching + الكنتورات كبديل.
    Returns: قائمة بـ (x, y, w, h)
    """
    if config is None:
        config = Config()

    if easyocr_detections:
        boxes = []
        for det in easyocr_detections:
            pts = np.array(det[0], dtype=np.int32)
            x, y, w, h = cv2.boundingRect(pts)
            if w > config.min_word_w and h > config.min_word_h:
                boxes.append((x, y, w, h))
        if boxes:
            return boxes

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, config.dilation_kernel)
    dilated = cv2.dilate(binary, kernel, iterations=1)
    contours, _ = cv2.findContours(
        dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    boxes = [
        (x, y, w, h)
        for c in contours
        for x, y, w, h in [cv2.boundingRect(c)]
        if w > config.min_word_w and h > config.min_word_h
    ]
    return sorted(boxes, key=lambda b: (b[1], b[0]))


def match_boxes_with_detections(
    boxes: list,
    detections: list,
    iou_threshold: float = 0.3,
) -> list:
    """ربط المستطيلات مع كشف EasyOCR باستخدام IoU."""
    if not detections:
        return [(b, None) for b in boxes]

    det_boxes = []
    for det in detections:
        pts = np.array(det[0], dtype=np.int32)
        det_boxes.append((cv2.boundingRect(pts), det))

    result, used = [], set()
    for box in boxes:
        best_det, best_iou = None, 0
        for i, (db, det) in enumerate(det_boxes):
            if i in used:
                continue
            iou = compute_iou(box, db)
            if iou > best_iou and iou > iou_threshold:
                best_iou, best_det = iou, det
                used.add(i)
        result.append((box, best_det))

    return result


def crop_safe(img: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    """قص آمن مع حدود الصورة — crops دائماً من img_bgr الأصلية (تصحيح #3)"""
    H, W = img.shape[:2]
    return img[max(0, y): min(H, y + h), max(0, x): min(W, x + w)]
