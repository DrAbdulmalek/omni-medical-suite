#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
معالج الوثائق الطبية - الإصدار النهائي الموحد v16-Final
يجمع أفضل الميزات من v13 إلى v16 مع إصلاحات خوارزميات القص والميلان.
"""

import sys
import os
import json
import time
import tempfile
import shutil
import numpy as np
import cv2
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QFileDialog, QMessageBox, QProgressBar,
    QGroupBox, QCheckBox, QSpinBox, QTextEdit, QListWidget, QSplitter,
    QShortcut, QListWidgetItem, QGridLayout, QFrame, QComboBox, QToolTip
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QImage, QKeySequence, QFont, QIcon, QColor

# ============================================================================
# 1. Core Algorithms (محسّنة بالكامل)
# ============================================================================

def find_page_bounds(img: np.ndarray, page_threshold: int = 200, min_page_fraction: float = 0.25) -> tuple:
    """
    كشف حدود الصفحة باستخدام Median فقط (بدون منطق Mean الهجين).
    يعتمد على أكبر كتلة متصلة - مثبت ومقاوم للنصوص الكثيفة.
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
        if len(starts) == 0 or len(ends) == 0:
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

    if right <= left:
        return (left, 0, w - left - 1, 0)

    page_region = gray[:, left:right+1]
    row_med = np.median(page_region, axis=1)
    row_s, row_e = _find_bounds(row_med, min_page_fraction)
    top = max(0, row_s - MARGIN)
    bottom = min(h - 1, row_e + MARGIN)

    return (left, top, w - right - 1, h - bottom - 1)


def auto_detect_skew(img: np.ndarray, max_angle: float = 5.0, step: float = 0.25) -> float:
    """
    كشف الميلان باستخدام إسقاط الصفوف (projection profile) مع التحقق من صحة الزاوية.
    أسرع وأكثر موثوقية من minAreaRect للصفحات المستقيمة.
    """
    # إزالة الهوامش أولاً
    l, t, r, b = find_page_bounds(img)
    h, w = img.shape[:2]
    x1, x2 = l, w - r if r > 0 else w
    y1, y2 = t, h - b if b > 0 else h
    if x2 <= x1 or y2 <= y1:
        page = img
    else:
        page = img[y1:y2, x1:x2]

    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY) if page.ndim == 3 else page
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    ph, pw = binary.shape
    best_score, best_angle = -1.0, 0.0

    for angle in np.arange(-max_angle, max_angle + step, step):
        M = cv2.getRotationMatrix2D((pw / 2, ph / 2), angle, 1.0)
        rotated = cv2.warpAffine(binary, M, (pw, ph),
                                 flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        profile = np.sum(rotated, axis=1)
        variance = np.var(profile)
        non_empty = np.sum(profile > 0)
        score = variance * (1 + non_empty / ph)
        if score > best_score:
            best_score, best_angle = score, angle

    # تحقق: ألا تكون الزاوية خاطئة (فارق أداء أقل من 5% مع 0°)
    M0 = cv2.getRotationMatrix2D((pw / 2, ph / 2), 0.0, 1.0)
    rot0 = cv2.warpAffine(binary, M0, (pw, ph),
                          flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    profile0 = np.sum(rot0, axis=1)
    score0 = np.var(profile0) * (1 + np.sum(profile0 > 0) / ph)

    if best_score < score0 * 1.05 or abs(best_angle) < 0.3:
        return 0.0
    return best_angle


def smart_auto_crop(img: np.ndarray, padding: int = 15, dark_threshold: int = 200) -> tuple:
    """
    قص ذكي من مرحلتين:
    1. إزالة الخلفية الرمادية عبر find_page_bounds.
    2. قص محكم حول المحتوى الفعلي (نصوص/جداول).
    """
    h, w = img.shape[:2]
    left, top, right, bottom = find_page_bounds(img)
    x1, x2 = left, w - right if right > 0 else w
    y1, y2 = top, h - bottom if bottom > 0 else h

    if x2 <= x1 or y2 <= y1:
        return (left, top, right, bottom)

    page = img[y1:y2, x1:x2].copy()
    gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY) if page.ndim == 3 else page
    _, binary = cv2.threshold(gray, dark_threshold, 255, cv2.THRESH_BINARY_INV)

    col_has = np.any(binary > 0, axis=0)
    row_has = np.any(binary > 0, axis=1)

    if not np.any(col_has) or not np.any(row_has):
        return (left, top, right, bottom)

    content_cols = np.where(col_has)[0]
    content_rows = np.where(row_has)[0]

    cl = max(0, content_cols[0] - padding)
    cr = min(page.shape[1] - 1, content_cols[-1] + padding)
    ct = max(0, content_rows[0] - padding)
    cb = min(page.shape[0] - 1, content_rows[-1] + padding)

    final_left = left + cl
    final_top = top + ct
    final_right = right + (page.shape[1] - cr - 1)
    final_bottom = bottom + (page.shape[0] - cb - 1)

    return (final_left, final_top, final_right, final_bottom)


def apply_processing(img: np.ndarray, rotation: int, crop: tuple,
                     deskew_angle: float, flip_h: bool, sharpen: bool,
                     remove_shadow: bool, gray_threshold: int) -> np.ndarray:
    """تطبيق جميع العمليات على الصورة."""
    result = img.copy()
    h, w = result.shape[:2]

    # 1. تدوير يدوي
    if rotation != 0:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), rotation, 1.0)
        result = cv2.warpAffine(result, M, (w, h))

    # 2. قص
    left, top, right, bottom = crop
    x1, x2 = left, w - right if right > 0 else w
    y1, y2 = top, h - bottom if bottom > 0 else h
    if x2 > x1 and y2 > y1:
        result = result[y1:y2, x1:x2]

    # 3. تصحيح ميلان أوتوماتيكي
    if deskew_angle != 0.0:
        h2, w2 = result.shape[:2]
        M = cv2.getRotationMatrix2D((w2 / 2, h2 / 2), deskew_angle, 1.0)
        result = cv2.warpAffine(result, M, (w2, h2))

    # 4. قلب أفقي
    if flip_h:
        result = cv2.flip(result, 1)

    # 5. إزالة الظلال باستخدام CLAHE
    if remove_shadow:
        gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray_eq = clahe.apply(gray)
        result = cv2.cvtColor(gray_eq, cv2.COLOR_GRAY2BGR)

    # 6. شحذ (Unsharp Mask)
    if sharpen:
        blurred = cv2.GaussianBlur(result, (0, 0), 3.0)
        result = cv2.addWeighted(result, 1.5, blurred, -0.5, 0)

    # 7. عتبة الرمادي (تفتيح الخلفية)
    gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, gray_threshold, 255, cv2.THRESH_BINARY)
    result = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    return result


def calc_blur(img: np.ndarray) -> float:
    """حساب درجة ضبابية الصورة باستخدام Laplacian variance."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    return float(laplacian.var())


def extract_page_number(img: np.ndarray, region: tuple = None) -> int:
    """استخراج رقم الصفحة من منطقة محددة (أو من الركن السفلي) باستخدام OCR."""
    h, w = img.shape[:2]
    if region:
        x, y, rw, rh = region
        roi = img[y:y+rh, x:x+rw]
    else:
        # المنطقة السفلية اليمنى افتراضياً
        roi = img[int(h*0.85):h, int(w*0.7):w]

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    text = pytesseract.image_to_string(thresh, config='--psm 8 -c tessedit_char_whitelist=0123456789')
    digits = ''.join(filter(str.isdigit, text))
    return int(digits) if digits else 0


def assess_image_quality(img: np.ndarray) -> dict:
    """تقييم جودة الصورة: وضوح، تباين، سطوع."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = calc_blur(img)
    brightness = np.mean(gray)
    contrast = np.std(gray)
    return {"blur": blur, "brightness": brightness, "contrast": contrast}


def quality_label(score: dict) -> str:
    """تصنيف الجودة بناءً على درجة الوضوح."""
    blur = score["blur"]
    if blur > 500:
        return "ممتازة"
    elif blur > 200:
        return "جيدة"
    elif blur > 80:
        return "متوسطة"
    else:
        return "ضبابية"


# ============================================================================
# 2. نظام التعلّم التكيفي (KNN)
# ============================================================================

class TrainingDataCollector:
    """جمع بيانات التدريب من معالجة المستخدم."""
    def __init__(self, data_file="medical_doc_training.jsonl"):
        self.data_file = data_file

    def add_sample(self, img_hash: str, params: dict, quality: dict):
        sample = {
            "timestamp": time.time(),
            "img_hash": img_hash,
            "params": params,
            "quality": quality
        }
        with open(self.data_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    def get_similar_params(self, img_hash: str, quality_score: float) -> dict:
        """إرجاع أفضل المعلمات من العينات السابقة المشابهة."""
        if not os.path.exists(self.data_file):
            return None
        best_match = None
        best_dist = float('inf')
        with open(self.data_file, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    sample = json.loads(line.strip())
                    if sample["img_hash"] == img_hash:
                        dist = abs(sample["quality"]["blur"] - quality_score)
                        if dist < best_dist:
                            best_dist = dist
                            best_match = sample["params"]
                except:
                    continue
        return best_match


class AdaptiveLearner:
    """تطبيق الإعدادات المقترحة وتعديلها ذاتياً."""
    def __init__(self):
        self.collector = TrainingDataCollector()

    def suggest_settings(self, img: np.ndarray, img_hash: str) -> dict:
        quality = assess_image_quality(img)
        similar = self.collector.get_similar_params(img_hash, quality["blur"])
        if similar:
            return similar
        # إعدادات افتراضية ذكية
        blur_val = quality["blur"]
        if blur_val < 100:
            return {"sharpen": True, "remove_shadow": True, "gray_threshold": 180}
        elif blur_val < 300:
            return {"sharpen": False, "remove_shadow": True, "gray_threshold": 200}
        else:
            return {"sharpen": False, "remove_shadow": False, "gray_threshold": 220}

    def record_feedback(self, img_hash: str, params: dict, quality: dict):
        self.collector.add_sample(img_hash, params, quality)


# ============================================================================
# 3. فئة الصورة البطيئة التحميل (LazyImage)
# ============================================================================

class LazyImage:
    """تحميل الصورة من القرص فقط عند الحاجة (توفير الذاكرة)."""
    def __init__(self, path: str):
        self.path = path
        self._arr = None

    @property
    def array(self):
        if self._arr is None:
            self._arr = cv2.imread(self.path)
        return self._arr

    @array.setter
    def array(self, val):
        self._arr = val

    def release(self):
        self._arr = None


# ============================================================================
# 4. النافذة الرئيسية لتطبيق PyQt5
# ============================================================================

class MedicalDocApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("معالج الوثائق الطبية - الإصدار الموحد v16-Final")
        self.setMinimumSize(1200, 800)
        self.setAcceptDrops(True)

        # متغيرات الحالة
        self.image_list = []          # قائمة LazyImage
        self.current_idx = -1
        self.undo_stack = []          # تاريخ الصور
        self.redo_stack = []
        self.processing = False
        self.page_number_region = None   # (x, y, w, h)
        self.gray_threshold = 200
        self.page_threshold = 200
        self.auto_save_enabled = False
        self.output_dir = ""
        self.adaptive_learner = AdaptiveLearner()

        # إعدادات المعالجة الحالية
        self.current_rotation = 0
        self.current_crop = (0, 0, 0, 0)
        self.current_deskew = 0.0
        self.current_flip_h = False
        self.current_sharpen = False
        self.current_remove_shadow = True

        # واجهة المستخدم
        self._init_ui()
        self._setup_shortcuts()
        self._log("تم تشغيل التطبيق. اسحب وأفلت الصور أو استخدم فتح ملف.")

    def _init_ui(self):
        # القسم الأيمن: أدوات وإعدادات
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # أزرار رئيسية
        btn_open = QPushButton("📂 فتح ملفات/مجلد")
        btn_open.clicked.connect(self.load_files)
        btn_open.setObjectName("primaryBtn")
        right_layout.addWidget(btn_open)

        self.btn_next = QPushButton("▶ التالي")
        self.btn_prev = QPushButton("◀ السابق")
        self.btn_next.clicked.connect(lambda: self._navigate(1))
        self.btn_prev.clicked.connect(lambda: self._navigate(-1))
        nav_layout = QHBoxLayout()
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.btn_next)
        right_layout.addLayout(nav_layout)

        # مجموعة المعالجة
        proc_group = QGroupBox("معالجة الصورة")
        proc_layout = QVBoxLayout(proc_group)

        self.btn_auto_crop = QPushButton("✂️ قص ذكي")
        self.btn_auto_crop.clicked.connect(self._smart_crop)
        proc_layout.addWidget(self.btn_auto_crop)

        self.btn_deskew = QPushButton("🔄 كشف الميلان وتصحيحه")
        self.btn_deskew.clicked.connect(self._start_skew)
        proc_layout.addWidget(self.btn_deskew)

        self.chk_flip_h = QCheckBox("🪞 قلب أفقي")
        self.chk_flip_h.toggled.connect(lambda v: self._apply_and_refresh(flip_h=v))
        proc_layout.addWidget(self.chk_flip_h)

        self.chk_sharpen = QCheckBox("🔪 شحذ (Sharpen)")
        self.chk_sharpen.toggled.connect(lambda v: self._apply_and_refresh(sharpen=v))
        proc_layout.addWidget(self.chk_sharpen)

        self.chk_remove_shadow = QCheckBox("☀️ إزالة الظلال (CLAHE)")
        self.chk_remove_shadow.setChecked(True)
        self.chk_remove_shadow.toggled.connect(lambda v: self._apply_and_refresh(remove_shadow=v))
        proc_layout.addWidget(self.chk_remove_shadow)

        # شريط عتبة الرمادي
        gray_layout = QHBoxLayout()
        gray_layout.addWidget(QLabel("عتبة الرمادي:"))
        self.slider_gray = QSlider(Qt.Horizontal)
        self.slider_gray.setRange(150, 250)
        self.slider_gray.setValue(200)
        self.slider_gray.valueChanged.connect(self._on_gray_thr_change)
        self.lbl_gray_val = QLabel("200")
        gray_layout.addWidget(self.slider_gray)
        gray_layout.addWidget(self.lbl_gray_val)
        proc_layout.addLayout(gray_layout)

        # شريط عتبة الصفحة
        page_layout = QHBoxLayout()
        page_layout.addWidget(QLabel("عتبة الصفحة:"))
        self.slider_page = QSlider(Qt.Horizontal)
        self.slider_page.setRange(150, 250)
        self.slider_page.setValue(200)
        self.slider_page.valueChanged.connect(self._on_page_thr_change)
        self.lbl_page_val = QLabel("200")
        page_layout.addWidget(self.slider_page)
        page_layout.addWidget(self.lbl_page_val)
        proc_layout.addLayout(page_layout)

        # زر حفظ
        self.btn_save = QPushButton("💾 حفظ الصورة الحالية")
        self.btn_save.clicked.connect(self._save_current)
        proc_layout.addWidget(self.btn_save)

        # زر معالجة دفعة
        self.btn_batch = QPushButton("⚙️ معالجة دفعة وحفظ الكل")
        self.btn_batch.clicked.connect(self._start_batch)
        proc_layout.addWidget(self.btn_batch)

        self.chk_auto_save = QCheckBox("💾 حفظ تلقائي بعد المعالجة")
        self.chk_auto_save.toggled.connect(lambda v: setattr(self, 'auto_save_enabled', v))
        proc_layout.addWidget(self.chk_auto_save)

        right_layout.addWidget(proc_group)

        # مجموعة تحليل وOCR
        ocr_group = QGroupBox("تحليل ذكي")
        ocr_layout = QVBoxLayout(ocr_group)
        self.btn_select_region = QPushButton("📍 تحديد منطقة رقم الصفحة")
        self.btn_select_region.clicked.connect(self._select_page_number_region)
        ocr_layout.addWidget(self.btn_select_region)
        self.btn_analyze = QPushButton("🧠 تحليل وتنظيم الصفحات")
        self.btn_analyze.clicked.connect(self.analyze_and_organize_pages)
        ocr_layout.addWidget(self.btn_analyze)
        right_layout.addWidget(ocr_group)

        # سجل العمليات
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(200)
        right_layout.addWidget(QLabel("سجل العمليات:"))
        right_layout.addWidget(self.log_area)

        # شريط تقدم المعالجة الدفعية
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        right_layout.addWidget(self.progress_bar)

        # قائمة المصغرات
        self.thumb_list = QListWidget()
        self.thumb_list.setIconSize(QSize(80, 100))
        self.thumb_list.currentRowChanged.connect(self._on_thumb_selected)

        # تخطيط رئيسي
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.thumb_list)
        splitter.addWidget(right_panel)
        self.setCentralWidget(splitter)

        # حاوية عرض الصورة (سنضيفها لاحقاً)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("background-color: #2d2d2d;")
        splitter.insertWidget(0, self.image_label)
        splitter.setSizes([600, 300, 200])

        # تطبيق ستايل
        self.setStyleSheet("""
            QPushButton#primaryBtn { background-color: #2563eb; color: white; font-weight: bold; padding: 8px; border-radius: 6px; }
            QPushButton#primaryBtn:hover { background-color: #1d4ed8; }
            QPushButton { padding: 6px; background-color: #e2e8f0; border-radius: 4px; }
            QPushButton:hover { background-color: #cbd5e1; }
            QGroupBox { font-weight: bold; margin-top: 10px; }
            QSlider::groove:horizontal { height: 6px; background: #cbd5e1; border-radius: 3px; }
            QSlider::handle:horizontal { background: #2563eb; width: 16px; border-radius: 8px; }
        """)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo)
        QShortcut(QKeySequence("Ctrl+Y"), self, self._redo)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_current)
        QShortcut(QKeySequence("Right"), self, lambda: self._navigate(1))
        QShortcut(QKeySequence("Left"), self, lambda: self._navigate(-1))
        QShortcut(QKeySequence("Ctrl+D"), self, self._start_skew)
        QShortcut(QKeySequence("Ctrl+G"), self, self._smart_crop)
        QShortcut(QKeySequence("F11"), self, self.toggle_fullscreen)

    # ---------- الإجراءات الأساسية ----------
    def load_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "اختر صوراً أو PDF", "",
                                                "Images (*.png *.jpg *.jpeg *.bmp *.tiff);;PDF (*.pdf)")
        if not paths:
            return
        self._clear_all()
        for p in paths:
            if p.lower().endswith('.pdf'):
                self._load_pdf(p)
            else:
                self.image_list.append(LazyImage(p))
        self._refresh_thumbnail_list()
        if self.image_list:
            self.current_idx = 0
            self._update_preview()
        self._log(f"تم تحميل {len(self.image_list)} صفحة.")

    def _load_pdf(self, pdf_path):
        try:
            images = convert_from_path(pdf_path)
            for i, img in enumerate(images):
                temp_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                img.save(temp_path, "PNG")
                self.image_list.append(LazyImage(temp_path))
            self._log(f"PDF: تم تحويل {len(images)} صفحة.")
        except Exception as e:
            self._log(f"خطأ في قراءة PDF: {e}")

    def _clear_all(self):
        for lazy in self.image_list:
            lazy.release()
        self.image_list.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.current_idx = -1
        self.thumb_list.clear()

    def _refresh_thumbnail_list(self):
        self.thumb_list.clear()
        for i, lazy in enumerate(self.image_list):
            img = lazy.array
            if img is None:
                continue
            h, w = img.shape[:2]
            pixmap = self._cv2_to_pixmap(cv2.resize(img, (80, 100)))
            item = QListWidgetItem()
            item.setIcon(QIcon(pixmap))
            item.setText(f"صفحة {i+1}")
            item.setData(Qt.UserRole, i)
            self.thumb_list.addItem(item)

    def _on_thumb_selected(self, row):
        if row >= 0 and row < len(self.image_list):
            self.current_idx = row
            self._update_preview()

    def _navigate(self, delta):
        if not self.image_list:
            return
        new_idx = self.current_idx + delta
        if 0 <= new_idx < len(self.image_list):
            self.current_idx = new_idx
            self._update_preview()
            self.thumb_list.setCurrentRow(new_idx)

    def _push_undo(self):
        if self.current_idx >= 0:
            current_img = self.image_list[self.current_idx].array
            if current_img is not None:
                self.undo_stack.append(current_img.copy())
                self.redo_stack.clear()

    def _undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.image_list[self.current_idx].array.copy())
            self.image_list[self.current_idx].array = self.undo_stack.pop()
            self._update_preview()
            self._log("تم التراجع")

    def _redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.image_list[self.current_idx].array.copy())
            self.image_list[self.current_idx].array = self.redo_stack.pop()
            self._update_preview()
            self._log("تمت الإعادة")

    def _update_preview(self):
        if self.current_idx < 0 or self.current_idx >= len(self.image_list):
            return
        img = self.image_list[self.current_idx].array
        if img is None:
            return

        # تطبيق جميع الإعدادات الحالية
        processed = apply_processing(
            img, self.current_rotation, self.current_crop, self.current_deskew,
            self.current_flip_h, self.current_sharpen, self.current_remove_shadow,
            self.gray_threshold
        )
        pixmap = self._cv2_to_pixmap(processed)
        self.image_label.setPixmap(pixmap.scaled(self.image_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # عرض جودة الصورة
        quality = assess_image_quality(processed)
        blur = quality["blur"]
        label = quality_label(quality)
        self._log(f"🔍 جودة الصورة: {label} (الوضوح: {blur:.1f})", to_log_area=False)
        self.statusBar().showMessage(f"جودة: {label} | وضوح: {blur:.0f}")

    def _apply_and_refresh(self, **kwargs):
        self._push_undo()
        if "rotation" in kwargs:
            self.current_rotation = kwargs["rotation"]
        if "crop" in kwargs:
            self.current_crop = kwargs["crop"]
        if "deskew" in kwargs:
            self.current_deskew = kwargs["deskew"]
        if "flip_h" in kwargs:
            self.current_flip_h = kwargs["flip_h"]
        if "sharpen" in kwargs:
            self.current_sharpen = kwargs["sharpen"]
        if "remove_shadow" in kwargs:
            self.current_remove_shadow = kwargs["remove_shadow"]
        self._update_preview()
        if self.auto_save_enabled and self.current_idx >= 0:
            self._save_current()

    def _smart_crop(self):
        if self.current_idx < 0:
            return
        self._push_undo()
        img = self.image_list[self.current_idx].array
        self.current_crop = smart_auto_crop(img, padding=15, dark_threshold=self.gray_threshold)
        self._apply_and_refresh(crop=self.current_crop)
        self._log(f"✂️ قص ذكي: L={self.current_crop[0]} T={self.current_crop[1]} R={self.current_crop[2]} B={self.current_crop[3]}")

    def _start_skew(self):
        if self.current_idx < 0:
            return
        self._push_undo()
        img = self.image_list[self.current_idx].array
        angle = auto_detect_skew(img)
        if abs(angle) > 0.3:
            self.current_deskew = angle
            self._apply_and_refresh(deskew=angle)
            self._log(f"🔄 تم تصحيح الميلان: {angle:.2f}°")
        else:
            self._log("✅ الصفحة مستقيمة، لم يتم تطبيق تصحيح.")

    def _save_current(self):
        if self.current_idx < 0:
            return
        if not self.output_dir:
            self.output_dir = QFileDialog.getExistingDirectory(self, "اختر مجلد لحفظ الصور")
            if not self.output_dir:
                return
        img = self.image_list[self.current_idx].array
        processed = apply_processing(
            img, self.current_rotation, self.current_crop, self.current_deskew,
            self.current_flip_h, self.current_sharpen, self.current_remove_shadow,
            self.gray_threshold
        )
        # محاولة استخراج رقم الصفحة
        page_num = 0
        if self.page_number_region:
            page_num = extract_page_number(processed, self.page_number_region)
        if page_num:
            filename = f"page_{page_num:04d}.png"
        else:
            filename = f"image_{self.current_idx+1:04d}.png"
        full_path = os.path.join(self.output_dir, filename)
        cv2.imwrite(full_path, processed)
        self._log(f"💾 حفظت الصورة كـ {filename}")

    # ---------- المعالجة الدفعية غير الحاجبة ----------
    def _start_batch(self):
        if not self.image_list:
            self._log("لا توجد صور للمعالجة.")
            return
        if not self.output_dir:
            self.output_dir = QFileDialog.getExistingDirectory(self, "اختر مجلد حفظ النتائج")
            if not self.output_dir:
                return
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self.image_list))
        self.progress_bar.setValue(0)
        self._set_controls_enabled(False)
        self._batch_total = len(self.image_list)
        self._batch_completed = 0
        self._batch_failed = 0
        self._log(f"🚀 بدء معالجة دفعة لـ {self._batch_total} صورة ...")
        QTimer.singleShot(100, self._process_next_batch)

    def _process_next_batch(self):
        if self._batch_completed >= self._batch_total:
            self.progress_bar.setVisible(False)
            self._set_controls_enabled(True)
            self._log(f"🏁 انتهت المعالجة. نجحت: {self._batch_total - self._batch_failed}, فشلت: {self._batch_failed}")
            QMessageBox.information(self, "اكتملت المعالجة", f"تمت معالجة {self._batch_total} صورة.\nنجاح: {self._batch_total - self._batch_failed}\nفشل: {self._batch_failed}")
            return
        idx = self._batch_completed
        lazy = self.image_list[idx]
        img = lazy.array
        if img is None:
            self._batch_failed += 1
            self._batch_completed += 1
            self.progress_bar.setValue(self._batch_completed)
            QTimer.singleShot(10, self._process_next_batch)
            return
        try:
            # استخدام الإعدادات الحالية أو الاقتراح التكيفي
            params = self.adaptive_learner.suggest_settings(img, os.path.basename(lazy.path))
            processed = apply_processing(
                img, self.current_rotation, self.current_crop, self.current_deskew,
                self.current_flip_h, params.get("sharpen", False),
                params.get("remove_shadow", True), params.get("gray_threshold", self.gray_threshold)
            )
            page_num = extract_page_number(processed, self.page_number_region) if self.page_number_region else 0
            if page_num:
                filename = f"page_{page_num:04d}.png"
            else:
                filename = f"batch_{idx+1:04d}.png"
            cv2.imwrite(os.path.join(self.output_dir, filename), processed)
            self._log(f"✅ تمت معالجة {filename}")
        except Exception as e:
            self._batch_failed += 1
            self._log(f"❌ فشلت معالجة الصورة {idx+1}: {e}")
        self._batch_completed += 1
        self.progress_bar.setValue(self._batch_completed)
        QTimer.singleShot(10, self._process_next_batch)

    def _set_controls_enabled(self, enabled):
        for btn in [self.btn_auto_crop, self.btn_deskew, self.btn_save, self.btn_batch,
                    self.btn_next, self.btn_prev]:
            btn.setEnabled(enabled)

    # ---------- التحليل الذكي ----------
    def _select_page_number_region(self):
        if self.current_idx < 0:
            QMessageBox.warning(self, "تنبيه", "افتح صورة أولاً.")
            return
        QMessageBox.information(self, "تحديد المنطقة", "اسحب بالماوس لتحديد مستطيل حول رقم الصفحة.\nسيتم استخدامه لاستخراج الأرقام تلقائياً.")
        # سنقوم بتطبيق بسيط: فتح نافذة تفاعلية (يمكن توسيعه)
        self.page_number_region = (int(self.image_label.width()*0.7), int(self.image_label.height()*0.85),
                                   150, 60)
        self._log("تم تحديد المنطقة التجريبية. يمكنك تعديلها يدوياً لاحقاً.")

    def analyze_and_organize_pages(self):
        if not self.image_list:
            return
        self._log("بدء التحليل الذكي وإعادة تسمية الصفحات...")
        page_numbers = []
        for i, lazy in enumerate(self.image_list):
            img = apply_processing(lazy.array, 0, self.current_crop, 0, False, False, True, self.gray_threshold)
            num = extract_page_number(img, self.page_number_region)
            page_numbers.append(num)
            self._log(f"الصفحة {i+1} → رقم {num if num else 'غير معروف'}")
        # إعادة ترتيب الصور حسب رقم الصفحة
        if any(page_numbers):
            indexed = [(num, i, self.image_list[i]) for i, num in enumerate(page_numbers) if num > 0]
            indexed.sort(key=lambda x: x[0])
            new_list = [lazy for _, _, lazy in indexed]
            # إضافة الصفحات التي لم تُعرف في النهاية
            for i, lazy in enumerate(self.image_list):
                if i not in [idx for _, idx, _ in indexed]:
                    new_list.append(lazy)
            self.image_list = new_list
            self._refresh_thumbnail_list()
            self.current_idx = 0
            self._update_preview()
            self._log("تم إعادة ترتيب الصفحات حسب الأرقام المستخرجة.")

    # ---------- أدوات مساعدة ----------
    def _cv2_to_pixmap(self, img):
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        h, w, ch = img.shape
        bytes_per_line = ch * w
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        return QPixmap.fromImage(qimg)

    def _log(self, msg, to_log_area=True):
        if to_log_area:
            self.log_area.append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        print(msg)

    def _on_gray_thr_change(self, val):
        self.gray_threshold = val
        self.lbl_gray_val.setText(str(val))
        self._apply_and_refresh()

    def _on_page_thr_change(self, val):
        self.page_threshold = val
        self.lbl_page_val.setText(str(val))
        # إعادة حساب الحدود (يمكن تحديث crop)
        if self.current_idx >= 0:
            img = self.image_list[self.current_idx].array
            self.current_crop = find_page_bounds(img, page_threshold=self.page_threshold)
            self._apply_and_refresh(crop=self.current_crop)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.toLocalFile()]
        self._clear_all()
        for p in paths:
            if p.lower().endswith('.pdf'):
                self._load_pdf(p)
            elif p.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.tiff')):
                self.image_list.append(LazyImage(p))
        self._refresh_thumbnail_list()
        if self.image_list:
            self.current_idx = 0
            self._update_preview()
        self._log(f"تم إسقاط {len(self.image_list)} ملف.")

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()


# ============================================================================
# 5. تشغيل التطبيق
# ============================================================================
def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    window = MedicalDocApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
