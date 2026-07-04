#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏥 معالج الوثائق الطبية الذكي V10 - الإصدار المتكامل والمصحح

الميزات الكاملة:
✅ نظام تعلم آلي ذكي (يحفظ كل صورة وإعداداتها في learning_database.json)
✅ خوارزميات قص ذكي متقدمة (مسح الحواف + كشف الكونتورات)
✅ ضبط دقيق للميلان (+/- 0.5°) والهوامش (+/- 5px)
✅ تكبير/تصغير وملاءمة للصورة مع شريط تمرير
✅ تصحيح تلقائي للميلان عند الفتح (خلفية غير متزامنة)
✅ حفظ تلقائي لقاعدة التعلم والملفات الأصلية
✅ أداء محسن (معاينة محدودة 1600px، مصغرات سريعة)
✅ شريط مصغرات للملاحة السريعة
✅ تراجع/إعادة (Ctrl+Z/Y)
✅ معالج دفعة للملفات المتبقية
✅ تصدير/استيراد قاعدة التعلم و CSV
✅ دعم السحب والإفلات
✅ واجهة عربية كاملة
"""

import sys
import os
import json
import csv
import math
import shutil
from pathlib import Path
from datetime import datetime
from collections import deque
import cv2
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QSlider, QSpinBox, QCheckBox, QProgressBar,
    QTextEdit, QFileDialog, QMessageBox, QGroupBox, QFormLayout,
    QSplitter, QDialog, QScrollArea, QSizePolicy, QTabWidget, QFrame,
    QShortcut
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QImage, QFont, QKeySequence, QColor, QIcon

# ==================================================================
# 0. الثوابت والإعدادات العامة
# ==================================================================

IMG_EXT = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
LOG_FILE = Path("processing_log.txt")
LEARN_DB = Path("learning_database.json")
MAX_PREVIEW = 1600  # حد أقصى للمعاينة (بكسل)
THUMB_W, THUMB_H = 90, 115
UNDO_LIMIT = 20

PDF_SUPPORT = False
try:
    from pdf2image import convert_from_path
    PDF_SUPPORT = True
except ImportError:
    pass

# ==================================================================
# 1. خوارزميات معالجة الصور المتقدمة
# ==================================================================

def _scan_borders_crop(gray, padding=15, brightness_threshold=30):
    """
    الخوارزمية البسيطة: مسح الحواف صفاً وصفاً وعموداً وعموداً حتى أول بكسل يتجاوز العتبة
    """
    h, w = gray.shape
    top, bottom = 0, h - 1
    left, right = 0, w - 1

    # من الأعلى للاسفل
    for row in range(h):
        if np.mean(gray[row, :]) > brightness_threshold:
            top = row
            break
    # من الأسفل للأعلى
    for row in range(h - 1, -1, -1):
        if np.mean(gray[row, :]) > brightness_threshold:
            bottom = row
            break
    # من اليسار لليمين
    for col in range(w):
        if np.mean(gray[:, col]) > brightness_threshold:
            left = col
            break
    # من اليمين لليسار
    for col in range(w - 1, -1, -1):
        if np.mean(gray[:, col]) > brightness_threshold:
            right = col
            break

    if top >= bottom or left >= right:
        return (0, 0, 0, 0)

    # إضافة الهامش الأمان
    l = max(0, left - padding)
    t = max(0, top - padding)
    r = max(0, w - 1 - (right + padding))
    b = max(0, h - 1 - (bottom + padding))
    return (l, t, r, b)


def _document_corner_crop(img, padding=10):
    """
    الخوارزمية المتقدمة: كشف الحواف باستخدام Canny + تقريب المضلعات المحدبة + تحويل المنظور
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    # تنقية الحواف وإغلاق الفجوات
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # ترتيب الكونتورات حسب المساحة واختيار الأكبر
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
    approx = None

    for cnt in contours:
        peri = cv2.arcLength(cnt, True)
        approx_poly = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        # إذا حصلنا على مضلع رباعي الزوايا
        if len(approx_poly) == 4:
            approx = approx_poly
            break

    if approx is None:
        return None

    # استخراج النقاط
    pts = approx.reshape(4, 2)
    x_vals = pts[:, 0]
    y_vals = pts[:, 1]

    x_min = max(0, int(np.min(x_vals)) - padding)
    x_max = min(img.shape[1], int(np.max(x_vals)) + padding)
    y_min = max(0, int(np.min(y_vals)) - padding)
    y_max = min(img.shape[0], int(np.max(y_vals)) + padding)

    l = x_min
    t = y_min
    r = img.shape[1] - x_max
    b = img.shape[0] - y_max
    return (l, t, r, b)


def smart_auto_crop(img, padding=15, dark_threshold=30, use_advanced=True):
    """
    دالة القص الذكي الهجينة المتقدمة (v2)
    تجمع بين مسح الحواف البسيط وكشف المنظور المتقدم
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    h, w = gray.shape

    # 1. تجربة الخوارزمية البسيطة أولاً
    simple_result = _scan_borders_crop(gray, padding=padding, brightness_threshold=dark_threshold)
    l_s, t_s, r_s, b_s = simple_result

    crop_width = w - (l_s + r_s)
    crop_height = h - (t_s + b_s)

    # 2. التحقق من كفاءة القص
    if (crop_width > w * 0.10 and crop_height > h * 0.10) or not use_advanced:
        return simple_result

    # 3. الانتقال الذكي للخوارزمية المتقدمة
    advanced_result = _document_corner_crop(img, padding=padding)
    if advanced_result is not None:
        return advanced_result

    return simple_result


def rotate_image(image: np.ndarray, angle: float) -> np.ndarray:
    """تدوير الصورة بزاوية دقيقة مع الحفاظ على كامل أبعاد الصورة"""
    if abs(angle) < 0.01:
        return image.copy()
    h, w = image.shape[:2]
    cX, cY = w // 2, h // 2
    M = cv2.getRotationMatrix2D((cX, cY), angle, 1.0)
    cos = np.abs(M[0, 0])
    sin = np.abs(M[0, 1])
    nW = int((h * sin) + (w * cos))
    nH = int((h * cos) + (w * sin))
    M[0, 2] += (nW / 2) - cX
    M[1, 2] += (nH / 2) - cY
    return cv2.warpAffine(image, M, (nW, nH), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))


def apply_processing(img, params):
    """تطبيق جميع العمليات على الصورة: تدوير -> ميلان -> قص -> قلب -> تحسين"""
    out = img.copy()
    h, w = out.shape[:2]

    # 1. التدوير (90, 180, 270 درجة)
    rot = params.get("rotation", 0) % 360
    if rot == 90:
        out = cv2.rotate(out, cv2.ROTATE_90_CLOCKWISE)
    elif rot == 180:
        out = cv2.rotate(out, cv2.ROTATE_180)
    elif rot == 270:
        out = cv2.rotate(out, cv2.ROTATE_90_COUNTERCLOCKWISE)
    h, w = out.shape[:2]

    # 2. القص
    l, t, r, b = params.get("crop", (0, 0, 0, 0))
    r2, b2 = w - r, h - b
    if l < r2 and t < b2:
        out = out[t:b2, l:r2]

    # 3. الميلان الدقيق
    angle = params.get("deskew_angle", 0.0)
    if abs(angle) > 0.1:
        ch, cw = out.shape[:2]
        M = cv2.getRotationMatrix2D((cw//2, ch//2), angle, 1.0)
        out = cv2.warpAffine(out, M, (cw, ch), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))

    # 4. القلب الأفقي
    if params.get("flip_h", False):
        out = cv2.flip(out, 1)

    # 5. تحسين الوضوح
    if params.get("sharpen", False):
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        out = cv2.filter2D(out, -1, kernel)

    return out


def cv2_to_pixmap(img, zoom=1.0, max_w=0, max_h=0):
    """تحويل صورة OpenCV إلى QPixmap مع تحجيم"""
    h, w = img.shape[:2]
    nw, nh = int(w * zoom), int(h * zoom)
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


def calc_quality(img):
    """حساب درجة الوضوح باستخدام تباين لابلاس"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def auto_detect_skew_fast(img, max_angle=10, step=0.5):
    """كشف سريع ودقيق للميلان باستخدام تحليل ملفوف الإسقاط"""
    if img is None:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    h, w = gray.shape

    # تصغير الصورة للسرعة
    if w > 800:
        scale = 800 / w
        gray = cv2.resize(gray, (int(w * scale), int(h * scale)))

    gray = cv2.equalizeHist(gray)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    best_score, best_angle = -1.0, 0.0
    h, w = binary.shape
    center = (w // 2, h // 2)

    for angle in np.arange(-max_angle, max_angle + step, step):
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rot = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REPLICATE)
        # حساب التباين في الإسقاط الأفقي
        score = float(np.var(np.sum(rot, axis=1)))
        if score > best_score:
            best_score, best_angle = score, float(angle)

    return best_angle


# ==================================================================
# 2. نظام التعلم الذكي
# ==================================================================

class SmartLearner:
    """نظام تعلم يحفظ كل إجراء ويستخدمه لتحسين الأداء"""
    def __init__(self):
        self.database = []
        self.load()

    def load(self):
        if LEARN_DB.exists():
            try:
                with open(LEARN_DB, 'r', encoding='utf-8') as f:
                    self.database = json.load(f)
                # الاحتفاظ بآخر 500 سجل فقط للأداء
                if len(self.database) > 500:
                    self.database = self.database[-500:]
            except:
                self.database = []

    def save(self):
        with open(LEARN_DB, 'w', encoding='utf-8') as f:
            json.dump(self.database, f, ensure_ascii=False, indent=2)

    def extract_features(self, img):
        """استخراج ميزات الصورة للتعلم"""
        if img is None:
            return {}
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        h, w = gray.shape
        return {
            'width': w, 'height': h,
            'brightness': float(np.mean(gray)),
            'contrast': float(np.std(gray)),
            'aspect_ratio': round(w / max(h, 1), 3),
            'blur_score': float(cv2.Laplacian(gray, cv2.CV_64F).var())
        }

    def add_action(self, img, action_type, params, result_quality):
        """حفظ إجراء جديد في قاعدة البيانات"""
        features = self.extract_features(img)
        record = {
            'timestamp': datetime.now().isoformat(),
            'features': features,
            'action': action_type,
            'params': params,
            'result_quality': result_quality,
            'success': result_quality > 50  # نجاح إذا كانت الجودة > 50
        }
        self.database.append(record)
        self.save()
        return record

    def suggest_params(self, current_img, action_type):
        """اقتراح إعدادات بناءً على الإجراءات السابقة الناجحة"""
        if len(self.database) < 3:
            return None, 0.0

        current_features = self.extract_features(current_img)
        best_sim, best_params = 0.0, None

        # البحث في السجلات الناجحة فقط من نفس نوع الإجراء
        for rec in self.database:
            if not rec.get('success', True):
                continue
            if rec.get('action') != action_type:
                continue

            f = rec['features']
            # حساب التشابه
            sim = (
                (1 - abs(current_features['width'] - f['width']) / 3000) * 0.25 +
                (1 - abs(current_features['height'] - f['height']) / 4000) * 0.25 +
                (1 - abs(current_features['brightness'] - f['brightness']) / 255) * 0.25 +
                (1 - abs(current_features['blur_score'] - f['blur_score']) / 2000) * 0.25
            )

            if sim > best_sim:
                best_sim, best_params = sim, rec['params']

        return (best_params, best_sim) if best_sim > 0.85 else (None, 0.0)


# ==================================================================
# 3. خيوط المعالجة الخلفية
# ==================================================================

class DeskewWorker(QThread):
    """خيط لكشف زاوية الميلان تلقائيًا"""
    finished = pyqtSignal(float)

    def __init__(self, img):
        super().__init__()
        self.img = img

    def run(self):
        angle = auto_detect_skew_fast(self.img)
        self.finished.emit(angle)


class ThumbnailWorker(QThread):
    """خيط لتوليد صور مصغرة للملاحة السريعة"""
    ready = pyqtSignal(int, QPixmap)

    def __init__(self, image_list):
        super().__init__()
        self.image_list = image_list
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for i, entry in enumerate(self.image_list):
            if self._stop:
                break
            try:
                if isinstance(entry, Path):
                    img = cv2.imread(str(entry), cv2.IMREAD_REDUCED_COLOR_4)
                else:
                    img = entry
                if img is not None:
                    pix = cv2_to_pixmap(img, max_w=THUMB_W, max_h=THUMB_H)
                    self.ready.emit(i, pix)
            except:
                pass


class ProcessingWorker(QThread):
    """خيط لمعالجة دفية للملفات المتبقية"""
    progress = pyqtSignal(int, int)
    finished = pyqtSignal()

    def __init__(self, images, params, learner):
        super().__init__()
        self.images = images
        self.params = params
        self.learner = learner
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        for i, path in enumerate(self.images):
            if self._stop:
                break
            try:
                img = cv2.imread(str(path))
                if img is None:
                    continue

                # تطبيق المعالجة
                proc = apply_processing(img, self.params)

                # حساب الجودة
                quality = calc_quality(proc)

                # حفظ في قاعدة التعلم
                self.learner.add_action(img, 'batch', self.params, quality)

                # حفظ النتيجة
                out_dir = Path('processed')
                out_dir.mkdir(exist_ok=True)
                out_path = out_dir / f"doc_{i+1:04d}.png"
                cv2.imwrite(str(out_path), proc)

                # نقل الأصل إلى raw_scanned_files
                raw_dir = Path.home() / "Documents" / "raw_scanned_files"
                raw_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(path), str(raw_dir / path.name))

                self.progress.emit(i+1, len(self.images))
            except Exception as e:
                print(f"Error processing {path}: {e}")

        self.finished.emit()


# ==================================================================
# 4. الواجهة الرئيسية
# ==================================================================

class MedicalDocAppV10(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏥 معالج الوثائق الطبية الذكي V10")
        self.setMinimumSize(1024, 600)
        self.showMaximized()
        self.setFont(QFont("Noto Sans Arabic", 10))
        self.setAcceptDrops(True)
        self.setLayoutDirection(Qt.RightToLeft)

        # حالة التطبيق
        self.images = []
        self.image_names = []
        self.current_idx = 0
        self.current_img = None
        self.params = {
            'crop': (20, 20, 20, 20),
            'deskew_angle': 0.0,
            'rotation': 0,
            'flip_h': False,
            'sharpen': False
        }
        self.zoom_factor = 1.0
        self.min_zoom, self.max_zoom = 0.1, 5.0
        self.stats = {"total": 0, "processed": 0, "skipped": 0, "start_time": None}
        self.processing_records = []
        self.learner = SmartLearner()
        self.thumb_buttons = []
        self._deskew_worker = None
        self._thumb_worker = None
        self._undo_stack = deque(maxlen=UNDO_LIMIT)
        self._redo_stack = deque(maxlen=UNDO_LIMIT)

        self._build_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._clock = QTimer(self)
        self._clock.timeout.connect(self._tick_clock)
        self._clock.start(1000)

    # ==================================================================
    # بناء الواجهة
    # ==================================================================

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(4)

        # --- الشريط العلوي ---
        top = QHBoxLayout()
        self.lbl_status = QLabel("📁 افتح مجلداً أو اسحب ملفات هنا")
        self.lbl_index = QLabel("0 / 0")
        self.lbl_index.setStyleSheet("font-weight:bold;font-size:11pt;")
        self.btn_open = self._mk_btn("📂 فتح", "#0369a1")
        self.btn_prev = self._mk_btn("⬅️ السابق", "#475569", 85)
        self.btn_next = self._mk_btn("التالي ➡️", "#475569", 85)
        self.btn_export_csv = self._mk_btn("📤 CSV", "#7c3aed", 80)
        self.btn_export_learn = self._mk_btn("💾 تعلّم", "#0891b2", 80)
        self.btn_import_learn = self._mk_btn("📥 استيراد", "#0891b2", 80)
        self.btn_save_learn = self._mk_btn("💾 حفظ التعلّم", "#0891b2", 100)

        for w in [self.lbl_status, None, self.lbl_index, self.btn_prev, self.btn_next,
                  self.btn_export_csv, self.btn_export_learn, self.btn_import_learn,
                  self.btn_save_learn, self.btn_open]:
            if w is None:
                top.addStretch()
            else:
                top.addWidget(w)
        main_layout.addLayout(top)

        # --- المنطقة الوسطى (مقسم) ---
        mid_splitter = QSplitter(Qt.Horizontal)

        # اللوحة اليسرى: المعاينة
        left_w = QWidget()
        left_layout = QVBoxLayout(left_w)
        left_layout.setSpacing(4)

        # منطقة المعاينة مع شريط تمرير
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setAlignment(Qt.AlignCenter)
        self.preview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.preview_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.preview_scroll.setStyleSheet("QScrollArea{border:2px dashed #94a3b8;border-radius:8px;background:#f0f4f8;}")

        self.lbl_preview = QLabel("⏳ بانتظار التحميل...")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setMinimumSize(400, 300)
        self.preview_scroll.setWidget(self.lbl_preview)
        left_layout.addWidget(self.preview_scroll)

        # أزرار التحكم الرئيسية
        ctrl_row = QHBoxLayout()
        self.btn_refresh = self._mk_btn("🔄 تحديث", "#475569", h=32)
        self.btn_smart_crop = self._mk_btn("✂️ قص ذكي", "#7c3aed", h=32)
        self.btn_compare = self._mk_btn("🔍 مقارنة", "#6366f1", h=32)
        self.btn_confirm = self._mk_btn("✅ حفظ", "#16a34a", h=32)
        self.btn_skip = self._mk_btn("⏭️ تخطي", "#dc2626", h=32)
        self.btn_apply_all = self._mk_btn("🤖 طبّق على البقية", "#0369a1", h=32)
        self.btn_apply_all.setEnabled(False)

        for b in [self.btn_refresh, self.btn_smart_crop, self.btn_compare,
                  self.btn_confirm, self.btn_skip, self.btn_apply_all]:
            ctrl_row.addWidget(b)
        left_layout.addLayout(ctrl_row)

        # أزرار ضبط الميلان
        skew_row = QHBoxLayout()
        skew_row.addWidget(QLabel("📐 الميلان:"))
        self.btn_skew_minus = self._mk_btn("−", "#64748b", w=35, h=32)
        self.lbl_skew_val = QLabel("0.0°")
        self.lbl_skew_val.setFixedWidth(45)
        self.lbl_skew_val.setAlignment(Qt.AlignCenter)
        self.btn_skew_plus = self._mk_btn("+", "#64748b", w=35, h=32)
        skew_row.addWidget(self.btn_skew_minus)
        skew_row.addWidget(self.lbl_skew_val)
        skew_row.addWidget(self.btn_skew_plus)
        skew_row.addStretch()
        self.chk_auto_skew = QCheckBox("🔄 تصحيح تلقائي عند الفتح")
        self.chk_auto_skew.setChecked(True)
        skew_row.addWidget(self.chk_auto_skew)
        left_layout.addLayout(skew_row)

        # أزرار ضبط الهوامش
        crop_row = QHBoxLayout()
        crop_row.addWidget(QLabel("✂️ الهوامش:"))
        self.btn_crop_minus = self._mk_btn("−", "#64748b", w=35, h=32)
        self.lbl_crop_val = QLabel("20px")
        self.lbl_crop_val.setFixedWidth(45)
        self.lbl_crop_val.setAlignment(Qt.AlignCenter)
        self.btn_crop_plus = self._mk_btn("+", "#64748b", w=35, h=32)
        crop_row.addWidget(self.btn_crop_minus)
        crop_row.addWidget(self.lbl_crop_val)
        crop_row.addWidget(self.btn_crop_plus)
        crop_row.addStretch()
        self.chk_flip = QCheckBox("↔️ قلب أفقي")
        self.chk_sharpen = QCheckBox("🔆 تحسين الوضوح")
        crop_row.addWidget(self.chk_flip)
        crop_row.addWidget(self.chk_sharpen)
        left_layout.addLayout(crop_row)

        # أزرار التكبير
        zoom_row = QHBoxLayout()
        zoom_row.addWidget(QLabel("🔍 التكبير:"))
        self.btn_zoom_out = self._mk_btn("🔍-", "#475569", w=40, h=32)
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(45)
        self.lbl_zoom.setAlignment(Qt.AlignCenter)
        self.btn_zoom_in = self._mk_btn("🔍+", "#475569", w=40, h=32)
        self.btn_zoom_fit = self._mk_btn("⛶ ملاءمة", "#475569", w=70, h=32)
        zoom_row.addWidget(self.btn_zoom_out)
        zoom_row.addWidget(self.lbl_zoom)
        zoom_row.addWidget(self.btn_zoom_in)
        zoom_row.addWidget(self.btn_zoom_fit)
        zoom_row.addStretch()
        self.btn_fullscreen = self._mk_btn("⛶ ملء", "#475569", w=60, h=32)
        zoom_row.addWidget(self.btn_fullscreen)
        left_layout.addLayout(zoom_row)

        # أزرار التدوير
        rot_row = QHBoxLayout()
        rot_row.addWidget(QLabel("↻ التدوير:"))
        self.btn_rot_left = self._mk_btn("↺ يسار", "#7c3aed", w=70, h=32)
        self.lbl_rotation = QLabel("0°")
        self.lbl_rotation.setFixedWidth(40)
        self.lbl_rotation.setAlignment(Qt.AlignCenter)
        self.btn_rot_right = self._mk_btn("↻ يمين", "#7c3aed", w=70, h=32)
        rot_row.addWidget(self.btn_rot_left)
        rot_row.addWidget(self.lbl_rotation)
        rot_row.addWidget(self.btn_rot_right)
        rot_row.addStretch()
        left_layout.addLayout(rot_row)

        mid_splitter.addWidget(left_w)

        # --- اللوحة اليمنى (التبويبات) ---
        right_w = QWidget()
        right_w.setFixedWidth(420)
        right_layout = QVBoxLayout(right_w)
        tabs = QTabWidget()

        # تبويب الإعدادات
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)

        crop_group = QGroupBox("✂️ هوامش القص (بكسل)")
        form = QFormLayout()
        self.sp_crop_t = QSpinBox()
        self.sp_crop_t.setRange(0, 2000)
        self.sp_crop_t.setValue(20)
        self.sp_crop_b = QSpinBox()
        self.sp_crop_b.setRange(0, 2000)
        self.sp_crop_b.setValue(20)
        self.sp_crop_l = QSpinBox()
        self.sp_crop_l.setRange(0, 2000)
        self.sp_crop_l.setValue(20)
        self.sp_crop_r = QSpinBox()
        self.sp_crop_r.setRange(0, 2000)
        self.sp_crop_r.setValue(20)
        form.addRow("علوي:", self.sp_crop_t)
        form.addRow("سفلي:", self.sp_crop_b)
        form.addRow("أيسر:", self.sp_crop_l)
        form.addRow("أيمن:", self.sp_crop_r)
        crop_group.setLayout(form)
        settings_layout.addWidget(crop_group)

        settings_layout.addStretch()
        tabs.addTab(settings_tab, "⚙️ الإعدادات")

        # تبويب الجودة والإحصائيات
        stats_tab = QWidget()
        stats_layout = QVBoxLayout(stats_tab)

        self.lbl_quality = QLabel("⏳...")
        self.lbl_quality.setStyleSheet("font-weight:bold;padding:6px;border-radius:4px;")
        self.lbl_blur = QLabel("0")
        score_row = QHBoxLayout()
        score_row.addWidget(QLabel("📐 درجة الوضوح:"))
        score_row.addWidget(self.lbl_blur)
        score_row.addStretch()
        stats_layout.addWidget(self.lbl_quality)
        stats_layout.addLayout(score_row)

        stat_box = QGroupBox("📈 إحصائيات الجلسة")
        sl = QFormLayout()
        self.lbl_total = QLabel("0")
        self.lbl_processed = QLabel("0")
        self.lbl_skipped = QLabel("0")
        self.lbl_learned = QLabel("0")
        self.lbl_time = QLabel("00:00:00")
        sl.addRow("إجمالي:", self.lbl_total)
        sl.addRow("معالجة:", self.lbl_processed)
        sl.addRow("تخطي:", self.lbl_skipped)
        sl.addRow("سجلات التعلّم:", self.lbl_learned)
        sl.addRow("الوقت:", self.lbl_time)
        stat_box.setLayout(sl)
        stats_layout.addWidget(stat_box)

        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background:#0f172a;color:#94a3b8;font-family:monospace;font-size:9pt;")
        stats_layout.addWidget(QLabel("📝 سجل العمليات:"))
        stats_layout.addWidget(self.txt_log)
        tabs.addTab(stats_tab, "📊 الإحصائيات")

        right_layout.addWidget(tabs)
        mid_splitter.addWidget(right_w)
        mid_splitter.setSizes([960, 420])
        main_layout.addWidget(mid_splitter, stretch=1)

        # --- شريط المصغرات ---
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
        main_layout.addWidget(thumb_frame)

        # شريط التقدم
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFixedHeight(18)
        main_layout.addWidget(self.progress)

    def _mk_btn(self, text, color, w=0, h=34):
        """إنشاء زر بمواصفات موحدة"""
        btn = QPushButton(text)
        if w:
            btn.setFixedWidth(w)
        btn.setFixedHeight(h)
        btn.setStyleSheet(f"QPushButton{{background:{color};color:white;border-radius:5px;font-weight:bold;}}QPushButton:disabled{{background:#94a3b8;}}QPushButton:hover{{opacity:0.85;}}")
        return btn

    # ==================================================================
    # ربط الإشارات
    # ==================================================================

    def _connect_signals(self):
        # أزرار التنقل والفتح
        self.btn_open.clicked.connect(self._open_folder)
        self.btn_prev.clicked.connect(lambda: self._navigate(-1))
        self.btn_next.clicked.connect(lambda: self._navigate(1))

        # أزرار المعالجة
        self.btn_refresh.clicked.connect(self._update_preview)
        self.btn_smart_crop.clicked.connect(self._do_smart_crop)
        self.btn_compare.clicked.connect(self._show_compare)
        self.btn_confirm.clicked.connect(self._save_current)
        self.btn_skip.clicked.connect(self._skip_current)
        self.btn_apply_all.clicked.connect(self._apply_batch)

        # تصدير واستيراد
        self.btn_export_csv.clicked.connect(self._export_csv)
        self.btn_export_learn.clicked.connect(self._export_learn)
        self.btn_import_learn.clicked.connect(self._import_learn)
        self.btn_save_learn.clicked.connect(lambda: self.learner.save())

        # التكبير/التصغير
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_fit.clicked.connect(self.zoom_fit)
        self.btn_fullscreen.clicked.connect(self.toggle_fullscreen)

        # التدوير
        self.btn_rot_left.clicked.connect(self.rotate_left)
        self.btn_rot_right.clicked.connect(self.rotate_right)

        # ضبط الميلان
        self.btn_skew_minus.clicked.connect(lambda: self._adjust_skew(-0.5))
        self.btn_skew_plus.clicked.connect(lambda: self._adjust_skew(0.5))
        self.chk_auto_skew.toggled.connect(self._on_auto_skew_toggled)

        # ضبط الهوامش
        self.btn_crop_minus.clicked.connect(lambda: self._adjust_crop(-5))
        self.btn_crop_plus.clicked.connect(lambda: self._adjust_crop(5))

        # خيارات إضافية
        self.chk_flip.toggled.connect(self._on_param_change)
        self.chk_sharpen.toggled.connect(self._on_param_change)

        # SpinBoxes للهوامش
        for sp in [self.sp_crop_t, self.sp_crop_b, self.sp_crop_l, self.sp_crop_r]:
            sp.valueChanged.connect(self._on_param_change)

        # مؤقت لتحديث المعاينة عند تغيير المعلمات
        self._ptimer = QTimer(self)
        self._ptimer.setSingleShot(True)
        self._ptimer.timeout.connect(self._update_preview)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self._redo)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_current)
        QShortcut(QKeySequence("Right"), self, lambda: self._navigate(1))
        QShortcut(QKeySequence("Left"), self, lambda: self._navigate(-1))

    # ==================================================================
    # دوال المساعدة
    # ==================================================================

    def _adjust_skew(self, delta):
        self.params['deskew_angle'] = round(self.params['deskew_angle'] + delta, 1)
        self.lbl_skew_val.setText(f"{self.params['deskew_angle']:+.1f}°")
        self._update_preview()

    def _adjust_crop(self, delta):
        old = self.params['crop'][0]  # نفترض هوامش موحدة
        new_val = max(0, min(2000, old + delta))
        self.params['crop'] = (new_val, new_val, new_val, new_val)
        self.lbl_crop_val.setText(f"{new_val}px")
        for sp, val in [(self.sp_crop_l, new_val), (self.sp_crop_t, new_val),
                        (self.sp_crop_r, new_val), (self.sp_crop_b, new_val)]:
            sp.blockSignals(True)
            sp.setValue(val)
            sp.blockSignals(False)
        self._update_preview()

    def _on_param_change(self):
        """تحديث المعلمات عند تغيير أي عنصر"""
        self.params['crop'] = (
            self.sp_crop_l.value(),
            self.sp_crop_t.value(),
            self.sp_crop_r.value(),
            self.sp_crop_b.value()
        )
        self.params['flip_h'] = self.chk_flip.isChecked()
        self.params['sharpen'] = self.chk_sharpen.isChecked()
        self._ptimer.start(200)

    def _on_auto_skew_toggled(self, state):
        if state and self.current_img is not None:
            self._apply_auto_deskew()

    def _push_undo(self):
        """حفظ الحالة الحالية في مكدس التراجع"""
        self._undo_stack.append(self.params.copy())
        self._redo_stack.clear()

    def _undo(self):
        """تراجع إلى الحالة السابقة"""
        if not self._undo_stack:
            return
        self._redo_stack.append(self.params.copy())
        self.params = self._undo_stack.pop()
        self._sync_ui_from_params()
        self._update_preview()
        self._log("↩️ تراجع")

    def _redo(self):
        """إعادة إلى الحالة التالية"""
        if not self._redo_stack:
            return
        self._undo_stack.append(self.params.copy())
        self.params = self._redo_stack.pop()
        self._sync_ui_from_params()
        self._update_preview()
        self._log("↪️ إعادة")

    def _sync_ui_from_params(self):
        """مزامنة الواجهة مع المعلمات الحالية"""
        crop = self.params.get('crop', (20, 20, 20, 20))
        self.lbl_crop_val.setText(f"{crop[0]}px")
        self.lbl_skew_val.setText(f"{self.params['deskew_angle']:+.1f}°")
        self.chk_flip.setChecked(self.params.get('flip_h', False))
        self.chk_sharpen.setChecked(self.params.get('sharpen', False))
        self.lbl_rotation.setText(f"{self.params.get('rotation', 0)}°")
        for sp, val in [(self.sp_crop_l, crop[0]), (self.sp_crop_t, crop[1]),
                        (self.sp_crop_r, crop[2]), (self.sp_crop_b, crop[3])]:
            sp.blockSignals(True)
            sp.setValue(val)
            sp.blockSignals(False)

    # ==================================================================
    # عمليات التحميل والحفظ
    # ==================================================================

    def _open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "اختر مجلداً")
        if folder:
            self._load_paths([folder])

    def _load_paths(self, paths):
        images, names = [], []
        for p in paths:
            pp = Path(p)
            if pp.is_dir():
                for f in sorted(pp.glob("*")):
                    if f.suffix.lower() in IMG_EXT and f.exists():
                        images.append(f)
                        names.append(f.name)
            elif pp.is_file() and pp.suffix.lower() in IMG_EXT and pp.exists():
                images.append(pp)
                names.append(pp.name)

        if not images:
            QMessageBox.warning(self, "تنبيه", "لم يتم العثور على ملفات صالحة.")
            return

        # إيقاف خيط المصغرات السابق
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.stop()
            self._thumb_worker.wait()

        self.images, self.image_names = images, names
        self.current_idx = 0
        self.processing_records = []
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.stats = {"total": len(images), "processed": 0, "skipped": 0,
                     "start_time": datetime.now()}
        self.progress.setMaximum(len(images))
        self.lbl_total.setText(str(len(images)))
        self._log(f"📥 تم تحميل {len(images)} ملف")

        self._build_thumbnails()
        self._load_current()

    def _build_thumbnails(self):
        """إنشاء أزرار المصغرات"""
        for b in self.thumb_buttons:
            b.deleteLater()
        self.thumb_buttons.clear()
        while self.thumb_layout.count():
            item = self.thumb_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for i in range(len(self.images)):
            btn = QPushButton(str(i+1))
            btn.setFixedSize(THUMB_W+6, THUMB_H+18)
            btn.setStyleSheet("QPushButton{background:#1e293b;color:#cbd5e1;border:1px solid #334155;border-radius:4px;}")
            btn.clicked.connect(lambda _, idx=i: self._jump_to(idx))
            self.thumb_buttons.append(btn)
            self.thumb_layout.addWidget(btn)
        self.thumb_layout.addStretch()

        self._thumb_worker = ThumbnailWorker(self.images)
        self._thumb_worker.ready.connect(self._on_thumb_ready)
        self._thumb_worker.start()

    def _on_thumb_ready(self, idx, pix):
        if idx < len(self.thumb_buttons):
            self.thumb_buttons[idx].setIcon(QIcon(pix))
            self.thumb_buttons[idx].setIconSize(QSize(THUMB_W, THUMB_H))
            self.thumb_buttons[idx].setText("")

    def _jump_to(self, idx):
        self.current_idx = idx
        self._load_current()

    def _load_current(self):
        """تحميل الصورة الحالية"""
        if not self.images:
            return

        path = self.images[self.current_idx]
        name = self.image_names[self.current_idx]
        self.lbl_index.setText(f"{self.current_idx+1} / {len(self.images)}")
        self.progress.setValue(self.current_idx)

        # تحديث تحديد المصغرة
        for i, b in enumerate(self.thumb_buttons):
            style = "QPushButton{background:#1e293b;color:#cbd5e1;border:1px solid #334155;border-radius:4px;}"
            if i == self.current_idx:
                style = "QPushButton{background:#2563eb;color:white;border:2px solid #60a5fa;border-radius:4px;}"
            b.setStyleSheet(style)

        img = cv2.imread(str(path))
        if img is None:
            self._log(f"❌ فشل قراءة: {name}")
            return

        self.current_img = img

        # إعادة تعيين الدوران لكل صورة جديدة
        self.params['rotation'] = 0
        self.lbl_rotation.setText("0°")

        # اقتراح من قاعدة التعلم
        sugg, sim = self.learner.suggest_params(img, 'load')
        if sugg and sim > 0.9:
            self.params.update(sugg)
            self._log(f"🤖 اقتراح مستفاد ({sim*100:.0f}%)")
        else:
            self._log(f"📄 تحميل: {name}")

        # مزامنة الواجهة
        self._sync_ui_from_params()

        # تصحيح تلقائي للميلان إذا كان مفعلاً
        if self.chk_auto_skew.isChecked():
            self._apply_auto_deskew()
        else:
            self._update_preview()

    def _apply_auto_deskew(self):
        """تصحيح تلقائي للميلان"""
        if self.current_img is None:
            return
        self._deskew_worker = DeskewWorker(self.current_img)
        self._deskew_worker.finished.connect(self._on_auto_deskew_done)
        self._deskew_worker.start()
        self.lbl_status.setText("⏳ جاري كشف الميلان...")

    def _on_auto_deskew_done(self, angle):
        if abs(angle) > 0.3:
            self.params['deskew_angle'] = round(angle, 1)
            self.lbl_skew_val.setText(f"{self.params['deskew_angle']:+.1f}°")
            self._log(f"🤖 تصحيح تلقائي للميلان: {angle:+.2f}°")
        self._update_preview()
        self.lbl_status.setText("✅ جاهز")

    def _update_preview(self):
        """تحديث معاينة الصورة"""
        if self.current_img is None:
            return

        processed = apply_processing(self.current_img, self.params)
        pix = cv2_to_pixmap(processed, zoom=self.zoom_factor, max_w=MAX_PREVIEW, max_h=MAX_PREVIEW)
        self.lbl_preview.setPixmap(pix)
        self.lbl_preview.setFixedSize(pix.width(), pix.height())

        # تحديث جودة المعاينة
        qual = calc_quality(processed)
        self.lbl_blur.setText(f"{qual:.1f}")
        if qual > 150:
            col, txt = "#16a34a", "✅ ممتازة"
        elif qual > 80:
            col, txt = "#d97706", "⚠️ مقبولة"
        else:
            col, txt = "#dc2626", "❌ ضبابية"
        self.lbl_quality.setText(txt)
        self.lbl_quality.setStyleSheet(f"font-weight:bold;padding:6px;border-radius:4px;background:{col}22;color:{col};border:1px solid {col};")

    # ==================================================================
    # عمليات التكبير/التصغير
    # ==================================================================

    def zoom_in(self):
        self.zoom_factor = min(self.max_zoom, self.zoom_factor * 1.2)
        self.lbl_zoom.setText(f"{int(self.zoom_factor*100)}%")
        self._update_preview()

    def zoom_out(self):
        self.zoom_factor = max(self.min_zoom, self.zoom_factor / 1.2)
        self.lbl_zoom.setText(f"{int(self.zoom_factor*100)}%")
        self._update_preview()

    def zoom_fit(self):
        if self.current_img is None:
            return
        h, w = self.current_img.shape[:2]
        vp = self.preview_scroll.viewport().size()
        self.zoom_factor = max(self.min_zoom, min(self.max_zoom, min(vp.width()/w, vp.height()/h)))
        self.lbl_zoom.setText(f"{int(self.zoom_factor*100)}%")
        self._update_preview()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ==================================================================
    # عمليات التدوير
    # ==================================================================

    def rotate_left(self):
        self._push_undo()
        self.params['rotation'] = (self.params.get('rotation', 0) - 90) % 360
        self.lbl_rotation.setText(f"{self.params['rotation']}°")
        self._update_preview()

    def rotate_right(self):
        self._push_undo()
        self.params['rotation'] = (self.params.get('rotation', 0) + 90) % 360
        self.lbl_rotation.setText(f"{self.params['rotation']}°")
        self._update_preview()

    # ==================================================================
    # قص ذكي
    # ==================================================================

    def _do_smart_crop(self):
        """تنفيذ القص الذكي باستخدام الخوارزمية الهجينة"""
        if self.current_img is None:
            return
        self._push_undo()
        crop = smart_auto_crop(self.current_img, padding=15, dark_threshold=30, use_advanced=True)
        self.params['crop'] = crop
        self.lbl_crop_val.setText(f"{crop[0]}px")
        for sp, val in [(self.sp_crop_l, crop[0]), (self.sp_crop_t, crop[1]),
                        (self.sp_crop_r, crop[2]), (self.sp_crop_b, crop[3])]:
            sp.blockSignals(True)
            sp.setValue(val)
            sp.blockSignals(False)
        self._update_preview()
        self._log(f"✂️ قص ذكي: L={crop[0]} T={crop[1]} R={crop[2]} B={crop[3]}")

    # ==================================================================
    # حفظ وتخطي
    # ==================================================================

    def _save_current(self):
        """حفظ الصورة الحالية مع جميع التصحيحات"""
        if self.current_img is None:
            return

        self._push_undo()
        processed = apply_processing(self.current_img, self.params)
        q_after = calc_quality(processed)

        # حفظ النسخة المعدلة
        out_dir = Path("processed")
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"doc_{self.current_idx+1:04d}.png"
        cv2.imwrite(str(out_path), processed)

        # نقل النسخة الأصلية إلى raw_scanned_files
        orig_path = self.images[self.current_idx]
        raw_dir = Path.home() / "Documents" / "raw_scanned_files"
        raw_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(orig_path), str(raw_dir / orig_path.name))
        except Exception as e:
            self._log(f"⚠️ لم يتم نقل الأصل: {e}")

        # حفظ في قاعدة التعلم
        self.learner.add_action(self.current_img, 'save', self.params.copy(), q_after)

        self.stats["processed"] += 1
        self._record_csv("processed", out_path)
        self._log(f"✅ حفظ: {out_path.name} | وضوح: {q_after:.0f}")
        self.btn_apply_all.setEnabled(True)
        self._update_stats()
        self._navigate(1)

    def _skip_current(self):
        """تخطي الصورة الحالية"""
        if self.current_img is None:
            return

        out_dir = Path("skipped")
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / f"skip_{self.current_idx+1:04d}.png"
        cv2.imwrite(str(out_path), self.current_img)

        self.stats["skipped"] += 1
        self._record_csv("skipped", out_path)
        self._log(f"⏭️ تخطي: {out_path.name}")
        self._update_stats()
        self._navigate(1)

    def _apply_batch(self):
        """معالجة جميع الصور المتبقية دفعة واحدة"""
        if self.current_img is None:
            return

        reply = QMessageBox.question(
            self, "تأكيد",
            f"معالجة {len(self.images)-self.current_idx} صورة متبقية؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self.worker = ProcessingWorker(
            self.images[self.current_idx:],
            self.params,
            self.learner
        )
        self.worker.progress.connect(self._on_batch_progress)
        self.worker.finished.connect(self._on_batch_finished)
        self.worker.start()
        self.btn_apply_all.setEnabled(False)

    def _on_batch_progress(self, cur, total):
        self.progress.setValue(self.current_idx + cur)
        self.lbl_status.setText(f"⏳ معالجة {cur}/{total}...")

    def _on_batch_finished(self):
        self.stats["processed"] += len(self.images) - self.current_idx
        self.current_idx = len(self.images)
        self._update_stats()
        self.btn_apply_all.setEnabled(True)
        self.lbl_status.setText("✅ اكتملت المعالجة")
        QMessageBox.information(self, "اكتمل", "تمت معالجة جميع الصور المتبقية")

    def _navigate(self, step):
        """الانتقال بين الصور"""
        new = self.current_idx + step
        if 0 <= new < len(self.images):
            self.current_idx = new
            self._load_current()
        elif new >= len(self.images):
            QMessageBox.information(
                self, "اكتمل",
                f"✅ انتهى القائمة!\nمعالجة: {self.stats['processed']} | تخطي: {self.stats['skipped']}"
            )

    # ==================================================================
    # مقارنة جانبية
    # ==================================================================

    def _show_compare(self):
        """عرض مقارنة قبل/بعد"""
        if self.current_img is None:
            return

        proc = apply_processing(self.current_img, self.params)

        def to_pix(img, maxs=600):
            h, w = img.shape[:2]
            s = min(maxs/w, maxs/h)
            small = cv2.resize(img, (int(w*s), int(h*s)))
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, small.shape[1], small.shape[0], small.shape[1]*3, QImage.Format_RGB888)
            return QPixmap.fromImage(qimg)

        dlg = QDialog(self)
        dlg.setWindowTitle("🔍 قبل / بعد")
        dlg.resize(1000, 500)
        lay = QHBoxLayout(dlg)

        for title, px in [("الأصلية", to_pix(self.current_img)), ("بعد المعالجة", to_pix(proc))]:
            box = QGroupBox(title)
            bl = QVBoxLayout()
            lbl = QLabel()
            lbl.setPixmap(px)
            bl.addWidget(lbl)
            box.setLayout(bl)
            lay.addWidget(box)

        btn = QPushButton("إغلاق")
        btn.clicked.connect(dlg.accept)
        lay.addWidget(btn)
        dlg.exec_()

    # ==================================================================
    # السجل والإحصائيات
    # ==================================================================

    def _update_stats(self):
        self.lbl_total.setText(str(self.stats["total"]))
        self.lbl_processed.setText(str(self.stats["processed"]))
        self.lbl_skipped.setText(str(self.stats["skipped"]))
        self.lbl_learned.setText(str(len(self.learner.database)))

    def _tick_clock(self):
        if self.stats["start_time"]:
            elapsed = datetime.now() - self.stats["start_time"]
            self.lbl_time.setText(str(elapsed).split('.')[0])

    def _log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.txt_log.append(line)
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _record_csv(self, action, dest):
        self.processing_records.append({
            "name": self.image_names[self.current_idx],
            "output": str(dest),
            "action": action,
            "crop": str(self.params.get('crop')),
            "deskew": round(self.params.get('deskew_angle', 0), 2),
            "flip_h": self.params.get('flip_h', False),
            "sharpen": self.params.get('sharpen', False),
            "rotation": self.params.get('rotation', 0),
            "timestamp": datetime.now().isoformat(timespec="seconds")
        })

    def _export_csv(self):
        if not self.processing_records:
            return
        path, _ = QFileDialog.getSaveFileName(self, "حفظ CSV", "report.csv", "CSV (*.csv)")
        if path:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=self.processing_records[0].keys())
                w.writeheader()
                w.writerows(self.processing_records)
            self._log(f"📤 تم تصدير {len(self.processing_records)} سجل")

    def _export_learn(self):
        path, _ = QFileDialog.getSaveFileName(self, "تصدير قاعدة التعلم", "learning_db.json", "JSON (*.json)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.learner.database, f, ensure_ascii=False, indent=2)
            self._log(f"💾 تصدير {len(self.learner.database)} سجل تعلم")

    def _import_learn(self):
        path, _ = QFileDialog.getOpenFileName(self, "استيراد قاعدة التعلم", "", "JSON (*.json)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.learner.database = json.load(f)
                self.learner.save()
                self._log(f"📥 تم استيراد {len(self.learner.database)} سجل")
                self._update_stats()
            except Exception as e:
                QMessageBox.critical(self, "خطأ", str(e))

    # ==================================================================
    # الأحداث الخاصة
    # ==================================================================

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self._load_paths([u.toLocalFile() for u in e.mimeData().urls()])

    def closeEvent(self, e):
        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.stop()
            self._thumb_worker.wait()
        self.learner.save()
        e.accept()


# ==================================================================
# 5. نقطة الدخول
# ==================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MedicalDocAppV10()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
