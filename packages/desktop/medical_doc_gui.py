#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
معالج الوثائق الطبية التفاعلي - v12 (النسخة النهائية المدمجة)
═══════════════════════════════════════════════════════════════
الجديد في v12 (مدمج من medical_document_suite_merged):
  1. حفظ تلقائي تسلسلي بـ QTimer — الواجهة متجاوبة دائماً (لا تجميد)
  2. إلغاء عمليات الدُفعات في أي وقت (_batch_cancelled)
  3. تبديل ذكي للحفظ التلقائي مع سؤال المستخدم
  4. إدارة موحدة لتعطيل/تفعيل الأزرار (_set_controls_enabled)
  5. لقطات شاشة لأي ويدجت (_save_screenshot)
  6. حفظ ذكي مع OCR وترقيم الصفحات تلقائياً
  7. فتح مجلد النتائج بعد التحليل

موروث من v10.1:
  - LazyImage (تحميل كسول + كاش ذاكرة)
  - find_page_bounds + auto_detect_skew (إزالة الرمادي أولاً)
  - smart_auto_crop ثنائي المراحل (Vectorized)
  - _safe_move (cross-filesystem)
  - QMutex + _is_processing (منع Race Condition)
  - gray_threshold قابل للتعديل من الواجهة
  - logger موحّد (ملف + طرفية)
  - نظام تعلّم تكيفي KNN + TrainingDataCollector
  - OCR + كشف المكررات + تقييم الجودة
═══════════════════════════════════════════════════════════════
"""
import sys
import csv
import json
import re
import shutil
import subprocess
import logging
from collections import deque
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any, Union

import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QCheckBox, QProgressBar,
    QTextEdit, QFileDialog, QMessageBox, QGroupBox, QFormLayout,
    QSplitter, QDialog, QScrollArea, QSizePolicy, QTabWidget, QFrame,
    QInputDialog, QDialogButtonBox, QShortcut, QRubberBand,
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QMutex, QMutexLocker, QRect, QPoint
from PyQt5.QtGui import QPixmap, QImage, QFont, QKeySequence, QColor, QIcon, QPainter, QPen

# ── نظام التسجيل الموحّد ─────────────────────────────────────────
logger = logging.getLogger("MedicalDocApp")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    _fh = logging.FileHandler("medical_doc_app.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s"))
    logger.addHandler(_fh)
    _ch = logging.StreamHandler()
    _ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(_ch)

# PDF support (optional)
PDF_SUPPORT = False
try:
    from pdf2image import convert_from_path
    PDF_SUPPORT = True
except ImportError:
    pass

# OCR & Hash support (optional)
OCR_SUPPORT = False
HASH_SUPPORT = False
try:
    import pytesseract
    from PIL import Image as PILImage
    import imagehash
    OCR_SUPPORT = True
    HASH_SUPPORT = True
except ImportError:
    pass

IMG_EXT = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
ALL_EXT = IMG_EXT | ({".pdf"} if PDF_SUPPORT else set())
LOG_FILE = Path("processing_log.txt")
THUMB_W, THUMB_H = 90, 115
UNDO_LIMIT = 15


# ════════════════════════════════════════════════════════════════
#  LazyImage — تحميل عند الطلب، تخزين مؤقت، توفير الذاكرة
# ════════════════════════════════════════════════════════════════

class LazyImage:
    """
    يحمّل الصورة من القرص عند أول طلب فقط.
    يُخزّن مؤقتاً (cache) لتسريع الوصول المتكرر.
    يدعم Path (صور ملفات) و np.ndarray (صفحات PDF).
    """
    def __init__(self, source: Union[Path, np.ndarray], name: str = ""):
        self._path   = source if isinstance(source, Path) else None
        self._array  = source if isinstance(source, np.ndarray) else None
        self._cache: Optional[np.ndarray] = None
        self.name    = name if name else (source.name if isinstance(source, Path) else "array")

    # ── الخصائص الأساسية ──────────────────────────────────────
    @property
    def is_path(self) -> bool:
        return self._path is not None

    def exists(self) -> bool:
        return self._path.exists() if self._path else (self._array is not None)

    # ── الحصول على الصورة ──────────────────────────────────────
    def get(self) -> Optional[np.ndarray]:
        if self._cache is not None:
            return self._cache
        if self._array is not None:
            return self._array           # لا نُخزّن PDF pages في الكاش (تأتي محمّلة)
        if self._path and self._path.exists():
            self._cache = cv2.imread(str(self._path))
            if self._cache is None:
                logger.warning("LazyImage: فشل قراءة %s", self._path)
            return self._cache
        return None

    def clear_cache(self):
        """تحرير الذاكرة — ستُعاد القراءة عند الطلب التالي."""
        self._cache = None

    # ── تحديث المسار (بعد نقل الملف) ─────────────────────────
    def update_path(self, new_path: Path):
        self._path  = new_path
        self._cache = None               # أُعد القراءة من المسار الجديد

    def __repr__(self):
        return f"LazyImage({self.name})"



# ════════════════════════════════════════════════════════════════
#  Core Image Processing Functions
# ════════════════════════════════════════════════════════════════

def apply_processing(img: np.ndarray, params: dict) -> np.ndarray:
    """Full processing pipeline: rotation, crop, deskew, flip, sharpen, shadow removal."""
    out = img.copy()
    # 0. Rotation
    rotation = params.get("rotation", 0) % 360
    if rotation == 90:
        out = cv2.rotate(out, cv2.ROTATE_90_CLOCKWISE)
    elif rotation == 180:
        out = cv2.rotate(out, cv2.ROTATE_180)
    elif rotation == 270:
        out = cv2.rotate(out, cv2.ROTATE_90_COUNTERCLOCKWISE)
    # 1. Crop
    h, w = out.shape[:2]
    l, t, r, b = params.get("crop", (0, 0, 0, 0))
    r2, b2 = w - r, h - b
    if l < r2 and t < b2:
        out = out[t:b2, l:r2]
    # 2. Deskew
    angle = params.get("deskew_angle", 0.0)
    if abs(angle) > 0.05:
        ch, cw = out.shape[:2]
        M = cv2.getRotationMatrix2D((cw / 2, ch / 2), angle, 1.0)
        out = cv2.warpAffine(out, M, (cw, ch),
                             flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT,
                             borderValue=(255, 255, 255))
    # 3. Horizontal flip
    if params.get("flip_h", False):
        out = cv2.flip(out, 1)
    # 4. Sharpen (USM)
    if params.get("sharpen", False):
        blurred = cv2.GaussianBlur(out, (0, 0), 3)
        out = cv2.addWeighted(out, 1.5, blurred, -0.5, 0)
    # 5. Shadow removal
    if params.get("remove_shadow", False):
        out = _remove_shadow(out)
    return out


def _remove_shadow(img: np.ndarray) -> np.ndarray:
    """Remove shadow/uneven background using morphological operations."""
    planes = cv2.split(img)
    result = []
    for plane in planes:
        dilated = cv2.dilate(plane, np.ones((7, 7), np.uint8))
        bg = cv2.medianBlur(dilated, 21)
        diff = 255 - cv2.absdiff(plane, bg)
        normed = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)
        result.append(normed)
    return cv2.merge(result)


def cv2_to_pixmap(img: np.ndarray, zoom: float = 1.0, max_w: int = 0, max_h: int = 0) -> QPixmap:
    """Convert numpy image to QPixmap with optional zoom and max size."""
    h, w = img.shape[:2]
    if zoom != 1.0:
        nw, nh = int(w * zoom), int(h * zoom)
    else:
        nw, nh = w, h
    if max_w > 0 and nw > max_w:
        scale = max_w / nw
        nw, nh = int(nw * scale), int(nh * scale)
    if max_h > 0 and nh > max_h:
        scale = max_h / nh
        nw, nh = int(nw * scale), int(nh * scale)
    if nw != w or nh != h:
        small = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    else:
        small = img
    rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
    qimg = QImage(rgb.data, nw, nh, nw * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimg)


def calc_blur(img: np.ndarray) -> float:
    """Calculate blur score using Laplacian variance."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def quality_label(score: float, thr: float) -> Tuple[str, str, str]:
    """Return quality label, color, icon based on blur score and threshold."""
    if score >= thr * 2:
        return "ممتازة", "#16a34a", "✅"
    if score >= thr:
        return "مقبولة", "#d97706", "⚠️"
    return "ضبابية", "#dc2626", "❌"


def find_page_bounds(img: np.ndarray,
                     page_threshold: int = 200,
                     min_page_fraction: float = 0.25) -> tuple:
    """
    ═══════════════════════════════════════════════════════════════
    يجد حدود الصفحة البيضاء داخل خلفية الماسح الرمادية.

    يعمل على الأعمدة فقط (يمين/يسار) لأن:
    - الرمادي الرئيسي في الصور الممسوحة على الجانبين
    - تحليل الصفوف يُخطئ بسبب كثافة النص
      (صفوف النص الكثيف لها median < 200 مثل الخلفية الرمادية)

    المنطق:
    - الرمادي (الماسح): median الأعمدة ≈ 150–160  (<  page_threshold)
    - الصفحة البيضاء: median الأعمدة ≈ 254–255  (>  page_threshold)

    خوارزمية "أكبر كتلة متصلة" تتجنب الأعمدة البيضاء المزيفة
    (cols 0–10 بيضاء في بعض الصور ثم يبدأ الرمادي).

    يُرجع (l, 0, r, 0) — قص يسار/يمين فقط.
    ═══════════════════════════════════════════════════════════════
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    w    = gray.shape[1]
    col_p50 = np.median(gray, axis=0)       # (w,) median لكل عمود

    def _largest_block(signal: np.ndarray) -> tuple:
        n       = len(signal)
        is_page = np.concatenate([[False], signal > page_threshold, [False]])
        diff    = np.diff(is_page.astype(np.int8))
        starts  = np.where(diff == 1)[0]
        ends    = np.where(diff == -1)[0]
        if len(starts) == 0:
            return 0, n - 1
        lengths = ends - starts
        best    = int(np.argmax(lengths))
        if lengths[best] < min_page_fraction * n:
            return 0, n - 1         # لا صفحة واضحة → لا قص
        return int(starts[best]), int(ends[best]) - 1

    col_s, col_e = _largest_block(col_p50)
    MARGIN       = 5
    left         = max(0,   col_s - MARGIN)
    right        = min(w-1, col_e + MARGIN)
    return (left, 0, w - right - 1, 0)     # t=0, b=0


def auto_detect_skew(img: np.ndarray, max_a: float = 15.0, step: float = 0.5) -> float:
    """
    يكشف زاوية الميلان الحقيقية.
    ✅ يُزيل الحدود الرمادية أولاً → لا "زوايا خاطئة" من حواف الماسح.
    """
    # ── المرحلة 1: احصل على الصفحة النظيفة ────────────────────
    l, _t, r, _b = find_page_bounds(img)
    h, w = img.shape[:2]
    x0, x1 = l, w - r if r > 0 else w
    page = img[:, x0:x1] if (x1 > x0) else img

    # ── المرحلة 2: كشف الميلان على الصفحة النظيفة ─────────────
    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY) if page.ndim == 3 else page
    gray = cv2.equalizeHist(gray)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ph, pw = binary.shape
    best_score, best_angle = -1.0, 0.0
    for angle in np.arange(-max_a, max_a + step, step):
        M = cv2.getRotationMatrix2D((pw // 2, ph // 2), angle, 1.0)
        rot = cv2.warpAffine(binary, M, (pw, ph),
                             flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REPLICATE)
        score = float(np.var(np.sum(rot, axis=1)))
        if score > best_score:
            best_score, best_angle = score, float(angle)
    return best_angle


def smart_auto_crop(img: np.ndarray, padding: int = 15, dark_threshold: int = 200) -> tuple:
    """
    قص ذكي على مرحلتين — يحل مشكلة الرمادي كلياً:

    المرحلة 1 — find_page_bounds():
        يُزيل الحدود الرمادية للماسح (يمين/يسار)
        المنطق: الرمادي median ≈ 150–160 ≠ الصفحة ≈ 254–255

    المرحلة 2 — كشف المحتوى:
        يجد النص داخل الصفحة النظيفة (بكسلات أقل من dark_threshold)
        Vectorized numpy بدل حلقات Python → 100× أسرع
    """
    h, w = img.shape[:2]

    # المرحلة 1: إزالة الرمادي
    gl, gt, gr, gb = find_page_bounds(img)
    x0, x1 = gl, w - gr if gr > 0 else w
    if x1 <= x0:
        return (0, 0, 0, 0)
    page = img[:, x0:x1]
    pw = page.shape[1]

    # المرحلة 2: كشف المحتوى
    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY) if page.ndim == 3 else page
    _, binary = cv2.threshold(gray, dark_threshold, 255, cv2.THRESH_BINARY_INV)

    col_has = binary.max(axis=0) > 0       # (pw,) bool — أسرع بـ 100× من for
    row_has = binary.max(axis=1) > 0       # (h,)  bool

    content_cols = np.where(col_has)[0]
    content_rows = np.where(row_has)[0]

    if len(content_cols) == 0 or len(content_rows) == 0:
        return (gl, gt, gr, gb)             # فارغة: أرجع حدود الرمادي فقط

    cl = max(0,    content_cols[0]  - padding)
    cr = min(pw-1, content_cols[-1] + padding)
    ct = max(0,    content_rows[0]  - padding)
    cb = min(h-1,  content_rows[-1] + padding)

    return (max(0, gl + cl),
            max(0, gt + ct),
            max(0, gr + (pw - cr - 1)),
            max(0, gb + (h  - cb - 1)))



def load_pdf_as_images(pdf_path: str, dpi: int = 200) -> List[np.ndarray]:
    """Convert PDF pages to numpy images."""
    pages = convert_from_path(pdf_path, dpi=dpi)
    result = []
    for page in pages:
        arr = np.array(page)
        result.append(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    return result


# ════════════════════════════════════════════════════════════════
#  AI Helper Functions (OCR, Hash, Quality)
# ════════════════════════════════════════════════════════════════

def extract_page_number(img: np.ndarray, region=None, regions=None) -> int:
    """
    Extract page number using OCR.

    Args:
        img: BGR image (full page).
        region: Single region (x_frac, y_frac, w_frac, h_frac) as fractions.
        regions: List of regions for multi-location support.
        If both region and regions are None, searches default corners.
    """
    if not OCR_SUPPORT:
        return 0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Build list of regions to search
    search_regions = []

    if regions:
        # Multiple user-defined regions (for books with variable page number positions)
        for r in regions:
            x = int(r[0] * w)
            y = int(r[1] * h)
            rw = int(r[2] * w)
            rh = int(r[3] * h)
            if rw > 0 and rh > 0 and x < w and y < h:
                search_regions.append(gray[y:y+rh, x:x+rw])
    elif region:
        # Single user-defined region (backward compatibility)
        x = int(region[0] * w)
        y = int(region[1] * h)
        rw = int(region[2] * w)
        rh = int(region[3] * h)
        if rw > 0 and rh > 0 and x < w and y < h:
            search_regions.append(gray[y:y+rh, x:x+rw])
    else:
        # Default: search common page number locations
        bottom_strip_h = max(100, h // 10)
        top_strip_h = max(100, h // 10)
        # Bottom areas (most common)
        search_regions.append(gray[h - bottom_strip_h:h, :])  # أسفل كامل
        search_regions.append(gray[h - bottom_strip_h:h, w//3:2*w//3])  # أسفل وسط
        search_regions.append(gray[h - 150:h, w - 200:w])  # أسفل يمين
        search_regions.append(gray[h - 150:h, 0:200])  # أسفل يسار
        # Top areas (chapter starts, headers)
        search_regions.append(gray[0:top_strip_h, :])  # أعلى كامل
        search_regions.append(gray[0:top_strip_h, w//3:2*w//3])  # أعلى وسط
        search_regions.append(gray[0:150, w - 200:w])  # أعلى يمين
        search_regions.append(gray[0:150, 0:200])  # أعلى يسار

    best_number = 0
    best_confidence = 0

    for rgn in search_regions:
        try:
            enhanced = cv2.bitwise_not(rgn)
            _, enhanced = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            if enhanced.shape[1] < 200:
                enhanced = cv2.resize(enhanced, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            data = pytesseract.image_to_data(
                enhanced,
                config='--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789',
                lang='eng',
                output_type=pytesseract.Output.DICT
            )
            for text, conf in zip(data['text'], data['conf']):
                text = text.strip()
                if text.isdigit() and int(text) > 0 and conf > best_confidence:
                    best_confidence = conf
                    best_number = int(text)
        except Exception:
            continue

    return best_number


def images_are_similar(img1: np.ndarray, img2: np.ndarray, threshold: int = 15) -> Tuple[bool, float]:
    """Compare two images using Perceptual Hash."""
    if not HASH_SUPPORT:
        return False, 100.0
    try:
        s1 = cv2.resize(img1, (256, 256))
        s2 = cv2.resize(img2, (256, 256))
        pil1 = PILImage.fromarray(cv2.cvtColor(s1, cv2.COLOR_BGR2RGB))
        pil2 = PILImage.fromarray(cv2.cvtColor(s2, cv2.COLOR_BGR2RGB))
        h1 = imagehash.phash(pil1)
        h2 = imagehash.phash(pil2)
        distance = h1 - h2
        return distance < threshold, float(distance)
    except Exception as e:
        print(f"Hash comparison error: {e}")
        return False, 100.0


def assess_image_quality(img: np.ndarray) -> Dict[str, float]:
    """Comprehensive quality assessment: sharpness, contrast, content, brightness."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    contrast = float(gray.std())
    edges = cv2.Canny(gray, 50, 150)
    edge_density = float(np.mean(edges > 0))
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    content_ratio = float(np.sum(binary > 0) / binary.size)
    brightness = float(np.mean(gray))
    brightness_score = 1.0 - abs(brightness - 128) / 128

    overall = (
        min(blur_score / 1000, 1.0) * 0.35 +
        edge_density * 0.25 +
        content_ratio * 0.20 +
        brightness_score * 0.10 +
        min(contrast / 100, 1.0) * 0.10
    )

    return {
        'overall': overall,
        'blur_score': blur_score,
        'contrast': contrast,
        'edge_density': edge_density,
        'content_ratio': content_ratio,
        'brightness': brightness,
    }


# ════════════════════════════════════════════════════════════════
#  Worker Thread Classes
# ════════════════════════════════════════════════════════════════

class SkewWorker(QThread):
    """Background skew detection worker."""
    finished = pyqtSignal(float)
    error = pyqtSignal(str)

    def __init__(self, img: np.ndarray):
        super().__init__()
        self.img = img

    def run(self):
        try:
            self.finished.emit(auto_detect_skew(self.img))
        except Exception as e:
            self.error.emit(str(e))


class ThumbnailWorker(QThread):
    """Background thumbnail generation. Supports LazyImage, Path, and ndarray."""
    ready = pyqtSignal(int, QPixmap)

    def __init__(self, image_list: list):
        super().__init__()
        self.image_list = image_list
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for i, item in enumerate(self.image_list):
            if self._stop:
                break
            try:
                if hasattr(item, 'get'):                             # LazyImage
                    img = item.get()
                    if img is not None and item.is_path:
                        item.clear_cache()                           # تحرير الكاش بعد المصغرة
                elif isinstance(item, Path):
                    img = cv2.imread(str(item), cv2.IMREAD_REDUCED_COLOR_4)
                else:
                    img = item
                if img is not None:
                    pix = cv2_to_pixmap(img, max_w=THUMB_W, max_h=THUMB_H)
                    self.ready.emit(i, pix)
            except Exception:
                pass


# ════════════════════════════════════════════════════════════════
#  Learning System Classes
# ════════════════════════════════════════════════════════════════

class AdaptiveLearner:
    """Simple adaptive learning system based on feature similarity."""
    MAX = 30

    def __init__(self):
        self.history = []  # type: List[dict]

    def _feat(self, img: np.ndarray) -> dict:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        h, w = g.shape
        return {"w": w, "h": h,
                "bright": float(np.mean(g)),
                "ratio": round(w / max(h, 1), 3)}

    def suggest(self, img: np.ndarray) -> Tuple[Optional[dict], float]:
        if len(self.history) < 2:
            return None, 0.0
        f = self._feat(img)
        best_sim, best_p = 0.0, None
        for rec in self.history:
            rf = rec["features"]
            d = (((f["w"] - rf["w"]) / 3000) ** 2 +
                 ((f["h"] - rf["h"]) / 4000) ** 2 +
                 ((f["bright"] - rf["bright"]) / 255) ** 2 +
                 ((f["ratio"] - rf["ratio"]) / 2) ** 2) ** 0.5
            sim = max(0.0, 1.0 - d)
            if sim > best_sim:
                best_sim, best_p = sim, rec["params"]
        return (best_p, best_sim) if best_sim > 0.85 else (None, 0.0)

    def add(self, img: np.ndarray, params: dict):
        self.history.append({"features": self._feat(img), "params": params.copy()})
        if len(self.history) > self.MAX:
            self.history.pop(0)

    def export(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.history, f, ensure_ascii=False, indent=2)

    def load(self, path: str):
        with open(path, "r", encoding="utf-8") as f:
            self.history = json.load(f)


class ImageFeatureExtractor:
    """30-feature extraction for machine learning."""

    @staticmethod
    def extract(img: np.ndarray) -> dict:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img.copy()
        h, w = gray.shape
        gray_f = gray.astype(np.float32)

        brightness_mean = float(np.mean(gray_f))
        brightness_std = float(np.std(gray_f))
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.mean(edges > 0))
        dark_mask = (gray < 128).astype(np.float32)
        horiz_proj = dark_mask.sum(axis=1)
        vert_proj = dark_mask.sum(axis=0)
        horiz_var = float(np.var(horiz_proj))
        vert_var = float(np.var(vert_proj))
        dark_ratio = float(np.mean(dark_mask))
        hist = cv2.calcHist([gray], [0], None, [16], [0, 256]).flatten()
        hist = (hist / max(h * w, 1)).tolist()
        gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        grad_mean = float(np.mean(np.sqrt(gx ** 2 + gy ** 2)))

        feats = {
            "w": w, "h": h,
            "aspect_ratio": round(w / max(h, 1), 4),
            "brightness_mean": round(brightness_mean, 2),
            "brightness_std": round(brightness_std, 2),
            "blur_score": round(blur_score, 2),
            "edge_density": round(edge_density, 4),
            "horiz_proj_var": round(horiz_var, 2),
            "vert_proj_var": round(vert_var, 2),
            "dark_ratio": round(dark_ratio, 4),
            "grad_mean": round(grad_mean, 2),
        }
        for i, v in enumerate(hist):
            feats["hist_{:02d}".format(i)] = round(v, 6)
        return feats

    @staticmethod
    def similarity(a: dict, b: dict) -> float:
        """Weighted cosine similarity between two feature vectors."""
        keys_w = {
            "aspect_ratio": (2.0, 3.0),
            "brightness_mean": (255.0, 2.0),
            "brightness_std": (128.0, 1.5),
            "blur_score": (2000.0, 1.0),
            "edge_density": (0.3, 2.0),
            "dark_ratio": (0.3, 2.0),
            "grad_mean": (200.0, 1.0),
        }
        dist_sq = 0.0
        for k, (norm, weight) in keys_w.items():
            av, bv = a.get(k, 0), b.get(k, 0)
            dist_sq += weight * ((av - bv) / max(norm, 1e-9)) ** 2
        for i in range(16):
            key = "hist_{:02d}".format(i)
            dist_sq += 4.0 * ((a.get(key, 0) - b.get(key, 0)) ** 2)
        return max(0.0, 1.0 - dist_sq ** 0.5)


class TrainingDataCollector:
    """KNN-based training data collector. Saves to JSONL."""
    FILEPATH = Path("medical_doc_training.jsonl")
    MIN_INFER = 5
    SIM_THRESH = 0.80

    def __init__(self):
        self.records = []  # type: List[dict]
        self._load_existing()

    def _load_existing(self):
        if not self.FILEPATH.exists():
            return
        with open(self.FILEPATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        self.records.append(json.loads(line))
                    except Exception:
                        pass

    def save_record(self, img: np.ndarray, initial_params: dict,
                    final_params: dict, operations: list,
                    blur_before: float, blur_after: float,
                    image_name: str = ""):
        features = ImageFeatureExtractor.extract(img)

        def _serialize(p):
            return {k: (list(v) if isinstance(v, tuple) else v)
                    for k, v in p.items()}

        record = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "image_name": image_name,
            "features": features,
            "initial_params": _serialize(initial_params),
            "final_params": _serialize(final_params),
            "operations": operations,
            "quality": {
                "blur_before": round(blur_before, 2),
                "blur_after": round(blur_after, 2),
                "improvement": round(blur_after - blur_before, 2),
            },
        }
        self.records.append(record)
        with open(self.FILEPATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def predict(self, img: np.ndarray) -> Tuple:
        """Predict optimal settings using weighted KNN (top 3 neighbors)."""
        if len(self.records) < self.MIN_INFER:
            return None, 0.0

        query = ImageFeatureExtractor.extract(img)
        scored = [
            (ImageFeatureExtractor.similarity(query, rec["features"]), rec["final_params"])
            for rec in self.records
        ]
        top3 = sorted(scored, key=lambda x: x[0], reverse=True)[:3]
        best_sim = top3[0][0]

        if best_sim < self.SIM_THRESH:
            return None, 0.0

        total_w = sum(s for s, _ in top3) or 1.0
        crop_avg = [0.0] * 4
        deskew_avg = 0.0
        flip_score = 0.0
        sharpen_score = 0.0
        rot_votes = {}

        for sim, params in top3:
            w = sim / total_w
            crop = params.get("crop", [0, 0, 0, 0])
            for i in range(4):
                crop_avg[i] += crop[i] * w
            deskew_avg += params.get("deskew_angle", 0.0) * w
            flip_score += (1.0 if params.get("flip_h", False) else 0.0) * w
            sharpen_score += (1.0 if params.get("sharpen", False) else 0.0) * w
            rot = params.get("rotation", 0)
            rot_votes[rot] = rot_votes.get(rot, 0.0) + w

        predicted = {
            "crop": tuple(int(round(v)) for v in crop_avg),
            "deskew_angle": round(deskew_avg, 1),
            "flip_h": flip_score > 0.5,
            "sharpen": sharpen_score > 0.5,
            "rotation": max(rot_votes, key=rot_votes.get) if rot_votes else 0,
        }
        return predicted, best_sim

    def stats(self) -> dict:
        if not self.records:
            return {"count": 0, "avg_improvement": 0, "max_improvement": 0}
        imps = [r["quality"]["improvement"] for r in self.records]
        return {
            "count": len(self.records),
            "avg_improvement": round(sum(imps) / len(imps), 1),
            "max_improvement": round(max(imps), 1),
        }


# ════════════════════════════════════════════════════════════════
#  Dialog and UI Helper Classes
# ════════════════════════════════════════════════════════════════

class CompareDialog(QDialog):
    """Before/after comparison dialog."""

    def __init__(self, orig: QPixmap, proc: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 قبل / بعد")
        self.resize(1250, 750)
        lay = QHBoxLayout(self)
        for title, pix in [("الأصلية", orig), ("بعد المعالجة", proc)]:
            box = QGroupBox(title)
            bl = QVBoxLayout()
            lbl = QLabel()
            lbl.setPixmap(pix)
            lbl.setAlignment(Qt.AlignCenter)
            bl.addWidget(lbl)
            box.setLayout(bl)
            lay.addWidget(box)
        btn = QPushButton("✖ إغلاق")
        btn.setFixedWidth(100)
        btn.clicked.connect(self.accept)
        lay.addWidget(btn, alignment=Qt.AlignTop)


class ThumbButton(QPushButton):
    """Custom thumbnail button with index display."""

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setFixedSize(THUMB_W + 6, THUMB_H + 22)
        self.setCheckable(True)
        self._apply_style(False)
        self.setToolTip("صورة {}".format(index + 1))

    def set_pixmap(self, pix: QPixmap):
        self.setIcon(QIcon(pix))
        self.setIconSize(QSize(THUMB_W, THUMB_H))
        self.setText("\n{}".format(self.index + 1))

    def _apply_style(self, selected: bool):
        if selected:
            self.setStyleSheet(
                "QPushButton{border:2px solid #2563eb;border-radius:4px;"
                "background:#dbeafe;color:#1e40af;font-size:9pt;font-weight:bold;}")
        else:
            self.setStyleSheet(
                "QPushButton{border:1px solid #cbd5e1;border-radius:4px;"
                "background:#f8fafc;color:#475569;font-size:9pt;}"
                "QPushButton:hover{border:1px solid #94a3b8;background:#f1f5f9;}")

    def setChecked(self, checked: bool):
        super().setChecked(checked)
        self._apply_style(checked)


# ════════════════════════════════════════════════════════════════
#  Embedded Region Selector
# ════════════════════════════════════════════════════════════════

class RegionSelectorLabel(QLabel):
    """QLabel يدعم رسم مربع تحديد بالماوس."""

    region_selected = pyqtSignal(QRect)  # يُرسل QRect بالبكسل

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rubber = QRubberBand(QRubberBand.Rectangle, self)
        self._origin = QPoint()
        self._current_region = None
        self._active = False

    def start_selection(self):
        """تفعيل وضع التحديد."""
        self._active = True
        self.setCursor(Qt.CrossCursor)
        self._rubber.hide()
        self._current_region = None

    def cancel_selection(self):
        """إلغاء وضع التحديد."""
        self._active = False
        self.setCursor(Qt.ArrowCursor)
        self._rubber.hide()

    def get_region(self):
        """الحصول على المنطقة المحددة."""
        return self._current_region

    def paintEvent(self, event):
        """رسم المستطيل الأحمر إذا كانت هناك منطقة محددة."""
        super().paintEvent(event)
        if self._current_region and not self._active:
            painter = QPainter(self)
            pen = QPen(QColor(239, 68, 68), 3, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self._current_region)
            painter.end()

    def mousePressEvent(self, event):
        if not self._active:
            super().mousePressEvent(event)
            return
        self._origin = event.pos()
        self._rubber.setGeometry(QRect(self._origin, QSize()))
        self._rubber.show()

    def mouseMoveEvent(self, event):
        if not self._active or not self._rubber.isVisible():
            super().mouseMoveEvent(event)
            return
        self._rubber.setGeometry(QRect(self._origin, event.pos()).normalized())

    def mouseReleaseEvent(self, event):
        if not self._active:
            super().mouseReleaseEvent(event)
            return
        self._rubber.hide()
        rect = QRect(self._origin, event.pos()).normalized()
        if rect.width() > 20 and rect.height() > 10:
            self._current_region = rect
            self._active = False
            self.setCursor(Qt.ArrowCursor)
            self.region_selected.emit(rect)
            self.update()  # إعادة الرسم لإظهار المستطيل الأحمر
        else:
            QMessageBox.warning(self, "منطقة صغيرة", "المنطقة صغيرة جداً. حاول مرة أخرى.")


class RegionSelectorDialog(QDialog):
    """حوار لتحديد منطقة رقم الصفحة."""

    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📍 تحديد منطقة رقم الصفحة")
        self.resize(900, 700)

        layout = QVBoxLayout(self)

        self.label = RegionSelectorLabel()
        self.label.setPixmap(pixmap)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.region_selected.connect(self._on_region)
        layout.addWidget(self.label)

        btn_layout = QHBoxLayout()
        self.btn_select = QPushButton("✚ ابدأ التحديد")
        self.btn_select.setStyleSheet("background:#16a34a;color:white;font-weight:bold;padding:8px;")
        self.btn_select.clicked.connect(self._start)

        self.btn_test = QPushButton("🧪 اختبار OCR")
        self.btn_test.setEnabled(False)
        self.btn_test.clicked.connect(self._test_ocr)

        self.btn_ok = QPushButton("✅ حفظ المنطقة")
        self.btn_ok.setEnabled(False)
        self.btn_ok.clicked.connect(self.accept)

        self.btn_cancel = QPushButton("❌ إلغاء")
        self.btn_cancel.clicked.connect(self.reject)

        for b in [self.btn_select, self.btn_test, self.btn_ok, self.btn_cancel]:
            btn_layout.addWidget(b)
        layout.addLayout(btn_layout)

        self._region = None
        self._test_result = None

    def _start(self):
        self.label.start_selection()
        self.btn_select.setText("⏳ ارسم المربع...")
        self.btn_select.setEnabled(False)

    def _on_region(self, rect):
        self._region = rect
        self.btn_select.setText("✚ إعادة التحديد")
        self.btn_select.setEnabled(True)
        self.btn_test.setEnabled(True)
        self.btn_ok.setEnabled(True)

    def _test_ocr(self):
        if not self._region:
            return
        self._test_result = self._region
        QMessageBox.information(self, "منطقة محددة",
            "المنطقة: x={}, y={}, w={}, h={}\n\n"
            "اضغط 'حفظ المنطقة' للتأكيد.".format(
                self._region.x(), self._region.y(),
                self._region.width(), self._region.height()))

    def get_region(self):
        """الحصول على المنطقة المحددة كـ QRect بالبكسل."""
        return self._region


# ════════════════════════════════════════════════════════════════
#  Main Application Class
# ════════════════════════════════════════════════════════════════

class MedicalDocApp(QMainWindow):

    # ──────────────────────────────────────────────────────────
    #  Initialization
    # ──────────────────────────────────────────────────────────

    def _get_unique_path(self, base_dir, relative_path, ext=".png"):
        """Generate a unique file path, appending _1, _2 etc. if needed."""
        target_dir = Path(base_dir) / Path(relative_path).parent
        target_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(relative_path).stem
        candidate = target_dir / "{}{}".format(stem, ext)
        if not candidate.exists():
            return candidate
        counter = 1
        while True:
            new_name = "{}_{}{}".format(stem, counter, ext)
            candidate = target_dir / new_name
            if not candidate.exists():
                return candidate
            counter += 1

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏥 معالج الوثائق الطبية v12")
        self.setMinimumSize(1024, 600)
        self.showMaximized()
        self.setFont(QFont("Noto Sans Arabic", 10))
        self.setAcceptDrops(True)

        # ── حماية من التداخل (Race Condition) ──────────────────
        self._mutex              = QMutex()
        self._is_processing      = False    # يمنع تحميل صورة أثناء كشف الميلان
        self._auto_save_in_prog  = False    # يمنع حفظ متداخل

        # Image data (LazyImage list)
        self.image_list  = []       # type: List[LazyImage]
        self.image_names = []       # type: List[str]
        self.image_paths = []       # type: List[Path]  — مسارات الملفات الأصلية
        self.current_idx = 0
        self.current_img  = None    # type: Optional[np.ndarray]
        self.current_blur = 0.0
        self.processed_blur = 0.0
        self.blur_threshold = 100.0
        self.gray_threshold = 200   # عتبة الرمادي — قابلة للتعديل من الواجهة
        self.current_params = {
            "crop": (20, 20, 20, 20),
            "deskew_angle": 0.0,
            "flip_h": False,
            "sharpen": False,
            "remove_shadow": False,
            "rotation": 0,
        }

        # Undo/Redo
        self._undo_stack = deque(maxlen=UNDO_LIMIT)  # type: deque
        self._redo_stack = deque(maxlen=UNDO_LIMIT)  # type: deque

        # Stats
        self.stats = {"total": 0, "processed": 0, "skipped": 0, "start_time": None}
        self.processing_records = []  # type: List[dict]

        # Learning
        self.learner = AdaptiveLearner()
        self.training = TrainingDataCollector()
        self.operation_history = []  # type: List[str]
        self.initial_params_snapshot = {}  # type: dict

        # Thumbnails
        self.thumb_buttons = []  # type: List[ThumbButton]

        # Workers
        self._skew_worker = None  # type: Optional[SkewWorker]
        self._thumb_worker = None  # type: Optional[ThumbnailWorker]
        self._detected_angle = 0.0

        # Zoom
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0

        # Auto-save
        self.auto_save_enabled = False

        # ── Auto-save (v12: QTimer-based sequential, non-blocking) ──
        self._auto_save_queue: list  = []
        self._auto_save_timer        = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(0)
        self._auto_save_timer.timeout.connect(self._auto_save_step)
        self._batch_cancelled: bool  = False
        self.page_registry: dict     = {}   # رقم الصفحة → بيانات الملف

        # ── Page number regions (multi-region support) ──
        self._page_number_regions: list = []  # قائمة مناطق [(fx, fy, fw, fh), ...]

        # Build UI
        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()

        # Clock timer
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._tick_clock)
        self._clock.start(1000)

    # ──────────────────────────────────────────────────────────
    #  UI Building
    # ──────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main_vbox = QVBoxLayout(root)
        main_vbox.setSpacing(4)

        # ── Top bar ──
        top = QHBoxLayout()
        self.lbl_status = QLabel("📁 افتح مجلداً أو اسحب ملفات هنا")
        self.lbl_index = QLabel("0 / 0")
        self.lbl_index.setStyleSheet("font-weight:bold;font-size:11pt;")

        self.btn_open = self._mk_btn("📂 فتح", "#0369a1")
        self.btn_prev = self._mk_btn("⬅️ السابق", "#475569", w=90)
        self.btn_next = self._mk_btn("التالي ➡️", "#475569", w=90)
        self.btn_export_csv = self._mk_btn("📤 CSV", "#7c3aed", w=90)
        self.btn_export_learn = self._mk_btn("💾 تعلّم", "#0891b2", w=90)
        self.btn_import_learn = self._mk_btn("📥 استيراد", "#0891b2", w=90)
        self.btn_analyze_pages = self._mk_btn("🧠 تحليل ذكي", "#8b5cf6", w=110)

        for w in [self.lbl_status, None, self.lbl_index,
                  self.btn_prev, self.btn_next,
                  self.btn_export_csv, self.btn_export_learn, self.btn_import_learn,
                  self.btn_analyze_pages, self.btn_open]:
            if w is None:
                top.addStretch()
            else:
                top.addWidget(w)
        main_vbox.addLayout(top)

        # ── Middle splitter ──
        mid_splitter = QSplitter(Qt.Horizontal)

        # Left: preview + controls
        left_w = QWidget()
        left_l = QVBoxLayout(left_w)
        left_l.setSpacing(4)

        # Preview with scroll
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setAlignment(Qt.AlignCenter)
        self.preview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.preview_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.preview_scroll.setStyleSheet("QScrollArea { border: none; background: #f0f4f8; }")
        self.lbl_preview = QLabel("⏳ بانتظار التحميل...")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setStyleSheet("background:#f0f4f8; border:2px dashed #94a3b8; border-radius:8px;")
        self.preview_scroll.setWidget(self.lbl_preview)
        left_l.addWidget(self.preview_scroll)

        # Control buttons — إنشاء + توزيع على 3 صفوف
        # ── إنشاء الأزرار ───────────────────────────────────────
        self.btn_refresh = self._mk_btn("🔄 تحديث", "#475569", h=32)
        self.btn_zoom_out = self._mk_btn("🔍- تصغير", "#475569", h=32, w=70)
        self.btn_zoom_in = self._mk_btn("🔍+ تكبير", "#475569", h=32, w=70)
        self.btn_zoom_fit = self._mk_btn("⛶ ملاءمة", "#475569", h=32, w=70)
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(50)
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        self.btn_fullscreen = self._mk_btn("⛶ ملء", "#475569", h=32, w=60)
        self.btn_rotate_left = self._mk_btn("↺ يسار", "#7c3aed", h=32, w=70)
        self.lbl_rotation = QLabel("0°")
        self.lbl_rotation.setFixedWidth(32)
        self.lbl_rotation.setAlignment(Qt.AlignCenter)
        self.lbl_rotation.setStyleSheet("font-weight:bold; color:#7c3aed;")
        self.btn_rotate_right = self._mk_btn("↻ يمين", "#7c3aed", h=32, w=70)
        self.btn_auto_deskew = self._mk_btn("📐 كشف ميلان", "#f59e0b", h=32)
        self.btn_apply_deskew = self._mk_btn("✔️ تطبيق الميلان", "#0ea5e9", h=32)
        self.btn_smart_crop = self._mk_btn("✂️ قص ذكي", "#7c3aed", h=32)
        self.btn_remove_gray = self._mk_btn("🖼️ إزالة رمادي", "#0891b2", h=32)
        self.btn_compare = self._mk_btn("🔍 مقارنة", "#6366f1", h=32)
        self.btn_save_inplace = self._mk_btn("💾 حفظ محلي", "#0891b2", h=32)
        self.btn_confirm = self._mk_btn("✅ تأكيد وحفظ", "#16a34a", h=32)
        self.btn_skip = self._mk_btn("⏭️ تخطي", "#dc2626", h=32)
        self.btn_apply_all = self._mk_btn("🤖 طبّق على البقية", "#0369a1", h=32)
        self.btn_auto_save_all  = self._mk_btn("🔁 حفظ تلقائي الكل", "#dc6b19", h=32)
        self.btn_cancel_batch   = self._mk_btn("⏹️ إلغاء",            "#dc2626", h=32, w=65)
        self.btn_screenshot     = self._mk_btn("📸 لقطة",              "#475569", h=32, w=65)
        self.btn_cancel_batch.setVisible(False)
        self.btn_apply_deskew.setEnabled(False)
        self.btn_apply_all.setEnabled(False)

        # ── التوزيع على 3 صفوف داخل QScrollArea ─────────────────
        ctrl = QVBoxLayout()
        ctrl.setSpacing(4)

        row1 = QHBoxLayout()
        row1.setSpacing(4)
        for w in [self.btn_refresh, self.btn_zoom_out, self.btn_zoom_in, self.btn_zoom_fit,
                  self.lbl_zoom, self.btn_fullscreen,
                  self.btn_rotate_left, self.lbl_rotation, self.btn_rotate_right]:
            row1.addWidget(w)
        row1.addStretch()

        row2 = QHBoxLayout()
        row2.setSpacing(4)
        for w in [self.btn_auto_deskew, self.btn_apply_deskew,
                  self.btn_smart_crop, self.btn_remove_gray, self.btn_compare]:
            row2.addWidget(w)
        row2.addStretch()

        row3 = QHBoxLayout()
        row3.setSpacing(4)
        self.btn_select_region = self._mk_btn("📍 تحديد رقم الصفحة", "#dc2626", h=32)
        for w in [self.btn_save_inplace, self.btn_confirm, self.btn_skip,
                  self.btn_apply_all, self.btn_auto_save_all,
                  self.btn_cancel_batch, self.btn_screenshot,
                  self.btn_select_region]:
            row3.addWidget(w)
        row3.addStretch()

        # حاوية للصفوف
        ctrl_widget = QWidget()
        ctrl_inner = QVBoxLayout(ctrl_widget)
        ctrl_inner.setSpacing(4)
        ctrl_inner.setContentsMargins(0, 0, 0, 0)
        ctrl_inner.addLayout(row1)
        ctrl_inner.addLayout(row2)
        ctrl_inner.addLayout(row3)

        # ScrollArea للأزرار
        btn_scroll = QScrollArea()
        btn_scroll.setWidgetResizable(True)
        btn_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        btn_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        btn_scroll.setFixedHeight(130)  # ارتفاع ثابت للأزرار
        btn_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        btn_scroll.setWidget(ctrl_widget)

        left_l.addWidget(btn_scroll)

        # Right panel with tabs — داخل QScrollArea
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        right_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        right_w = QWidget()
        right_w.setFixedWidth(320)
        right_l = QVBoxLayout(right_w)
        right_l.setSpacing(4)
        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.North)

        # ── Tab: Settings ──
        tab_settings = QWidget()
        ts_l = QVBoxLayout(tab_settings)

        crop_box = QGroupBox("✂️ هوامش القص (بكسل)")
        cl = QFormLayout()
        self.sp_left = self._spinbox(0, 3000, 20)
        self.sp_top = self._spinbox(0, 3000, 20)
        self.sp_right = self._spinbox(0, 3000, 20)
        self.sp_bottom = self._spinbox(0, 3000, 20)
        for label, sp in [("أيسر:", self.sp_left), ("علوي:", self.sp_top),
                          ("أيمن:", self.sp_right), ("سفلي:", self.sp_bottom)]:
            cl.addRow(label, sp)
        crop_box.setLayout(cl)
        ts_l.addWidget(crop_box)

        misc_box = QGroupBox("⚙️ تصحيحات وأتمتة")
        ml = QVBoxLayout()
        deskew_row = QHBoxLayout()
        self.btn_deskew_minus = QPushButton("−")
        self.btn_deskew_plus = QPushButton("+")
        for btn in [self.btn_deskew_minus, self.btn_deskew_plus]:
            btn.setFixedSize(26, 26)
            btn.setStyleSheet(
                "QPushButton{background:#475569;color:white;border-radius:4px;"
                "font-weight:bold;font-size:14pt;}"
                "QPushButton:pressed{background:#334155;}")
        self.slider_deskew = QSlider(Qt.Horizontal)
        self.slider_deskew.setRange(-150, 150)
        self.slider_deskew.setValue(0)
        self.lbl_deskew = QLabel("0.0°")
        self.lbl_deskew.setFixedWidth(45)
        deskew_row.addWidget(QLabel("ميلان:"))
        deskew_row.addWidget(self.btn_deskew_minus)
        deskew_row.addWidget(self.slider_deskew)
        deskew_row.addWidget(self.btn_deskew_plus)
        deskew_row.addWidget(self.lbl_deskew)
        self.chk_flip = QCheckBox("↔️ قلب أفقي")
        self.btn_sharpen = QPushButton("🔆 تحسين الوضوح (USM)")
        self.btn_sharpen.setCheckable(True)
        self.chk_shadow = QCheckBox("🌑 إزالة الظل")
        self.chk_auto_deskew = QCheckBox("🤖 تصحيح ميلان تلقائي عند الفتح")
        self.chk_auto_deskew.setChecked(True)
        self.chk_auto_save = QCheckBox("💾 حفظ تلقائي بعد الميلان والقص")
        self.chk_auto_save.setChecked(False)
        self.chk_learn = QCheckBox("🧠 تعلّم + حفظ بيانات تدريب")
        self.chk_learn.setChecked(True)

        # ── عتبة الرمادي ─────────────────────────────────────────
        gray_box = QGroupBox("🖼️ إزالة الإطار الرمادي")
        gray_l = QHBoxLayout()
        self.slider_gray_thr = QSlider(Qt.Horizontal)
        self.slider_gray_thr.setRange(150, 250)
        self.slider_gray_thr.setValue(self.gray_threshold)
        self.lbl_gray_thr = QLabel(str(self.gray_threshold))
        self.lbl_gray_thr.setFixedWidth(35)
        gray_l.addWidget(QLabel("عتبة:"))
        gray_l.addWidget(self.slider_gray_thr)
        gray_l.addWidget(self.lbl_gray_thr)
        gray_box.setLayout(gray_l)

        ml.addWidget(self.chk_auto_save)
        ml.addWidget(self.chk_auto_deskew)
        ml.addLayout(deskew_row)
        ml.addWidget(self.chk_flip)
        ml.addWidget(self.btn_sharpen)
        ml.addWidget(self.chk_shadow)
        self.chk_smart_save = QCheckBox("🔖 حفظ ذكي (OCR + ترقيم صفحات)")
        self.chk_smart_save.setChecked(False)
        ml.addWidget(self.chk_learn)
        ml.addWidget(self.chk_smart_save)
        ml.addWidget(gray_box)
        misc_box.setLayout(ml)
        ts_l.addWidget(misc_box)
        ts_l.addStretch()
        tabs.addTab(tab_settings, "⚙️ الإعدادات")

        # ── Tab: Quality ──
        tab_quality = QWidget()
        tq_l = QVBoxLayout(tab_quality)
        self.lbl_quality = QLabel("⏳ بانتظار...")
        self.lbl_quality.setAlignment(Qt.AlignCenter)
        self.lbl_quality.setStyleSheet("font-weight:bold;padding:8px;border-radius:5px;")
        self.lbl_quality.setMinimumHeight(50)
        score_row = QHBoxLayout()
        score_row.addWidget(QLabel("📐 درجة الوضوح:"))
        self.lbl_blur_val = QLabel("0")
        self.lbl_blur_val.setStyleSheet("font-weight:bold;font-size:13pt;")
        score_row.addWidget(self.lbl_blur_val)
        score_row.addStretch()
        thr_box = QGroupBox("عتبة الجودة الدنيا")
        thr_l = QHBoxLayout()
        self.slider_threshold = QSlider(Qt.Horizontal)
        self.slider_threshold.setRange(10, 500)
        self.slider_threshold.setValue(int(self.blur_threshold))
        self.lbl_thr = QLabel(str(int(self.blur_threshold)))
        self.lbl_thr.setFixedWidth(35)
        thr_l.addWidget(self.slider_threshold)
        thr_l.addWidget(self.lbl_thr)
        thr_box.setLayout(thr_l)
        self.lbl_blur_warn = QLabel("")
        self.lbl_blur_warn.setAlignment(Qt.AlignCenter)
        self.lbl_blur_warn.setStyleSheet("color:#dc2626;font-weight:bold;padding:4px;")
        self.lbl_blur_warn.setWordWrap(True)
        tq_l.addWidget(self.lbl_quality)
        tq_l.addLayout(score_row)
        tq_l.addWidget(thr_box)
        tq_l.addWidget(self.lbl_blur_warn)
        tq_l.addStretch()
        tabs.addTab(tab_quality, "📊 الجودة")

        # ── Tab: Stats ──
        tab_stats = QWidget()
        tst_l = QVBoxLayout(tab_stats)
        stat_box = QGroupBox("📈 إحصائيات الجلسة")
        sl = QFormLayout()
        self.lbl_s_total = QLabel("0")
        self.lbl_s_proc = QLabel("0")
        self.lbl_s_skip = QLabel("0")
        self.lbl_s_learn = QLabel("0")
        self.lbl_s_time = QLabel("00:00:00")
        self.lbl_s_undo = QLabel("0 / 0")
        self.lbl_train_count = QLabel("0")
        self.lbl_train_avg = QLabel("—")
        for label, w in [("إجمالي:", self.lbl_s_total),
                         ("معالجة:", self.lbl_s_proc),
                         ("تخطي:", self.lbl_s_skip),
                         ("سجلات التعلّم:", self.lbl_s_learn),
                         ("تراجع/إعادة:", self.lbl_s_undo),
                         ("الوقت:", self.lbl_s_time),
                         ("📊 سجلات التدريب:", self.lbl_train_count),
                         ("📈 متوسط التحسن:", self.lbl_train_avg)]:
            sl.addRow(label, w)
        stat_box.setLayout(sl)
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background:#0f172a;color:#94a3b8;font-family:monospace;font-size:9pt;")
        tst_l.addWidget(stat_box)
        tst_l.addWidget(QLabel("📝 سجل العمليات:"))
        tst_l.addWidget(self.txt_log)
        tabs.addTab(tab_stats, "📈 الإحصائيات")

        right_l.addWidget(tabs)
        right_scroll.setWidget(right_w)
        mid_splitter.addWidget(left_w)
        mid_splitter.addWidget(right_scroll)
        mid_splitter.setSizes([960, 440])
        main_vbox.addWidget(mid_splitter, stretch=1)

        # ── Thumbnail strip ──
        thumb_frame = QFrame()
        thumb_frame.setFixedHeight(THUMB_H + 40)
        thumb_frame.setStyleSheet("QFrame{background:#1e293b;border-top:2px solid #334155;}")
        thumb_outer = QVBoxLayout(thumb_frame)
        thumb_outer.setContentsMargins(4, 4, 4, 4)
        self.thumb_scroll = QScrollArea()
        self.thumb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.thumb_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.thumb_scroll.setWidgetResizable(True)
        self.thumb_scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self.thumb_container = QWidget()
        self.thumb_layout = QHBoxLayout(self.thumb_container)
        self.thumb_layout.setSpacing(4)
        self.thumb_layout.setContentsMargins(4, 2, 4, 2)
        self.thumb_layout.addStretch()
        self.thumb_scroll.setWidget(self.thumb_container)
        thumb_outer.addWidget(self.thumb_scroll)
        main_vbox.addWidget(thumb_frame)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFixedHeight(18)
        main_vbox.addWidget(self.progress)

    # ──────────────────────────────────────────────────────────
    #  Signal Connections
    # ──────────────────────────────────────────────────────────

    def _connect_signals(self):
        """Connect all UI signals."""
        self.btn_open.clicked.connect(self._open_folder)
        self.btn_prev.clicked.connect(lambda: self._navigate(-1))
        self.btn_next.clicked.connect(lambda: self._navigate(1))
        self.btn_refresh.clicked.connect(self._update_preview)
        self.btn_auto_deskew.clicked.connect(self._start_skew)
        self.btn_apply_deskew.clicked.connect(self._apply_skew)
        self.btn_smart_crop.clicked.connect(self._do_smart_crop)
        self.btn_remove_gray.clicked.connect(self._do_remove_gray)
        self.btn_compare.clicked.connect(self._show_compare)
        self.btn_confirm.clicked.connect(self._confirm_save)
        self.btn_save_inplace.clicked.connect(self._save_in_place)
        self.btn_auto_save_all.clicked.connect(self._auto_save_all)
        self.btn_cancel_batch.clicked.connect(self._cancel_batch)
        self.btn_screenshot.clicked.connect(lambda: self._save_screenshot(self.lbl_preview))
        self.chk_auto_save.stateChanged.connect(self._on_auto_save_toggle)
        self.btn_skip.clicked.connect(self._skip_save)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_fit.clicked.connect(self.zoom_fit)
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        self.btn_rotate_left.clicked.connect(self.rotate_left)
        self.btn_rotate_right.clicked.connect(self.rotate_right)
        self.btn_apply_all.clicked.connect(self._apply_to_remaining)
        self.btn_export_csv.clicked.connect(self._export_csv)
        self.btn_export_learn.clicked.connect(self._export_learn)
        self.btn_import_learn.clicked.connect(self._import_learn)
        self.btn_analyze_pages.clicked.connect(self.analyze_and_organize_pages)
        self.btn_select_region.clicked.connect(self._select_page_number_region)

        self.slider_deskew.valueChanged.connect(
            lambda v: self.lbl_deskew.setText("{:+.1f}°".format(v / 10)))
        self.slider_threshold.valueChanged.connect(self._on_thr_change)
        self.slider_gray_thr.valueChanged.connect(self._on_gray_thr_change)

        # Preview timer for parameter changes
        self._ptimer = QTimer(self)
        self._ptimer.setSingleShot(True)
        self._ptimer.timeout.connect(self._update_preview)
        for w in [self.sp_left, self.sp_top, self.sp_right, self.sp_bottom, self.slider_deskew]:
            w.valueChanged.connect(lambda: self._ptimer.start(250))

        self.btn_deskew_minus.clicked.connect(
            lambda: (self.slider_deskew.setValue(self.slider_deskew.value() - 1),
                     self._ptimer.start(120)))
        self.btn_deskew_plus.clicked.connect(
            lambda: (self.slider_deskew.setValue(self.slider_deskew.value() + 1),
                     self._ptimer.start(120)))

        for chk in [self.chk_flip, self.btn_sharpen, self.chk_shadow]:
            chk.toggled.connect(lambda: self._ptimer.start(250))

    # ──────────────────────────────────────────────────────────
    #  Keyboard Shortcuts
    # ──────────────────────────────────────────────────────────

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self._redo)
        QShortcut(QKeySequence("Ctrl+S"), self, self._confirm_save)
        QShortcut(QKeySequence("Right"), self, lambda: self._navigate(1))
        QShortcut(QKeySequence("Left"), self, lambda: self._navigate(-1))
        QShortcut(QKeySequence("Space"), self, self._update_preview)
        QShortcut(QKeySequence("Ctrl+D"), self, self._start_skew)
        QShortcut(QKeySequence("Ctrl+G"), self, self._do_smart_crop)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, self.analyze_and_organize_pages)
        QShortcut(QKeySequence("F11"), self, self.toggle_fullscreen)
        QShortcut(QKeySequence("Ctrl+P"), self, self._apply_predicted)

    # ──────────────────────────────────────────────────────────
    #  Drag & Drop
    # ──────────────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        """Accept drag events with URLs (files/folders)."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Handle dropped files/folders."""
        self._load_paths([url.toLocalFile() for url in event.mimeData().urls()])

    # ──────────────────────────────────────────────────────────
    #  Keyboard Events
    # ──────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts not covered by QShortcut."""
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key_Plus and modifiers & Qt.ControlModifier:
            self.zoom_in()
            event.accept()
            return
        elif key == Qt.Key_Minus and modifiers & Qt.ControlModifier:
            self.zoom_out()
            event.accept()
            return
        elif key == Qt.Key_0 and modifiers & Qt.ControlModifier:
            self.zoom_fit()
            event.accept()
            return
        elif key == Qt.Key_R and modifiers & Qt.ControlModifier:
            self.rotate_right()
            event.accept()
            return
        elif key == Qt.Key_L and modifiers & Qt.ControlModifier:
            self.rotate_left()
            event.accept()
            return
        elif key == Qt.Key_F and modifiers & Qt.ControlModifier and modifiers & Qt.ShiftModifier:
            self.toggle_fullscreen()
            event.accept()
            return

        super().keyPressEvent(event)

    # ──────────────────────────────────────────────────────────
    #  Window Close Event
    # ──────────────────────────────────────────────────────────

    def closeEvent(self, event):
        """Cleanup on window close."""
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.stop()
            self._thumb_worker.wait()
        if self._skew_worker and self._skew_worker.isRunning():
            self._skew_worker.quit()
            self._skew_worker.wait()
        event.accept()

    # ──────────────────────────────────────────────────────────
    #  File Loading
    # ──────────────────────────────────────────────────────────

    def _open_folder(self):
        """Open a folder dialog and load images from it."""
        folder = QFileDialog.getExistingDirectory(self, "اختر مجلداً")
        if folder:
            self._load_paths([folder])

    def _load_paths(self, paths: list):
        """Load images using LazyImage for lazy loading and memory efficiency."""
        lazy_imgs, names, img_paths = [], [], []
        for p in paths:
            pp = Path(p)
            if pp.is_dir():
                for f in sorted(pp.glob("*")):
                    ext = f.suffix.lower()
                    if ext in IMG_EXT:
                        if f.exists():
                            lazy_imgs.append(LazyImage(f, f.name))
                            names.append(f.name)
                            img_paths.append(f)
                        else:
                            self._log("⚠️ تجاهل ملف غير موجود: {}".format(f.name))
                    elif ext == ".pdf" and PDF_SUPPORT:
                        try:
                            pages = load_pdf_as_images(str(f))
                            for j, pg in enumerate(pages):
                                lazy_imgs.append(LazyImage(pg, "{}_p{:03d}.png".format(f.stem, j+1)))
                                names.append("{}_p{:03d}.png".format(f.stem, j+1))
                                img_paths.append(f)
                        except Exception as e:
                            self._log("⚠️ خطأ PDF {}: {}".format(f.name, e))
            elif pp.is_file():
                ext = pp.suffix.lower()
                if ext in IMG_EXT:
                    if pp.exists():
                        lazy_imgs.append(LazyImage(pp, pp.name))
                        names.append(pp.name)
                        img_paths.append(pp)
                    else:
                        self._log("⚠️ تجاهل ملف غير موجود: {}".format(pp.name))
                elif ext == ".pdf" and PDF_SUPPORT:
                    try:
                        pages = load_pdf_as_images(str(pp))
                        for j, pg in enumerate(pages):
                            lazy_imgs.append(LazyImage(pg, "{}_p{:03d}.png".format(pp.stem, j+1)))
                            names.append("{}_p{:03d}.png".format(pp.stem, j+1))
                            img_paths.append(pp)
                    except Exception as e:
                        self._log("⚠️ خطأ PDF {}: {}".format(pp.name, e))
        if not lazy_imgs:
            QMessageBox.warning(self, "تنبيه", "لم يتم العثور على ملفات صالحة.")
            return
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.stop()
            self._thumb_worker.wait()
        self.image_list  = lazy_imgs
        self.image_names = names
        self.image_paths = img_paths
        self.current_idx = 0
        self.processing_records = []
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.stats = {"total": len(lazy_imgs), "processed": 0, "skipped": 0, "start_time": datetime.now()}
        self.progress.setMaximum(len(lazy_imgs))
        self.lbl_s_total.setText(str(len(lazy_imgs)))
        self._log("📥 تم تحميل {} ملف (LazyImage — تحميل كسول)".format(len(lazy_imgs)))
        self._build_thumbnails()
        self._load_current()

    def _load_current(self):
        """Load current image with race condition protection."""
        if not self.image_list:
            return
        # ── حماية: منع التحميل أثناء كشف الميلان ──────────────
        if self._is_processing:
            logger.debug("_load_current: تأجيل — المعالجة قيد التشغيل")
            return

        entry = self.image_list[self.current_idx]
        name  = self.image_names[self.current_idx]
        self.lbl_index.setText("{} / {}".format(self.current_idx + 1, len(self.image_list)))
        self.progress.setValue(self.current_idx)
        self._update_thumb_selection()

        # التحقق من وجود الملف (LazyImage أو Path مباشر)
        if not entry.exists():
            self._log("⚠️ الملف {} غير موجود — حذف من القائمة".format(name))
            self.image_list.pop(self.current_idx)
            self.image_names.pop(self.current_idx)
            if self.current_idx < len(self.image_paths):
                self.image_paths.pop(self.current_idx)
            self.stats["total"] = len(self.image_list)
            self.progress.setMaximum(self.stats["total"])
            self.lbl_s_total.setText(str(self.stats["total"]))
            if self.current_idx >= len(self.image_list):
                self.current_idx = max(0, len(self.image_list) - 1)
            self._load_current()
            return

        img = entry.get()
        if img is None:
            self._log("❌ فشل قراءة: {}".format(name))
            return

        self.current_img  = img
        self.current_blur = calc_blur(img)   # ← يُحسب مرة واحدة هنا ويُمرَّر لاحقاً
        self._update_quality_display()
        self.current_params["rotation"] = 0
        self.operation_history = []

        # اقتراح من نظام التعلّم
        if self.chk_learn.isChecked():
            t_params, t_sim = self.training.predict(img)
            if t_params:
                self.current_params.update(t_params)
                self._log("🧠 تنبؤ ({}%): {}".format(int(t_sim * 100), name))
            else:
                a_params, a_sim = self.learner.suggest(img)
                if a_params:
                    self.current_params.update(a_params)
                    self._log("🤖 اقتراح ({}%): {}".format(int(a_sim * 100), name))
                else:
                    self._log("📄 تحميل: {}".format(name))
        else:
            self._log("📄 تحميل: {}".format(name))

        self.initial_params_snapshot = self.current_params.copy()
        self._sync_ui_from_params()
        self.btn_apply_deskew.setEnabled(False)

        if hasattr(self, 'chk_auto_deskew') and (self.chk_auto_deskew.isChecked() or self.auto_save_enabled):
            self._apply_auto_deskew_on_load()
        else:
            self._update_preview()

    # ──────────────────────────────────────────────────────────
    #  Thumbnails
    # ──────────────────────────────────────────────────────────

    def _build_thumbnails(self):
        """Build thumbnail buttons for all loaded images."""
        for btn in self.thumb_buttons:
            btn.deleteLater()
        self.thumb_buttons.clear()
        while self.thumb_layout.count():
            item = self.thumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i in range(len(self.image_list)):
            btn = ThumbButton(i)
            btn.setText(str(i + 1))
            btn.clicked.connect(lambda checked, idx=i: self._jump_to(idx))
            self.thumb_buttons.append(btn)
            self.thumb_layout.addWidget(btn)
        self.thumb_layout.addStretch()
        if self.thumb_buttons:
            self.thumb_buttons[0].setChecked(True)
        self._thumb_worker = ThumbnailWorker(self.image_list)
        self._thumb_worker.ready.connect(self._on_thumb_ready)
        self._thumb_worker.start()

    def _on_thumb_ready(self, idx: int, pix: QPixmap):
        """Set thumbnail pixmap when thumbnail worker emits."""
        if idx < len(self.thumb_buttons):
            self.thumb_buttons[idx].set_pixmap(pix)

    def _on_thumb_click(self, idx: int):
        """Alias for _jump_to — kept for compatibility."""
        self._jump_to(idx)

    def _update_thumb_selection(self):
        """Highlight the current thumbnail."""
        for i, btn in enumerate(self.thumb_buttons):
            btn.setChecked(i == self.current_idx)
        if self.current_idx < len(self.thumb_buttons):
            btn = self.thumb_buttons[self.current_idx]
            self.thumb_scroll.ensureWidgetVisible(btn)

    def _jump_to(self, idx: int):
        """Jump to a specific image by index."""
        self.current_idx = idx
        self._load_current()

    # ──────────────────────────────────────────────────────────
    #  Image Loading & Preview
    # ──────────────────────────────────────────────────────────

    def _load_image(self, idx: int):
        """Load image at a specific index. Alias for _load_current with index."""
        self.current_idx = idx
        self._load_current()


    # ──────────────────────────────────────────────────────────
    #  Undo / Redo
    # ──────────────────────────────────────────────────────────

    def _push_undo(self):
        """Push current params to undo stack."""
        self._undo_stack.append(self.current_params.copy())
        self._redo_stack.clear()
        self._update_undo_label()

    def _undo(self):
        """Undo last parameter change."""
        if not self._undo_stack:
            return
        self._redo_stack.append(self.current_params.copy())
        self.current_params = self._undo_stack.pop()
        self._sync_ui_from_params()
        self._update_preview()
        self._update_undo_label()
        self._log("↩️ تراجع")

    def _redo(self):
        """Redo last undone parameter change."""
        if not self._redo_stack:
            return
        self._undo_stack.append(self.current_params.copy())
        self.current_params = self._redo_stack.pop()
        self._sync_ui_from_params()
        self._update_preview()
        self._update_undo_label()
        self._log("↪️ إعادة")

    def _update_undo_label(self):
        """Update undo/redo count label."""
        self.lbl_s_undo.setText("{} / {}".format(len(self._undo_stack), len(self._redo_stack)))


    def _sync_ui_from_params(self):
        """Synchronize UI controls from current_params."""
        crop = self.current_params.get("crop", (20, 20, 20, 20))
        for sp, val in [(self.sp_left, crop[0]), (self.sp_top, crop[1]),
                        (self.sp_right, crop[2]), (self.sp_bottom, crop[3])]:
            sp.blockSignals(True)
            sp.setValue(val)
            sp.blockSignals(False)
        angle = int(self.current_params.get("deskew_angle", 0.0) * 10)
        self.slider_deskew.blockSignals(True)
        self.slider_deskew.setValue(angle)
        self.slider_deskew.blockSignals(False)
        self.lbl_deskew.setText("{:+.1f}°".format(angle / 10))
        self.chk_flip.setChecked(self.current_params.get("flip_h", False))
        self.btn_sharpen.setChecked(self.current_params.get("sharpen", False))
        self.chk_shadow.setChecked(self.current_params.get("remove_shadow", False))
        self.lbl_rotation.setText("{}°".format(self.current_params.get('rotation', 0)))

    def _collect_params(self) -> dict:
        """Collect current UI values into a params dict."""
        return {
            "crop": (self.sp_left.value(), self.sp_top.value(),
                     self.sp_right.value(), self.sp_bottom.value()),
            "deskew_angle": self.slider_deskew.value() / 10.0,
            "flip_h": self.chk_flip.isChecked(),
            "sharpen": self.btn_sharpen.isChecked(),
            "remove_shadow": self.chk_shadow.isChecked(),
            "rotation": self.current_params.get("rotation", 0),
        }

    def _update_preview(self):
        """Update the preview image with current processing parameters."""
        if self.current_img is None:
            return
        self.current_params = self._collect_params()
        processed = apply_processing(self.current_img, self.current_params)
        self.processed_blur = calc_blur(processed)
        pix = cv2_to_pixmap(processed, zoom=self.zoom_factor, max_w=1600, max_h=1600)
        self.lbl_preview.setPixmap(pix)
        self.lbl_preview.setText("")
        self.lbl_preview.setFixedSize(pix.width(), pix.height())

    def _push_undo(self):
        """Push current params to undo stack."""
        self._undo_stack.append(self.current_params.copy())
        self._redo_stack.clear()
        self._update_undo_label()

    def _undo(self):
        """Undo last parameter change."""
        if not self._undo_stack:
            return
        self._redo_stack.append(self.current_params.copy())
        self.current_params = self._undo_stack.pop()
        self._sync_ui_from_params()
        self._update_preview()
        self._update_undo_label()
        self._log("↩️ تراجع")

    def _redo(self):
        """Redo last undone parameter change."""
        if not self._redo_stack:
            return
        self._undo_stack.append(self.current_params.copy())
        self.current_params = self._redo_stack.pop()
        self._sync_ui_from_params()
        self._update_preview()
        self._update_undo_label()
        self._log("↪️ إعادة")

    def _update_undo_label(self):
        """Update undo/redo count label."""
        self.lbl_s_undo.setText("{} / {}".format(len(self._undo_stack), len(self._redo_stack)))

    # ──────────────────────────────────────────────────────────
    #  Smart Crop
    # ──────────────────────────────────────────────────────────

    def _do_smart_crop(self):
        """Perform smart auto-crop on current image."""
        if self.current_img is None:
            return
        self._push_undo()
        crop = smart_auto_crop(self.current_img)
        self.sp_left.setValue(crop[0])
        self.sp_top.setValue(crop[1])
        self.sp_right.setValue(crop[2])
        self.sp_bottom.setValue(crop[3])
        self.current_params["crop"] = crop
        self.operation_history.append("قص ذكي")
        self._update_preview()
        self._log("✂️ قص ذكي: L={} T={} R={} B={}".format(crop[0], crop[1], crop[2], crop[3]))
        if self.chk_auto_save.isChecked():
            self._confirm_save()

    def _do_remove_gray(self):
        """
        يُزيل فقط الحدود الرمادية للماسح بدون المساس بالمحتوى.
        أسرع وأدق من القص الذكي — مفيد كخطوة أولى قبل تصحيح الميلان.
        بعد إزالة الرمادي يكون كشف الميلان أكثر دقة.
        """
        if self.current_img is None:
            return
        self._push_undo()
        crop = find_page_bounds(self.current_img)
        self.sp_left.setValue(crop[0])
        self.sp_top.setValue(crop[1])
        self.sp_right.setValue(crop[2])
        self.sp_bottom.setValue(crop[3])
        self.current_params["crop"] = crop
        self.operation_history.append("إزالة رمادي")
        self._update_preview()
        self._log("🖼️ إزالة رمادي: L={} T={} R={} B={}".format(
            crop[0], crop[1], crop[2], crop[3]))

    # ──────────────────────────────────────────────────────────
    #  Skew Detection
    # ──────────────────────────────────────────────────────────

    def _start_skew(self):
        """Start background skew detection."""
        if self.current_img is None:
            return
        self._log("📐 كشف ميلان...")
        self.btn_auto_deskew.setEnabled(False)
        self.btn_auto_deskew.setText("⏳ جاري...")
        self._skew_worker = SkewWorker(self.current_img)
        self._skew_worker.finished.connect(self._on_skew_done)
        self._skew_worker.error.connect(self._on_skew_err)
        self._skew_worker.start()

    def _on_skew_done(self, angle: float):
        """Handle completed skew detection."""
        self._detected_angle = angle
        self.slider_deskew.setValue(int(angle * 10))
        self.lbl_deskew.setText("{:+.1f}°".format(angle))
        self.btn_apply_deskew.setEnabled(abs(angle) > 0.1)
        self.btn_auto_deskew.setEnabled(True)
        self.btn_auto_deskew.setText("📐 كشف ميلان")
        self._log("📐 ميلان مكتشف: {:.1f}°".format(angle))
        self._update_preview()
        note = "✅ مائلة — اضغط 'تطبيق الميلان'" if abs(angle) > 0.5 else "✔️ مستقيمة تقريباً"
        QMessageBox.information(self, "نتيجة الكشف", "زاوية الميلان: {:+.1f}°\n{}".format(angle, note))

    def _on_skew_err(self, msg: str):
        """Handle skew detection error."""
        self.btn_auto_deskew.setEnabled(True)
        self.btn_auto_deskew.setText("📐 كشف ميلان")
        self._log("⚠️ خطأ في كشف الميلان: {}".format(msg))

    def _apply_skew(self):
        """Apply the detected skew angle."""
        if abs(self._detected_angle) > 0.05:
            self._push_undo()
            self.current_params["deskew_angle"] = self._detected_angle
            self.operation_history.append("ميلان: {:.1f}°".format(self._detected_angle))
            self.btn_apply_deskew.setEnabled(False)
            self._log("✔️ تطبيق ميلان: {:.1f}°".format(self._detected_angle))
            self._update_preview()

    # ──────────────────────────────────────────────────────────
    #  Auto-deskew on Load
    # ──────────────────────────────────────────────────────────

    def _apply_auto_deskew_on_load(self):
        """Auto deskew with processing guard to prevent race conditions."""
        if self.current_img is None or self._is_processing:
            return
        self._is_processing = True          # ← تأمين
        self.btn_auto_deskew.setEnabled(False)
        self.btn_auto_deskew.setText("⏳ جاري...")
        self._skew_worker = SkewWorker(self.current_img)
        self._skew_worker.finished.connect(self._on_auto_skew_done)
        self._skew_worker.error.connect(self._on_auto_skew_err)
        self._skew_worker.start()

    def _on_auto_skew_done(self, angle: float):
        """Handle auto deskew completion. Uses cached gray_threshold."""
        self._is_processing = False         # ← فك التأمين
        self._detected_angle = angle
        if abs(angle) > 0.1:
            self._push_undo()
            self.current_params["deskew_angle"] = angle
            self.slider_deskew.setValue(int(angle * 10))
            self.lbl_deskew.setText("{:+.1f}°".format(angle))
            self.operation_history.append("ميلان تلقائي: {:.1f}°".format(angle))
            self._log("📐 ميلان مكتشف: {:.1f}°".format(angle))
        else:
            self._log("✅ لا ميلان مكتشف")

        # قص ذكي بعد الميلان — يستخدم gray_threshold القابل للتعديل
        if self.current_img is not None:
            crop = smart_auto_crop(self.current_img, dark_threshold=self.gray_threshold)
            self.sp_left.setValue(crop[0])
            self.sp_top.setValue(crop[1])
            self.sp_right.setValue(crop[2])
            self.sp_bottom.setValue(crop[3])
            self.current_params["crop"] = crop
            self.operation_history.append("قص ذكي تلقائي")
            self._log("✂️ قص ذكي تلقائي: L={} T={} R={} B={}".format(*crop))

        self.btn_auto_deskew.setEnabled(True)
        self.btn_auto_deskew.setText("📐 كشف ميلان")
        self._update_preview()

        if self.chk_auto_save.isChecked() and not self._auto_save_in_prog:
            self._confirm_save()

    def _on_auto_skew_err(self, msg: str):
        """Handle auto deskew error."""
        self._is_processing = False         # ← فك التأمين دائماً
        self.btn_auto_deskew.setEnabled(True)
        self.btn_auto_deskew.setText("📐 كشف ميلان")
        self._log("⚠️ خطأ في كشف الميلان التلقائي: {}".format(msg))
        self._update_preview()

    def _on_gray_thr_change(self, val: int):
        """Update gray threshold from slider."""
        self.gray_threshold = val
        self.lbl_gray_thr.setText(str(val))

    def _safe_move(self, src: Path, dst: Path):
        """
        نقل ملف بأمان عبر أنظمة ملفات مختلفة.
        إذا فشل shutil.move (خطأ cross-device) يستخدم copy2 + unlink.
        """
        try:
            shutil.move(str(src), str(dst))
        except (shutil.Error, OSError) as e:
            logger.warning("shutil.move فشل: %s — استخدام copy2+unlink", e)
            shutil.copy2(str(src), str(dst))
            if src.exists():
                src.unlink()

    # ──────────────────────────────────────────────────────────
    #  Training Stats
    # ──────────────────────────────────────────────────────────

    def _update_training_stats(self):
        """Update training statistics labels."""
        t_stats = self.training.stats()
        self.lbl_train_count.setText(str(t_stats["count"]))
        self.lbl_train_avg.setText(str(t_stats["avg_improvement"]))
        self.lbl_s_learn.setText(str(len(self.learner.history)))

    # ──────────────────────────────────────────────────────────
    #  Apply Predicted Settings from Learning
    # ──────────────────────────────────────────────────────────

    def _apply_predicted(self):
        """Apply predicted settings from the learning system to current image."""
        if self.current_img is None:
            self._log("⚠️ لا توجد صورة محملة لتطبيق التنبؤ")
            return

        # Try TrainingDataCollector first (more accurate)
        t_params, t_sim = self.training.predict(self.current_img)
        if t_params:
            self._push_undo()
            self.current_params.update(t_params)
            self._sync_ui_from_params()
            self._update_preview()
            self._log("🧠 تم تطبيق تنبؤ بيانات التدريب ({}% تشابه)".format(int(t_sim * 100)))
            return

        # Fall back to AdaptiveLearner
        a_params, a_sim = self.learner.suggest(self.current_img)
        if a_params:
            self._push_undo()
            self.current_params.update(a_params)
            self._sync_ui_from_params()
            self._update_preview()
            self._log("🤖 تم تطبيق اقتراح التعلّم ({}% تشابه)".format(int(a_sim * 100)))
            return

        self._log("⚠️ لا توجد بيانات كافية للتنبؤ (أقل من {} سجل)".format(TrainingDataCollector.MIN_INFER))

    # ──────────────────────────────────────────────────────────
    #  Compare Dialog
    # ──────────────────────────────────────────────────────────

    def _show_compare(self):
        """Show before/after comparison dialog."""
        if self.current_img is None:
            return
        self._update_preview()
        orig_pix = cv2_to_pixmap(self.current_img, max_w=600, max_h=800)
        proc = apply_processing(self.current_img, self.current_params)
        proc_pix = cv2_to_pixmap(proc, max_w=600, max_h=800)
        dlg = CompareDialog(orig_pix, proc_pix, self)
        dlg.exec_()

    # ──────────────────────────────────────────────────────────
    #  Quality Display
    # ──────────────────────────────────────────────────────────

    def _update_quality_display(self):
        """Update quality labels based on current blur score."""
        label, color, icon = quality_label(self.current_blur, self.blur_threshold)
        self.lbl_blur_val.setText("{:.1f}".format(self.current_blur))
        self.lbl_quality.setText("{} جودة الأصل: {}".format(icon, label))
        self.lbl_quality.setStyleSheet(
            "font-weight:bold;padding:8px;border-radius:5px;"
            "background:{}22;color:{};border:1px solid {};".format(color, color, color))
        if self.current_blur < self.blur_threshold:
            self.lbl_blur_warn.setText(
                "⚠️ صورة ضبابية  ({:.0f} < {:.0f})".format(self.current_blur, self.blur_threshold))
        else:
            self.lbl_blur_warn.setText("")

    def _on_thr_change(self, val):
        """Handle quality threshold slider change."""
        self.blur_threshold = float(val)
        self.lbl_thr.setText(str(val))
        self._update_quality_display()

    # ──────────────────────────────────────────────────────────
    #  Save Methods
    # ──────────────────────────────────────────────────────────

    def _confirm_save(self):
        """Save processed image. Protected against reentrancy."""
        if self.current_img is None or self._auto_save_in_prog:
            return
        self._auto_save_in_prog = True
        try:
            # تحذير الجودة — يستخدم processed_blur المحسوب مسبقاً في _update_preview
            if self.processed_blur < self.blur_threshold * 0.5:
                reply = QMessageBox.question(
                    self, "تحذير جودة",
                    "الصورة المعالجة ضبابية جداً ({:.0f})\nهل تريد الحفظ؟".format(self.processed_blur),
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                if reply == QMessageBox.No:
                    return

            self._push_undo()
            processed = apply_processing(self.current_img, self.current_params)

            # ── مسارات الحفظ ────────────────────────────────────
            docs_dir = Path.home() / "Documents"
            raw_base  = docs_dir / "raw_scanned_files"
            crop_base = docs_dir / "cropped_scanned_files"

            name  = self.image_names[self.current_idx] if self.current_idx < len(self.image_names) else "img.png"
            entry = self.image_list[self.current_idx]  # LazyImage

            # نقل الأصل باستخدام _safe_move (يدعم cross-filesystem)
            if entry.is_path and entry.exists():
                raw_dest = self._get_unique_path(raw_base, name, ext=entry._path.suffix)
                self._safe_move(entry._path, raw_dest)
                entry.update_path(raw_dest)    # ← تحديث LazyImage للمسار الجديد

            # حفظ المعالَجة
            dest = self._get_unique_path(crop_base, name, ext=".png")
            cv2.imwrite(str(dest), processed)

            self.stats["processed"] += 1
            self._record_csv("confirmed", dest)

            # التعلّم — يستخدم current_blur وprocessed_blur المحسوبَين مسبقاً
            if self.chk_learn.isChecked():
                self.learner.add(self.current_img, self.current_params)
                self.training.save_record(
                    img            = self.current_img,
                    initial_params = self.initial_params_snapshot,
                    final_params   = self.current_params,
                    operations     = list(self.operation_history),
                    blur_before    = self.current_blur,       # ← لا إعادة حساب
                    blur_after     = self.processed_blur,     # ← لا إعادة حساب
                    image_name     = name,
                )
                self._update_training_stats()

            self._update_stats()
            self._log("💾 حفظ: {} | جودة: {:.0f}".format(dest.name, self.processed_blur))
            self.btn_apply_all.setEnabled(True)
            if self.current_idx < len(self.image_list) - 1:
                self._navigate(1)
        finally:
            self._auto_save_in_prog = False

    def _save_in_place(self):
        """Save processed image over the original file (in-place). Resets params to zero."""
        if self.current_img is None:
            return
        entry = self.image_list[self.current_idx]
        if not entry.is_path:
            QMessageBox.warning(self, "تنبيه", "لا يمكن الحفظ المحلي لصفحات PDF.")
            return
        processed = apply_processing(self.current_img, self.current_params)
        cv2.imwrite(str(entry._path), processed)
        self.operation_history.append("save_in_place")
        self._log("💾 حفظ محلي: {} — الإعدادات أُعيدت للصفر".format(entry.name))
        # الصورة المعالجة تصبح الأصل الجديد
        self.current_img  = processed
        entry._cache      = processed    # تحديث الكاش مباشرة
        self.current_blur = calc_blur(processed)
        self.initial_params_snapshot = {
            "crop": (0, 0, 0, 0), "deskew_angle": 0.0,
            "flip_h": False, "sharpen": False,
            "remove_shadow": False, "rotation": 0,
        }
        self.current_params = self.initial_params_snapshot.copy()
        self._sync_ui_from_params()
        self._update_quality_display()
        self._update_preview()

    # ──────────────────────────────────────────────────────────
    #  Log — يستخدم logger الموحّد
    # ──────────────────────────────────────────────────────────

    def _log(self, msg: str):
        """Log to both UI and file logger."""
        ts   = datetime.now().strftime("%H:%M:%S")
        line = "[{}] {}".format(ts, msg)
        self.txt_log.append(line)
        self.txt_log.verticalScrollBar().setValue(
            self.txt_log.verticalScrollBar().maximum())
        logger.info(msg)                   # ← يكتب في medical_doc_app.log
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def _auto_save_all(self):
        """v12: Batch save using QTimer — non-blocking, UI stays responsive."""
        if not self.image_list or self._auto_save_in_prog:
            return
        remaining = len(self.image_list) - self.current_idx
        reply = QMessageBox.question(
            self, "تأكيد الحفظ التلقائي",
            "سيتم حفظ {} صورة تلقائياً (تصحيح ميلان + قص ذكي).\nهل تريد المتابعة؟".format(remaining),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return
        self._auto_save_in_prog = True
        self._batch_cancelled   = False
        self._set_controls_enabled(False)
        self.btn_cancel_batch.setVisible(True)
        self.btn_auto_save_all.setText("⏳ جاري (0/{})...".format(remaining))
        self.lbl_status.setText("🔁 حفظ تلقائي جارٍ...")
        self._auto_save_queue = list(range(self.current_idx, len(self.image_list)))
        self._auto_save_timer.start(0)   # ← يبدأ فوراً بعد إعادة رسم الواجهة

    def _auto_save_step(self):
        """v12: Process ONE image per QTimer tick — لا تجميد للواجهة."""
        if not self._auto_save_queue or self._batch_cancelled:
            # اكتمل أو ألُغي
            self._auto_save_timer.stop()
            self._auto_save_in_prog = False
            self._set_controls_enabled(True)
            self.btn_cancel_batch.setVisible(False)
            self.btn_auto_save_all.setText("🔁 حفظ تلقائي الكل")
            self._update_training_stats()
            self._update_stats()
            if self._batch_cancelled:
                self._auto_save_queue.clear()
                self.lbl_status.setText("⏹️ تم إلغاء الحفظ التلقائي")
                self._log("⏹️ إلغاء الحفظ التلقائي")
            else:
                total = len(self.image_list) - self.current_idx
                self.lbl_status.setText("✅ اكتمل الحفظ التلقائي ({} صورة)".format(total))
                self._log("🔁 اكتمل الحفظ التلقائي")
            return

        i = self._auto_save_queue.pop(0)
        done = (len(self.image_list) - self.current_idx) - len(self._auto_save_queue)
        total = len(self.image_list) - self.current_idx
        self.btn_auto_save_all.setText("⏳ جاري ({}/{})...".format(done, total))
        self.progress.setValue(i + 1)
        self.lbl_status.setText("🔁 حفظ تلقائي: {} / {}".format(done, total))

        try:
            entry = self.image_list[i]
            name  = self.image_names[i]
            img   = entry.get()
            if img is None:
                self._log("⚠️ تخطي: {}".format(name))
            else:
                angle  = auto_detect_skew(img)
                blur_b = calc_blur(img)
                params = {
                    "crop":          smart_auto_crop(img, dark_threshold=self.gray_threshold),
                    "deskew_angle":  angle,
                    "flip_h":        False,
                    "sharpen":       self.btn_sharpen.isChecked(),
                    "remove_shadow": self.chk_shadow.isChecked(),
                    "rotation":      0,
                }
                processed = apply_processing(img, params)
                blur_a    = calc_blur(processed)

                docs_dir  = Path.home() / "Documents"
                raw_base  = docs_dir / "raw_scanned_files"
                crop_base = docs_dir / "cropped_scanned_files"

                if entry.is_path and entry.exists():
                    raw_d = self._get_unique_path(raw_base, name, ext=entry._path.suffix)
                    self._safe_move(entry._path, raw_d)
                    entry.update_path(raw_d)

                # ── حفظ ذكي: OCR + ترقيم الصفحات ──────────────
                save_name = name
                if self.chk_smart_save.isChecked() and OCR_SUPPORT:
                    user_regions = getattr(self, '_page_number_regions', None)
                    page_num = extract_page_number(processed, regions=user_regions)
                    if page_num > 0:
                        save_name = "page_{:04d}.png".format(page_num)
                        self.page_registry[page_num] = {
                            'quality': blur_a,
                            'path': str(crop_base / save_name),
                            'name': name,
                        }

                crp_d = self._get_unique_path(crop_base, save_name, ext=".png")
                cv2.imwrite(str(crp_d), processed)

                if self.chk_learn.isChecked():
                    self.learner.add(img, params)
                    self.training.save_record(
                        img=img, initial_params=params, final_params=params,
                        operations=["auto_save_all"],
                        blur_before=blur_b, blur_after=blur_a,
                        image_name=name)

                entry.clear_cache()
                self.stats["processed"] += 1
                self._record_csv("auto_saved", crp_d)

        except Exception as exc:
            self._log("❌ خطأ في {}: {}".format(self.image_names[i], exc))
            logger.exception("auto_save_step error at index %d", i)

        # جدولة الخطوة التالية (فور انتهاء رسم الواجهة)
        self._auto_save_timer.start(0)

    def _cancel_batch(self):
        """v12: Cancel any running batch operation."""
        self._batch_cancelled = True
        self.btn_cancel_batch.setEnabled(False)
        self._log("⏹️ طلب إلغاء الدُفعة...")

    def _set_controls_enabled(self, enabled: bool):
        """v12: Enable/disable ALL interactive buttons at once."""
        targets = [
            self.btn_confirm, self.btn_skip, self.btn_auto_save_all,
            self.btn_apply_all, self.btn_smart_crop, self.btn_auto_deskew,
            self.btn_apply_deskew, self.btn_compare, self.btn_save_inplace,
            self.btn_rotate_left, self.btn_rotate_right, self.btn_analyze_pages,
            self.btn_prev, self.btn_next, self.btn_open, self.btn_refresh,
            self.btn_zoom_in, self.btn_zoom_out, self.btn_zoom_fit,
            self.btn_fullscreen, self.btn_remove_gray,
        ]
        for btn in targets:
            if hasattr(btn, 'setEnabled'):
                btn.setEnabled(enabled)
        self.btn_cancel_batch.setEnabled(not enabled)

    def _on_auto_save_toggle(self, state: int):
        """v12: Smart auto-save toggle with user confirmation."""
        if state == Qt.Checked:
            self.auto_save_enabled = True
            if self.image_list:
                reply = QMessageBox.question(
                    self, "حفظ تلقائي",
                    "تم تفعيل الحفظ التلقائي.\nهل تريد بدء الحفظ التلقائي الآن؟",
                    QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self._auto_save_all()
                else:
                    self._log("💾 تم تفعيل الحفظ التلقائي (بدون بدء)")
        else:
            self.auto_save_enabled = False
            if self._auto_save_timer.isActive():
                self._cancel_batch()
                self._log("⏹️ تم إيقاف الحفظ التلقائي")

    def _save_screenshot(self, widget=None):
        """v12: Capture and save a screenshot of any widget."""
        target = widget if widget else self
        pixmap = target.grab()
        path, _ = QFileDialog.getSaveFileName(
            self, "حفظ لقطة شاشة",
            "screenshot_{}.png".format(datetime.now().strftime('%Y%m%d_%H%M%S')),
            "PNG (*.png);;JPEG (*.jpg)")
        if path:
            pixmap.save(path)
            self._log("📸 لقطة محفوظة: {}".format(Path(path).name))

    def _skip_save(self):
        """Skip current image and move to next."""
        if self.current_img is None:
            return
        self.stats["skipped"] += 1
        self._update_stats()
        name = self.image_names[self.current_idx] if self.current_idx < len(self.image_names) else ""
        self._log("⏭️ تخطي: {}".format(name))
        if self.current_idx < len(self.image_list) - 1:
            self._navigate(1)

    def _apply_to_remaining(self):
        """Apply current processing parameters to all remaining images."""
        if self.current_img is None:
            return
        params = self.current_params.copy()
        remaining = len(self.image_list) - self.current_idx
        reply = QMessageBox.question(
            self, "تأكيد",
            "سيتم تطبيق الإعدادات الحالية على {} صورة متبقية.\nهل تريد المتابعة؟".format(remaining),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No:
            return

        docs_dir = Path.home() / "Documents"
        raw_base = docs_dir / "raw_scanned_files"
        crop_base = docs_dir / "cropped_scanned_files"
        count = 0

        for i in range(self.current_idx, len(self.image_list)):
            try:
                entry = self.image_list[i]
                name = self.image_names[i]
                img = entry.get()
                if img is None:
                    continue

                # Move raw
                if entry.is_path:
                    raw_dest = self._get_unique_path(raw_base, name, ext=Path(entry.name).suffix)
                    try:
                        shutil.move(str(entry._path), str(raw_dest))
                    except Exception:
                        pass

                # Save processed
                dest = self._get_unique_path(crop_base, name, ext=".png")
                cv2.imwrite(str(dest), apply_processing(img, params))

                if self.chk_learn.isChecked():
                    self.learner.add(img, params)

                count += 1
                self.progress.setValue(i + 1)
                QApplication.processEvents()
            except Exception:
                continue

        self.stats["processed"] += count
        self._update_stats()
        self._log("🤖 تم تطبيق الإعدادات على {} صورة".format(count))
        QMessageBox.information(self, "اكتمل", "تمت معالجة {} صورة.".format(count))

    # ──────────────────────────────────────────────────────────
    #  Navigation & Stats
    # ──────────────────────────────────────────────────────────

    def _navigate(self, step: int):
        """Navigate to next/previous image."""
        new_idx = self.current_idx + step
        if 0 <= new_idx < len(self.image_list):
            self.current_idx = new_idx
            self._load_current()
        elif new_idx >= len(self.image_list):
            QMessageBox.information(
                self, "اكتمل",
                "✅ وصلت إلى نهاية القائمة!\n"
                "معالجة: {}  |  تخطي: {}".format(self.stats['processed'], self.stats['skipped']))

    def _update_stats(self):
        """Update statistics labels."""
        self.lbl_s_total.setText(str(self.stats["total"]))
        self.lbl_s_proc.setText(str(self.stats["processed"]))
        self.lbl_s_skip.setText(str(self.stats["skipped"]))
        self.lbl_s_learn.setText(str(len(self.learner.history)))
        self._update_undo_label()

    def _tick_clock(self):
        """Update the session clock every second."""
        if self.stats.get("start_time"):
            elapsed = datetime.now() - self.stats["start_time"]
            self.lbl_s_time.setText(str(elapsed).split(".")[0])

    # ──────────────────────────────────────────────────────────
    #  Logging
    # ──────────────────────────────────────────────────────────

    def _log(self, msg: str):
        """Log a message to the UI and file."""
        ts = datetime.now().strftime("%H:%M:%S")
        line = "[{}] {}".format(ts, msg)
        self.txt_log.append(line)
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────
    #  CSV Export/Import
    # ──────────────────────────────────────────────────────────

    def _record_csv(self, action: str, dest: Path):
        """Record a processing action for CSV export."""
        name = self.image_names[self.current_idx] if self.current_idx < len(self.image_names) else ""
        self.processing_records.append({
            "name": name,
            "output": str(dest),
            "action": action,
            "crop": str(self.current_params.get("crop")),
            "deskew": round(self.current_params.get("deskew_angle", 0), 2),
            "flip_h": self.current_params.get("flip_h", False),
            "blur": round(self.current_blur, 1),
            "timestamp": datetime.now().isoformat(timespec="seconds")
        })

    def _record_processing(self, action: str, dest: Path):
        """Alias for _record_csv — kept for compatibility."""
        self._record_csv(action, dest)

    def _export_csv(self):
        """Export processing records to CSV."""
        if not self.processing_records:
            QMessageBox.information(self, "معلومات", "لا توجد سجلات بعد.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "حفظ تقرير CSV", "report.csv", "CSV (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=self.processing_records[0].keys())
            w.writeheader()
            w.writerows(self.processing_records)
        self._log("📤 CSV: {}".format(Path(path).name))
        QMessageBox.information(self, "نجاح", "تم حفظ التقرير:\n{}".format(path))

    def _export_learn(self):
        """Export learning data to JSON."""
        path, _ = QFileDialog.getSaveFileName(self, "حفظ التعلّم", "learner.json", "JSON (*.json)")
        if path:
            self.learner.export(path)
            self._log("💾 تصدير التعلّم: {}".format(Path(path).name))
            QMessageBox.information(self, "نجاح", "تم الحفظ:\n{}".format(path))

    def _import_learn(self):
        """Import learning data from JSON."""
        path, _ = QFileDialog.getOpenFileName(self, "استيراد التعلّم", "", "JSON (*.json)")
        if path:
            try:
                self.learner.load(path)
                self._log("📥 استيراد {} سجل".format(len(self.learner.history)))
                self._update_stats()
            except Exception as e:
                QMessageBox.critical(self, "خطأ", "فشل الاستيراد:\n{}".format(e))

    # ──────────────────────────────────────────────────────────
    #  UI Helper Methods
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _mk_btn(text: str, color: str, w: int = 0, h: int = 34) -> QPushButton:
        """Create a styled push button."""
        btn = QPushButton(text)
        if w:
            btn.setFixedWidth(w)
        btn.setFixedHeight(h)
        btn.setStyleSheet(
            "QPushButton{{background:{color};color:white;border-radius:6px;"
            "font-weight:bold;}}"
            "QPushButton:hover{{opacity:0.9;}}"
            "QPushButton:disabled{{background:#94a3b8;}}".format(color=color))
        return btn

    @staticmethod
    def _spinbox(lo: int, hi: int, val: int) -> QSpinBox:
        """Create a spin box with given range and initial value."""
        sb = QSpinBox()
        sb.setRange(lo, hi)
        sb.setValue(val)
        return sb

    # ──────────────────────────────────────────────────────────
    #  Zoom & Fullscreen
    # ──────────────────────────────────────────────────────────

    def _update_zoom_label(self):
        """Update zoom percentage label."""
        self.lbl_zoom.setText("{}%".format(int(self.zoom_factor * 100)))

    def zoom_in(self):
        """Zoom in by 25%."""
        self.zoom_factor = min(self.max_zoom, self.zoom_factor * 1.25)
        self._update_zoom_label()
        self._update_preview()

    def zoom_out(self):
        """Zoom out by 25%."""
        self.zoom_factor = max(self.min_zoom, self.zoom_factor / 1.25)
        self._update_zoom_label()
        self._update_preview()

    def zoom_fit(self):
        """Fit image to preview area."""
        if self.current_img is not None:
            h, w = self.current_img.shape[:2]
            scroll_size = self.preview_scroll.viewport().size()
            fit_w = scroll_size.width() / max(w, 1)
            fit_h = scroll_size.height() / max(h, 1)
            self.zoom_factor = max(self.min_zoom, min(self.max_zoom, min(fit_w, fit_h)))
        else:
            self.zoom_factor = 1.0
        self._update_zoom_label()
        self._update_preview()

    def toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ──────────────────────────────────────────────────────────
    #  Rotation
    # ──────────────────────────────────────────────────────────

    def rotate_left(self):
        """Rotate image 90° counter-clockwise."""
        if self.current_img is None:
            return
        self._push_undo()
        r = (self.current_params.get("rotation", 0) - 90) % 360
        self.current_params["rotation"] = r
        self.lbl_rotation.setText("{}°".format(r))
        self.operation_history.append("تدوير يسار → {}°".format(r))
        self._update_preview()
        self._log("↺ تدوير يسار → {}°".format(r))
        # Auto smart crop after rotation
        self._do_smart_crop()
        if self.chk_auto_save.isChecked():
            self._confirm_save()

    def rotate_right(self):
        """Rotate image 90° clockwise."""
        if self.current_img is None:
            return
        self._push_undo()
        r = (self.current_params.get("rotation", 0) + 90) % 360
        self.current_params["rotation"] = r
        self.lbl_rotation.setText("{}°".format(r))
        self.operation_history.append("تدوير يمين → {}°".format(r))
        self._update_preview()
        self._log("↻ تدوير يمين → {}°".format(r))
        # Auto smart crop after rotation
        self._do_smart_crop()
        if self.chk_auto_save.isChecked():
            self._confirm_save()

    # ──────────────────────────────────────────────────────────
    #  Clean Missing Files
    # ──────────────────────────────────────────────────────────

    def _clean_missing_files(self):
        """Remove entries for files that no longer exist."""
        if not self.image_list:
            return
        to_remove = []
        for i, entry in enumerate(self.image_list):
            if isinstance(entry, Path) and not entry.exists():
                to_remove.append(i)
                self._log("⚠️ ملف غير موجود تم حذفه: {}".format(entry.name))
        for i in reversed(to_remove):
            self.image_list.pop(i)
            self.image_names.pop(i)
            if i < len(self.image_paths):
                self.image_paths.pop(i)
        if to_remove:
            self.stats["total"] = len(self.image_list)
            self.progress.setMaximum(self.stats["total"])
            self.lbl_s_total.setText(str(self.stats["total"]))
            self._build_thumbnails()
            if self.current_idx >= len(self.image_list):
                self.current_idx = max(0, len(self.image_list) - 1)
            self._load_current()

    # ──────────────────────────────────────────────────────────
    #  Compatibility Aliases
    # ──────────────────────────────────────────────────────────

    def _show_current(self):
        """Alias for _load_current — kept for compatibility."""
        self._load_current()

    # ──────────────────────────────────────────────────────────
    #  Page Number Region Selection
    # ──────────────────────────────────────────────────────────

    def _select_page_number_region(self):
        """
        فتح حوار تحديد منطقة رقم الصفحة.
        يدعم مناطق متعددة للكتب ذات أرقام متغيرة الموقع (أعلى/أسفل).
        """
        if self.current_img is None:
            QMessageBox.warning(self, "تنبيه", "لا توجد صورة محملة.")
            return

        pix = cv2_to_pixmap(self.current_img, max_w=900, max_h=700)
        dlg = RegionSelectorDialog(pix, self)

        if dlg.exec_() == QDialog.Accepted:
            region_px = dlg.get_region()
            if region_px:
                # ── إصلاح Bug 1: تحويل من إحداثيات الـ Label إلى إحداثيات الـ Pixmap ──
                # الـ Label قد يكون أكبر من الصورة (AlignCenter) → نحسب offset
                pix_w = pix.width()
                pix_h = pix.height()
                lbl_w = dlg.label.width()
                lbl_h = dlg.label.height()
                offset_x = max(0, (lbl_w - pix_w) / 2)
                offset_y = max(0, (lbl_h - pix_h) / 2)

                # إحداثيات المربع بالنسبة للصورة (ليس الـ Label)
                rx = region_px.x() - offset_x
                ry = region_px.y() - offset_y
                rw = region_px.width()
                rh = region_px.height()

                # قص على حدود الصورة
                rx = max(0, min(rx, pix_w))
                ry = max(0, min(ry, pix_h))
                rw = max(0, min(rw, pix_w - rx))
                rh = max(0, min(rh, pix_h - ry))

                # تحويل إلى كسور (0-1) من أبعاد الـ Pixmap المصغّر
                # هذه الكسور ستعمل مع أي حجم صورة لأنها نسبية
                new_region = (
                    rx / pix_w,
                    ry / pix_h,
                    rw / pix_w,
                    rh / pix_h,
                )

                # تحقق من التكرار
                is_dup = False
                for existing in self._page_number_regions:
                    if (abs(existing[0] - new_region[0]) < 0.05 and
                        abs(existing[1] - new_region[1]) < 0.05):
                        is_dup = True
                        break

                if is_dup:
                    QMessageBox.information(self, "مكرر",
                        "هذه المنطقة محددة مسبقاً.\nحدد منطقة مختلفة أو مكان آخر للرقم.")
                    return

                # إضافة المنطقة الجديدة
                self._page_number_regions.append(new_region)
                self.btn_select_region.setText(
                    "📍 مناطق: {} ".format(len(self._page_number_regions)))
                self._log("📍 منطقة رقم الصفحة #{}: ({:.2f}, {:.2f}, {:.2f}, {:.2f})".format(
                    len(self._page_number_regions), *new_region))

                # اختبار فوري
                self._test_page_number_region()

    def _test_page_number_region(self):
        """اختبار OCR على جميع المناطق المحددة."""
        if not self._page_number_regions:
            return
        if self.current_img is None:
            return

        results = []
        for i, region in enumerate(self._page_number_regions):
            num = extract_page_number(self.current_img, region=region)
            results.append((i + 1, num))

        msg_parts = []
        found_any = False
        for idx, num in results:
            if num > 0:
                msg_parts.append("منطقة {}: صفحة {}".format(idx, num))
                found_any = True
            else:
                msg_parts.append("منطقة {}: لم يُعثر على رقم".format(idx))

        msg = "\n".join(msg_parts)
        if found_any:
            QMessageBox.information(self, "🧪 نتيجة الاختبار", msg)
            self._log("🧪 اختبار OCR: {}".format(msg))
        else:
            QMessageBox.warning(self, "⚠️ فشل الاختبار",
                "{}\n\nحاول رسم مربع أدق حول الرقم.".format(msg))

    # ──────────────────────────────────────────────────────────
    #  Smart Page Analysis & Organization
    # ──────────────────────────────────────────────────────────

    def analyze_and_organize_pages(self):
        """
        🧠 Comprehensive page analysis:
        - Extract page numbers using OCR
        - Detect duplicates using Perceptual Hash
        - Select best quality version for each page
        - Report missing and low-quality pages
        - Organize and save to directories
        """
        if not self.image_list:
            QMessageBox.warning(self, "تنبيه", "لا توجد صور لتحليلها.")
            return

        # Check OCR availability
        if not OCR_SUPPORT:
            QMessageBox.critical(
                self, "مكتبة مفقودة",
                "❌ مكتبة pytesseract غير مثبتة.\n\n"
                "ثبتها عبر:\n"
                "pip install pytesseract Pillow\n\n"
                "ثبت tesseract على نظامك أيضاً:\n"
                "Arch: sudo pacman -S tesseract tesseract-data-ara tesseract-data-eng\n"
                "Ubuntu: sudo apt install tesseract-ocr tesseract-ocr-ara tesseract-ocr-eng"
            )
            return

        # Warn about missing hash library
        if not HASH_SUPPORT:
            QMessageBox.warning(
                self, "تحذير",
                "⚠️ مكتبة imagehash غير مثبتة.\n"
                "سيتم الاستمرار بدون كشف المكررات الدقيق.\n\n"
                "للتثبيت: pip install imagehash"
            )

        # Ask for expected total pages
        expected_total, ok = QInputDialog.getInt(
            self, "العدد المتوقع للصفحات",
            "أدخل العدد الإجمالي المتوقع للصفحات\n(0 إذا كان مجهولاً):",
            0, 0, 10000, 1
        )
        if not ok:
            return

        self._log("🔍 بدء التحليل الذكي للصفحات...")
        self.progress.setMaximum(len(self.image_list))
        self.progress.setValue(0)

        # Data structures
        page_data = {}  # type: Dict[int, list]
        unknown_pages = []  # type: List[tuple]
        duplicates_info = []  # type: List[dict]

        # ═══ Phase 1: Extract page numbers & assess quality ═══
        for idx, entry in enumerate(self.image_list):
            try:
                # Load image
                img = entry.get()

                if img is None:
                    self._log("⚠️ تخطي (قراءة فاشلة): {}".format(self.image_names[idx]))
                    continue

                # Extract page number and assess quality
                user_regions = getattr(self, '_page_number_regions', None)
                page_num = extract_page_number(img, regions=user_regions)
                quality = assess_image_quality(img)
                name = self.image_names[idx] if idx < len(self.image_names) else "img_{}".format(idx)

                if page_num == 0:
                    unknown_pages.append((idx, quality, img, name))
                    self._log("❓ لا يوجد رقم صفحة واضح: {}".format(name))
                else:
                    if page_num not in page_data:
                        page_data[page_num] = []
                    page_data[page_num].append((idx, quality, img, name))
                    self._log("📄 صفحة {} | جودة: {:.3f} | {}".format(page_num, quality['overall'], name))

                # Update progress
                self.progress.setValue(idx + 1)
                QApplication.processEvents()

            except Exception as e:
                self._log("❌ خطأ في معالجة {}: {}".format(self.image_names[idx], e))

        # ═══ Phase 2: Select best version & detect duplicates ═══
        best_pages = {}  # type: Dict[int, tuple]

        for page_num, candidates in page_data.items():
            if len(candidates) == 1:
                best_pages[page_num] = candidates[0]
            else:
                # Sort by overall quality descending
                candidates.sort(key=lambda x: x[1]['overall'], reverse=True)
                best_pages[page_num] = candidates[0]

                # Check remaining candidates for true duplicates
                best_idx, best_qual, best_img, best_name = candidates[0]
                for dup_idx, dup_qual, dup_img, dup_name in candidates[1:]:
                    is_similar, distance = images_are_similar(best_img, dup_img)
                    if is_similar:
                        duplicates_info.append({
                            'page': page_num,
                            'best_idx': best_idx,
                            'best_quality': best_qual['overall'],
                            'dup_idx': dup_idx,
                            'dup_quality': dup_qual['overall'],
                            'similarity': 100.0 - distance,
                            'distance': distance,
                        })
                        self._log(
                            "🗑️ مكررة مكتشفة: صفحة {} | "
                            "تشابه: {:.1f}% | "
                            "جودة الأفضل: {:.3f} vs {:.3f}".format(
                                page_num, 100 - distance,
                                best_qual['overall'], dup_qual['overall']))

        # ═══ Phase 3: Create output directories ═══
        base_dir = Path.home() / "Documents" / "scanned_pages_analysis"
        best_dir = base_dir / "best_pages"
        duplicates_dir = base_dir / "duplicates"
        unknown_dir = base_dir / "unknown_pages"
        low_quality_dir = base_dir / "low_quality_pages"

        for d in [best_dir, duplicates_dir, unknown_dir, low_quality_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Save best pages
        saved_pages = []
        for page_num, (idx, quality, img, name) in best_pages.items():
            dest = best_dir / "page_{:04d}.png".format(page_num)
            cv2.imwrite(str(dest), img)
            saved_pages.append({
                'page': page_num,
                'quality': quality['overall'],
                'blur': quality['blur_score'],
                'file': dest.name,
                'original': name,
            })
            if quality['overall'] < 0.4:
                low_dest = low_quality_dir / "low_quality_page_{:04d}.png".format(page_num)
                cv2.imwrite(str(low_dest), img)
                self._log("⚠️ جودة منخفضة: صفحة {} ({:.3f})".format(page_num, quality['overall']))

        # Save duplicates
        for dup in duplicates_info:
            dup_idx = dup['dup_idx']
            entry = self.image_list[dup_idx]
            if isinstance(entry, Path) and entry.exists():
                dup_dest = duplicates_dir / (
                    "duplicate_page_{:04d}_sim_{:03.0f}p_q{:03.0f}.png".format(
                        dup['page'], dup['similarity'], dup['dup_quality'] * 1000))
                shutil.copy(str(entry), str(dup_dest))

        # Save unknown pages
        for idx, quality, img, name in unknown_pages:
            dest = unknown_dir / "unknown_{:04d}_q{:03.0f}.png".format(idx, quality['overall'] * 1000)
            cv2.imwrite(str(dest), img)

        # ═══ Phase 4: Detect missing pages ═══
        missing_pages = []
        if expected_total > 0:
            existing_pages = set(best_pages.keys())
            missing_pages = [p for p in range(1, expected_total + 1) if p not in existing_pages]

        # ═══ Phase 5: Generate comprehensive CSV report ═══
        report_path = base_dir / "analysis_report.csv"
        with open(report_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "رقم الصفحة", "الحالة", "درجة الجودة", "وضوح الصورة",
                "نسبة المحتوى", "اسم الملف", "ملاحظات"
            ])

            for page in saved_pages:
                qual = best_pages[page['page']][1]
                writer.writerow([
                    page['page'],
                    "✅ أفضل نسخة",
                    "{:.4f}".format(page['quality']),
                    "{:.1f}".format(qual['blur_score']),
                    "{:.4f}".format(qual['content_ratio']),
                    page['file'],
                    "أصلي: {}".format(page['original']),
                ])

            for dup in duplicates_info:
                writer.writerow([
                    dup['page'],
                    "🗑️ مكررة محذوفة",
                    "{:.4f}".format(dup['dup_quality']),
                    "",
                    "",
                    "تشابه {:.1f}% مع الأفضل".format(dup['similarity']),
                    "جودة الأفضل: {:.4f}".format(dup['best_quality']),
                ])

            for page_num in missing_pages:
                writer.writerow([page_num, "❌ ناقصة", "", "", "", "", "تحتاج إعادة مسح"])

            for idx, quality, img, name in unknown_pages:
                writer.writerow([
                    "؟؟",
                    "❓ بدون رقم",
                    "{:.4f}".format(quality['overall']),
                    "{:.1f}".format(quality['blur_score']),
                    "{:.4f}".format(quality['content_ratio']),
                    name,
                    "مراجعة يدوية مطلوبة",
                ])

        # ═══ Phase 6: Display summary ═══
        low_quality_count = sum(1 for p in saved_pages if p['quality'] < 0.4)

        summary_lines = [
            "✅ اكتمل التحليل الذكي بنجاح!",
            "",
            "📊 الإحصائيات:",
            "• إجمالي الصور المحللة: {}".format(len(self.image_list)),
            "• الصفحات المكتشفة (برقم): {}".format(len(best_pages)),
            "• المكررات المحذوفة: {}".format(len(duplicates_info)),
            "• الصفحات بدون رقم: {}".format(len(unknown_pages)),
            "• الصفحات ذات جودة منخفضة: {}".format(low_quality_count),
        ]

        if expected_total > 0:
            summary_lines.append("• الصفحات الناقصة: {} / {}".format(len(missing_pages), expected_total))
            if missing_pages:
                missing_str = ", ".join(str(p) for p in missing_pages[:20])
                if len(missing_pages) > 20:
                    missing_str += " ... و {} أخرى".format(len(missing_pages) - 20)
                summary_lines.append("  الأرقام الناقصة: {}".format(missing_str))

        summary_lines.extend([
            "",
            "📁 موقع النتائج:",
            str(base_dir),
            "",
            "المجلدات:",
            "  📄 best_pages/ — أفضل نسخة من كل صفحة",
            "  🗑️ duplicates/ — النسخ المكررة المحذوفة",
            "  ⚠️ low_quality_pages/ — الصفحات الرديئة",
            "  ❓ unknown_pages/ — الصفحات بدون رقم",
            "  📋 analysis_report.csv — التقرير الكامل",
        ])

        summary = "\n".join(summary_lines)

        self._log("═" * 50)
        for line in summary_lines:
            self._log(line)
        self._log("═" * 50)

        QMessageBox.information(self, "🧠 التحليل الذكي — النتائج", summary)

        # Offer to open results folder
        reply = QMessageBox.question(
            self, "فتح المجلد",
            "هل تريد فتح مجلد النتائج في مدير الملفات؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            subprocess.run(['xdg-open', str(base_dir)])

        self.progress.setValue(len(self.image_list))

    def _save_analysis_report(self, report_text: str):
        """Save analysis report to a text file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "حفظ تقرير التحليل", "analysis_report.txt", "Text (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(report_text)
            self._log("💾 تم حفظ التقرير: {}".format(Path(path).name))
            QMessageBox.information(self, "نجاح", "تم حفظ التقرير:\n{}".format(path))


# ════════════════════════════════════════════════════════════════
#  Main Entry Point
# ════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setStyle("Fusion")
    window = MedicalDocApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
