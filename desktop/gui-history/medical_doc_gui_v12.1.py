#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
معالج الوثائق الطبية التفاعلي - v12.1 (النسخة النهائية المُدمجة)
───────────────────────────────────────────────────────
مبنية على v10 + v10.1 + v12 مع جميع التحسينات:
  ✅ معالجة صور كاملة (قص، ميلان، تدوير، تحسين، إزالة ظل)
  ✅ نظام تعلّم تكيفي + جامع بيانات تدريب (KNN)
  ✅ تحليل ذكي للصفحات (OCR + تجميع + تقارير)
  ✅ كشف المكررات باستخدام Perceptual Hash
  ✅ تقييم شامل لجودة الصور
  ✅ دعم السحب والإفلات واختصارات لوحة المفاتيح
  ✅ تراجع/إعادة + تصدير CSV/JSON
  ✅ إصلاح Race Condition بـ QMutex + _is_processing
  ✅ نقل آمن عبر أنظمة ملفات مختلفة (_safe_move)
  ✅ تعطيل الأزرار أثناء المعالجة الجماعية
  ✅ تمرير blur محسوب بدلاً من إعادة حساب
  ✅ LazyImage محسّن مع تحرير ذاكرة فوري
  ✅ عتبة رمادي قابلة للتعديل من الواجهة
  ✅ نظام logging موحّد
  ✅ حفظ تلقائي تسلسلي غير حاجب (QTimer)
  ✅ حفظ محلي (فوق الأصل) مع إعادة تعيين البارامترات
  ✅ تدوير → قص ذكي تلقائي → حفظ تلقائي إذا مفعّل
  ✅ إصلاح _on_auto_skew_done (مرة واحدة فقط)
  ✅ حفظ ذكي مع OCR وترقيم صفحات
  ✅ إلغاء عمليات الدُفعات
  ✅ لقطات الشاشة
  ✅ إدارة موحدة للأزرار
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
    QInputDialog, QDialogButtonBox, QShortcut,
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize, QMutex, QMutexLocker
from PyQt5.QtGui import QPixmap, QImage, QFont, QKeySequence, QColor, QIcon

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

    @property
    def is_path(self) -> bool:
        return self._path is not None

    def exists(self) -> bool:
        return self._path.exists() if self._path else (self._array is not None)

    def get(self) -> Optional[np.ndarray]:
        if self._cache is not None:
            return self._cache
        if self._array is not None:
            return self._array
        if self._path and self._path.exists():
            self._cache = cv2.imread(str(self._path))
            if self._cache is None:
                logger.warning("LazyImage: فشل قراءة %s", self._path)
            return self._cache
        return None

    def clear_cache(self):
        """تحرير الذاكرة — ستُعاد القراءة عند الطلب التالي."""
        self._cache = None

    def update_path(self, new_path: Path):
        self._path  = new_path
        self._cache = None

    def __repr__(self):
        return f"LazyImage({self.name})"


# ════════════════════════════════════════════════════════════════
#  Core Image Processing Functions
# ════════════════════════════════════════════════════════════════

def apply_processing(img: np.ndarray, params: dict) -> np.ndarray:
    """Full processing pipeline: rotation, crop, deskew, flip, sharpen, shadow removal."""
    out = img.copy()
    rotation = params.get("rotation", 0) % 360
    if rotation == 90:
        out = cv2.rotate(out, cv2.ROTATE_90_CLOCKWISE)
    elif rotation == 180:
        out = cv2.rotate(out, cv2.ROTATE_180)
    elif rotation == 270:
        out = cv2.rotate(out, cv2.ROTATE_90_COUNTERCLOCKWISE)
    h, w = out.shape[:2]
    l, t, r, b = params.get("crop", (0, 0, 0, 0))
    r2, b2 = w - r, h - b
    if l < r2 and t < b2:
        out = out[t:b2, l:r2]
    angle = params.get("deskew_angle", 0.0)
    if abs(angle) > 0.05:
        ch, cw = out.shape[:2]
        M = cv2.getRotationMatrix2D((cw / 2, ch / 2), angle, 1.0)
        out = cv2.warpAffine(out, M, (cw, ch),
                             flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT,
                             borderValue=(255, 255, 255))
    if params.get("flip_h", False):
        out = cv2.flip(out, 1)
    if params.get("sharpen", False):
        blurred = cv2.GaussianBlur(out, (0, 0), 3)
        out = cv2.addWeighted(out, 1.5, blurred, -0.5, 0)
    if params.get("remove_shadow", False):
        out = _remove_shadow(out)
    return out


def _remove_shadow(img: np.ndarray) -> np.ndarray:
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
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def quality_label(score: float, thr: float) -> Tuple[str, str, str]:
    if score >= thr * 2:
        return "ممتازة", "#16a34a", "✅"
    if score >= thr:
        return "مقبولة", "#d97706", "⚠️"
    return "ضبابية", "#dc2626", "❌"


def find_page_bounds(img: np.ndarray,
                     page_threshold: int = 200,
                     min_page_fraction: float = 0.25) -> tuple:
    """
    يجد حدود الصفحة البيضاء داخل خلفية الماسح الرمادية.
    يعمل على الأعمدة فقط (يمين/يسار).
    يُرجع (l, 0, r, 0) — قص يسار/يمين فقط.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    w    = gray.shape[1]
    col_p50 = np.median(gray, axis=0)

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
            return 0, n - 1
        return int(starts[best]), int(ends[best]) - 1

    col_s, col_e = _largest_block(col_p50)
    MARGIN       = 5
    left         = max(0,   col_s - MARGIN)
    right        = min(w-1, col_e + MARGIN)
    return (left, 0, w - right - 1, 0)


def auto_detect_skew(img: np.ndarray, max_a: float = 15.0, step: float = 0.5) -> float:
    """يكشف زاوية الميلان — يُزيل الحدود الرمادية أولاً."""
    l, _t, r, _b = find_page_bounds(img)
    h, w = img.shape[:2]
    x0, x1 = l, w - r if r > 0 else w
    page = img[:, x0:x1] if (x1 > x0) else img
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
    """قص ذكي على مرحلتين — إزالة الرمادي ثم كشف المحتوى."""
    h, w = img.shape[:2]
    gl, gt, gr, gb = find_page_bounds(img)
    x0, x1 = gl, w - gr if gr > 0 else w
    if x1 <= x0:
        return (0, 0, 0, 0)
    page = img[:, x0:x1]
    pw = page.shape[1]
    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY) if page.ndim == 3 else page
    _, binary = cv2.threshold(gray, dark_threshold, 255, cv2.THRESH_BINARY_INV)
    col_has = binary.max(axis=0) > 0
    row_has = binary.max(axis=1) > 0
    content_cols = np.where(col_has)[0]
    content_rows = np.where(row_has)[0]
    if len(content_cols) == 0 or len(content_rows) == 0:
        return (gl, gt, gr, gb)
    cl = max(0,    content_cols[0]  - padding)
    cr = min(pw-1, content_cols[-1] + padding)
    ct = max(0,    content_rows[0]  - padding)
    cb = min(h-1,  content_rows[-1] + padding)
    return (max(0, gl + cl),
            max(0, gt + ct),
            max(0, gr + (pw - cr - 1)),
            max(0, gb + (h  - cb - 1)))


def load_pdf_as_images(pdf_path: str, dpi: int = 200) -> List[np.ndarray]:
    pages = convert_from_path(pdf_path, dpi=dpi)
    result = []
    for page in pages:
        arr = np.array(page)
        result.append(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    return result


# ════════════════════════════════════════════════════════════════
#  AI Helper Functions (OCR, Hash, Quality)
# ════════════════════════════════════════════════════════════════

def extract_page_number(img: np.ndarray) -> int:
    if not OCR_SUPPORT:
        return 0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    regions = [
        gray[h - 150:h, w - 150:w],
        gray[h - 150:h, 0:150],
        gray[0:150, w - 150:w],
        gray[0:150, 0:150],
    ]
    best_number, best_confidence = 0, 0
    for region in regions:
        try:
            enhanced = cv2.bitwise_not(region)
            _, enhanced = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            if enhanced.shape[1] < 200:
                enhanced = cv2.resize(enhanced, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            data = pytesseract.image_to_data(
                enhanced,
                config='--oem 3 --psm 10 -c tessedit_char_whitelist=0123456789',
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
        logger.warning("Hash comparison error: %s", e)
        return False, 100.0


def assess_image_quality(img: np.ndarray) -> Dict[str, float]:
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
                if hasattr(item, 'get'):
                    img = item.get()
                    if img is not None and item.is_path:
                        item.clear_cache()
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
    MAX = 30

    def __init__(self):
        self.history = []

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
    FILEPATH = Path("medical_doc_training.jsonl")
    MIN_INFER = 5
    SIM_THRESH = 0.80

    def __init__(self):
        self.records = []
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
            return {k: (list(v) if isinstance(v, tuple) else v) for k, v in p.items()}
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
#  Main Application Class
# ════════════════════════════════════════════════════════════════

class MedicalDocApp(QMainWindow):

    def _get_unique_path(self, base_dir, relative_path, ext=".png"):
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

    @staticmethod
    def _safe_move(src: Path, dst: Path):
        """نقل آمن عبر أنظمة ملفات مختلفة."""
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(src), str(dst))
        except shutil.Error:
            shutil.copy2(str(src), str(dst))
            src.unlink()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏥 معالج الوثائق الطبية v12.1")
        self.setMinimumSize(1024, 600)
        self.showMaximized()
        self.setFont(QFont("Noto Sans Arabic", 10))
        self.setAcceptDrops(True)

        # ── حماية من التداخل ──────────────────────────────────
        self._mutex             = QMutex()
        self._is_processing     = False
        self._auto_save_in_prog = False
        self._batch_cancelled   = False

        # Image data
        self.image_list   = []
        self.image_names  = []
        self.image_paths  = []
        self.current_idx  = 0
        self.current_img  = None
        self.current_blur = 0.0
        self.processed_blur = 0.0
        self.blur_threshold = 100.0
        self.gray_threshold = 200
        self.current_params = {
            "crop": (20, 20, 20, 20),
            "deskew_angle": 0.0,
            "flip_h": False,
            "sharpen": False,
            "remove_shadow": False,
            "rotation": 0,
        }

        # Undo/Redo
        self._undo_stack = deque(maxlen=UNDO_LIMIT)
        self._redo_stack = deque(maxlen=UNDO_LIMIT)

        # Stats
        self.stats = {"total": 0, "processed": 0, "skipped": 0, "start_time": None}
        self.processing_records = []

        # Learning
        self.learner = AdaptiveLearner()
        self.training = TrainingDataCollector()
        self.operation_history = []
        self.initial_params_snapshot = {}

        # Thumbnails
        self.thumb_buttons = []

        # Workers
        self._skew_worker = None
        self._thumb_worker = None
        self._detected_angle = 0.0

        # Zoom
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0

        # Auto-save
        self.auto_save_enabled = False

        # v12: Sequential auto-save queue & timer (non-blocking)
        self._auto_save_queue = []
        self._auto_save_timer = QTimer(self)
        self._auto_save_timer.setSingleShot(True)
        self._auto_save_timer.setInterval(0)
        self._auto_save_timer.timeout.connect(self._auto_save_step)

        # v12: Smart save page registry
        self.page_registry = {}

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

    def _mk_btn(self, text, color, w=None, h=None):
        btn = QPushButton(text)
        style = ("QPushButton{{background:{};color:white;border:none;"
                 "border-radius:4px;padding:4px 10px;font-weight:bold;}}"
                 "QPushButton:hover{{opacity:0.9;}}"
                 "QPushButton:pressed{{background:#1e293b;}}"
                 "QPushButton:disabled{{background:#94a3b8;}}").format(color)
        btn.setStyleSheet(style)
        if w:
            btn.setFixedWidth(w)
        if h:
            btn.setFixedHeight(h)
        return btn

    def _spinbox(self, lo, hi, val):
        sp = QSpinBox()
        sp.setRange(lo, hi)
        sp.setValue(val)
        sp.setFixedWidth(80)
        return sp

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

        left_w = QWidget()
        left_l = QVBoxLayout(left_w)
        left_l.setSpacing(4)

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

        ctrl = QHBoxLayout()
        self.btn_refresh = self._mk_btn("🔄 تحديث", "#475569", h=32)
        self.btn_zoom_out = self._mk_btn("🔍-", "#475569", h=32, w=50)
        self.btn_zoom_in = self._mk_btn("🔍+", "#475569", h=32, w=50)
        self.btn_zoom_fit = self._mk_btn("⛶ ملاءمة", "#475569", h=32, w=70)
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(45)
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        self.btn_fullscreen = self._mk_btn("⛶ ملء", "#475569", h=32, w=50)
        self.btn_rotate_left = self._mk_btn("↺ يسار", "#7c3aed", h=32, w=65)
        self.lbl_rotation = QLabel("0°")
        self.lbl_rotation.setFixedWidth(28)
        self.lbl_rotation.setAlignment(Qt.AlignCenter)
        self.lbl_rotation.setStyleSheet("font-weight:bold; color:#7c3aed;")
        self.btn_rotate_right = self._mk_btn("↻ يمين", "#7c3aed", h=32, w=65)
        self.btn_auto_deskew = self._mk_btn("📐 كشف ميلان", "#f59e0b", h=32)
        self.btn_apply_deskew = self._mk_btn("✔️ تطبيق", "#0ea5e9", h=32, w=75)
        self.btn_smart_crop = self._mk_btn("✂️ قص ذكي", "#7c3aed", h=32)
        self.btn_remove_gray = self._mk_btn("🖼️ إزالة رمادي", "#0891b2", h=32)
        self.btn_compare = self._mk_btn("🔍 مقارنة", "#6366f1", h=32)
        self.btn_save_inplace = self._mk_btn("💾 حفظ محلي", "#0891b2", h=32)
        self.btn_confirm = self._mk_btn("✅ تأكيد وحفظ", "#16a34a", h=32)
        self.btn_skip = self._mk_btn("⏭️ تخطي", "#dc2626", h=32)
        self.btn_apply_all = self._mk_btn("🤖 طبّق على البقية", "#0369a1", h=32)
        self.btn_auto_save_all = self._mk_btn("🔁 حفظ تلقائي الكل", "#dc6b19", h=32)
        self.btn_apply_deskew.setEnabled(False)
        self.btn_apply_all.setEnabled(False)

        for b in [self.btn_refresh, self.btn_zoom_out, self.btn_zoom_in, self.btn_zoom_fit,
                  self.lbl_zoom, self.btn_fullscreen,
                  self.btn_rotate_left, self.lbl_rotation, self.btn_rotate_right,
                  self.btn_auto_deskew, self.btn_apply_deskew,
                  self.btn_smart_crop, self.btn_remove_gray, self.btn_compare,
                  self.btn_save_inplace, self.btn_confirm, self.btn_skip,
                  self.btn_apply_all, self.btn_auto_save_all]:
            ctrl.addWidget(b)
        left_l.addLayout(ctrl)

        right_w = QWidget()
        right_w.setFixedWidth(440)
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

        self.chk_smart_save = QCheckBox("📄 حفظ ذكي (OCR وترقيم)")
        self.chk_smart_save.setChecked(True)
        if not OCR_SUPPORT:
            self.chk_smart_save.setEnabled(False)
            self.chk_smart_save.setToolTip("يتطلب تثبيت pytesseract")

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
        mid_splitter.addWidget(left_w)
        mid_splitter.addWidget(right_w)
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

        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFixedHeight(18)
        main_vbox.addWidget(self.progress)

    # ──────────────────────────────────────────────────────────
    #  Signal Connections
    # ──────────────────────────────────────────────────────────

    def _connect_signals(self):
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

        self.chk_auto_save.stateChanged.connect(self._on_auto_save_toggle)

        self.slider_deskew.valueChanged.connect(
            lambda v: self.lbl_deskew.setText("{:+.1f}°".format(v / 10)))
        self.slider_threshold.valueChanged.connect(self._on_thr_change)
        self.slider_gray_thr.valueChanged.connect(self._on_gray_thr_change)

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
        QShortcut(QKeySequence("Escape"), self, self._cancel_batch)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self._save_in_place)

    # ──────────────────────────────────────────────────────────
    #  Drag & Drop
    # ──────────────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self._load_paths([url.toLocalFile() for url in event.mimeData().urls()])

    def keyPressEvent(self, event):
        key = event.key()
        mod = event.modifiers()
        if key == Qt.Key_Plus and mod & Qt.ControlModifier:
            self.zoom_in(); event.accept(); return
        elif key == Qt.Key_Minus and mod & Qt.ControlModifier:
            self.zoom_out(); event.accept(); return
        elif key == Qt.Key_0 and mod & Qt.ControlModifier:
            self.zoom_fit(); event.accept(); return
        elif key == Qt.Key_R and mod & Qt.ControlModifier:
            self.rotate_right(); event.accept(); return
        elif key == Qt.Key_L and mod & Qt.ControlModifier:
            self.rotate_left(); event.accept(); return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self._batch_cancelled = True
        self._auto_save_timer.stop()
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.stop()
            self._thumb_worker.wait()
        if self._skew_worker and self._skew_worker.isRunning():
            self._skew_worker.quit()
            self._skew_worker.wait()
        event.accept()

    # ──────────────────────────────────────────────────────────
    #  Unified Button Management
    # ──────────────────────────────────────────────────────────

    def _set_controls_enabled(self, enabled: bool):
        """تعطيل/تفعيل الأزرار أثناء المعالجة الجماعية"""
        for btn in [self.btn_confirm, self.btn_skip, self.btn_apply_all,
                    self.btn_auto_save_all, self.btn_open, self.btn_smart_crop,
                    self.btn_remove_gray, self.btn_auto_deskew, self.btn_apply_deskew,
                    self.btn_save_inplace, self.btn_rotate_left, self.btn_rotate_right,
                    self.btn_prev, self.btn_next]:
            btn.setEnabled(enabled)

    # ──────────────────────────────────────────────────────────
    #  File Loading
    # ──────────────────────────────────────────────────────────

    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "اختر مجلداً")
        if folder:
            self._load_paths([folder])

    def _load_paths(self, paths: list):
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
                    elif ext == ".pdf" and PDF_SUPPORT:
                        try:
                            pages = load_pdf_as_images(str(f))
                            for j, pg in enumerate(pages):
                                n = "{}_p{:03d}.png".format(f.stem, j + 1)
                                lazy_imgs.append(LazyImage(pg, n))
                                names.append(n)
                                img_paths.append(f)
                        except Exception as e:
                            self._log("⚠️ خطأ PDF {}: {}".format(f.name, e))
            elif pp.is_file():
                ext = pp.suffix.lower()
                if ext in IMG_EXT and pp.exists():
                    lazy_imgs.append(LazyImage(pp, pp.name))
                    names.append(pp.name)
                    img_paths.append(pp)
                elif ext == ".pdf" and PDF_SUPPORT:
                    try:
                        pages = load_pdf_as_images(str(pp))
                        for j, pg in enumerate(pages):
                            n = "{}_p{:03d}.png".format(pp.stem, j + 1)
                            lazy_imgs.append(LazyImage(pg, n))
                            names.append(n)
                            img_paths.append(pp)
                    except Exception as e:
                        self._log("⚠️ خطأ PDF {}: {}".format(pp.name, e))
        if not lazy_imgs:
            QMessageBox.warning(self, "تنبيه", "لم يتم العثور على ملفات صالحة.")
            return
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.stop()
            self._thumb_worker.wait()
        self.image_list = lazy_imgs
        self.image_names = names
        self.image_paths = img_paths
        self.current_idx = 0
        self.processing_records = []
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.page_registry = {}
        self.stats = {"total": len(lazy_imgs), "processed": 0, "skipped": 0, "start_time": datetime.now()}
        self.progress.setMaximum(len(lazy_imgs))
        self.lbl_s_total.setText(str(len(lazy_imgs)))
        self._log("📥 تم تحميل {} ملف (LazyImage — تحميل كسول)".format(len(lazy_imgs)))
        self._build_thumbnails()
        self._load_current()

    def _load_current(self):
        if not self.image_list:
            return
        if self._is_processing:
            logger.debug("_load_current: تأجيل — المعالجة قيد التشغيل")
            return

        entry = self.image_list[self.current_idx]
        name = self.image_names[self.current_idx]
        self.lbl_index.setText("{} / {}".format(self.current_idx + 1, len(self.image_list)))
        self.progress.setValue(self.current_idx)
        self._update_thumb_selection()

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
            if self.image_list:
                self._load_current()
            return

        img = entry.get()
        if img is None:
            self._log("❌ فشل قراءة: {}".format(name))
            return

        self.current_img = img
        self.current_blur = calc_blur(img)
        self.processed_blur = 0.0
        self._update_quality_display()

        # إعادة تعيين البارامترات
        self.current_params = {
            "crop": (0, 0, 0, 0),
            "deskew_angle": 0.0,
            "flip_h": False,
            "sharpen": False,
            "remove_shadow": False,
            "rotation": 0,
        }
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

        if hasattr(self, 'chk_auto_deskew') and self.chk_auto_deskew.isChecked():
            self._apply_auto_deskew_on_load()
        else:
            self._update_preview()

    # ──────────────────────────────────────────────────────────
    #  Thumbnails
    # ──────────────────────────────────────────────────────────

    def _build_thumbnails(self):
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
        if idx < len(self.thumb_buttons):
            self.thumb_buttons[idx].set_pixmap(pix)

    def _update_thumb_selection(self):
        for i, btn in enumerate(self.thumb_buttons):
            btn.setChecked(i == self.current_idx)
        if self.current_idx < len(self.thumb_buttons):
            self.thumb_scroll.ensureWidgetVisible(self.thumb_buttons[self.current_idx])

    def _jump_to(self, idx: int):
        self.current_idx = idx
        self._load_current()

    # ──────────────────────────────────────────────────────────
    #  UI Sync
    # ──────────────────────────────────────────────────────────

    def _sync_ui_from_params(self):
        crop = self.current_params.get("crop", (0, 0, 0, 0))
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
        self.lbl_rotation.setText("{}°".format(self.current_params.get("rotation", 0)))

    def _collect_params(self) -> dict:
        return {
            "crop": (self.sp_left.value(), self.sp_top.value(),
                     self.sp_right.value(), self.sp_bottom.value()),
            "deskew_angle": self.slider_deskew.value() / 10.0,
            "flip_h": self.chk_flip.isChecked(),
            "sharpen": self.btn_sharpen.isChecked(),
            "remove_shadow": self.chk_shadow.isChecked(),
            "rotation": self.current_params.get("rotation", 0),
        }

    def _reset_params(self):
        """إعادة تعيين جميع البارامترات إلى الصفر."""
        self.current_params = {
            "crop": (0, 0, 0, 0),
            "deskew_angle": 0.0,
            "flip_h": False,
            "sharpen": False,
            "remove_shadow": False,
            "rotation": 0,
        }
        self._sync_ui_from_params()

    # ──────────────────────────────────────────────────────────
    #  Preview
    # ──────────────────────────────────────────────────────────

    def _update_preview(self):
        if self.current_img is None:
            return
        self.current_params = self._collect_params()
        processed = apply_processing(self.current_img, self.current_params)
        self.processed_blur = calc_blur(processed)
        vp_w = self.preview_scroll.viewport().width() - 20
        vp_h = self.preview_scroll.viewport().height() - 20
        pix = cv2_to_pixmap(processed, zoom=self.zoom_factor, max_w=vp_w, max_h=vp_h)
        self.lbl_preview.setPixmap(pix)
        self.lbl_zoom.setText("{}%".format(int(self.zoom_factor * 100)))
        self._update_quality_display()

    def _update_quality_display(self):
        score = self.processed_blur if self.processed_blur > 0 else self.current_blur
        self.lbl_blur_val.setText("{:.1f}".format(score))
        label, color, icon = quality_label(score, self.blur_threshold)
        self.lbl_quality.setText("{} {}".format(icon, label))
        self.lbl_quality.setStyleSheet(
            "font-weight:bold;padding:8px;border-radius:5px;"
            "background:{};color:white;".format(color))
        if score < self.blur_threshold:
            self.lbl_blur_warn.setText("⚠️ الصورة ضبابية — درجة الوضوح أقل من العتبة ({})".format(
                int(self.blur_threshold)))
        else:
            self.lbl_blur_warn.setText("")

    # ──────────────────────────────────────────────────────────
    #  Navigation
    # ──────────────────────────────────────────────────────────

    def _navigate(self, delta: int):
        if not self.image_list:
            return
        new_idx = self.current_idx + delta
        if 0 <= new_idx < len(self.image_list):
            self.current_idx = new_idx
            self._load_current()

    # ──────────────────────────────────────────────────────────
    #  Zoom
    # ──────────────────────────────────────────────────────────

    def zoom_in(self):
        self.zoom_factor = min(self.zoom_factor * 1.25, self.max_zoom)
        self._update_preview()

    def zoom_out(self):
        self.zoom_factor = max(self.zoom_factor / 1.25, self.min_zoom)
        self._update_preview()

    def zoom_fit(self):
        self.zoom_factor = 1.0
        self._update_preview()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    # ──────────────────────────────────────────────────────────
    #  Rotation → قص ذكي تلقائي → حفظ تلقائي إذا مفعّل
    # ──────────────────────────────────────────────────────────

    def rotate_left(self):
        self._do_rotate(-90)

    def rotate_right(self):
        self._do_rotate(90)

    def _do_rotate(self, degrees: int):
        if self.current_img is None:
            return
        self._push_undo()
        rot = self.current_params.get("rotation", 0)
        self.current_params["rotation"] = (rot + degrees) % 360
        self._sync_ui_from_params()
        self._update_preview()

        # قص ذكي تلقائي بعد التدوير (الأبعاد تغيرت)
        QTimer.singleShot(100, self._auto_crop_after_rotation)

    def _auto_crop_after_rotation(self):
        """قص ذكي تلقائي بعد التدوير."""
        if self.current_img is None:
            return
        self.current_params = self._collect_params()
        processed = apply_processing(self.current_img, self.current_params)
        crop = smart_auto_crop(processed, padding=15, dark_threshold=int(self.blur_threshold))
        self.current_params["crop"] = crop
        self._sync_ui_from_params()
        self._update_preview()
        self._log("✂️ قص ذكي تلقائي بعد التدوير: L={} T={} R={} B={}".format(*crop))

        # حفظ تلقائي إذا مفعّل
        if self.chk_auto_save.isChecked():
            QTimer.singleShot(150, self._save_in_place)

    # ──────────────────────────────────────────────────────────
    #  Undo / Redo
    # ──────────────────────────────────────────────────────────

    def _push_undo(self):
        self._undo_stack.append(self.current_params.copy())
        self._redo_stack.clear()
        self._update_undo_label()

    def _undo(self):
        if not self._undo_stack:
            return
        self._redo_stack.append(self.current_params.copy())
        self.current_params = self._undo_stack.pop()
        self._sync_ui_from_params()
        self._update_preview()
        self._update_undo_label()

    def _redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append(self.current_params.copy())
        self.current_params = self._redo_stack.pop()
        self._sync_ui_from_params()
        self._update_preview()
        self._update_undo_label()

    def _update_undo_label(self):
        self.lbl_s_undo.setText("{} / {}".format(len(self._undo_stack), len(self._redo_stack)))

    # ──────────────────────────────────────────────────────────
    #  Skew Detection & Application
    # ──────────────────────────────────────────────────────────

    def _start_skew(self):
        if self.current_img is None:
            return
        self._is_processing = True
        self.btn_auto_deskew.setEnabled(False)
        self._log("📐 جاري كشف الميلان...")
        self._skew_worker = SkewWorker(self.current_img)
        self._skew_worker.finished.connect(self._on_skew_detected)
        self._skew_worker.error.connect(self._on_skew_error)
        self._skew_worker.start()

    def _on_skew_detected(self, angle: float):
        self._is_processing = False
        self.btn_auto_deskew.setEnabled(True)
        self._detected_angle = angle
        self._log("📐 ميلان مكتشف: {:+.1f}°".format(angle))
        self.btn_apply_deskew.setEnabled(True)
        if self.chk_auto_deskew.isChecked():
            self._apply_skew()

    def _on_skew_error(self, err: str):
        self._is_processing = False
        self.btn_auto_deskew.setEnabled(True)
        self._log("❌ خطأ كشف الميلان: {}".format(err))

    def _apply_skew(self):
        self._push_undo()
        self.current_params["deskew_angle"] = self._detected_angle
        self._sync_ui_from_params()
        self.btn_apply_deskew.setEnabled(False)
        self.operation_history.append("deskew:{:+.1f}".format(self._detected_angle))
        self._update_preview()
        self._log("✔️ تم تطبيق الميلان: {:+.1f}°".format(self._detected_angle))

    def _apply_auto_deskew_on_load(self):
        if self.current_img is None:
            return
        self._is_processing = True
        self._skew_worker = SkewWorker(self.current_img)
        self._skew_worker.finished.connect(self._on_auto_skew_done)
        self._skew_worker.error.connect(self._on_auto_skew_error)
        self._skew_worker.start()

    def _on_auto_skew_done(self, angle: float):
        """إصلاح: مرة واحدة فقط — لا تكرار."""
        self._is_processing = False
        self._detected_angle = angle
        if abs(angle) > 0.1:
            self.current_params["deskew_angle"] = angle
            self._sync_ui_from_params()
            self.operation_history.append("auto_deskew:{:+.1f}".format(angle))
            self._log("📐 ميلان تلقائي: {:+.1f}°".format(angle))

        # قص ذكي تلقائي بعد الميلان
        if self.current_img is not None:
            self.current_params = self._collect_params()
            processed = apply_processing(self.current_img, self.current_params)
            crop = smart_auto_crop(processed, padding=15, dark_threshold=int(self.blur_threshold))
            self.current_params["crop"] = crop
            self._sync_ui_from_params()
            self._log("✂️ قص ذكي تلقائي: L={} T={} R={} B={}".format(*crop))

        # حفظ تلقائي إذا مفعّل
        if self.chk_auto_save.isChecked():
            self._do_save_to_output()
            self._navigate(1)
        else:
            self._update_preview()

    def _on_auto_skew_error(self, err: str):
        self._is_processing = False
        self._log("❌ خطأ ميلان تلقائي: {}".format(err))
        if self.chk_auto_save.isChecked():
            self._do_save_to_output()
            self._navigate(1)
        else:
            self._update_preview()

    # ──────────────────────────────────────────────────────────
    #  Smart Crop & Remove Gray
    # ──────────────────────────────────────────────────────────

    def _do_smart_crop(self):
        if self.current_img is None:
            return
        self._push_undo()
        crop = smart_auto_crop(self.current_img, padding=15, dark_threshold=int(self.blur_threshold))
        self.current_params["crop"] = crop
        self._sync_ui_from_params()
        self.operation_history.append("smart_crop:{}".format(crop))
        self._update_preview()
        self._log("✂️ قص ذكي: يسار={} علوي={} أيمن={} سفلي={}".format(*crop))

    def _do_remove_gray(self):
        if self.current_img is None:
            return
        self._push_undo()
        crop = find_page_bounds(self.current_img, page_threshold=self.gray_threshold)
        l, t, r, b = crop
        self.current_params["crop"] = (l, t, r, b)
        self._sync_ui_from_params()
        self.operation_history.append("remove_gray:{}".format(crop))
        self._update_preview()
        self._log("🖼️ إزالة رمادي: يسار={} أيمن={}".format(l, r))

    # ──────────────────────────────────────────────────────────
    #  Compare
    # ──────────────────────────────────────────────────────────

    def _show_compare(self):
        if self.current_img is None:
            return
        orig_pix = cv2_to_pixmap(self.current_img, max_w=600, max_h=700)
        processed = apply_processing(self.current_img, self.current_params)
        proc_pix = cv2_to_pixmap(processed, max_w=600, max_h=700)
        dlg = CompareDialog(orig_pix, proc_pix, self)
        dlg.exec_()

    # ──────────────────────────────────────────────────────────
    #  Save Operations
    # ──────────────────────────────────────────────────────────

    def _confirm_save(self):
        """تأكيد وحفظ — ينظم في مجلدات حسب الجودة."""
        if self.current_img is None:
            return
        self._do_save_to_output(organize=True)

    def _save_in_place(self):
        """
        💾 حفظ محلي — يكتب الصورة المعالجة فوق الأصل مباشرة
        ثم يُعيد جميع البارامترات إلى الصفر تلقائياً جاهزاً للمرحلة التالية.
        """
        if self.current_img is None:
            return

        params = self._collect_params()
        processed = apply_processing(self.current_img, params)
        self.processed_blur = calc_blur(processed)

        name = self.image_names[self.current_idx]
        base_path = self.image_paths[self.current_idx] if self.current_idx < len(self.image_paths) else None

        # حفظ فوق الأصل
        if base_path and base_path.exists():
            cv2.imwrite(str(base_path), processed)
            self._log("💾 حفظ محلي فوق الأصل: {} (وضوح: {:.1f}→{:.1f})".format(
                name, self.current_blur, self.processed_blur))
            # تحديث LazyImage
            entry = self.image_list[self.current_idx]
            entry.clear_cache()
            if entry.is_path:
                entry.update_path(base_path)
        else:
            # PDF صفحة — حفظ مؤقت
            tmp = Path("temp_local_save") / name
            tmp.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(tmp), processed)
            self._log("💾 حفظ محلي (مؤقت): {}".format(name))

        # حفظ بيانات التدريب
        if self.chk_learn.isChecked():
            self.training.save_record(
                self.current_img, self.initial_params_snapshot, params,
                self.operation_history, self.current_blur, self.processed_blur, name)
            self.learner.add(self.current_img, params)

        self.stats["processed"] += 1
        self.processing_records.append({
            "name": name, "blur_before": round(self.current_blur, 2),
            "blur_after": round(self.processed_blur, 2),
            "status": quality_label(self.processed_blur, self.blur_threshold)[0],
        })
        self.lbl_s_proc.setText(str(self.stats["processed"]))
        self._update_training_stats()

        # ★ إعادة تعيين البارامترات إلى الصفر — جاهز للمرحلة التالية ★
        self.current_img = processed  # الصورة المعالجة أصبحت الأصل الجديد
        self.current_blur = self.processed_blur
        self.processed_blur = 0.0
        self._reset_params()
        self._update_quality_display()
        self._update_preview()

    def _do_save_to_output(self, organize: bool = True):
        """حفظ الصورة المعالجة — مع تنظيم في مجلدات أو في الموقع."""
        params = self._collect_params()
        processed = apply_processing(self.current_img, params)
        self.processed_blur = calc_blur(processed)

        name = self.image_names[self.current_idx]
        base_path = self.image_paths[self.current_idx] if self.current_idx < len(self.image_paths) else None

        # حفظ ذكي مع OCR
        page_num = 0
        if self.chk_smart_save.isChecked() and OCR_SUPPORT:
            page_num = extract_page_number(processed)

        if organize and base_path:
            label, _, _ = quality_label(self.processed_blur, self.blur_threshold)
            if label == "ممتازة":
                out_dir = base_path.parent / "processed"
            elif label == "مقبولة":
                out_dir = base_path.parent / "acceptable"
            else:
                out_dir = base_path.parent / "rejected"
            out_path = self._get_unique_path(out_dir, name)
        elif base_path:
            out_path = base_path
        else:
            out_path = Path(name)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), processed)

        # تحديث سجل الصفحات
        if page_num > 0:
            self.page_registry[page_num] = {
                'quality': self.processed_blur,
                'path': str(out_path),
                'name': name,
            }

        # حفظ بيانات التدريب
        if self.chk_learn.isChecked() and self.current_img is not None:
            self.training.save_record(
                self.current_img, self.initial_params_snapshot, params,
                self.operation_history, self.current_blur, self.processed_blur, name)
            self.learner.add(self.current_img, params)

        self.stats["processed"] += 1
        self.processing_records.append({
            "name": name, "blur_before": round(self.current_blur, 2),
            "blur_after": round(self.processed_blur, 2),
            "status": quality_label(self.processed_blur, self.blur_threshold)[0],
        })
        self.lbl_s_proc.setText(str(self.stats["processed"]))
        self._log("💾 حفظ: {} → {} (وضوح: {:.1f}→{:.1f})".format(
            name, out_path.name, self.current_blur, self.processed_blur))
        self._update_training_stats()

    def _skip_save(self):
        if not self.image_list:
            return
        name = self.image_names[self.current_idx]
        self.stats["skipped"] += 1
        self.lbl_s_skip.setText(str(self.stats["skipped"]))
        self._log("⏭️ تخطي: {}".format(name))
        self._navigate(1)

    # ──────────────────────────────────────────────────────────
    #  Auto-Save Toggle (v12)
    # ──────────────────────────────────────────────────────────

    def _on_auto_save_toggle(self, state):
        """عند تفعيل الحفظ التلقائي — سؤال المستخدم أولاً."""
        if state == Qt.Checked:
            reply = QMessageBox.question(
                self, "تأكيد",
                "سيتم الحفظ تلقائياً بعد كل ميلان وقص.\n"
                "هل تريد معالجة جميع الصور المتبقية الآن؟",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.chk_auto_save.setChecked(True)
                self._auto_save_all()
            else:
                self.chk_auto_save.setChecked(True)

    # ──────────────────────────────────────────────────────────
    #  Batch Operations
    # ──────────────────────────────────────────────────────────

    def _apply_to_remaining(self):
        if not self.image_list:
            return
        params = self._collect_params()
        remaining = len(self.image_list) - self.current_idx
        if remaining <= 1:
            return
        reply = QMessageBox.question(
            self, "تأكيد",
            "تطبيق الإعدادات الحالية على {} صورة متبقية؟".format(remaining),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        self._batch_cancelled = False
        self._set_controls_enabled(False)
        self.progress.setMaximum(remaining)
        self.progress.setValue(0)

        for i in range(self.current_idx, len(self.image_list)):
            if self._batch_cancelled:
                self._log("🛑 تم إلغاء العملية")
                break
            entry = self.image_list[i]
            img = entry.get()
            if img is None:
                continue
            name = self.image_names[i]
            base_path = self.image_paths[i] if i < len(self.image_paths) else None

            processed = apply_processing(img, params)
            blur_after = calc_blur(processed)
            blur_before = calc_blur(img)
            label, _, _ = quality_label(blur_after, self.blur_threshold)

            if base_path:
                if label == "ممتازة":
                    out_dir = base_path.parent / "processed"
                elif label == "مقبولة":
                    out_dir = base_path.parent / "acceptable"
                else:
                    out_dir = base_path.parent / "rejected"
                out_path = self._get_unique_path(out_dir, name)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(out_path), processed)

            self.stats["processed"] += 1
            self.processing_records.append({
                "name": name, "blur_before": round(blur_before, 2),
                "blur_after": round(blur_after, 2), "status": label,
            })

            if self.chk_learn.isChecked():
                self.training.save_record(img, self.initial_params_snapshot, params,
                                          ["apply_all"], blur_before, blur_after, name)
                self.learner.add(img, params)

            self.progress.setValue(i - self.current_idx + 1)
            QApplication.processEvents()

            if entry.is_path:
                entry.clear_cache()

        self.lbl_s_proc.setText(str(self.stats["processed"]))
        self._update_training_stats()
        self._set_controls_enabled(True)
        self._log("🤖 تم التطبيق على {} صورة".format(remaining))
        self.current_idx = len(self.image_list) - 1
        self._load_current()

    def _auto_save_all(self):
        """حفظ تلقائي تسلسلي غير حاجب — باستخدام QTimer."""
        if not self.image_list:
            return
        remaining = len(self.image_list) - self.current_idx
        if remaining <= 0:
            return

        # بناء قائمة الانتظار
        self._auto_save_queue = list(range(self.current_idx, len(self.image_list)))
        self._batch_cancelled = False
        self._auto_save_in_prog = True
        self._set_controls_enabled(False)
        self.progress.setMaximum(len(self.image_list))
        self._log("🔁 بدء الحفظ التلقائي لـ {} صورة (Esc للإلغاء)".format(remaining))
        self._auto_save_timer.start()

    def _auto_save_step(self):
        """خطوة واحدة من الحفظ التلقائي — غير حاجب."""
        if self._batch_cancelled or not self._auto_save_queue:
            self._finish_auto_save()
            return

        idx = self._auto_save_queue.pop(0)
        if idx >= len(self.image_list):
            self._finish_auto_save()
            return

        entry = self.image_list[idx]
        if not entry.exists():
            self._auto_save_timer.start()
            return

        img = entry.get()
        if img is None:
            self._auto_save_timer.start()
            return

        name = self.image_names[idx]
        base_path = self.image_paths[idx] if idx < len(self.image_paths) else None

        # كشف الميلان تلقائي
        try:
            angle = auto_detect_skew(img)
        except Exception:
            angle = 0.0

        # بناء البارامترات
        params = {
            "crop": (0, 0, 0, 0),
            "deskew_angle": angle if abs(angle) > 0.1 else 0.0,
            "flip_h": False,
            "sharpen": False,
            "remove_shadow": False,
            "rotation": 0,
        }

        # قص ذكي
        processed = apply_processing(img, params)
        crop = smart_auto_crop(processed, padding=15, dark_threshold=int(self.blur_threshold))
        params["crop"] = crop

        # معالجة نهائية
        processed = apply_processing(img, params)
        blur_after = calc_blur(processed)
        blur_before = calc_blur(img)
        label, _, _ = quality_label(blur_after, self.blur_threshold)

        # حفظ
        if base_path:
            if label == "ممتازة":
                out_dir = base_path.parent / "processed"
            elif label == "مقبولة":
                out_dir = base_path.parent / "acceptable"
            else:
                out_dir = base_path.parent / "rejected"
            out_path = self._get_unique_path(out_dir, name)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(out_path), processed)

        self.stats["processed"] += 1
        self.processing_records.append({
            "name": name, "blur_before": round(blur_before, 2),
            "blur_after": round(blur_after, 2), "status": label,
        })
        self.lbl_s_proc.setText(str(self.stats["processed"]))
        self.progress.setValue(idx + 1)
        self.lbl_status.setText("🔁 معالجة: {} ({}/{})".format(
            name, idx + 1, len(self.image_list)))

        if self.chk_learn.isChecked():
            self.training.save_record(img, {}, params,
                                      ["auto_save"], blur_before, blur_after, name)
            self.learner.add(img, params)

        if entry.is_path:
            entry.clear_cache()

        # الخطوة التالية
        self._auto_save_timer.start()

    def _finish_auto_save(self):
        self._auto_save_in_prog = False
        self._set_controls_enabled(True)
        self._update_training_stats()
        self._log("✔️ انتهى الحفظ التلقائي: {} صورة معالجة".format(self.stats["processed"]))
        self.lbl_status.setText("✔️ انتهى الحفظ التلقائي")
        if self.image_list:
            self.current_idx = min(self.current_idx, len(self.image_list) - 1)
            self._load_current()

    def _cancel_batch(self):
        """إلغاء عمليات الدُفعات (Esc)."""
        if self._auto_save_in_prog:
            self._batch_cancelled = True
            self._log("🛑 إلغاء الحفظ التلقائي...")
        if self._is_processing:
            self._batch_cancelled = True

    # ──────────────────────────────────────────────────────────
    #  Smart Analysis & Organization
    # ──────────────────────────────────────────────────────────

    def analyze_and_organize_pages(self):
        if not self.image_list:
            QMessageBox.information(self, "تنبيه", "لا توجد صور محملة.")
            return

        self._set_controls_enabled(False)
        total = len(self.image_list)
        self.progress.setMaximum(total)
        self.progress.setValue(0)
        self._log("🧠 بدء التحليل الذكي لـ {} صورة...".format(total))

        organized = {"excellent": [], "acceptable": [], "rejected": [],
                     "duplicates": [], "pages": {}}
        prev_hash = None
        dup_count = 0

        for i, entry in enumerate(self.image_list):
            img = entry.get()
            if img is None:
                continue
            name = self.image_names[i]

            quality = assess_image_quality(img)
            blur = quality['blur_score']
            label, _, _ = quality_label(blur, self.blur_threshold)

            if label == "ممتازة":
                organized["excellent"].append(name)
            elif label == "مقبولة":
                organized["acceptable"].append(name)
            else:
                organized["rejected"].append(name)

            if HASH_SUPPORT and prev_hash is not None:
                try:
                    s = cv2.resize(img, (256, 256))
                    pil = PILImage.fromarray(cv2.cvtColor(s, cv2.COLOR_BGR2RGB))
                    curr_hash = imagehash.phash(pil)
                    if prev_hash - curr_hash < 10:
                        organized["duplicates"].append(name)
                        dup_count += 1
                    prev_hash = curr_hash
                except Exception:
                    prev_hash = None
            elif HASH_SUPPORT:
                try:
                    s = cv2.resize(img, (256, 256))
                    pil = PILImage.fromarray(cv2.cvtColor(s, cv2.COLOR_BGR2RGB))
                    prev_hash = imagehash.phash(pil)
                except Exception:
                    prev_hash = None

            if OCR_SUPPORT:
                page_num = extract_page_number(img)
                if page_num > 0:
                    organized["pages"][name] = page_num

            self.progress.setValue(i + 1)
            QApplication.processEvents()
            if entry.is_path:
                entry.clear_cache()

        msg = "📊 نتائج التحليل الذكي:\n\n"
        msg += "✅ ممتازة: {}\n".format(len(organized["excellent"]))
        msg += "⚠️ مقبولة: {}\n".format(len(organized["acceptable"]))
        msg += "❌ ضبابية: {}\n".format(len(organized["rejected"]))
        if dup_count > 0:
            msg += "🔄 مكررات محتملة: {}\n".format(dup_count)
        if organized["pages"]:
            msg += "📄 أرقام صفحات مكتشفة: {}\n".format(len(organized["pages"]))
        msg += "\nهل تريد تنظيم الملفات في مجلدات حسب الجودة؟"

        reply = QMessageBox.question(self, "🧠 نتائج التحليل", msg,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self._organize_files(organized)

        self._set_controls_enabled(True)
        self._log("🧠 انتهى التحليل")

    def _organize_files(self, organized: dict):
        if not self.image_paths:
            return
        base_dir = self.image_paths[0].parent
        for label, folder_name in [("excellent", "processed"),
                                    ("acceptable", "acceptable"),
                                    ("rejected", "rejected")]:
            target_dir = base_dir / folder_name
            target_dir.mkdir(parents=True, exist_ok=True)
            for name in organized[label]:
                for i, img_name in enumerate(self.image_names):
                    if img_name == name and i < len(self.image_paths):
                        src = self.image_paths[i]
                        if src.exists():
                            dst = target_dir / src.name
                            self._safe_move(src, dst)
                        break
        self._log("📁 تم تنظيم الملفات في مجلدات")

    # ──────────────────────────────────────────────────────────
    #  Export Operations
    # ──────────────────────────────────────────────────────────

    def _export_csv(self):
        if not self.processing_records:
            QMessageBox.information(self, "تنبيه", "لا توجد سجلات للتصدير.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "تصدير CSV", "processing_report.csv",
                                              "CSV Files (*.csv)")
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["name", "blur_before", "blur_after", "status"])
            writer.writeheader()
            writer.writerows(self.processing_records)
        self._log("📤 تم تصدير CSV: {}".format(path))

    def _export_learn(self):
        path, _ = QFileDialog.getSaveFileName(self, "تصدير بيانات التعلّم", "learning_data.json",
                                              "JSON Files (*.json)")
        if not path:
            return
        self.learner.export(path)
        self._log("💾 تم تصدير بيانات التعلّم: {}".format(path))

    def _import_learn(self):
        path, _ = QFileDialog.getOpenFileName(self, "استيراد بيانات التعلّم", "",
                                              "JSON Files (*.json)")
        if not path:
            return
        try:
            self.learner.load(path)
            self._log("📥 تم استيراد بيانات التعلّم: {} سجل".format(len(self.learner.history)))
        except Exception as e:
            QMessageBox.warning(self, "خطأ", "فشل الاستيراد: {}".format(e))

    def _apply_predicted(self):
        if self.current_img is None:
            return
        params, sim = self.training.predict(self.current_img)
        if params is None:
            self._log("🧠 لا يوجد تنبؤ كافٍ")
            return
        self._push_undo()
        self.current_params.update(params)
        self._sync_ui_from_params()
        self._update_preview()
        self._log("🧠 تطبيق تنبؤ ({}%)".format(int(sim * 100)))

    # ──────────────────────────────────────────────────────────
    #  Slider Callbacks
    # ──────────────────────────────────────────────────────────

    def _on_thr_change(self, val):
        self.blur_threshold = float(val)
        self.lbl_thr.setText(str(val))
        self._update_quality_display()

    def _on_gray_thr_change(self, val):
        self.gray_threshold = val
        self.lbl_gray_thr.setText(str(val))

    # ──────────────────────────────────────────────────────────
    #  Clock & Stats
    # ──────────────────────────────────────────────────────────

    def _tick_clock(self):
        if self.stats.get("start_time"):
            elapsed = datetime.now() - self.stats["start_time"]
            h, rem = divmod(int(elapsed.total_seconds()), 3600)
            m, s = divmod(rem, 60)
            self.lbl_s_time.setText("{:02d}:{:02d}:{:02d}".format(h, m, s))
        self.lbl_s_learn.setText(str(len(self.learner.history)))

    def _update_training_stats(self):
        st = self.training.stats()
        self.lbl_train_count.setText(str(st["count"]))
        self.lbl_train_avg.setText(str(st["avg_improvement"]))

    # ──────────────────────────────────────────────────────────
    #  Logging
    # ──────────────────────────────────────────────────────────

    def _log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_log.append("[{}] {}".format(timestamp, msg))
        logger.info(msg)
        self.lbl_status.setText(msg)

    # ──────────────────────────────────────────────────────────
    #  Screenshot (v12)
    # ──────────────────────────────────────────────────────────

    def _save_screenshot(self, widget=None):
        """حفظ لقطة شاشة لأي ويدجت."""
        target = widget or self
        pixmap = target.grab()
        path, _ = QFileDialog.getSaveFileName(
            self, "حفظ لقطة شاشة", "screenshot_{}.png".format(
                datetime.now().strftime("%Y%m%d_%H%M%S")),
            "PNG Files (*.png)")
        if path:
            pixmap.save(path)
            self._log("📸 لقطة شاشة: {}".format(path))


# ════════════════════════════════════════════════════════════════
#  Main Entry Point
# ════════════════════════════════════════════════════════════════

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    palette = app.palette()
    palette.setColor(palette.Window, QColor("#f8fafc"))
    palette.setColor(palette.WindowText, QColor("#1e293b"))
    palette.setColor(palette.Base, QColor("#ffffff"))
    palette.setColor(palette.AlternateBase, QColor("#f1f5f9"))
    palette.setColor(palette.Button, QColor("#e2e8f0"))
    palette.setColor(palette.ButtonText, QColor("#1e293b"))
    palette.setColor(palette.Highlight, QColor("#2563eb"))
    palette.setColor(palette.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)

    window = MedicalDocApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
