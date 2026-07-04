#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏥 معالج الوثائق الطبية التفاعلي - v7 (النسخة المستقرة)
تم إصلاح جميع الأخطاء النحوية والتكرارات.
"""
import sys
import csv
import json
from collections import deque
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np
import math
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QCheckBox, QProgressBar,
    QTextEdit, QFileDialog, QMessageBox, QGroupBox, QFormLayout,
    QSplitter, QDialog, QScrollArea, QSizePolicy, QTabWidget, QFrame,
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QImage, QFont, QKeySequence, QColor, QIcon
from PyQt5.QtWidgets import QShortcut

# PDF support
PDF_SUPPORT = False
try:
    from pdf2image import convert_from_path
    PDF_SUPPORT = True
except ImportError:
    pass

IMG_EXT = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
ALL_EXT = IMG_EXT | ({".pdf"} if PDF_SUPPORT else set())
LOG_FILE = Path("processing_log.txt")
THUMB_W, THUMB_H = 90, 115
UNDO_LIMIT = 15

# ---------- image processing functions ----------
def apply_processing(img: np.ndarray, params: dict) -> np.ndarray:
    out = img.copy()
    h, w = out.shape[:2]
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
    if abs(angle) > 0.1:
        ch, cw = out.shape[:2]
        M = cv2.getRotationMatrix2D((cw // 2, ch // 2), angle, 1.0)
        out = cv2.warpAffine(out, M, (cw, ch),
                             flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT,
                             borderValue=(255, 255, 255))
    if params.get("flip_h", False):
        out = cv2.flip(out, 1)
    if params.get("sharpen", False):
        k = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        out = cv2.filter2D(out, -1, k)
    return out

def cv2_to_pixmap(img: np.ndarray, zoom: float = 1.0, max_w: int = 0, max_h: int = 0) -> QPixmap:
    h, w = img.shape[:2]
    if zoom != 1.0:
        nw = int(w * zoom)
        nh = int(h * zoom)
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

def quality_label(score: float, thr: float) -> tuple:
    if score >= thr * 2:
        return "ممتازة", "#16a34a", "✅"
    if score >= thr:
        return "مقبولة", "#d97706", "⚠️"
    return "ضبابية", "#dc2626", "❌"

def auto_detect_skew(img: np.ndarray, max_a: float = 15.0, step: float = 0.5) -> float:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    gray = cv2.equalizeHist(gray)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    h, w = binary.shape
    best_score, best_angle = -1.0, 0.0
    for angle in np.arange(-max_a, max_a + step, step):
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        rot = cv2.warpAffine(binary, M, (w, h),
                             flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REPLICATE)
        score = float(np.var(np.sum(rot, axis=1)))
        if score > best_score:
            best_score, best_angle = score, float(angle)
    return best_angle

def smart_auto_crop(img: np.ndarray, padding: int = 15, dark_threshold: int = 200) -> tuple:
    """
    قص ذكي يعتمد على كشف أول وآخر صف/عمود يحتوي على نص (بكسلات داكنة).
    يزيل الهوامش الفارغة تماماً (خلفية رمادية/بيضاء/سوداء) ويحتفظ بمنطقة المحتوى فقط.

    المعاملات:
        img: صورة الإدخال (BGR)
        padding: هامش إضافي (بكسل) بعد القص
        dark_threshold: العتبة التي تعتبر البكسل تحتها "داكناً" (نص). القيمة 200 مناسبة للخلفيات الفاتحة.
    """
    # تحويل إلى تدرج رمادي
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
    h, w = gray.shape

    # نطبق عتبة: أي بكسل قيمته < dark_threshold يعتبر نصاً (داكن)
    # ننشئ مصفوفة ثنائية حيث النص = 1، الخلفية = 0
    _, binary = cv2.threshold(gray, dark_threshold, 255, cv2.THRESH_BINARY_INV)
    # الآن النص أبيض (255)، الخلفية سوداء (0)

    # البحث عن أول صف يحتوي على نص (أي فيه قيمة > 0)
    top = 0
    for row in range(h):
        if np.any(binary[row, :] > 0):
            top = row
            break

    # البحث عن آخر صف يحتوي على نص
    bottom = h - 1
    for row in range(h - 1, -1, -1):
        if np.any(binary[row, :] > 0):
            bottom = row
            break

    # البحث عن أول عمود يحتوي على نص
    left = 0
    for col in range(w):
        if np.any(binary[:, col] > 0):
            left = col
            break

    # البحث عن آخر عمود يحتوي على نص
    right = w - 1
    for col in range(w - 1, -1, -1):
        if np.any(binary[:, col] > 0):
            right = col
            break

    # إذا لم يتم العثور على أي نص (الصورة فارغة)، نرجع عدم تغيير
    if top >= bottom or left >= right:
        return (0, 0, 0, 0)

    # إضافة الهامش (padding) مع التأكد من الحدود
    top = max(0, top - padding)
    left = max(0, left - padding)
    bottom = min(h - 1, bottom + padding)
    right = min(w - 1, right + padding)

    # تحويل إلى هوامش القص (l, t, r, b) كما يتوقعها التطبيق
    l = left
    t = top
    r = w - right - 1
    b = h - bottom - 1

    return (l, t, r, b)

def load_pdf_as_images(pdf_path: str, dpi: int = 200) -> list:
    pages = convert_from_path(pdf_path, dpi=dpi)
    result = []
    for page in pages:
        arr = np.array(page)
        result.append(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    return result

# ---------- worker threads ----------
class SkewWorker(QThread):
    finished = pyqtSignal(float)
    error    = pyqtSignal(str)
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
        for i, path_or_arr in enumerate(self.image_list):
            if self._stop:
                break
            try:
                if isinstance(path_or_arr, Path):
                    # IMREAD_REDUCED_COLOR_4 = تحميل بـ 1/4 الدقة → أسرع وأقل ذاكرة
                    img = cv2.imread(str(path_or_arr), cv2.IMREAD_REDUCED_COLOR_4)
                else:
                    img = path_or_arr
                if img is not None:
                    pix = cv2_to_pixmap(img, max_w=THUMB_W, max_h=THUMB_H)
                    self.ready.emit(i, pix)
            except Exception:
                pass

# ---------- adaptive learner ----------
class AdaptiveLearner:
    MAX = 30
    def __init__(self):
        self.history: list[dict] = []
    
    def _feat(self, img: np.ndarray) -> dict:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
        h, w = g.shape
        mean = float(np.mean(g))
        std = float(np.std(g))
        return {
            "w": w, "h": h,
            "bright": mean,
            "contrast": std,
            "ratio": round(w / max(h, 1), 4)
        }
    
    def suggest(self, img: np.ndarray):
        if len(self.history) < 2:
            return None, 0.0
        f = self._feat(img)
        best_sim, best_p = 0.0, None
        for rec in self.history:
            rf = rec["features"]
            # مسافة إقليدية موزونة
            dw = (f["w"] - rf["w"]) / 3000.0
            dh = (f["h"] - rf["h"]) / 4000.0
            db = (f["bright"] - rf["bright"]) / 255.0
            dc = (f["contrast"] - rf["contrast"]) / 128.0
            dr = (f["ratio"] - rf["ratio"]) / 2.0
            d = math.sqrt(dw*dw + dh*dh + db*db + dc*dc + dr*dr)
            sim = max(0.0, 1.0 - d)
            if sim > best_sim:
                best_sim, best_p = sim, rec["params"]
        return (best_p, best_sim) if best_sim > 0.75 else (None, 0.0)
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

# ---------- compare dialog ----------
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

# ---------- thumbnail button ----------
class ThumbButton(QPushButton):
    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self.index = index
        self.setFixedSize(THUMB_W + 6, THUMB_H + 22)
        self.setCheckable(True)
        self._apply_style(False)
        self.setToolTip(f"صورة {index + 1}")
    def set_pixmap(self, pix: QPixmap):
        self.setIcon(QIcon(pix))
        self.setIconSize(QSize(THUMB_W, THUMB_H))
        self.setText(f"\n{self.index + 1}")
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

# ---------- main application ----------
class MedicalDocApp(QMainWindow):

    def _get_unique_path(self, base_dir, relative_path, ext=".png"):
        target_dir = Path(base_dir) / Path(relative_path).parent
        target_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(relative_path).stem
        candidate = target_dir / f"{stem}{ext}"
        if not candidate.exists():
            return candidate
        counter = 1
        while True:
            new_name = f"{stem}_{counter}{ext}"
            candidate = target_dir / new_name
            if not candidate.exists():
                return candidate
            counter += 1

    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏥 معالج الوثائق الطبية v7")
        self.setMinimumSize(1024, 600)
        self.showMaximized()
        self.setFont(QFont("Noto Sans Arabic", 10))
        self.setAcceptDrops(True)

        self.image_list: list = []
        self.image_names: list[str] = []
        self.current_idx = 0
        self.current_img: np.ndarray | None = None
        self.current_blur = 0.0
        self.processed_blur = 0.0
        self.blur_threshold = 100.0
        self.current_params: dict = {
            "crop": (20, 20, 20, 20),
            "deskew_angle": 0.0,
            "flip_h": False,
            "sharpen": False,
        }
        self._undo_stack: deque[dict] = deque(maxlen=UNDO_LIMIT)
        self._redo_stack: deque[dict] = deque(maxlen=UNDO_LIMIT)
        self.stats = {"total": 0, "processed": 0, "skipped": 0, "start_time": None}
        self.processing_records: list[dict] = []
        self.learner = AdaptiveLearner()
        self._load_learning_data()
        self._load_learning_data()
        self.thumb_buttons: list[ThumbButton] = []
        self._skew_worker: SkewWorker | None = None
        self._thumb_worker: ThumbnailWorker | None = None
        self._detected_angle: float = 0.0
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0

        self._build_ui()
        self._setup_shortcuts()
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._tick_clock)
        self._clock.start(1000)

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        main_vbox = QVBoxLayout(root)
        main_vbox.setSpacing(4)

        # top bar
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
        for w in [self.lbl_status, None, self.lbl_index,
                  self.btn_prev, self.btn_next,
                  self.btn_export_csv, self.btn_export_learn,
                  self.btn_import_learn, self.btn_save_learn, self.btn_open]:
            if w is None:
                top.addStretch()
            else:
                top.addWidget(w)
        main_vbox.addLayout(top)

        # middle splitter
        mid_splitter = QSplitter(Qt.Horizontal)
        left_w = QWidget()
        left_l = QVBoxLayout(left_w)
        left_l.setSpacing(4)

        # preview with scroll
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

        # control buttons
        ctrl = QHBoxLayout()
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
self.btn_deskew_minus = self._mk_btn("−", "#475569", h=32, w=30)
        self.btn_deskew_plus = self._mk_btn("+", "#475569", h=32, w=30)
self.btn_deskew_minus = self._mk_btn("−", "#475569", h=32, w=30)
        self.btn_deskew_plus = self._mk_btn("+", "#475569", h=32, w=30)
        self.btn_smart_crop = self._mk_btn("✂️ قص ذكي", "#7c3aed", h=32)
        self.btn_compare = self._mk_btn("🔍 مقارنة", "#6366f1", h=32)
        self.btn_confirm = self._mk_btn("✅ تأكيد وحفظ", "#16a34a", h=32)
        self.btn_skip = self._mk_btn("⏭️ تخطي", "#dc2626", h=32)
        self.btn_apply_all = self._mk_btn("🤖 طبّق على البقية", "#0369a1", h=32)
        self.btn_apply_deskew.setEnabled(False)
        self.btn_apply_all.setEnabled(False)

        for b in [self.btn_refresh, self.btn_zoom_out, self.btn_zoom_in, self.btn_zoom_fit, self.lbl_zoom, self.btn_fullscreen,
                  self.btn_rotate_left, self.lbl_rotation, self.btn_rotate_right,
                  self.btn_auto_deskew, self.btn_apply_deskew, self.btn_deskew_minus, self.btn_deskew_plus, self.btn_deskew_minus, self.btn_deskew_plus,
                  self.btn_smart_crop, self.btn_compare,
                  self.btn_confirm, self.btn_skip, self.btn_apply_all]:
            ctrl.addWidget(b)
        left_l.addLayout(ctrl)

        # right panel with tabs
        right_w = QWidget()
        right_w.setFixedWidth(440)
        right_l = QVBoxLayout(right_w)
        right_l.setSpacing(4)
        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.North)

        # tab settings
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

        misc_box = QGroupBox("⚙️ تصحيحات")
        ml = QVBoxLayout()
        deskew_row = QHBoxLayout()
        self.slider_deskew = QSlider(Qt.Horizontal)
        self.slider_deskew.setRange(-150, 150)
        self.slider_deskew.setValue(0)
        self.lbl_deskew = QLabel("0.0°")
        self.lbl_deskew.setFixedWidth(45)
        deskew_row.addWidget(QLabel("ميلان:"))
        deskew_row.addWidget(self.slider_deskew)
        deskew_row.addWidget(self.lbl_deskew)
        self.chk_flip = QCheckBox("↔️ قلب أفقي")
        self.btn_sharpen = QPushButton("🔆 تحسين الوضوح")
        self.btn_sharpen.setCheckable(True)
        self.chk_learn = QCheckBox("🤖 تعلّم تطبيقي")
        self.chk_auto_deskew = QCheckBox("🔄 كشف وتطبيق الميلان تلقائياً عند فتح الصورة")
        self.chk_auto_deskew.setChecked(True)
        ml.addWidget(self.chk_auto_deskew)
        self.chk_learn.setChecked(True)
        ml.addLayout(deskew_row)
        ml.addWidget(self.chk_flip)
        ml.addWidget(self.btn_sharpen)
        ml.addWidget(self.chk_learn)
        misc_box.setLayout(ml)
        ts_l.addWidget(misc_box)
        ts_l.addStretch()
        tabs.addTab(tab_settings, "⚙️ الإعدادات")

        # tab quality
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

        # tab stats
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
        for label, w in [("إجمالي:", self.lbl_s_total),
                         ("معالجة:", self.lbl_s_proc),
                         ("تخطي:", self.lbl_s_skip),
                         ("سجلات التعلّم:", self.lbl_s_learn),
                         ("تراجع/إعادة:", self.lbl_s_undo),
                         ("الوقت:", self.lbl_s_time)]:
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

        # thumbnail strip
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

        self._connect_signals()

    def _connect_signals(self):
        self.btn_open.clicked.connect(self._open_folder)
        self.btn_prev.clicked.connect(lambda: self._navigate(-1))
        self.btn_next.clicked.connect(lambda: self._navigate(1))
        self.btn_refresh.clicked.connect(self._update_preview)
        self.btn_auto_deskew.clicked.connect(self._start_skew)
        self.btn_apply_deskew.clicked.connect(self._apply_skew)
        self.btn_smart_crop.clicked.connect(self._do_smart_crop)
        self.btn_compare.clicked.connect(self._show_compare)
        self.btn_confirm.clicked.connect(self._confirm_save)
        self.btn_skip.clicked.connect(self._skip_save)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_fit.clicked.connect(self.zoom_fit)
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)
        self.btn_rotate_left.clicked.connect(self.rotate_left)
        self.btn_rotate_right.clicked.connect(self.rotate_right)

        self.btn_deskew_minus.clicked.connect(self.deskew_minus)
        self.btn_deskew_plus.clicked.connect(self.deskew_plus)

        self.btn_deskew_minus.clicked.connect(self.deskew_minus)
        self.btn_deskew_plus.clicked.connect(self.deskew_plus)
        self.btn_apply_all.clicked.connect(self._apply_to_remaining)
        self.btn_export_csv.clicked.connect(self._export_csv)
        self.btn_export_learn.clicked.connect(self._export_learn)
        self.btn_import_learn.clicked.connect(self._import_learn)
        self.btn_save_learn.clicked.connect(self._save_learning_data)
        self.btn_save_learn.clicked.connect(self._save_learning_data)
        self.slider_deskew.valueChanged.connect(lambda v: self.lbl_deskew.setText(f"{v/10:+.1f}°"))
        self.slider_threshold.valueChanged.connect(self._on_thr_change)
        self._ptimer = QTimer(self)
        self._ptimer.setSingleShot(True)
        self._ptimer.timeout.connect(self._update_preview)
        for w in [self.sp_left, self.sp_top, self.sp_right, self.sp_bottom, self.slider_deskew]:
            w.valueChanged.connect(lambda: self._ptimer.start(250))
        for chk in [self.chk_flip, self.btn_sharpen]:
            chk.toggled.connect(lambda: self._ptimer.start(250))

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self._redo)
        QShortcut(QKeySequence("Ctrl+S"), self, self._confirm_save)
        QShortcut(QKeySequence("Right"), self, lambda: self._navigate(1))
        QShortcut(QKeySequence("Left"), self, lambda: self._navigate(-1))
        QShortcut(QKeySequence("Space"), self, self._update_preview)
        QShortcut(QKeySequence("Ctrl+D"), self, self._start_skew)
        QShortcut(QKeySequence("Ctrl+G"), self, self._do_smart_crop)

    # ---------- drag & drop ----------
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    def dropEvent(self, event):
        self._load_paths([url.toLocalFile() for url in event.mimeData().urls()])

    # ---------- file loading ----------
    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "اختر مجلداً")
        if folder:
            self._load_paths([folder])

    def _load_paths(self, paths: list[str]):
        images, names = [], []
        for p in paths:
            pp = Path(p)
            if pp.is_dir():
                for f in sorted(pp.glob("*")):
                    ext = f.suffix.lower()
                    if ext in IMG_EXT:
                        if f.exists():
                            images.append(f)
                            names.append(f.name)
                        else:
                            self._log(f"⚠️ تجاهل ملف غير موجود: {f.name}")
                    elif ext == ".pdf" and PDF_SUPPORT:
                        try:
                            pages = load_pdf_as_images(str(f))
                            for j, pg in enumerate(pages):
                                images.append(pg)
                                names.append(f"{f.stem}_p{j+1:03d}.png")
                        except Exception as e:
                            self._log(f"⚠️ خطأ PDF {f.name}: {e}")
            elif pp.is_file():
                ext = pp.suffix.lower()
                if ext in IMG_EXT:
                    if pp.exists():
                        images.append(pp)
                        names.append(pp.name)
                    else:
                        self._log(f"⚠️ تجاهل ملف غير موجود: {pp.name}")
                elif ext == ".pdf" and PDF_SUPPORT:
                    try:
                        pages = load_pdf_as_images(str(pp))
                        for j, pg in enumerate(pages):
                            images.append(pg)
                            names.append(f"{pp.stem}_p{j+1:03d}.png")
                    except Exception as e:
                        self._log(f"⚠️ خطأ PDF {pp.name}: {e}")
        if not images:
            QMessageBox.warning(self, "تنبيه", "لم يتم العثور على ملفات صالحة.")
            return
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.stop()
            self._thumb_worker.wait()
        self.image_list = images
        self.image_names = names
        self.current_idx = 0
        self.processing_records = []
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.stats = {"total": len(images), "processed": 0, "skipped": 0, "start_time": datetime.now()}
        self.progress.setMaximum(len(images))
        self.lbl_s_total.setText(str(len(images)))
        self._log(f"📥 تم تحميل {len(images)} ملف")
        self._build_thumbnails()
        self._load_current()

    # ---------- thumbnails ----------
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
            btn.setText(f"{i+1}")
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
            btn = self.thumb_buttons[self.current_idx]
            self.thumb_scroll.ensureWidgetVisible(btn)

    def _jump_to(self, idx: int):
        self.current_idx = idx
        self._load_current()

    # ---------- load current image ----------
    def _load_current(self):
        if not self.image_list:
            return
        entry = self.image_list[self.current_idx]
        name = self.image_names[self.current_idx]
        self.lbl_index.setText(f"{self.current_idx+1} / {len(self.image_list)}")
        self.progress.setValue(self.current_idx)
        self._update_thumb_selection()
        if isinstance(entry, Path):
            img = cv2.imread(str(entry))
        else:
            img = entry
        if isinstance(entry, Path) and not entry.exists():
            self._log(f"⚠️ الملف {entry.name} غير موجود. سيتم حذفه.")
            self.image_list.pop(self.current_idx)
            self.image_names.pop(self.current_idx)
            self.stats["total"] = len(self.image_list)
            self.progress.setMaximum(self.stats["total"])
            self.lbl_s_total.setText(str(self.stats["total"]))
            if self.current_idx >= len(self.image_list):
                self.current_idx = max(0, len(self.image_list)-1)
            self._load_current()
            return
        if img is None:
            self._log(f"❌ فشل قراءة: {name}")
            return
        self.current_img = img
        self.current_blur = calc_blur(img)
        self._update_quality_display()
        # إعادة تعيين الدوران لكل صورة جديدة
        self.current_params["rotation"] = 0
        if self.chk_learn.isChecked():
            suggested, sim = self.learner.suggest(img)
            if suggested:
                self.current_params.update(suggested)
                self._log(f"🤖 اقتراح مستفاد ({sim*100:.0f}%): {name}")
            else:
                self._log(f"📄 تحميل: {name}")
        else:
            self._log(f"📄 تحميل: {name}")
        self._sync_ui_from_params()
        self.btn_apply_deskew.setEnabled(False)
        if hasattr(self, 'chk_auto_deskew') and self.chk_auto_deskew.isChecked():
            self._apply_auto_deskew_on_load()
        self._update_preview()

    def _sync_ui_from_params(self):
        crop = self.current_params.get("crop", (20, 20, 20, 20))
        for sp, val in [(self.sp_left, crop[0]), (self.sp_top, crop[1]),
                        (self.sp_right, crop[2]), (self.sp_bottom, crop[3])]:
            sp.blockSignals(True); sp.setValue(val); sp.blockSignals(False)
        angle = int(self.current_params.get("deskew_angle", 0.0) * 10)
        self.slider_deskew.blockSignals(True)
        self.slider_deskew.setValue(angle)
        self.slider_deskew.blockSignals(False)
        self.lbl_deskew.setText(f"{angle/10:+.1f}°")
        self.chk_flip.setChecked(self.current_params.get("flip_h", False))
        self.btn_sharpen.setChecked(self.current_params.get("sharpen", False))
        self.lbl_rotation.setText(f"{self.current_params.get('rotation', 0)}°")

    def _collect_params(self) -> dict:
        return {
            "crop": (self.sp_left.value(), self.sp_top.value(),
                     self.sp_right.value(), self.sp_bottom.value()),
            "deskew_angle": self.slider_deskew.value() / 10.0,
            "flip_h": self.chk_flip.isChecked(),
            "sharpen": self.btn_sharpen.isChecked(),
            "rotation": self.current_params.get("rotation", 0),  # ← يحافظ على الدوران
        }

    def _update_preview(self):
        if self.current_img is None:
            return
        self.current_params = self._collect_params()
        processed = apply_processing(self.current_img, self.current_params)
        self.processed_blur = calc_blur(processed)
        # حد أقصى 1600px للمعاينة — أسرع وأقل ذاكرة
        pix = cv2_to_pixmap(processed, zoom=self.zoom_factor, max_w=1600, max_h=1600)
        self.lbl_preview.setPixmap(pix)
        self.lbl_preview.setText("")
        self.lbl_preview.setFixedSize(pix.width(), pix.height())

    # ---------- undo/redo ----------
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
        self._log("↩️ تراجع")

    def _redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append(self.current_params.copy())
        self.current_params = self._redo_stack.pop()
        self._sync_ui_from_params()
        self._update_preview()
        self._update_undo_label()
        self._log("↪️ إعادة")
    def _update_undo_label(self):
        self.lbl_s_undo.setText(f"{len(self._undo_stack)} / {len(self._redo_stack)}")

    # ---------- smart crop ----------
    def _do_smart_crop(self):
        if self.current_img is None:
            return
        self._push_undo()
        crop = smart_auto_crop(self.current_img)
        self.current_params["crop"] = crop
        self._sync_ui_from_params()
        self._update_preview()
        self._log(f"✂️ قص ذكي: L={crop[0]} T={crop[1]} R={crop[2]} B={crop[3]}")

    # ---------- skew detection ----------
    def _start_skew(self):
        if self.current_img is None:
            return
        self.btn_auto_deskew.setEnabled(False)
        self.btn_auto_deskew.setText("⏳ جاري...")
        self._skew_worker = SkewWorker(self.current_img)
        self._skew_worker.finished.connect(self._on_skew_done)
        self._skew_worker.error.connect(self._on_skew_err)
        self._skew_worker.start()

    def _on_skew_done(self, angle: float):
        self._detected_angle = angle
        self.slider_deskew.setValue(int(angle * 10))
        self.lbl_deskew.setText(f"{angle:+.1f}°")
        self.btn_apply_deskew.setEnabled(True)
        self.btn_auto_deskew.setEnabled(True)
        self.btn_auto_deskew.setText("📐 كشف ميلان")
        self._update_preview()
        self._log(f"📐 زاوية مكتشفة: {angle:+.2f}°")
        note = "✅ مائلة — اضغط 'تطبيق الميلان'" if abs(angle) > 0.5 else "✔️ مستقيمة تقريباً"
        QMessageBox.information(self, "نتيجة الكشف", f"زاوية الميلان: {angle:+.1f}°\n{note}")

    def _on_skew_err(self, msg: str):
        self.btn_auto_deskew.setEnabled(True)
        self.btn_auto_deskew.setText("📐 كشف ميلان")
        QMessageBox.critical(self, "خطأ", f"فشل الكشف:\n{msg}")

    def _apply_skew(self):
        self._push_undo()
        self.current_params["deskew_angle"] = self._detected_angle
        self.btn_apply_deskew.setEnabled(False)
        self._update_preview()
        self._log(f"✅ تصحيح الميلان: {self._detected_angle:+.2f}°")

    # ---------- compare ----------
    def _show_compare(self):
        if self.current_img is None:
            return
        self._update_preview()
        orig_pix = cv2_to_pixmap(self.current_img, max_w=600, max_h=800)
        proc = apply_processing(self.current_img, self.current_params)
        proc_pix = cv2_to_pixmap(proc, max_w=600, max_h=800)
        CompareDialog(orig_pix, proc_pix, self).exec_()

    # ---------- quality ----------
    def _update_quality_display(self):
        label, color, icon = quality_label(self.current_blur, self.blur_threshold)
        self.lbl_quality.setText(f"{icon}  جودة الأصل: {label}")
        self.lbl_quality.setStyleSheet(f"font-weight:bold;padding:8px;border-radius:5px;background:{color}22;color:{color};border:1px solid {color};")
        self.lbl_blur_val.setText(f"{self.current_blur:.1f}")
        if self.current_blur < self.blur_threshold:
            self.lbl_blur_warn.setText(f"⚠️ صورة ضبابية  ({self.current_blur:.0f} < {self.blur_threshold:.0f})")
        else:
            self.lbl_blur_warn.setText("")
    def _on_thr_change(self, v: int):
        self.blur_threshold = float(v)
        self.lbl_thr.setText(str(v))
        if self.current_img is not None:
            self._update_quality_display()

    # ---------- save ----------
    def _confirm_save(self):
        if self.current_img is None:
            return
        if self.processed_blur < self.blur_threshold * 0.5:
            reply = QMessageBox.question(self, "تحذير جودة", f"الصورة المعالجة ضبابية جداً ({self.processed_blur:.0f})\nهل تريد الحفظ؟", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return
        self._push_undo()
        original_path = self.image_list[self.current_idx]
        if isinstance(original_path, Path):
            original_abs = original_path
        else:
            original_abs = Path(self.image_names[self.current_idx])
        docs_dir = Path.home() / "Documents"
        try:
            relative_to = Path.cwd()
            rel_path = original_abs.relative_to(relative_to)
        except ValueError:
            rel_path = original_abs.name
        raw_base = docs_dir / "raw_scanned_files"
        raw_dest = self._get_unique_path(raw_base, rel_path, ext=original_abs.suffix if isinstance(original_path, Path) else ".png")
        if isinstance(original_path, Path):
            import shutil
            shutil.move(str(original_abs), str(raw_dest))
        else:
            cv2.imwrite(str(raw_dest), self.current_img)
        cropped_base = docs_dir / "cropped_scanned_files"
        cropped_dest = self._get_unique_path(cropped_base, rel_path, ext=".png")
        processed = apply_processing(self.current_img, self.current_params)
        cv2.imwrite(str(cropped_dest), processed)
        self.stats["processed"] += 1
        if self.chk_learn.isChecked():
            self.learner.add(self.current_img, self.current_params)
            self._save_learning_data()
            self._save_learning_data()
        self._record_csv("processed", cropped_dest)
        self._log(f"✅ حفظ: {cropped_dest.name}  (جودة: {self.processed_blur:.0f})")
        self.btn_apply_all.setEnabled(True)
        self._update_stats()
        self._navigate(1)

    def _skip_save(self):
        if self.current_img is None:
            return
        out = Path("skipped")
        out.mkdir(exist_ok=True)
        dest = out / f"skip_{self.current_idx+1:04d}.png"
        cv2.imwrite(str(dest), self.current_img)
        self.stats["skipped"] += 1
        self._record_csv("skipped", dest)
        self._log(f"⏭️ تخطي: {dest.name}")
        self._update_stats()
        self._navigate(1)

    def _apply_to_remaining(self):
        if self.current_img is None:
            return
        params = self.current_params.copy()
        out = Path("processed")
        out.mkdir(exist_ok=True)
        count = 0
        for i in range(self.current_idx, len(self.image_list)):
            entry = self.image_list[i]
            img = cv2.imread(str(entry)) if isinstance(entry, Path) else entry
            if img is None:
                continue
            orig_path = entry if isinstance(entry, Path) else Path(self.image_names[i])
            rel_path = orig_path.name
            raw_base = Path.home() / "Documents" / "raw_scanned_files"
            raw_dest = self._get_unique_path(raw_base, rel_path, ext=orig_path.suffix if isinstance(entry, Path) else ".png")
            if isinstance(entry, Path):
                import shutil
                shutil.move(str(orig_path), str(raw_dest))
            else:
                cv2.imwrite(str(raw_dest), img)
            cropped_base = Path.home() / "Documents" / "cropped_scanned_files"
            cropped_dest = self._get_unique_path(cropped_base, rel_path, ext=".png")
            cv2.imwrite(str(cropped_dest), apply_processing(img, params))
            if self.chk_learn.isChecked():
                self.learner.add(img, params)
            count += 1
        self.stats["processed"] += count
        self._log(f"🤖 دفعة: {count} صورة")
        self._update_stats()
        QMessageBox.information(self, "اكتمل", f"تمت معالجة {count} صورة وحفظها في processed/")

    def _navigate(self, step: int):
        new = self.current_idx + step
        if 0 <= new < len(self.image_list):
            self.current_idx = new
            self._load_current()
        elif new >= len(self.image_list):
            QMessageBox.information(self, "اكتمل", f"✅ وصلت إلى نهاية القائمة!\nمعالجة: {self.stats['processed']}  |  تخطي: {self.stats['skipped']}")

    def _update_stats(self):
        self.lbl_s_total.setText(str(self.stats["total"]))
        self.lbl_s_proc.setText(str(self.stats["processed"]))
        self.lbl_s_skip.setText(str(self.stats["skipped"]))
        self.lbl_s_learn.setText(str(len(self.learner.history)))
        self._update_undo_label()
    def _tick_clock(self):
        if self.stats["start_time"]:
            diff = datetime.now() - self.stats["start_time"]
            self.lbl_s_time.setText(str(diff).split(".")[0])
    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.txt_log.append(line)
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    def _record_csv(self, action: str, dest: Path):
        self.processing_records.append({
            "name": self.image_names[self.current_idx],
            "output": str(dest),
            "action": action,
            "crop": str(self.current_params.get("crop")),
            "deskew": round(self.current_params.get("deskew_angle", 0), 2),
            "flip_h": self.current_params.get("flip_h", False),
            "blur": round(self.current_blur, 1),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        })
    def _export_csv(self):
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
        self._log(f"📤 CSV: {Path(path).name}")
        QMessageBox.information(self, "نجاح", f"تم حفظ التقرير:\n{path}")
    def _export_learn(self):
        path, _ = QFileDialog.getSaveFileName(self, "حفظ التعلّم", "learner.json", "JSON (*.json)")
        if path:
            self.learner.export(path)
            self._log(f"💾 تصدير التعلّم: {Path(path).name}")
            QMessageBox.information(self, "نجاح", f"تم الحفظ:\n{path}")
    def _import_learn(self):
        path, _ = QFileDialog.getOpenFileName(self, "استيراد التعلّم", "", "JSON (*.json)")
        if path:
            try:
                self.learner.load(path)
                self._log(f"📥 استيراد {len(self.learner.history)} سجل")
                self._update_stats()
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"فشل الاستيراد:\n{e}")

    @staticmethod
    def _mk_btn(text: str, color: str, w: int = 0, h: int = 34) -> QPushButton:
        btn = QPushButton(text)
        if w:
            btn.setFixedWidth(w)
        btn.setFixedHeight(h)
        btn.setStyleSheet(f"QPushButton{{background:{color};color:white;border-radius:5px;font-weight:bold;padding:2px 6px;}}QPushButton:disabled{{background:#94a3b8;}}QPushButton:hover{{opacity:0.85;}}")
        return btn
    @staticmethod
    def _spinbox(lo: int, hi: int, val: int) -> QSpinBox:
        sb = QSpinBox()
        sb.setRange(lo, hi)
        sb.setValue(val)
        return sb

    # ---------- zoom ----------
    def zoom_in(self):
        self.zoom_factor = min(self.max_zoom, self.zoom_factor * 1.2)
        self._update_preview()
        self._update_zoom_label()

    def zoom_out(self):
        self.zoom_factor = max(self.min_zoom, self.zoom_factor / 1.2)
        self._update_preview()
        self._update_zoom_label()

    def zoom_fit(self):
        if self.current_img is None:
            return
        h, w = self.current_img.shape[:2]
        scroll_size = self.preview_scroll.viewport().size()
        fit_w = scroll_size.width() / w
        fit_h = scroll_size.height() / h
        self.zoom_factor = max(self.min_zoom, min(self.max_zoom, min(fit_w, fit_h)))
        self._update_preview()
        self._update_zoom_label()

    def _update_zoom_label(self):
        self.lbl_zoom.setText(f"{int(self.zoom_factor * 100)}%")

    # ---------- auto deskew on load ----------
    def _apply_auto_deskew_on_load(self):
        if self.current_img is None:
            return
        self.btn_auto_deskew.setEnabled(False)
        self.btn_auto_deskew.setText("⏳ جاري...")
        self._skew_worker = SkewWorker(self.current_img)
        self._skew_worker.finished.connect(self._on_auto_skew_done)
        self._skew_worker.error.connect(self._on_auto_skew_err)
        self._skew_worker.start()
    def _on_auto_skew_done(self, angle: float):
        self._detected_angle = angle
        self._push_undo()
        self.current_params["deskew_angle"] = angle
        self.slider_deskew.setValue(int(angle * 10))
        self.lbl_deskew.setText(f"{angle:+.1f}°")
        self._update_preview()
        self._log(f"🤖 تصحيح ميلان تلقائي: {angle:+.2f}°")
        self.btn_auto_deskew.setEnabled(True)
        self.btn_auto_deskew.setText("📐 كشف ميلان")
    def _on_auto_skew_err(self, msg: str):
        self.btn_auto_deskew.setEnabled(True)
        self.btn_auto_deskew.setText("📐 كشف ميلان")
        self._log(f"⚠️ فشل الكشف التلقائي: {msg}")

    # ---------- rotate ----------
    def rotate_left(self):
        self._push_undo()
        self.current_params["rotation"] = (self.current_params.get("rotation", 0) - 90) % 360
        self.lbl_rotation.setText(f"{self.current_params['rotation']}°")
        self._update_preview()
        self._log(f"↺ تدوير يسار → {self.current_params['rotation']}°")

    def rotate_right(self):
        self._push_undo()
        self.current_params["rotation"] = (self.current_params.get("rotation", 0) + 90) % 360
        self.lbl_rotation.setText(f"{self.current_params['rotation']}°")
        self._update_preview()
        self._log(f"↻ تدوير يمين → {self.current_params['rotation']}°")

    # ---------- fullscreen ----------
    
    def deskew_minus(self):
        val = self.slider_deskew.value() - 1
        self.slider_deskew.setValue(max(-150, val))
        self._update_preview()
    def deskew_plus(self):
        val = self.slider_deskew.value() + 1
        self.slider_deskew.setValue(min(150, val))
        self._update_preview()
    
    def deskew_minus(self):
        val = self.slider_deskew.value() - 1
        self.slider_deskew.setValue(max(-150, val))
        self._update_preview()
    def deskew_plus(self):
        val = self.slider_deskew.value() + 1
        self.slider_deskew.setValue(min(150, val))
        self._update_preview()
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ---------- clean missing files ----------
    
    def _save_learning_data(self, filename="training_data.json"):
        """حفظ بيانات التعلم إلى ملف JSON"""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.learner.history, f, ensure_ascii=False, indent=2)
            self._log(f"💾 تم حفظ {len(self.learner.history)} سجل تعلم في {filename}")
        except Exception as e:
            self._log(f"❌ فشل حفظ التعلم: {e}")
    
    def _load_learning_data(self, filename="training_data.json"):
        """تحميل بيانات التعلم من ملف JSON"""
        try:
            if Path(filename).exists():
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.learner.history = data[-self.learner.MAX:]
                    self._log(f"📥 تم تحميل {len(self.learner.history)} سجل تعلم من {filename}")
        except Exception as e:
            self._log(f"⚠️ لم نتمكن من تحميل التعلم: {e}")
    
    def _save_learning_data(self, filename="training_data.json"):
        """حفظ بيانات التعلم إلى ملف JSON"""
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(self.learner.history, f, ensure_ascii=False, indent=2)
            self._log(f"💾 تم حفظ {len(self.learner.history)} سجل تعلم في {filename}")
        except Exception as e:
            self._log(f"❌ فشل حفظ التعلم: {e}")
    
    def _load_learning_data(self, filename="training_data.json"):
        """تحميل بيانات التعلم من ملف JSON"""
        try:
            if Path(filename).exists():
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.learner.history = data[-self.learner.MAX:]
                    self._log(f"📥 تم تحميل {len(self.learner.history)} سجل تعلم من {filename}")
        except Exception as e:
            self._log(f"⚠️ لم نتمكن من تحميل التعلم: {e}")
    def _clean_missing_files(self):
        i = 0
        while i < len(self.image_list):
            entry = self.image_list[i]
            if isinstance(entry, Path) and not entry.exists():
                self._log(f"⚠️ إزالة ملف مفقود: {entry.name}")
                self.image_list.pop(i)
                self.image_names.pop(i)
                self.stats["total"] = len(self.image_list)
            else:
                i += 1
        self.progress.setMaximum(self.stats["total"])
        self.lbl_s_total.setText(str(self.stats["total"]))
        if self.current_idx >= len(self.image_list):
            self.current_idx = max(0, len(self.image_list)-1)
        if self.image_list:
            self._load_current()

    def closeEvent(self, event):
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.stop()
            self._thumb_worker.wait()
        event.accept()

# ---------- entry point ----------
def main():
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setStyle("Fusion")
    win = MedicalDocApp()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
