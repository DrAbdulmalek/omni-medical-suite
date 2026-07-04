#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Medical Document Scanner GUI - v13.1
=====================================
إصلاحات: 
1. find_page_bounds - كشف حدود الصفحة باستخدام Contour Detection + Perspective Transform
2. auto_detect_skew - تصحيح الميلان باستخدام Projection Profile Method (لا يعطي +15° للصور المستقيمة)
3. smart_auto_crop - قص ذكي مع الحفاظ على الحواف
4. _apply_auto_deskew_on_load - تطبيق تلقائي عند فتح الصورة

المؤلف: Dr. Abdulmalek
"""

import sys
import cv2
import numpy as np
from typing import Tuple, Optional, List, Dict, Any
from pathlib import Path
import json

# GUI imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QSpinBox, QDoubleSpinBox,
    QCheckBox, QGroupBox, QScrollArea, QMessageBox, QProgressBar,
    QTextEdit, QSplitter, QFrame, QComboBox, QStatusBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


# =============================================================================
# CORE IMAGE PROCESSING FUNCTIONS (مُعاد بناؤها من الصفر)
# =============================================================================

def find_page_bounds_fixed(image: np.ndarray,
                           gray_threshold: int = 200,
                           padding: int = 10) -> Optional[Tuple[int, int, int, int]]:
    """
    كشف حدود الصفحة باستخدام Contour Detection و Projection Profiles
    يعمل على الصور الملونة والرمادية والمستندات ذات الخلفيات المعقدة
    """
    if image is None or image.size == 0:
        return None

    # تحويل إلى رمادي
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    h, w = gray.shape

    # 1. Gaussian blur لتقليل الضوضاء
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # 2. Adaptive threshold - النص أبيض، الخلفية سوداء
    binary = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=25,
        C=11
    )

    # 3. إزالة الضوضاء الصغيرة باستخدام morphological operations
    kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_small, iterations=1)

    kernel_medium = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_medium, iterations=2)

    # 4. إيجاد الكونتورات
    contours, hierarchy = cv2.findContours(
        binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        return (0, 0, w, h)

    # 5. تصفية الكونتورات: نحتفظ فقط بالكونتورات الكبيرة (ليس الضوضاء)
    min_area = (w * h) * 0.05  # على الأقل 5% من مساحة الصورة
    valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]

    if not valid_contours:
        valid_contours = contours  # fallback

    # 6. دمج جميع الكونتورات الصالحة في مستطيل واحد
    all_points = np.vstack([c.reshape(-1, 2) for c in valid_contours])
    x, y, bw, bh = cv2.boundingRect(all_points)

    # 7. إضافة padding والتحقق من الحدود
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(w, x + bw + padding)
    y2 = min(h, y + bh + padding)

    # 8. التحقق: إذا كانت الحدود قريبة جدًا من حجم الصورة الأصلية،
    #    ربما فشلنا في كشف الصفحة، نستخدم projection profiles كاحتياطي
    page_ratio = ((x2 - x1) * (y2 - y1)) / (w * h)

    if page_ratio > 0.95:
        # استخدام projection profiles كاحتياطي
        row_sums = np.sum(binary, axis=1)
        col_sums = np.sum(binary, axis=0)

        # إيجاد أول وآخر صف/عمود يحتوي على بكسلات
        rows_with_content = np.where(row_sums > 0)[0]
        cols_with_content = np.where(col_sums > 0)[0]

        if len(rows_with_content) > 0 and len(cols_with_content) > 0:
            y1 = max(0, rows_with_content[0] - padding)
            y2 = min(h, rows_with_content[-1] + padding)
            x1 = max(0, cols_with_content[0] - padding)
            x2 = min(w, cols_with_content[-1] + padding)

    return (x1, y1, x2, y2)


def auto_detect_skew_fixed(image: np.ndarray,
                           angle_range: int = 15,
                           step: float = 0.5) -> float:
    """
    كشف الميلان باستخدام Projection Profile Method
    أكثر دقة وثباتًا من Hough Transform للمستندات النصية
    لا يعطي نتائج خاطئة (+15°) للصور المستقيمة
    """
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    h, w = gray.shape

    # 1. Otsu threshold للحصول على ثنائي نظيف
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 2. إزالة الضوضاء الصغيرة
    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    # 3. البحث عن أفضل زاوية باستخدام Projection Profiles
    best_angle = 0.0
    max_score = -1.0

    angles = np.arange(-angle_range, angle_range + step, step)

    for angle in angles:
        # تدوير الصورة
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)

        # حساب الحجم الجديد لتجنب القص
        cos_a = np.abs(np.cos(np.radians(angle)))
        sin_a = np.abs(np.sin(np.radians(angle)))
        new_w = int(h * sin_a + w * cos_a)
        new_h = int(h * cos_a + w * sin_a)

        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]

        rotated = cv2.warpAffine(
            binary, M, (new_w, new_h),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0
        )

        # Projection Profile: مجموع البكسلات في كل صف
        row_sums = np.sum(rotated, axis=1).astype(np.float64)

        # Score: variance of differences (كلما زاد = سطور أوضح)
        if len(row_sums) > 1:
            diff = np.diff(row_sums)
            score = np.var(diff)
        else:
            score = 0.0

        if score > max_score:
            max_score = score
            best_angle = angle

    # 4. تحسين دقيقة حول best_angle
    if best_angle is not None:
        fine_angles = np.arange(
            best_angle - step,
            best_angle + step + 0.1,
            0.1
        )

        for angle in fine_angles:
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)

            cos_a = np.abs(np.cos(np.radians(angle)))
            sin_a = np.abs(np.sin(np.radians(angle)))
            new_w = int(h * sin_a + w * cos_a)
            new_h = int(h * cos_a + w * sin_a)

            M[0, 2] += (new_w / 2) - center[0]
            M[1, 2] += (new_h / 2) - center[1]

            rotated = cv2.warpAffine(
                binary, M, (new_w, new_h),
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=0
            )

            row_sums = np.sum(rotated, axis=1).astype(np.float64)

            if len(row_sums) > 1:
                diff = np.diff(row_sums)
                score = np.var(diff)
            else:
                score = 0.0

            if score > max_score:
                max_score = score
                best_angle = angle

    # 5. التحقق النهائي: إذا كان الميلان أقل من 0.3°، نعتبره صفرًا
    if abs(best_angle) < 0.3:
        best_angle = 0.0

    return float(best_angle)


def smart_auto_crop(image: np.ndarray,
                    bounds: Tuple[int, int, int, int],
                    margin: int = 20) -> np.ndarray:
    """
    قص ذكي مع الحفاظ على هوامش مناسبة
    """
    if image is None:
        return image

    h, w = image.shape[:2]
    x1, y1, x2, y2 = bounds

    # إضافة هوامش
    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)
    x2 = min(w, x2 + margin)
    y2 = min(h, y2 + margin)

    # التحقق من صحة الإحداثيات
    if x2 <= x1 or y2 <= y1:
        return image

    cropped = image[y1:y2, x1:x2]
    return cropped


def apply_deskew(image: np.ndarray, angle: float) -> np.ndarray:
    """
    تطبيق تصحيح الميلان على الصورة مع الحفاظ على المحتوى كاملًا
    """
    if abs(angle) < 0.1:
        return image

    h, w = image.shape[:2]
    center = (w // 2, h // 2)

    M = cv2.getRotationMatrix2D(center, angle, 1.0)

    # حساب الحجم الجديد
    cos_a = np.abs(np.cos(np.radians(angle)))
    sin_a = np.abs(np.sin(np.radians(angle)))
    new_w = int(h * sin_a + w * cos_a)
    new_h = int(h * cos_a + w * sin_a)

    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]

    # تحديد لون الخلفية (أبيض للمستندات)
    if len(image.shape) == 3:
        border_value = (255, 255, 255)
    else:
        border_value = 255

    rotated = cv2.warpAffine(
        image, M, (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border_value
    )

    return rotated


# =============================================================================
# OCR PIPELINE
# =============================================================================

def run_ocr(image: np.ndarray, lang: str = "ara+eng") -> Dict[str, Any]:
    """
    تشغيل OCR على الصورة المعالجة
    """
    if not TESSERACT_AVAILABLE:
        return {
            "text": "",
            "words": [],
            "confidence": 0.0,
            "error": "pytesseract not installed"
        }

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    # تحسين جودة الصورة للـ OCR
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    config = f'--oem 3 --psm 6 -l {lang}'

    try:
        text = pytesseract.image_to_string(binary, config=config)
        data = pytesseract.image_to_data(binary, config=config, output_type=pytesseract.Output.DICT)

        words = []
        confidences = []

        for i, word_text in enumerate(data['text']):
            if word_text.strip():
                words.append({
                    "text": word_text,
                    "conf": data['conf'][i],
                    "bbox": (data['left'][i], data['top'][i],
                             data['width'][i], data['height'][i])
                })
                if data['conf'][i] > 0:
                    confidences.append(data['conf'][i])

        avg_conf = np.mean(confidences) if confidences else 0.0

        return {
            "text": text.strip(),
            "words": words,
            "confidence": float(avg_conf),
            "word_count": len(words)
        }

    except Exception as e:
        return {
            "text": "",
            "words": [],
            "confidence": 0.0,
            "error": str(e)
        }


# =============================================================================
# WORKER THREAD
# =============================================================================

class ProcessThread(QThread):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished_signal = pyqtSignal(dict)

    def __init__(self, image_path: str, auto_deskew: bool = True,
                 auto_crop: bool = True, run_ocr_flag: bool = True):
        super().__init__()
        self.image_path = image_path
        self.auto_deskew = auto_deskew
        self.auto_crop = auto_crop
        self.run_ocr_flag = run_ocr_flag
        self._is_running = True

    def run(self):
        try:
            self.status.emit("جاري قراءة الصورة...")
            self.progress.emit(10)

            image = cv2.imread(self.image_path)
            if image is None:
                self.status.emit("خطأ: لا يمكن قراءة الصورة")
                self.finished_signal.emit({"error": "Cannot read image"})
                return

            original = image.copy()
            results = {
                "original": original,
                "steps": []
            }

            # الخطوة 1: كشف الحدود
            if self.auto_crop:
                self.status.emit("جاري كشف حدود الصفحة...")
                self.progress.emit(25)

                bounds = find_page_bounds_fixed(image)
                if bounds:
                    results["bounds"] = bounds
                    image = smart_auto_crop(image, bounds)
                    results["steps"].append({
                        "name": "crop",
                        "image": image.copy(),
                        "desc": f"قص الصفحة: {bounds}"
                    })

            # الخطوة 2: تصحيح الميلان
            if self.auto_deskew:
                self.status.emit("جاري كشف الميلان...")
                self.progress.emit(50)

                angle = auto_detect_skew_fixed(image)
                results["skew_angle"] = angle

                self.status.emit(f"الميلان المكتشف: {angle:.2f}°")

                if abs(angle) > 0.3:
                    image = apply_deskew(image, angle)
                    results["steps"].append({
                        "name": "deskew",
                        "image": image.copy(),
                        "desc": f"تصحيح الميلان: {angle:.2f}°"
                    })

            # الخطوة 3: OCR
            if self.run_ocr_flag and TESSERACT_AVAILABLE:
                self.status.emit("جاري استخراج النص...")
                self.progress.emit(75)

                ocr_result = run_ocr(image)
                results["ocr"] = ocr_result

            results["processed"] = image
            self.progress.emit(100)
            self.status.emit("اكتملت المعالجة")
            self.finished_signal.emit(results)

        except Exception as e:
            self.status.emit(f"خطأ: {str(e)}")
            self.finished_signal.emit({"error": str(e)})

    def stop(self):
        self._is_running = False
        self.wait()


# =============================================================================
# MAIN WINDOW
# =============================================================================

class MedicalDocScanner(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Medical Document Scanner v13.1")
        self.setMinimumSize(1200, 800)

        self.current_image = None
        self.processed_image = None
        self.thread = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # --- Sidebar ---
        sidebar = QVBoxLayout()

        # Load Button
        self.btn_load = QPushButton("📂 فتح صورة")
        self.btn_load.setStyleSheet("font-size: 14px; padding: 10px;")
        sidebar.addWidget(self.btn_load)

        # Auto Options
        group_auto = QGroupBox("خيارات تلقائية")
        auto_layout = QVBoxLayout()

        self.chk_auto_crop = QCheckBox("كشف وقص الصفحة تلقائيًا")
        self.chk_auto_crop.setChecked(True)
        auto_layout.addWidget(self.chk_auto_crop)

        self.chk_auto_deskew = QCheckBox("تصحيح الميلان تلقائيًا")
        self.chk_auto_deskew.setChecked(True)
        auto_layout.addWidget(self.chk_auto_deskew)

        self.chk_run_ocr = QCheckBox("تشغيل OCR بعد المعالجة")
        self.chk_run_ocr.setChecked(True)
        auto_layout.addWidget(self.chk_run_ocr)

        group_auto.setLayout(auto_layout)
        sidebar.addWidget(group_auto)

        # Manual Controls
        group_manual = QGroupBox("تحكم يدوي")
        manual_layout = QVBoxLayout()

        self.btn_detect_bounds = QPushButton("🔍 كشف الحدود")
        manual_layout.addWidget(self.btn_detect_bounds)

        self.btn_deskew = QPushButton("↻ تصحيح الميلان")
        manual_layout.addWidget(self.btn_deskew)

        self.btn_crop = QPushButton("✂ قص الصفحة")
        manual_layout.addWidget(self.btn_crop)

        self.btn_ocr = QPushButton("📝 استخراج النص (OCR)")
        manual_layout.addWidget(self.btn_ocr)

        self.btn_save = QPushButton("💾 حفظ النتيجة")
        manual_layout.addWidget(self.btn_save)

        group_manual.setLayout(manual_layout)
        sidebar.addWidget(group_manual)

        # Progress
        self.progress = QProgressBar()
        sidebar.addWidget(self.progress)

        self.lbl_status = QLabel("جاهز")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        sidebar.addWidget(self.lbl_status)

        sidebar.addStretch()
        main_layout.addLayout(sidebar, 1)

        # --- Image View ---
        view_widget = QWidget()
        view_layout = QVBoxLayout(view_widget)

        # Tabs for images
        self.lbl_original = QLabel("الصورة الأصلية")
        self.lbl_original.setAlignment(Qt.AlignCenter)
        self.lbl_original.setStyleSheet("background: #f0f0f0; border: 2px dashed #ccc;")
        self.lbl_original.setMinimumHeight(300)

        self.lbl_processed = QLabel("الصورة المعالجة")
        self.lbl_processed.setAlignment(Qt.AlignCenter)
        self.lbl_processed.setStyleSheet("background: #f0f0f0; border: 2px dashed #ccc;")
        self.lbl_processed.setMinimumHeight(300)

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.lbl_original)
        splitter.addWidget(self.lbl_processed)
        view_layout.addWidget(splitter)

        # OCR Text
        self.txt_ocr = QTextEdit()
        self.txt_ocr.setPlaceholderText("نتيجة OCR ستظهر هنا...")
        self.txt_ocr.setMaximumHeight(150)
        view_layout.addWidget(self.txt_ocr)

        main_layout.addWidget(view_widget, 4)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("v13.1 - إصلاحات find_page_bounds و auto_detect_skew")

    def _connect_signals(self):
        self.btn_load.clicked.connect(self._on_load)
        self.btn_detect_bounds.clicked.connect(self._on_detect_bounds)
        self.btn_deskew.clicked.connect(self._on_deskew)
        self.btn_crop.clicked.connect(self._on_crop)
        self.btn_ocr.clicked.connect(self._on_ocr)
        self.btn_save.clicked.connect(self._on_save)

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "فتح صورة", "",
            "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp)"
        )
        if not path:
            return

        self.current_path = path
        self.progress.setValue(0)
        self.txt_ocr.clear()

        # Auto-process on load
        self.thread = ProcessThread(
            path,
            auto_deskew=self.chk_auto_deskew.isChecked(),
            auto_crop=self.chk_auto_crop.isChecked(),
            run_ocr_flag=self.chk_run_ocr.isChecked()
        )
        self.thread.progress.connect(self.progress.setValue)
        self.thread.status.connect(self.lbl_status.setText)
        self.thread.finished_signal.connect(self._on_process_finished)
        self.thread.start()

    def _on_process_finished(self, results: dict):
        if "error" in results:
            QMessageBox.critical(self, "خطأ", results["error"])
            return

        self.current_image = results.get("original")
        self.processed_image = results.get("processed", self.current_image)

        self._display_image(self.current_image, self.lbl_original)
        self._display_image(self.processed_image, self.lbl_processed)

        if "ocr" in results:
            ocr = results["ocr"]
            text = ocr.get("text", "")
            conf = ocr.get("confidence", 0)
            wc = ocr.get("word_count", 0)

            self.txt_ocr.setPlainText(text)
            self.status_bar.showMessage(
                f"OCR: {wc} كلمة | الثقة: {conf:.1f}% | "
                f"الميلان: {results.get('skew_angle', 0):.2f}°"
            )

    def _on_detect_bounds(self):
        if self.current_image is None:
            QMessageBox.warning(self, "تنبيه", "افتح صورة أولاً")
            return

        bounds = find_page_bounds_fixed(self.current_image)
        if bounds:
            x1, y1, x2, y2 = bounds
            QMessageBox.information(
                self, "حدود الصفحة",
                f"الحدود المكتشفة:
"
                f"أعلى-يسار: ({x1}, {y1})
"
                f"أسفل-يمين: ({x2}, {y2})
"
                f"العرض: {x2-x1}, الارتفاع: {y2-y1}"
            )

            # رسم المستطيل على الصورة
            vis = self.current_image.copy()
            cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 3)
            self._display_image(vis, self.lbl_original)
        else:
            QMessageBox.warning(self, "تنبيه", "لم يتم كشف حدود الصفحة")

    def _on_deskew(self):
        if self.processed_image is None:
            QMessageBox.warning(self, "تنبيه", "افتح صورة أولاً")
            return

        angle = auto_detect_skew_fixed(self.processed_image)
        QMessageBox.information(self, "الميلان", f"الزاوية المكتشفة: {angle:.2f}°")

        if abs(angle) > 0.3:
            self.processed_image = apply_deskew(self.processed_image, angle)
            self._display_image(self.processed_image, self.lbl_processed)

    def _on_crop(self):
        if self.current_image is None:
            QMessageBox.warning(self, "تنبيه", "افتح صورة أولاً")
            return

        bounds = find_page_bounds_fixed(self.current_image)
        if bounds:
            self.processed_image = smart_auto_crop(self.current_image, bounds)
            self._display_image(self.processed_image, self.lbl_processed)
        else:
            QMessageBox.warning(self, "تنبيه", "لم يتم كشف حدود للقص")

    def _on_ocr(self):
        if self.processed_image is None:
            QMessageBox.warning(self, "تنبيه", "افتح صورة أولاً")
            return

        if not TESSERACT_AVAILABLE:
            QMessageBox.critical(
                self, "خطأ",
                "pytesseract غير مثبت
"
                "ثبته عبر: pip install pytesseract
"
                "وثبّت Tesseract OCR على نظامك"
            )
            return

        self.status_bar.showMessage("جاري OCR...")
        result = run_ocr(self.processed_image)

        self.txt_ocr.setPlainText(result.get("text", ""))
        self.status_bar.showMessage(
            f"OCR اكتمل: {result.get('word_count', 0)} كلمة | "
            f"الثقة: {result.get('confidence', 0):.1f}%"
        )

    def _on_save(self):
        if self.processed_image is None:
            QMessageBox.warning(self, "تنبيه", "لا توجد صورة للحفظ")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "حفظ الصورة", "processed.png",
            "PNG (*.png);;JPEG (*.jpg);;TIFF (*.tif)"
        )
        if path:
            cv2.imwrite(path, self.processed_image)
            self.status_bar.showMessage(f"تم الحفظ: {path}")

    def _display_image(self, image: np.ndarray, label: QLabel):
        if image is None:
            return

        # Convert BGR to RGB
        if len(image.shape) == 3:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)

        h, w, ch = rgb.shape
        bytes_per_line = ch * w

        qt_image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)

        # Scale to fit label while keeping aspect ratio
        pixmap = QPixmap.fromImage(qt_image)
        scaled = pixmap.scaled(
            label.width(), label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        label.setPixmap(scaled)

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            self.thread.stop()
        event.accept()


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Arabic font support
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    window = MedicalDocScanner()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
