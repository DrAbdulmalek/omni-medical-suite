#!/usr/bin/env python3
"""
Medical Document Processing GUI Application v16 (Final)
PyQt5-based application for processing medical document images.
Supports rotation, cropping, deskewing, shadow removal, OCR, and batch processing.
"""

import os
import sys
import cv2
import numpy as np
import logging
import shutil
from collections import deque
from typing import List, Optional, Tuple, Dict

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QCheckBox, QSlider, QTabWidget, QScrollArea, QTextEdit,
    QFileDialog, QMessageBox, QDialog, QFormLayout, QProgressBar,
    QSplitter, QGroupBox, QAction, QStatusBar, QToolBar,
    QGridLayout, QSizePolicy, QDialogButtonBox, QMenu, QMenuBar,
)
from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, pyqtSlot, QMutex, QRect,
    QSize, QPoint, QModelIndex,
)
from PyQt5.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QFont, QIcon, QKeySequence,
)

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    from pdf2image import convert_from_path
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False

try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("MedicalDoc")

# ---------------------------------------------------------------------------
# LazyImage – defers heavy decoding until needed
# ---------------------------------------------------------------------------
class LazyImage:
    """Wrapper that lazy-loads an image from a file path."""

    def __init__(self, path: str):
        self.path = path
        self._arr = None

    @property
    def array(self) -> np.ndarray:
        if self._arr is None:
            self._arr = cv2.imread(self.path)
            if self._arr is None:
                logger.error("Cannot read image: %s", self.path)
                self._arr = np.zeros((100, 100, 3), dtype=np.uint8)
        return self._arr

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @property
    def exists(self) -> bool:
        return os.path.isfile(self.path)

    def release(self):
        self._arr = None


# ---------------------------------------------------------------------------
# Core image processing helpers
# ---------------------------------------------------------------------------

def apply_processing(
    img: np.ndarray,
    rotation: int = 0,
    crop: Tuple[int, int, int, int] = (0, 0, 0, 0),
    deskew_angle: float = 0.0,
    flip_h: bool = False,
    sharpen: bool = False,
    remove_shadow: bool = False,
    gray_threshold: int = 200,
) -> np.ndarray:
    """Apply a chain of image-processing operations and return the result."""
    result = img.copy()
    # Crop
    left, top, right, bottom = crop
    h, w = result.shape[:2]
    x1 = max(0, left)
    y1 = max(0, top)
    x2 = min(w, w - right)
    y2 = min(h, h - bottom)
    if x2 > x1 and y2 > y1:
        result = result[y1:y2, x1:x2].copy()

    # Flip
    if flip_h:
        result = cv2.flip(result, 1)

    # Rotation
    if rotation in (90, 180, 270):
        if rotation == 90:
            result = cv2.rotate(result, cv2.ROTATE_90_CLOCKWISE)
        elif rotation == 180:
            result = cv2.rotate(result, cv2.ROTATE_180)
        elif rotation == 270:
            result = cv2.rotate(result, cv2.ROTATE_90_COUNTERCLOCKWISE)

    # Deskew
    if abs(deskew_angle) > 0.05:
        h, w = result.shape[:2]
        center = (w / 2, h / 2)
        M = cv2.getRotationMatrix2D(center, deskew_angle, 1.0)
        result = cv2.warpAffine(
            result, M, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

    # Shadow removal
    if remove_shadow:
        result = _remove_shadow(result, gray_threshold)

    # Sharpen
    if sharpen:
        kernel = np.array(
            [[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32
        )
        result = cv2.filter2D(result, -1, kernel)

    return result


def _remove_shadow(img: np.ndarray, threshold: int = 200) -> np.ndarray:
    """Remove shadow using morphological opening on grayscale image."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    rgb_planes = cv2.split(img) if img.ndim == 3 else [gray]
    result_planes = []
    dilation_size = max(3, int(min(img.shape[:2]) / 400))
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (dilation_size, dilation_size)
    )
    for plane in rgb_planes:
        dilated = cv2.dilate(plane, kernel)
        bg = cv2.medianBlur(dilated, max(3, dilation_size * 2 + 1))
        diff = 255 - cv2.absdiff(plane, bg)
        norm = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)
        result_planes.append(norm)
    if len(result_planes) == 1:
        return result_planes[0]
    return cv2.merge(result_planes)


def cv2_to_pixmap(img: np.ndarray) -> QPixmap:
    """Convert an OpenCV BGR numpy array to QPixmap."""
    if img is None or img.size == 0:
        return QPixmap()
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    h, w, ch = img.shape
    bytes_per_line = ch * w
    if ch == 4:
        qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_RGBA8888)
    else:
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg.copy())


def calc_blur(img: np.ndarray) -> float:
    """Return a blur score (Laplacian variance); lower = more blurry."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def quality_label(score: float, threshold: float = 100.0) -> str:
    """Return a human-readable quality label based on blur score."""
    if score >= threshold:
        return "جيدة ✓"
    elif score >= threshold * 0.5:
        return "متوسطة ⚠"
    else:
        return "ضعيفة ✗"


def find_page_bounds(
    img: np.ndarray,
    page_threshold: int = 200,
    min_page_fraction: float = 0.25,
) -> Tuple[int, int, int, int]:
    """Detect the page boundaries using MEDIAN projection (not hybrid).

    Returns (left, top, right, bottom) crop margins.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    h, w = gray.shape
    col_med = np.median(gray, axis=0)

    def _find_bounds(signal, min_frac):
        n = len(signal)
        is_page = np.concatenate([[False], signal > page_threshold, [False]])
        diff = np.diff(is_page.astype(np.int8))
        starts = np.where(diff == 1)[0]
        ends = np.where(diff == -1)[0]
        if len(starts) == 0:
            return 0, n - 1
        lengths = ends - starts
        best = int(np.argmax(lengths))
        if lengths[best] < min_frac * n:
            return 0, n - 1
        return int(starts[best]), int(ends[best]) - 1

    col_s, col_e = _find_bounds(col_med, min_page_fraction)
    MARGIN = 5
    left = max(0, col_s - MARGIN)
    right = min(w - 1, col_e + MARGIN)

    page_region = gray[:, left:right + 1] if right > left else gray
    row_med = np.median(page_region, axis=1)
    row_s, row_e = _find_bounds(row_med, min_page_fraction)
    top = max(0, row_s - MARGIN)
    bottom = min(h - 1, row_e + MARGIN)

    return (left, top, w - right - 1, h - bottom - 1)


def auto_detect_skew(img: np.ndarray) -> float:
    """Detect dominant text skew angle using a minAreaRect on contours."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 5))
    dilated = cv2.dilate(binary, kernel, iterations=1)
    contours, _ = cv2.findContours(dilated, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0.0
    angles = []
    for c in contours:
        if cv2.contourArea(c) < 100:
            continue
        rect = cv2.minAreaRect(c)
        angle = rect[-1]
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = angle - 90
        angles.append(angle)
    if not angles:
        return 0.0
    # Median angle is robust to outliers
    return float(np.median(angles))


def smart_auto_crop(img: np.ndarray) -> Tuple[int, int, int, int]:
    """Smart crop using page-bound detection with content-aware padding."""
    bounds = find_page_bounds(img)
    left, top, right, bottom = bounds
    h, w = img.shape[:2]
    # Clamp to sensible values
    left = min(left, w // 4)
    top = min(top, h // 4)
    right = min(right, w // 4)
    bottom = min(bottom, h // 4)
    return (left, top, right, bottom)


def load_pdf_as_images(pdf_path: str, dpi: int = 200) -> List[np.ndarray]:
    """Convert PDF pages to a list of OpenCV images."""
    if not HAS_PDF2IMAGE:
        logger.warning("pdf2image not installed; cannot load PDF.")
        return []
    images = convert_from_path(pdf_path, dpi=dpi)
    result = []
    for pil_img in images:
        arr = np.array(pil_img)
        if arr.ndim == 3 and arr.shape[2] == 4:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
        elif arr.ndim == 3 and arr.shape[2] == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        else:
            arr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
        result.append(arr)
    return result


# ---------------------------------------------------------------------------
# AI / OCR helper functions
# ---------------------------------------------------------------------------

def extract_page_number(img: np.ndarray, region: Tuple[int, int, int, int] = None) -> Optional[int]:
    """Extract a page number from an image region using Tesseract OCR."""
    if not HAS_TESSERACT:
        logger.warning("pytesseract not installed; OCR unavailable.")
        return None
    if region is not None:
        x, y, rw, rh = region
        roi = img[y:y + rh, x:x + rw]
    else:
        roi = img
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi
    gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    try:
        text = pytesseract.image_to_string(binary, config="--psm 7 -c tessedit_char_whitelist=0123456789").strip()
        numbers = [int(w) for w in text.split() if w.isdigit()]
        return numbers[0] if numbers else None
    except Exception as e:
        logger.error("OCR error: %s", e)
        return None


def images_are_similar(img1: np.ndarray, img2: np.ndarray, threshold: float = 10.0) -> bool:
    """Check if two images are perceptually similar using image hashing."""
    if HAS_IMAGEHASH:
        try:
            pil1 = PILImage.fromarray(cv2.cvtColor(img1, cv2.COLOR_BGR2RGB)) if img1.ndim == 3 else PILImage.fromarray(img1)
            pil2 = PILImage.fromarray(cv2.cvtColor(img2, cv2.COLOR_BGR2RGB)) if img2.ndim == 3 else PILImage.fromarray(img2)
            h1 = imagehash.average_hash(pil1)
            h2 = imagehash.average_hash(pil2)
            return h1 - h2 < threshold
        except Exception:
            pass
    # Fallback: pixel-level comparison
    try:
        r1 = cv2.resize(img1, (64, 64))
        r2 = cv2.resize(img2, (64, 64))
        diff = np.abs(r1.astype(float) - r2.astype(float))
        return float(np.mean(diff)) < 10.0
    except Exception:
        return False


def assess_image_quality(img: np.ndarray) -> Dict[str, object]:
    """Return a dictionary of quality metrics for the given image."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    blur_score = calc_blur(img)
    brightness = float(np.mean(gray))
    contrast = float(np.std(gray))
    noise_estimate = float(np.median(np.abs(np.diff(gray.astype(float)))))
    # Sharpness via Sobel
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    sharpness = float(np.mean(np.sqrt(sobel_x ** 2 + sobel_y ** 2)))
    return {
        "blur_score": blur_score,
        "brightness": brightness,
        "contrast": contrast,
        "noise": noise_estimate,
        "sharpness": sharpness,
        "quality_label": quality_label(blur_score),
    }


# ---------------------------------------------------------------------------
# Worker threads
# ---------------------------------------------------------------------------

class SkewWorker(QThread):
    """Background thread for skew angle detection."""
    finished = pyqtSignal(float)
    error = pyqtSignal(str)

    def __init__(self, img: np.ndarray, parent=None):
        super().__init__(parent)
        self.img = img

    def run(self):
        try:
            angle = auto_detect_skew(self.img)
            self.finished.emit(angle)
        except Exception as e:
            self.error.emit(str(e))


class ThumbnailWorker(QThread):
    """Background thread for generating thumbnails."""
    thumb_ready = pyqtSignal(int, QPixmap)

    def __init__(self, items: List[Tuple[int, LazyImage]], parent=None):
        super().__init__(parent)
        self.items = items

    def run(self):
        for idx, lazy in self.items:
            try:
                img = lazy.array
                if img is None:
                    continue
                # Generate small thumbnail
                max_h, max_w = 120, 90
                h, w = img.shape[:2]
                scale = min(max_w / w, max_h / h, 1.0)
                if scale < 1.0:
                    small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                else:
                    small = img
                pixmap = cv2_to_pixmap(small)
                self.thumb_ready.emit(idx, pixmap)
            except Exception as e:
                logger.error("Thumbnail generation error for %s: %s", lazy.path, e)


# ---------------------------------------------------------------------------
# Learning / Adaptive system
# ---------------------------------------------------------------------------

class ImageFeatureExtractor:
    """Extract features from an image for the adaptive learning system."""

    @staticmethod
    def extract(img: np.ndarray) -> Dict[str, float]:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        h, w = gray.shape
        features = {
            "aspect_ratio": w / max(h, 1),
            "brightness": float(np.mean(gray)),
            "contrast": float(np.std(gray)),
            "blur": calc_blur(img),
            "dark_pixel_ratio": float(np.sum(gray < 50) / gray.size),
            "light_pixel_ratio": float(np.sum(gray > 200) / gray.size),
            "edge_density": float(np.sum(cv2.Canny(gray, 50, 150) > 0) / gray.size),
        }
        return features


class TrainingDataCollector:
    """Collect (features, params) pairs for training."""

    def __init__(self):
        self.data: List[Tuple[Dict[str, float], dict]] = []

    def add_sample(self, features: Dict[str, float], params: dict):
        self.data.append((features, params.copy()))

    def get_data(self) -> List[Tuple[Dict[str, float], dict]]:
        return list(self.data)

    def clear(self):
        self.data.clear()

    @property
    def count(self) -> int:
        return len(self.data)


class AdaptiveLearner:
    """Simple nearest-neighbour adaptive learner for suggesting parameters."""

    def __init__(self):
        self._data: List[Tuple[Dict[str, float], dict]] = []

    def train(self, data: List[Tuple[Dict[str, float], dict]]):
        self._data = list(data)

    def predict(self, features: Dict[str, float], k: int = 3) -> Optional[dict]:
        """Predict processing parameters using k-nearest-neighbours."""
        if len(self._data) < 1:
            return None
        feature_keys = sorted(features.keys())
        dists = []
        for train_feats, train_params in self._data:
            sq_sum = 0.0
            for key in feature_keys:
                if key in train_feats:
                    a = features.get(key, 0.0)
                    b = train_feats[key]
                    sq_sum += (a - b) ** 2
            dists.append((np.sqrt(sq_sum), train_params))
        dists.sort(key=lambda x: x[0])
        top_k = dists[:k]
        # Weighted average of parameters
        total_w = sum(1.0 / max(d, 1e-9) for d, _ in top_k)
        if total_w == 0:
            return None
        result = {}
        param_keys = list(top_k[0][1].keys())
        for key in param_keys:
            val = 0.0
            for d, params in top_k:
                w = 1.0 / max(d, 1e-9)
                val += w * params[key]
            result[key] = val / total_w
        # Round / convert
        result["rotation"] = int(round(result.get("rotation", 0)))
        result["deskew_angle"] = round(result.get("deskew_angle", 0.0), 2)
        result["flip_h"] = result.get("flip_h", False)
        result["sharpen"] = result.get("sharpen", False)
        result["remove_shadow"] = result.get("remove_shadow", False)
        result["crop"] = (
            int(result.get("crop_left", 0)),
            int(result.get("crop_top", 0)),
            int(result.get("crop_right", 0)),
            int(result.get("crop_bottom", 0)),
        )
        # Clean up numeric keys
        for key in list(result.keys()):
            if key.startswith("crop_"):
                del result[key]
        return result

    @property
    def is_trained(self) -> bool:
        return len(self._data) > 0

    @property
    def sample_count(self) -> int:
        return len(self._data)


# ---------------------------------------------------------------------------
# UI Helper classes
# ---------------------------------------------------------------------------

class RegionSelectorLabel(QLabel):
    """QLabel that allows drawing a rectangle to select a region."""

    region_selected = pyqtSignal(tuple)

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._start = None
        self._end = None
        self._drawing = False
        self.setPixmap(pixmap.scaled(600, 800, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._start = event.pos()
            self._end = event.pos()
            self._drawing = True

    def mouseMoveEvent(self, event):
        if self._drawing:
            self._end = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drawing:
            self._drawing = False
            self._end = event.pos()
            if self._start and self._end:
                x1 = min(self._start.x(), self._end.x())
                y1 = min(self._start.y(), self._end.y())
                x2 = max(self._start.x(), self._end.x())
                y2 = max(self._start.y(), self._end.y())
                if x2 - x1 > 5 and y2 - y1 > 5:
                    # Scale coordinates back to original image
                    pm = self.pixmap()
                    orig_w = self._pixmap.width()
                    orig_h = self._pixmap.height()
                    scale_x = orig_w / max(pm.width(), 1)
                    scale_y = orig_h / max(pm.height(), 1)
                    rx = int(x1 * scale_x)
                    ry = int(y1 * scale_y)
                    rw = int((x2 - x1) * scale_x)
                    rh = int((y2 - y1) * scale_y)
                    self.region_selected.emit((rx, ry, rw, rh))

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._start and self._end:
            painter = QPainter(self)
            pen = QPen(QColor(255, 0, 0), 2, Qt.DashLine)
            painter.setPen(pen)
            painter.drawRect(QRect(self._start, self._end))


class RegionSelectorDialog(QDialog):
    """Dialog for selecting an OCR region on the image."""

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("اختيار منطقة رقم الصفحة")
        self.setMinimumSize(700, 900)
        layout = QVBoxLayout(self)
        self.label = RegionSelectorLabel(pixmap, self)
        layout.addWidget(self.label)
        hint = QLabel("ارسم مستطيل حول منطقة رقم الصفحة ثم اضغط 'تأكيد'")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("تأكيد")
        cancel_btn = QPushButton("إلغاء")
        btn_layout.addStretch()
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        self.selected_region = None
        self.label.region_selected.connect(self._on_region)

    def _on_region(self, region):
        self.selected_region = region


class CompareDialog(QDialog):
    """Dialog to compare before and after processing."""

    def __init__(self, before: QPixmap, after: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("مقارنة قبل وبعد المعالجة")
        self.setMinimumSize(1100, 700)
        layout = QHBoxLayout(self)
        # Before
        left = QVBoxLayout()
        lbl_before = QLabel("قبل المعالجة")
        lbl_before.setAlignment(Qt.AlignCenter)
        lbl_before.setFont(QFont("Arial", 12, QFont.Bold))
        before_label = QLabel()
        before_label.setPixmap(before.scaled(500, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        before_label.setAlignment(Qt.AlignCenter)
        left.addWidget(lbl_before)
        left.addWidget(before_label)
        # After
        right = QVBoxLayout()
        lbl_after = QLabel("بعد المعالجة")
        lbl_after.setAlignment(Qt.AlignCenter)
        lbl_after.setFont(QFont("Arial", 12, QFont.Bold))
        after_label = QLabel()
        after_label.setPixmap(after.scaled(500, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        after_label.setAlignment(Qt.AlignCenter)
        right.addWidget(lbl_after)
        right.addWidget(after_label)
        layout.addLayout(left)
        layout.addLayout(right)
        close_btn = QPushButton("إغلاق")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)


class ThumbButton(QPushButton):
    """A thumbnail button in the left panel."""

    clicked_idx = pyqtSignal(int)

    def __init__(self, idx: int, parent=None):
        super().__init__(parent)
        self.idx = idx
        self.setChecked(False)
        self.setCheckable(True)
        self.setFixedSize(100, 130)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setToolTip(f"صورة {idx + 1}")
        self.clicked.connect(lambda: self.clicked_idx.emit(self.idx))


# ===========================================================================
# MAIN APPLICATION CLASS
# ===========================================================================

class MedicalDocApp(QMainWindow):
    """Main application window for medical document processing."""

    def __init__(self):
        super().__init__()
        # ── State variables ──────────────────────────────────────────────
        self.image_list: List[LazyImage] = []
        self.current_idx: int = -1
        self.current_img: Optional[np.ndarray] = None
        self.current_params: dict = {
            "rotation": 0,
            "crop": (0, 0, 0, 0),
            "deskew_angle": 0.0,
            "flip_h": False,
            "sharpen": False,
            "remove_shadow": False,
        }
        self.undo_stack: deque = deque(maxlen=50)
        self.redo_stack: deque = deque(maxlen=50)
        self.operation_history: list = []
        self._is_processing: bool = False
        self._mutex = QMutex()
        self.blur_threshold: float = 100.0
        self.gray_threshold: int = 200
        self._batch_timer: QTimer = QTimer(self)
        self._batch_queue: list = []
        self._auto_save_in_prog: bool = False
        self.page_registry: dict = {}
        self._ocr_regions: list = []
        self._trainer: TrainingDataCollector = TrainingDataCollector()
        self._learner: AdaptiveLearner = AdaptiveLearner()
        self._detected_angle: float = 0.0
        self._thumb_worker: Optional[ThumbnailWorker] = None
        self._skew_worker: Optional[SkewWorker] = None
        self._output_dir: str = ""
        self._zoom_level: float = 1.0

        self._init_ui()
        self._create_menu_bar()
        self._create_toolbar()
        self._connect_signals()
        self._apply_stylesheet()
        self._log("تم تشغيل التطبيق بنجاح ✓")
        self._log("افتح ملفات الصور أو مجلداً للبدء.")

    # ====================================================================
    # UI Construction
    # ====================================================================

    def _init_ui(self):
        """Build the entire UI layout."""
        self.setWindowTitle("معالج المستندات الطبية - الإصدار 16")
        self.setMinimumSize(1400, 900)
        self.resize(1500, 950)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Splitter for the top area
        top_splitter = QSplitter(Qt.Horizontal)

        # Left panel – thumbnails
        self._create_left_panel()
        top_splitter.addWidget(self.left_scroll)

        # Center panel – image preview
        self._create_center_panel()
        top_splitter.addWidget(self.center_scroll)

        # Right panel – controls
        self._create_right_panel()
        top_splitter.addWidget(self.right_panel)

        top_splitter.setSizes([160, 900, 340])
        main_layout.addWidget(top_splitter, stretch=1)

        # Bottom panel – log, progress, status
        self._create_bottom_panel()
        main_layout.addLayout(self.bottom_layout)

    # ----------------------------------------------------------------

    def _create_menu_bar(self):
        """Create the menu bar with File, Edit, Tools, Help."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("ملف")
        open_action = QAction("فتح ملفات...", self)
        open_action.setShortcut(QKeySequence.Open)
        open_action.triggered.connect(self.open_files)
        file_menu.addAction(open_action)

        open_folder_action = QAction("فتح مجلد...", self)
        open_folder_action.triggered.connect(self.open_folder)
        file_menu.addAction(open_folder_action)

        open_pdf_action = QAction("فتح ملف PDF...", self)
        open_pdf_action.triggered.connect(self._open_pdf)
        file_menu.addAction(open_pdf_action)

        file_menu.addSeparator()

        save_action = QAction("حفظ", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self._save_current)
        file_menu.addAction(save_action)

        save_all_action = QAction("حفظ الكل", self)
        save_all_action.triggered.connect(self._save_all_processed)
        file_menu.addAction(save_all_action)

        file_menu.addSeparator()

        exit_action = QAction("خروج", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("تحرير")
        undo_action = QAction("تراجع", self)
        undo_action.setShortcut(QKeySequence.Undo)
        undo_action.triggered.connect(self._undo)
        edit_menu.addAction(undo_action)

        redo_action = QAction("إعادة", self)
        redo_action.setShortcut(QKeySequence.Redo)
        redo_action.triggered.connect(self._redo)
        edit_menu.addAction(redo_action)

        # Tools menu
        tools_menu = menubar.addMenu("أدوات")
        batch_action = QAction("معالجة دفعية...", self)
        batch_action.triggered.connect(self._start_batch)
        tools_menu.addAction(batch_action)

        # Help menu
        help_menu = menubar.addMenu("مساعدة")
        about_action = QAction("حول البرنامج", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ----------------------------------------------------------------

    def _create_toolbar(self):
        """Create the toolbar with common actions."""
        toolbar = QToolBar("شريط الأدوات")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        open_btn = QPushButton("📂 فتح")
        open_btn.clicked.connect(self.open_files)
        toolbar.addWidget(open_btn)

        save_btn = QPushButton("💾 حفظ")
        save_btn.clicked.connect(self._save_current)
        toolbar.addWidget(save_btn)

        toolbar.addSeparator()

        self.auto_deskew_btn = QPushButton("📐 تدوير تلقائي")
        self.auto_deskew_btn.clicked.connect(self._apply_auto_deskew)
        toolbar.addWidget(self.auto_deskew_btn)

        self.smart_crop_btn = QPushButton("✂️ قص ذكي")
        self.smart_crop_btn.clicked.connect(self._smart_crop)
        toolbar.addWidget(self.smart_crop_btn)

        toolbar.addSeparator()

        undo_btn = QPushButton("↩️ تراجع")
        undo_btn.clicked.connect(self._undo)
        toolbar.addWidget(undo_btn)

        redo_btn = QPushButton("↪️ إعادة")
        redo_btn.clicked.connect(self._redo)
        toolbar.addWidget(redo_btn)

        toolbar.addSeparator()

        zoom_in_btn = QPushButton("🔍+ تكبير")
        zoom_in_btn.clicked.connect(self._zoom_in)
        toolbar.addWidget(zoom_in_btn)

        zoom_out_btn = QPushButton("🔍- تصغير")
        zoom_out_btn.clicked.connect(self._zoom_out)
        toolbar.addWidget(zoom_out_btn)

        zoom_fit_btn = QPushButton("🔍 ملاءمة")
        zoom_fit_btn.clicked.connect(self._zoom_fit)
        toolbar.addWidget(zoom_fit_btn)

        toolbar.addStretch()

        self.auto_save_cb_toolbar = QCheckBox("حفظ تلقائي")
        self.auto_save_cb_toolbar.stateChanged.connect(lambda s: self._on_auto_save_toggle(s == Qt.Checked))
        toolbar.addWidget(self.auto_save_cb_toolbar)

    # ----------------------------------------------------------------

    def _create_left_panel(self):
        """Create the left panel with thumbnail grid."""
        self.left_scroll = QScrollArea()
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setMinimumWidth(140)
        self.left_scroll.setMaximumWidth(200)

        left_widget = QWidget()
        self.left_layout = QVBoxLayout(left_widget)
        self.left_layout.setAlignment(Qt.AlignTop)
        self.left_layout.setSpacing(4)

        lbl = QLabel("الصور المصغرة")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("font-weight: bold; font-size: 13px; padding: 4px;")
        self.left_layout.addWidget(lbl)

        self.left_scroll.setWidget(left_widget)

    # ----------------------------------------------------------------

    def _create_center_panel(self):
        """Create the center panel with image preview."""
        self.center_scroll = QScrollArea()
        self.center_scroll.setWidgetResizable(True)
        self.center_scroll.setAlignment(Qt.AlignCenter)

        self.image_label = QLabel("لا توجد صورة مفتوحة")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(400, 400)
        self.image_label.setStyleSheet("color: #888; font-size: 16px;")

        self.center_scroll.setWidget(self.image_label)

    # ----------------------------------------------------------------

    def _create_right_panel(self):
        """Create the right panel with tabbed controls."""
        self.right_panel = QTabWidget()
        self.right_panel.setMinimumWidth(300)
        self.right_panel.setMaximumWidth(400)

        # ── Tab 1: Processing ──
        proc_tab = QWidget()
        proc_layout = QVBoxLayout(proc_tab)
        proc_layout.setSpacing(6)

        # Rotation
        group_rot = QGroupBox("التدوير")
        rot_layout = QHBoxLayout(group_rot)
        rot_layout.addWidget(QLabel("الزاوية:"))
        self.rotation_combo = QComboBox()
        self.rotation_combo.addItems(["0°", "90°", "180°", "270°"])
        self.rotation_combo.setCurrentIndex(0)
        rot_layout.addWidget(self.rotation_combo)
        proc_layout.addWidget(group_rot)

        # Crop
        group_crop = QGroupBox("القص")
        crop_layout = QGridLayout(group_crop)
        crop_layout.addWidget(QLabel("يسار:"), 0, 0)
        self.crop_left_spin = QSpinBox()
        self.crop_left_spin.setRange(0, 5000)
        self.crop_left_spin.setValue(0)
        crop_layout.addWidget(self.crop_left_spin, 0, 1)

        crop_layout.addWidget(QLabel("أعلى:"), 0, 2)
        self.crop_top_spin = QSpinBox()
        self.crop_top_spin.setRange(0, 5000)
        self.crop_top_spin.setValue(0)
        crop_layout.addWidget(self.crop_top_spin, 0, 3)

        crop_layout.addWidget(QLabel("يمين:"), 1, 0)
        self.crop_right_spin = QSpinBox()
        self.crop_right_spin.setRange(0, 5000)
        self.crop_right_spin.setValue(0)
        crop_layout.addWidget(self.crop_right_spin, 1, 1)

        crop_layout.addWidget(QLabel("أسفل:"), 1, 2)
        self.crop_bottom_spin = QSpinBox()
        self.crop_bottom_spin.setRange(0, 5000)
        self.crop_bottom_spin.setValue(0)
        crop_layout.addWidget(self.crop_bottom_spin, 1, 3)

        proc_layout.addWidget(group_crop)

        # Deskew slider
        group_deskew = QGroupBox("تصحيح الميل")
        deskew_layout = QHBoxLayout(group_deskew)
        self.deskew_slider = QSlider(Qt.Horizontal)
        self.deskew_slider.setRange(-500, 500)
        self.deskew_slider.setValue(0)
        self.deskew_label = QLabel("0.00°")
        self.deskew_label.setMinimumWidth(55)
        deskew_layout.addWidget(self.deskew_slider)
        deskew_layout.addWidget(self.deskew_label)
        proc_layout.addWidget(group_deskew)

        # Options
        group_opts = QGroupBox("خيارات")
        opts_layout = QVBoxLayout(group_opts)
        self.flip_cb = QCheckBox("قلب أفقي")
        self.sharpen_cb = QCheckBox("حدة الصورة")
        self.shadow_cb = QCheckBox("إزالة الظلال")
        opts_layout.addWidget(self.flip_cb)
        opts_layout.addWidget(self.sharpen_cb)
        opts_layout.addWidget(self.shadow_cb)
        proc_layout.addWidget(group_opts)

        # Gray threshold slider
        group_gray = QGroupBox("حد الرمادي (للظلال)")
        gray_layout = QHBoxLayout(group_gray)
        self.gray_slider = QSlider(Qt.Horizontal)
        self.gray_slider.setRange(100, 255)
        self.gray_slider.setValue(200)
        self.gray_label_val = QLabel("200")
        gray_layout.addWidget(self.gray_slider)
        gray_layout.addWidget(self.gray_label_val)
        proc_layout.addWidget(group_gray)

        # Buttons
        btn_layout = QHBoxLayout()
        self.apply_btn = QPushButton("✅ تطبيق")
        self.apply_btn.setObjectName("primaryBtn")
        btn_layout.addWidget(self.apply_btn)

        self.clear_btn = QPushButton("🔄 إعادة تعيين")
        btn_layout.addWidget(self.clear_btn)
        proc_layout.addLayout(btn_layout)

        btn_layout2 = QHBoxLayout()
        self.undo_btn = QPushButton("↩️ تراجع")
        btn_layout2.addWidget(self.undo_btn)
        self.redo_btn = QPushButton("↪️ إعادة")
        btn_layout2.addWidget(self.redo_btn)
        proc_layout.addLayout(btn_layout2)

        proc_layout.addStretch()
        self.right_panel.addTab(proc_tab, "المعالجة")

        # ── Tab 2: Tools ──
        tools_tab = QWidget()
        tools_layout = QVBoxLayout(tools_tab)
        tools_layout.setSpacing(8)

        self.auto_deskew_btn2 = QPushButton("📐 كشف الميل تلقائياً")
        self.auto_deskew_btn2.setObjectName("toolBtn")
        tools_layout.addWidget(self.auto_deskew_btn2)

        self.smart_crop_btn2 = QPushButton("✂️ قص ذكي")
        self.smart_crop_btn2.setObjectName("toolBtn")
        tools_layout.addWidget(self.smart_crop_btn2)

        self.compare_btn = QPushButton("🔀 مقارنة قبل / بعد")
        self.compare_btn.setObjectName("toolBtn")
        tools_layout.addWidget(self.compare_btn)

        self.quality_btn = QPushButton("📊 تقييم الجودة")
        self.quality_btn.setObjectName("toolBtn")
        tools_layout.addWidget(self.quality_btn)

        tools_layout.addStretch()
        self.right_panel.addTab(tools_tab, "أدوات")

        # ── Tab 3: Save ──
        save_tab = QWidget()
        save_layout = QVBoxLayout(save_tab)
        save_layout.setSpacing(8)

        self.save_btn = QPushButton("💾 حفظ الصورة الحالية")
        self.save_btn.setObjectName("primaryBtn")
        save_layout.addWidget(self.save_btn)

        self.save_all_btn = QPushButton("📁 حفظ جميع الصور")
        self.save_all_btn.setObjectName("toolBtn")
        save_layout.addWidget(self.save_all_btn)

        self.auto_save_cb = QCheckBox("حفظ تلقائي بعد المعالجة")
        save_layout.addWidget(self.auto_save_cb)

        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("مجلد الحفظ:"))
        self.output_dir_label = QLabel("(افتراضي: processed/)")
        self.output_dir_label.setWordWrap(True)
        dir_layout.addWidget(self.output_dir_label, stretch=1)
        self.dir_select_btn = QPushButton("📁")
        self.dir_select_btn.setFixedWidth(40)
        dir_layout.addWidget(self.dir_select_btn)
        save_layout.addLayout(dir_layout)

        save_layout.addStretch()
        self.right_panel.addTab(save_tab, "حفظ")

        # ── Tab 4: AI / Learning ──
        ai_tab = QWidget()
        ai_layout = QVBoxLayout(ai_tab)
        ai_layout.setSpacing(8)

        self.ai_stats_label = QLabel("عينات التدريب: 0")
        ai_layout.addWidget(self.ai_stats_label)

        self.ai_suggest_btn = QPushButton("🤖 اقتراح ذكي")
        self.ai_suggest_btn.setObjectName("toolBtn")
        ai_layout.addWidget(self.ai_suggest_btn)

        self.ai_train_btn = QPushButton("📚 تدريب على الصورة الحالية")
        self.ai_train_btn.setObjectName("toolBtn")
        ai_layout.addWidget(self.ai_train_btn)

        ai_layout.addStretch()
        self.right_panel.addTab(ai_tab, "ذكاء")

        # ── Tab 5: Page number region ──
        ocr_tab = QWidget()
        ocr_layout = QVBoxLayout(ocr_tab)
        ocr_layout.setSpacing(8)

        self.ocr_select_btn = QPushButton("🔲 اختيار منطقة رقم الصفحة")
        self.ocr_select_btn.setObjectName("toolBtn")
        ocr_layout.addWidget(self.ocr_select_btn)

        self.ocr_test_btn = QPushButton("🔬 اختبار OCR")
        self.ocr_test_btn.setObjectName("toolBtn")
        ocr_layout.addWidget(self.ocr_test_btn)

        self.ocr_result_label = QLabel("النتيجة: -")
        self.ocr_result_label.setWordWrap(True)
        ocr_layout.addWidget(self.ocr_result_label)

        ocr_layout.addStretch()
        self.right_panel.addTab(ocr_tab, "منطقة رقم الصفحة")

    # ----------------------------------------------------------------

    def _create_bottom_panel(self):
        """Create the bottom panel with log, progress, and status."""
        self.bottom_layout = QHBoxLayout()
        self.bottom_layout.setSpacing(6)

        # Log
        log_group = QGroupBox("السجل")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(140)
        log_layout.addWidget(self.log_text)
        self.bottom_layout.addWidget(log_group, stretch=3)

        # Progress + status
        right_group = QWidget()
        right_v = QVBoxLayout(right_group)
        right_v.setContentsMargins(0, 0, 0, 0)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        right_v.addWidget(self.progress_bar)

        status_grid = QGridLayout()
        status_grid.addWidget(QLabel("الأبعاد:"), 0, 0)
        self.dim_label = QLabel("-")
        status_grid.addWidget(self.dim_label, 0, 1)

        status_grid.addWidget(QLabel("الوضوح:"), 1, 0)
        self.blur_label = QLabel("-")
        status_grid.addWidget(self.blur_label, 1, 1)

        status_grid.addWidget(QLabel("الجودة:"), 2, 0)
        self.quality_label_val = QLabel("-")
        status_grid.addWidget(self.quality_label_val, 2, 1)

        right_v.addLayout(status_grid)
        self.bottom_layout.addWidget(right_group, stretch=1)

    # ----------------------------------------------------------------

    def _connect_signals(self):
        """Connect all signals/slots."""
        # Processing controls
        self.rotation_combo.currentIndexChanged.connect(self._on_rotation_changed)
        self.crop_left_spin.valueChanged.connect(self._on_crop_changed)
        self.crop_top_spin.valueChanged.connect(self._on_crop_changed)
        self.crop_right_spin.valueChanged.connect(self._on_crop_changed)
        self.crop_bottom_spin.valueChanged.connect(self._on_crop_changed)
        self.deskew_slider.valueChanged.connect(self._on_deskew_slider)
        self.flip_cb.toggled.connect(self._on_flip_toggled)
        self.sharpen_cb.toggled.connect(self._on_sharpen_toggled)
        self.shadow_cb.toggled.connect(self._on_shadow_toggled)
        self.gray_slider.valueChanged.connect(self._on_gray_threshold)

        # Buttons
        self.apply_btn.clicked.connect(self._apply_processing)
        self.clear_btn.clicked.connect(self._clear_processing)
        self.undo_btn.clicked.connect(self._undo)
        self.redo_btn.clicked.connect(self._redo)

        # Tools tab
        self.auto_deskew_btn2.clicked.connect(self._apply_auto_deskew)
        self.smart_crop_btn2.clicked.connect(self._smart_crop)
        self.compare_btn.clicked.connect(self._compare_before_after)
        self.quality_btn.clicked.connect(self._assess_quality)

        # Save tab
        self.save_btn.clicked.connect(self._save_current)
        self.save_all_btn.clicked.connect(self._save_all_processed)
        self.auto_save_cb.stateChanged.connect(lambda s: self.auto_save_cb_toolbar.setChecked(s == Qt.Checked))
        self.dir_select_btn.clicked.connect(self._select_output_dir)

        # AI tab
        self.ai_suggest_btn.clicked.connect(self._show_ai_suggestion)
        self.ai_train_btn.clicked.connect(self._train_on_current)

        # OCR tab
        self.ocr_select_btn.clicked.connect(self._select_page_number_region)
        self.ocr_test_btn.clicked.connect(self._test_page_number_region)

        # Batch timer
        self._batch_timer.timeout.connect(self._process_next_batch)

    # ====================================================================
    # File I/O
    # ====================================================================

    def open_files(self):
        """Open one or more image files via file dialog."""
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "فتح ملفات الصور",
            "",
            "الصور (*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.webp);;PDF (*.pdf);;جميع الملفات (*)",
        )
        if not paths:
            return
        # Separate PDF files
        pdf_paths = [p for p in paths if p.lower().endswith('.pdf')]
        img_paths = [p for p in paths if not p.lower().endswith('.pdf')]
        self._load_images(img_paths)
        for pdf_path in pdf_paths:
            self._open_pdf(path=pdf_path)

    def open_folder(self):
        """Open all images in a folder."""
        folder = QFileDialog.getExistingDirectory(self, "فتح مجلد الصور")
        if not folder:
            return
        extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'}
        paths = sorted([
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in extensions
        ])
        if paths:
            self._load_images(paths)
        else:
            self._log("لا توجد صور في المجلد المحدد.")

    def _open_pdf(self, path: str = None):
        """Open a PDF file and load its pages as images."""
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "فتح ملف PDF", "", "PDF (*.pdf)"
            )
        if not path or not HAS_PDF2IMAGE:
            if path and not HAS_PDF2IMAGE:
                self._log("خطأ: pdf2image غير مثبت. قم بتثبيته: pip install pdf2image")
            return
        self._log(f"جاري تحميل PDF: {os.path.basename(path)}")
        QApplication.processEvents()
        images = load_pdf_as_images(path)
        if not images:
            self._log("لم يتم تحميل أي صفحة من PDF.")
            return
        # Save as temporary images and load them
        tmp_dir = os.path.join(os.path.dirname(path), "_pdf_cache")
        os.makedirs(tmp_dir, exist_ok=True)
        saved_paths = []
        for i, img in enumerate(images):
            out_path = os.path.join(tmp_dir, f"{os.path.basename(path)}_page_{i + 1}.png")
            cv2.imwrite(out_path, img)
            saved_paths.append(out_path)
        self._load_images(saved_paths)
        self._log(f"تم تحميل {len(images)} صفحة من PDF.")

    def _load_images(self, paths: List[str]):
        """Load a list of image file paths as LazyImage objects."""
        if not paths:
            return
        # Release old images
        for lazy in self.image_list:
            lazy.release()

        start_idx = len(self.image_list)
        for p in paths:
            self.image_list.append(LazyImage(p))

        self._log(f"تم تحميل {len(paths)} صورة. المجموع: {len(self.image_list)}")

        # Generate thumbnails in background
        items = [(start_idx + i, self.image_list[start_idx + i]) for i in range(len(paths))]
        self._thumb_worker = ThumbnailWorker(items, self)
        self._thumb_worker.thumb_ready.connect(self._on_thumb_ready)
        self._thumb_worker.start()

        # Auto-select first image if nothing selected
        if self.current_idx < 0:
            self._select_image(0)

    def _select_image(self, idx: int):
        """Select an image by index and update the preview."""
        if idx < 0 or idx >= len(self.image_list):
            return
        self.current_idx = idx
        self.current_img = self.image_list[idx].array
        self._clear_processing()
        # Highlight selected thumbnail
        for i in range(self.left_layout.count()):
            widget = self.left_layout.itemAt(i).widget()
            if isinstance(widget, ThumbButton):
                widget.setChecked(widget.idx == idx)
        self._update_preview()
        self._update_status()

    # ====================================================================
    # Processing
    # ====================================================================

    def _update_preview(self):
        """Apply current processing parameters and display the result."""
        if self._mutex.tryLock():
            self._is_processing = True
            try:
                if self.current_img is None:
                    self.image_label.setText("لا توجد صورة مفتوحة")
                    self.image_label.setPixmap(QPixmap())
                    return

                params = self.current_params
                processed = apply_processing(
                    self.current_img,
                    rotation=params["rotation"],
                    crop=params["crop"],
                    deskew_angle=params["deskew_angle"],
                    flip_h=params["flip_h"],
                    sharpen=params["sharpen"],
                    remove_shadow=params["remove_shadow"],
                    gray_threshold=self.gray_threshold,
                )

                pixmap = cv2_to_pixmap(processed)
                if pixmap.isNull():
                    self._log("خطأ: فشل تحويل الصورة.")
                    return

                # Apply zoom
                if self._zoom_level != 1.0:
                    new_w = int(pixmap.width() * self._zoom_level)
                    new_h = int(pixmap.height() * self._zoom_level)
                    pixmap = pixmap.scaled(
                        new_w, new_h,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation if self._zoom_level < 1.0 else Qt.FastTransformation,
                    )

                self.image_label.setPixmap(pixmap)
                self.image_label.setText("")
            finally:
                self._is_processing = False
                self._mutex.unlock()
        else:
            QTimer.singleShot(50, self._update_preview)

    def _update_status(self):
        """Update status bar information."""
        if self.current_img is None:
            self.dim_label.setText("-")
            self.blur_label.setText("-")
            self.quality_label_val.setText("-")
            return

        h, w = self.current_img.shape[:2]
        self.dim_label.setText(f"{w} × {h}")

        blur = calc_blur(self.current_img)
        self.blur_label.setText(f"{blur:.1f}")
        self.quality_label_val.setText(quality_label(blur, self.blur_threshold))

    # ====================================================================
    # Undo / Redo
    # ====================================================================

    def _push_undo(self):
        """Save current parameters to undo stack."""
        state = {
            "params": self.current_params.copy(),
            "gray_threshold": self.gray_threshold,
            "idx": self.current_idx,
        }
        state["params"]["crop"] = tuple(state["params"]["crop"])
        self.undo_stack.append(state)
        self.redo_stack.clear()
        self._log("تم حفظ الحالة (تراجع)")

    def _undo(self):
        """Undo the last operation."""
        if not self.undo_stack:
            self._log("لا يوجد إجراء للتراجع عنه.")
            return
        # Save current state to redo
        current_state = {
            "params": self.current_params.copy(),
            "gray_threshold": self.gray_threshold,
            "idx": self.current_idx,
        }
        current_state["params"]["crop"] = tuple(current_state["params"]["crop"])
        self.redo_stack.append(current_state)

        # Restore previous state
        state = self.undo_stack.pop()
        if state["idx"] == self.current_idx:
            self.current_params = state["params"].copy()
            self.gray_threshold = state["gray_threshold"]
            self._sync_ui_from_params()
            self._update_preview()
            self._log("تم التراجع.")
        else:
            # Navigate to the image first
            self._select_image(state["idx"])
            self.current_params = state["params"].copy()
            self.gray_threshold = state["gray_threshold"]
            self._sync_ui_from_params()
            self._update_preview()
            self._log("تم التراجع (مع التبديل للصورة).")

    def _redo(self):
        """Redo the last undone operation."""
        if not self.redo_stack:
            self._log("لا يوجد إجراء للإعادة.")
            return
        # Save current state to undo
        current_state = {
            "params": self.current_params.copy(),
            "gray_threshold": self.gray_threshold,
            "idx": self.current_idx,
        }
        current_state["params"]["crop"] = tuple(current_state["params"]["crop"])
        self.undo_stack.append(current_state)

        state = self.redo_stack.pop()
        if state["idx"] != self.current_idx:
            self._select_image(state["idx"])
        self.current_params = state["params"].copy()
        self.gray_threshold = state["gray_threshold"]
        self._sync_ui_from_params()
        self._update_preview()
        self._log("تمت الإعادة.")

    def _sync_ui_from_params(self):
        """Synchronize UI widgets with current_params."""
        p = self.current_params
        # Rotation
        rot_map = {0: 0, 90: 1, 180: 2, 270: 3}
        self.rotation_combo.setCurrentIndex(rot_map.get(p["rotation"], 0))
        # Crop
        left, top, right, bottom = p["crop"]
        self.crop_left_spin.setValue(left)
        self.crop_top_spin.setValue(top)
        self.crop_right_spin.setValue(right)
        self.crop_bottom_spin.setValue(bottom)
        # Deskew
        self.deskew_slider.setValue(int(p["deskew_angle"] * 100))
        # Options
        self.flip_cb.setChecked(p["flip_h"])
        self.sharpen_cb.setChecked(p["sharpen"])
        self.shadow_cb.setChecked(p["remove_shadow"])
        # Gray threshold
        self.gray_slider.setValue(self.gray_threshold)

    def _clear_processing(self):
        """Reset all processing parameters to defaults."""
        self._push_undo()
        self.current_params = {
            "rotation": 0,
            "crop": (0, 0, 0, 0),
            "deskew_angle": 0.0,
            "flip_h": False,
            "sharpen": False,
            "remove_shadow": False,
        }
        self.gray_threshold = 200
        self._sync_ui_from_params()
        self._update_preview()
        self._log("تم إعادة تعيين المعالجة.")

    # ====================================================================
    # Processing parameter change handlers
    # ====================================================================

    def _on_rotation_changed(self, value):
        """Handle rotation combo change."""
        rot_values = [0, 90, 180, 270]
        self.current_params["rotation"] = rot_values[value]
        self._update_preview()

    def _on_crop_changed(self):
        """Handle any crop spinbox change."""
        self.current_params["crop"] = (
            self.crop_left_spin.value(),
            self.crop_top_spin.value(),
            self.crop_right_spin.value(),
            self.crop_bottom_spin.value(),
        )
        self._update_preview()

    def _on_deskew_slider(self, value):
        """Handle deskew slider change."""
        angle = value / 100.0
        self.current_params["deskew_angle"] = angle
        self.deskew_label.setText(f"{angle:.2f}°")
        self._update_preview()

    def _on_flip_toggled(self, checked):
        """Handle flip checkbox."""
        self.current_params["flip_h"] = checked
        self._update_preview()

    def _on_sharpen_toggled(self, checked):
        """Handle sharpen checkbox."""
        self.current_params["sharpen"] = checked
        self._update_preview()

    def _on_shadow_toggled(self, checked):
        """Handle shadow removal checkbox."""
        self.current_params["remove_shadow"] = checked
        self._update_preview()

    def _on_gray_threshold(self, value):
        """Handle gray threshold slider."""
        self.gray_threshold = value
        self.gray_label_val.setText(str(value))
        if self.current_params["remove_shadow"]:
            self._update_preview()

    # ====================================================================
    # Auto deskew
    # ====================================================================

    def _apply_auto_deskew(self):
        """Start skew angle detection in a background thread."""
        if self.current_img is None:
            self._log("لا توجد صورة مفتوحة.")
            return
        if self._skew_worker is not None and self._skew_worker.isRunning():
            self._log("جاري الكشف بالفعل...")
            return
        self._log("جاري كشف زاوية الميل...")
        QApplication.processEvents()
        self._push_undo()
        self._skew_worker = SkewWorker(self.current_img, self)
        self._skew_worker.finished.connect(self._on_auto_skew_done)
        self._skew_worker.error.connect(self._on_auto_skew_err)
        self._skew_worker.start()

    def _on_auto_skew_done(self, angle: float):
        """Handle auto-skew result."""
        self._detected_angle = angle
        self.current_params["deskew_angle"] = angle
        self.deskew_slider.setValue(int(angle * 100))
        self._log(f"زاوية الميل المكتشفة: {angle:.2f}°")
        self._update_preview()

    def _on_auto_skew_err(self, msg: str):
        """Handle auto-skew error."""
        self._log(f"خطأ في كشف الميل: {msg}")

    # ====================================================================
    # Smart crop
    # ====================================================================

    def _smart_crop(self):
        """Apply smart auto crop to the current image."""
        if self.current_img is None:
            self._log("لا توجد صورة مفتوحة.")
            return
        self._push_undo()
        bounds = smart_auto_crop(self.current_img)
        self.current_params["crop"] = bounds
        self.crop_left_spin.setValue(bounds[0])
        self.crop_top_spin.setValue(bounds[1])
        self.crop_right_spin.setValue(bounds[2])
        self.crop_bottom_spin.setValue(bounds[3])
        self._log(f"قص ذكي: يسار={bounds[0]} أعلى={bounds[1]} يمين={bounds[2]} أسفل={bounds[3]}")
        self._update_preview()

    # ====================================================================
    # Compare / Quality
    # ====================================================================

    def _apply_processing(self):
        """Alias for _update_preview (explicit apply button)."""
        self._push_undo()
        self._update_preview()
        self._log("تم تطبيق المعالجة.")

    def _compare_before_after(self):
        """Show a dialog comparing original and processed image."""
        if self.current_img is None:
            self._log("لا توجد صورة مفتوحة.")
            return
        before_pixmap = cv2_to_pixmap(self.current_img)
        processed = apply_processing(
            self.current_img,
            rotation=self.current_params["rotation"],
            crop=self.current_params["crop"],
            deskew_angle=self.current_params["deskew_angle"],
            flip_h=self.current_params["flip_h"],
            sharpen=self.current_params["sharpen"],
            remove_shadow=self.current_params["remove_shadow"],
            gray_threshold=self.gray_threshold,
        )
        after_pixmap = cv2_to_pixmap(processed)
        dlg = CompareDialog(before_pixmap, after_pixmap, self)
        dlg.exec_()

    def _assess_quality(self):
        """Assess and display quality metrics for the current image."""
        if self.current_img is None:
            self._log("لا توجد صورة مفتوحة.")
            return
        metrics = assess_image_quality(self.current_img)
        msg = (
            f"تقييم جودة الصورة\n"
            f"{'=' * 30}\n"
            f"وضوح الصورة: {metrics['blur_score']:.1f}\n"
            f"السطوع: {metrics['brightness']:.1f}\n"
            f"التباين: {metrics['contrast']:.1f}\n"
            f"التشويش: {metrics['noise']:.2f}\n"
            f"الحدة: {metrics['sharpness']:.2f}\n"
            f"{'=' * 30}\n"
            f"التقييم العام: {metrics['quality_label']}"
        )
        QMessageBox.information(self, "تقييم الجودة", msg)
        self._log(f"تقييم الجودة: {metrics['quality_label']} (وضوح={metrics['blur_score']:.1f})")

    # ====================================================================
    # Save / Output
    # ====================================================================

    def _select_output_dir(self):
        """Let user select an output directory."""
        directory = QFileDialog.getExistingDirectory(self, "اختر مجلد الحفظ")
        if directory:
            self._output_dir = directory
            self.output_dir_label.setText(directory)
            self._log(f"مجلد الحفظ: {directory}")

    def _save_current(self):
        """Save the current processed image."""
        if self.current_img is None:
            self._log("لا توجد صورة مفتوحة.")
            return

        processed = apply_processing(
            self.current_img,
            rotation=self.current_params["rotation"],
            crop=self.current_params["crop"],
            deskew_angle=self.current_params["deskew_angle"],
            flip_h=self.current_params["flip_h"],
            sharpen=self.current_params["sharpen"],
            remove_shadow=self.current_params["remove_shadow"],
            gray_threshold=self.gray_threshold,
        )

        # Determine output directory
        if self._output_dir:
            output_dir = self._output_dir
        else:
            source_dir = os.path.dirname(self.image_list[self.current_idx].path)
            output_dir = os.path.join(source_dir, "processed")

        os.makedirs(output_dir, exist_ok=True)

        # Try to detect page number for smart naming
        page_num = None
        if self._ocr_regions and self.current_idx < len(self._ocr_regions):
            region = self._ocr_regions[self.current_idx]
            page_num = extract_page_number(self.current_img, region)
        if page_num is None:
            page_num = extract_page_number(processed)

        if page_num is not None:
            filename = f"page_{page_num:04d}.png"
        else:
            base = os.path.splitext(self.image_list[self.current_idx].name)[0]
            filename = f"{base}_processed.png"

        save_path = os.path.join(output_dir, filename)
        save_path = self._get_unique_path(os.path.dirname(save_path), os.path.basename(save_path), ".png")

        # Check for similar already saved
        if page_num is not None and page_num in self.page_registry:
            existing_path = self.page_registry[page_num]
            if os.path.exists(existing_path):
                existing_img = cv2.imread(existing_path)
                if existing_img is not None and images_are_similar(processed, existing_img):
                    self._log(f"تم تخطي {filename} – صورة مشابهة محفوظة مسبقاً.")
                    return

        success = cv2.imwrite(save_path, processed)
        if success:
            if page_num is not None:
                self.page_registry[page_num] = save_path
            self._log(f"تم الحفظ: {save_path}")
        else:
            self._log(f"خطأ في حفظ: {save_path}")

    def _get_unique_path(self, base_dir: str, filename: str, ext: str) -> str:
        """Generate a unique file path by appending _N if needed."""
        name, _ = os.path.splitext(filename)
        path = os.path.join(base_dir, name + ext)
        counter = 1
        while os.path.exists(path):
            path = os.path.join(base_dir, f"{name}_{counter}{ext}")
            counter += 1
        return path

    def _save_all_processed(self):
        """Batch save all images with smart crop and auto deskew."""
        if not self.image_list:
            self._log("لا توجد صور للحفظ.")
            return

        reply = QMessageBox.question(
            self,
            "حفظ جميع الصور",
            f"هل تريد حفظ ومعالجة جميع الصور ({len(self.image_list)} صورة)؟\n"
            "سيتم تطبيق القص الذكي والتصحيح التلقائي.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._batch_queue = list(range(len(self.image_list)))
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self._batch_queue))
        self.progress_bar.setValue(0)
        self._set_controls_enabled(False)
        self._batch_timer.start(100)
        self._log(f"بدء المعالجة الدفعية: {len(self._batch_queue)} صورة...")

    def _confirm_save(self):
        """Auto-save with confirmation."""
        if self._auto_save_in_prog:
            return
        self._auto_save_in_prog = True
        try:
            self._save_current()
            if self.auto_save_cb.isChecked():
                # Try to move processed image to output dir
                pass  # Save is already done in _save_current
        finally:
            self._auto_save_in_prog = False

    def _safe_move(self, src: str, dst_dir: str):
        """Safely move a file to a directory."""
        if not os.path.exists(src):
            return False
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, os.path.basename(src))
        dst = self._get_unique_path(dst_dir, os.path.basename(src), os.path.splitext(src)[1])
        try:
            shutil.move(src, dst)
            return True
        except Exception as e:
            self._log(f"خطأ في نقل الملف: {e}")
            return False

    def _on_auto_save_toggle(self, checked: bool):
        """Handle auto-save checkbox toggle."""
        self.auto_save_cb_toolbar.blockSignals(True)
        self.auto_save_cb_toolbar.setChecked(checked)
        self.auto_save_cb_toolbar.blockSignals(False)
        self._log(f"الحفظ التلقائي: {'مفعّل' if checked else 'معطّل'}")

    # ====================================================================
    # OCR Region
    # ====================================================================

    def _select_page_number_region(self):
        """Open a dialog to select the page number region on the current image."""
        if self.current_img is None:
            self._log("لا توجد صورة مفتوحة.")
            return
        pixmap = cv2_to_pixmap(self.current_img)
        dlg = RegionSelectorDialog(pixmap, self)
        if dlg.exec_() == QDialog.Accepted and dlg.selected_region is not None:
            region = dlg.selected_region
            # Store for this image (and as default for all)
            while len(self._ocr_regions) <= self.current_idx:
                self._ocr_regions.append(None)
            self._ocr_regions[self.current_idx] = region
            self._log(f"تم تحديد منطقة رقم الصفحة: x={region[0]} y={region[1]} w={region[2]} h={region[3]}")

    def _test_page_number_region(self):
        """Test OCR on the selected page number region."""
        if self.current_img is None:
            self._log("لا توجد صورة مفتوحة.")
            return
        if not HAS_TESSERACT:
            self._log("خطأ: pytesseract غير مثبت.")
            self.ocr_result_label.setText("النتيجة: pytesseract غير مثبت")
            return

        region = None
        if self.current_idx < len(self._ocr_regions):
            region = self._ocr_regions[self.current_idx]

        page_num = extract_page_number(self.current_img, region)
        if page_num is not None:
            self.ocr_result_label.setText(f"النتيجة: رقم الصفحة = {page_num}")
            self._log(f"OCR: رقم الصفحة = {page_num}")
        else:
            self.ocr_result_label.setText("النتيجة: لم يتم الكشف عن رقم صفحة")
            self._log("OCR: لم يتم الكشف عن رقم صفحة")

    # ====================================================================
    # Batch processing
    # ====================================================================

    def _start_batch(self):
        """Start batch processing on all loaded images."""
        if not self.image_list:
            self._log("لا توجد صور للمعالجة.")
            return
        self._batch_queue = list(range(len(self.image_list)))
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self._batch_queue))
        self.progress_bar.setValue(0)
        self._set_controls_enabled(False)
        self._batch_timer.start(100)
        self._log(f"بدء المعالجة الدفعية: {len(self._batch_queue)} صورة...")

    def _process_next_batch(self):
        """Process the next image in the batch queue."""
        if not self._batch_queue:
            self._cancel_batch()
            self._log("تم الانتهاء من المعالجة الدفعية ✓")
            QMessageBox.information(self, "انتهت المعالجة", "تم الانتهاء من معالجة جميع الصور.")
            return

        idx = self._batch_queue.pop(0)
        self.progress_bar.setValue(self.progress_bar.maximum() - len(self._batch_queue))

        try:
            img = self.image_list[idx].array
            if img is None:
                self._log(f"⚠ تخطي صورة {idx + 1}: لا يمكن القراءة")
                return

            # Auto deskew
            angle = auto_detect_skew(img)
            # Smart crop
            crop = smart_auto_crop(img)
            # Apply
            processed = apply_processing(
                img,
                rotation=0,
                crop=crop,
                deskew_angle=angle,
                flip_h=False,
                sharpen=False,
                remove_shadow=True,
                gray_threshold=self.gray_threshold,
            )

            # Save
            if self._output_dir:
                output_dir = self._output_dir
            else:
                output_dir = os.path.join(
                    os.path.dirname(self.image_list[idx].path), "processed"
                )
            os.makedirs(output_dir, exist_ok=True)

            # Smart naming with page number
            page_num = extract_page_number(processed)
            if page_num is not None:
                filename = f"page_{page_num:04d}.png"
                if page_num in self.page_registry:
                    existing = self.page_registry[page_num]
                    if os.path.exists(existing):
                        existing_img = cv2.imread(existing)
                        if existing_img is not None and images_are_similar(processed, existing_img):
                            self._log(f"⚠ تخطي صورة {idx + 1} – مشابهة لصفحة {page_num}")
                            return
                self.page_registry[page_num] = os.path.join(output_dir, filename)
            else:
                base = os.path.splitext(self.image_list[idx].name)[0]
                filename = f"{base}_processed.png"

            save_path = os.path.join(output_dir, filename)
            save_path = self._get_unique_path(output_dir, filename, ".png")
            cv2.imwrite(save_path, processed)
            self._log(f"✓ صورة {idx + 1}/{len(self.image_list)}: {os.path.basename(save_path)}")

        except Exception as e:
            self._log(f"خطأ في صورة {idx + 1}: {e}")

        QApplication.processEvents()

    def _cancel_batch(self):
        """Cancel the batch processing timer."""
        self._batch_timer.stop()
        self._batch_queue.clear()
        self._set_controls_enabled(True)
        self.progress_bar.setVisible(False)

    def _set_controls_enabled(self, enabled: bool):
        """Enable or disable all processing controls."""
        for widget in [
            self.rotation_combo, self.crop_left_spin, self.crop_top_spin,
            self.crop_right_spin, self.crop_bottom_spin, self.deskew_slider,
            self.flip_cb, self.sharpen_cb, self.shadow_cb, self.gray_slider,
            self.apply_btn, self.clear_btn, self.undo_btn, self.redo_btn,
            self.auto_deskew_btn2, self.smart_crop_btn2, self.compare_btn,
            self.quality_btn, self.save_btn, self.save_all_btn,
            self.ai_suggest_btn, self.ai_train_btn,
            self.ocr_select_btn, self.ocr_test_btn,
            self.auto_deskew_btn, self.smart_crop_btn,
        ]:
            widget.setEnabled(enabled)

    # ====================================================================
    # AI / Learning
    # ====================================================================

    def _show_ai_suggestion(self):
        """Show AI-based parameter suggestion for current image."""
        if self.current_img is None:
            self._log("لا توجد صورة مفتوحة.")
            return
        if not self._learner.is_trained:
            self._log("النظام الذكي غير مدرب بعد. أضف عينات تدريب أولاً.")
            QMessageBox.information(
                self, "النظام الذكي",
                "النظام الذكي غير مدرب بعد.\n"
                "استخدم 'تدريب على الصورة الحالية' لإضافة عينات.",
            )
            return

        features = ImageFeatureExtractor.extract(self.current_img)
        suggestion = self._learner.predict(features)
        if suggestion is None:
            self._log("لم يتم الحصول على اقتراح.")
            return

        msg = (
            f"اقتراح ذكي:\n"
            f"{'=' * 25}\n"
            f"التدوير: {suggestion['rotation']}°\n"
            f"القص: {suggestion['crop']}\n"
            f"الميل: {suggestion['deskew_angle']:.2f}°\n"
            f"قلب أفقي: {'نعم' if suggestion['flip_h'] else 'لا'}\n"
            f"الحدة: {'نعم' if suggestion['sharpen'] else 'لا'}\n"
            f"إزالة الظلال: {'نعم' if suggestion['remove_shadow'] else 'لا'}\n"
        )
        reply = QMessageBox.question(
            self, "اقتراح ذكي",
            msg + "\nهل تريد تطبيق هذا الاقتراح؟",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._push_undo()
            self.current_params.update(suggestion)
            self._sync_ui_from_params()
            self._update_preview()
            self._log("تم تطبيق الاقتراح الذكي.")

    def _train_on_current(self):
        """Train the learning system on the current image and its params."""
        if self.current_img is None:
            self._log("لا توجد صورة مفتوحة.")
            return

        features = ImageFeatureExtractor.extract(self.current_img)
        params = self.current_params.copy()
        # Flatten crop for training
        crop = params["crop"]
        flat_params = {
            "rotation": float(params["rotation"]),
            "deskew_angle": params["deskew_angle"],
            "flip_h": float(params["flip_h"]),
            "sharpen": float(params["sharpen"]),
            "remove_shadow": float(params["remove_shadow"]),
            "crop_left": float(crop[0]),
            "crop_top": float(crop[1]),
            "crop_right": float(crop[2]),
            "crop_bottom": float(crop[3]),
        }
        self._trainer.add_sample(features, flat_params)
        self._learner.train(self._trainer.get_data())
        self.ai_stats_label.setText(f"عينات التدريب: {self._trainer.count}")
        self._log(f"تم إضافة عينة تدريب. المجموع: {self._trainer.count}")

    # ====================================================================
    # Zoom
    # ====================================================================

    def _zoom_in(self):
        """Zoom in the image preview."""
        self._zoom_level = min(self._zoom_level * 1.25, 5.0)
        self._update_preview()
        self._log(f"التكبير: {self._zoom_level:.1f}x")

    def _zoom_out(self):
        """Zoom out the image preview."""
        self._zoom_level = max(self._zoom_level / 1.25, 0.1)
        self._update_preview()
        self._log(f"التصغير: {self._zoom_level:.1f}x")

    def _zoom_fit(self):
        """Reset zoom to fit the view."""
        self._zoom_level = 1.0
        self._update_preview()
        self._log("تم ملاءمة الصورة.")

    # ====================================================================
    # Thumbnail handling
    # ====================================================================

    def _on_thumb_ready(self, idx: int, pixmap: QPixmap):
        """Receive a thumbnail from the worker thread and display it."""
        # Check if ThumbButton already exists for this index
        existing = None
        for i in range(self.left_layout.count()):
            widget = self.left_layout.itemAt(i).widget()
            if isinstance(widget, ThumbButton) and widget.idx == idx:
                existing = widget
                break

        if existing is None:
            btn = ThumbButton(idx, self)
            btn.setPixmap(pixmap.scaled(90, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            # Connect the custom signal
            btn.clicked_idx.connect(self._select_image)
            self.left_layout.addWidget(btn)
        else:
            existing.setPixmap(pixmap.scaled(90, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # Ensure selected state is correct
        if idx == self.current_idx:
            for i in range(self.left_layout.count()):
                widget = self.left_layout.itemAt(i).widget()
                if isinstance(widget, ThumbButton):
                    widget.setChecked(widget.idx == idx)

    # ====================================================================
    # Logging
    # ====================================================================

    def _log(self, msg: str):
        """Add a timestamped message to the log text area."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {msg}")
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        logger.info(msg)

    # ====================================================================
    # About
    # ====================================================================

    def _show_about(self):
        """Show the about dialog."""
        QMessageBox.about(
            self,
            "حول البرنامج",
            "معالج المستندات الطبية\n"
            "الإصدار 16 (نهائي)\n\n"
            "برنامج لمعالجة صور المستندات الطبية\n"
            "يدعم: التدوير، القص، تصحيح الميل، إزالة الظلال،\n"
            "التعرف على رقم الصفحة، والمعالجة الدفعية.\n\n"
            "ال مكتبات المطلوبة:\n"
            "PyQt5, opencv-python, numpy\n"
            "(اختياري: pytesseract, pdf2image, imagehash)",
        )

    # ====================================================================
    # Event handlers
    # ====================================================================

    def closeEvent(self, event):
        """Handle window close: stop workers, cleanup."""
        # Stop batch timer
        if self._batch_timer.isActive():
            self._cancel_batch()
        # Wait for workers to finish
        if self._thumb_worker is not None and self._thumb_worker.isRunning():
            self._thumb_worker.quit()
            self._thumb_worker.wait(2000)
        if self._skew_worker is not None and self._skew_worker.isRunning():
            self._skew_worker.quit()
            self._skew_worker.wait(2000)
        # Release images
        for lazy in self.image_list:
            lazy.release()
        self._log("تم إغلاق البرنامج.")
        event.accept()

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        key = event.key()
        modifiers = event.modifiers()

        if modifiers & Qt.ControlModifier:
            if key == Qt.Key_Z:
                self._undo()
                return
            elif key == Qt.Key_Y:
                self._redo()
                return
            elif key == Qt.Key_S:
                self._save_current()
                return
            elif key == Qt.Key_O:
                self.open_files()
                return

        # Arrow keys for navigation
        if key == Qt.Key_Left and self.current_idx > 0:
            self._select_image(self.current_idx - 1)
            return
        elif key == Qt.Key_Right and self.current_idx < len(self.image_list) - 1:
            self._select_image(self.current_idx + 1)
            return
        elif key == Qt.Key_Plus or key == Qt.Key_Equal:
            self._zoom_in()
            return
        elif key == Qt.Key_Minus:
            self._zoom_out()
            return

        super().keyPressEvent(event)

    # ====================================================================
    # Stylesheet
    # ====================================================================

    def _apply_stylesheet(self):
        """Apply a modern, clean stylesheet."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f2f5;
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 12px;
            }
            QWidget {
                font-family: 'Segoe UI', 'Arial', sans-serif;
                font-size: 12px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
                background-color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
                color: #374151;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 6px 14px;
                min-height: 20px;
                color: #1f2937;
            }
            QPushButton:hover {
                background-color: #f3f4f6;
                border-color: #9ca3af;
            }
            QPushButton:pressed {
                background-color: #e5e7eb;
            }
            QPushButton:disabled {
                background-color: #f9fafb;
                color: #9ca3af;
                border-color: #e5e7eb;
            }
            QPushButton#primaryBtn {
                background-color: #16a34a;
                border-color: #16a34a;
                color: #ffffff;
                font-weight: bold;
            }
            QPushButton#primaryBtn:hover {
                background-color: #15803d;
            }
            QPushButton#toolBtn {
                background-color: #eff6ff;
                border-color: #bfdbfe;
                color: #1e40af;
            }
            QPushButton#toolBtn:hover {
                background-color: #dbeafe;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px 8px;
                min-height: 22px;
            }
            QComboBox:hover {
                border-color: #9ca3af;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                padding: 3px 6px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #e5e7eb;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #2563eb;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #1d4ed8;
            }
            QCheckBox {
                spacing: 6px;
                color: #1f2937;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #d1d5db;
                border-radius: 4px;
                background-color: #ffffff;
            }
            QCheckBox::indicator:checked {
                background-color: #16a34a;
                border-color: #16a34a;
            }
            QTabWidget::pane {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background-color: #f9fafb;
                border: 1px solid #d1d5db;
                border-bottom: none;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 8px 14px;
                margin-right: 2px;
                color: #6b7280;
            }
            QTabBar::tab:selected {
                background-color: #ffffff;
                color: #2563eb;
                font-weight: bold;
                border-bottom: 2px solid #2563eb;
            }
            QTabBar::tab:hover:!selected {
                background-color: #f3f4f6;
            }
            QScrollArea {
                border: 1px solid #e5e7eb;
                border-radius: 6px;
                background-color: #ffffff;
            }
            QTextEdit {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background-color: #fafafa;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                color: #374151;
            }
            QProgressBar {
                border: 1px solid #d1d5db;
                border-radius: 4px;
                text-align: center;
                background-color: #f3f4f6;
                min-height: 20px;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 4px;
            }
            QToolBar {
                background-color: #ffffff;
                border-bottom: 1px solid #e5e7eb;
                padding: 4px 8px;
                spacing: 6px;
            }
            QMenuBar {
                background-color: #ffffff;
                border-bottom: 1px solid #e5e7eb;
                color: #1f2937;
            }
            QMenuBar::item:selected {
                background-color: #eff6ff;
            }
            QMenu {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 30px 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
            QLabel {
                color: #1f2937;
            }
            ThumbButton {
                background-color: #ffffff;
                border: 2px solid #e5e7eb;
                border-radius: 6px;
                padding: 2px;
                min-width: 90px;
                min-height: 120px;
            }
            ThumbButton:checked {
                border-color: #2563eb;
                background-color: #eff6ff;
            }
            ThumbButton:hover {
                border-color: #93c5fd;
            }
        """)


# ===========================================================================
# Entry point
# ===========================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Set application-wide font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # High DPI support
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    window = MedicalDocApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
