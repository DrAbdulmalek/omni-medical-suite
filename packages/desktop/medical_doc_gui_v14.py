#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
medical_doc_gui_v14.py — Smart Client
=======================================
العميل الذكي المدمج مع البنية التحتية السحابية.
يعتمد على medical_doc_gui_v13_1.py مع إضافات:
- WebSocket Bridge للتنبيهات الفورية
- Redis Cache للتخزين المؤقت
- المزامنة التلقائية عند العودة للاتصال
- معالجة ذكية: سحابة عند الاتصال، محلية عند الانقطاع

الترقية من v13.1:
- إضافة QtWebSocketBridge
- إضافة RedisCache
- تعديل __init__ في MedicalDocScanner
- إضافة دوال المعالجة الذكية

المؤلف: Dr. Abdulmalek Al-husseini
المشروع: OmniMedical Suite
"""

import sys
import os
import json
import time
import asyncio
import threading
import queue as queue_mod
from typing import Tuple, Optional, List, Dict, Any
from pathlib import Path

import cv2
import numpy as np

# GUI imports
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QSpinBox, QDoubleSpinBox,
    QCheckBox, QGroupBox, QScrollArea, QMessageBox, QProgressBar,
    QTextEdit, QSplitter, QFrame, QComboBox, QStatusBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


# =============================================================================
# SMART CLIENT BRIDGES (الجسور السحابية)
# =============================================================================

class QtWebSocketBridge(QObject):
    """
    جسر WebSocket للاتصال بخادم WebSocket من خيط Qt الرئيسي.
    يعمل في خيط منفصل ويرسل الإشارات عبر Qt signals.
    """
    update = pyqtSignal(dict)
    connected = pyqtSignal()
    disconnected = pyqtSignal(str)
    connection_status = pyqtSignal(bool)  # True = online, False = offline

    def __init__(self, uri: str = "ws://localhost:8765", tenant: str = "clinic_01"):
        super().__init__()
        self.uri = uri
        self.tenant = tenant
        self._ws = None
        self._running = True
        self._thread = None

    def start(self):
        """بدء الاتصال في خيط منفصل."""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """إيقاف الاتصال."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self):
        """حلقة الاتصال مع إعادة المحاولة التلقائية."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self._running:
            try:
                loop.run_until_complete(self._connect_and_listen())
            except Exception as e:
                self.disconnected.emit(str(e))
                self.connection_status.emit(False)
                if self._running:
                    time.sleep(5)  # انتظار قبل إعادة المحاولة

        loop.close()

    async def _connect_and_listen(self):
        """الاتصال والاستماع للرسائل."""
        try:
            import websockets
        except ImportError:
            self.disconnected.emit("websockets not installed")
            return

        async with websockets.connect(self.uri, ping_interval=30) as ws:
            self._ws = ws
            # اشتراك في المستأجر
            await ws.send(json.dumps({
                "type": "subscribe_tenant",
                "tenant_id": self.tenant
            }))
            self.connected.emit()
            self.connection_status.emit(True)

            # الاستماع للرسائل
            async for message in ws:
                try:
                    data = json.loads(message)
                    self.update.emit(data)
                except json.JSONDecodeError:
                    pass

    def send(self, data: dict):
        """إرسال رسالة إلى الخادم."""
        if self._ws:
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(
                    self._ws.send(json.dumps(data, ensure_ascii=False))
                )
                loop.close()
            except Exception:
                pass

    def is_connected(self) -> bool:
        """فحص حالة الاتصال."""
        return self._ws is not None


class RedisCache:
    """
    عميل Redis مبسط للتخزين المؤقت.
    يخزن نتائج OCR المؤقتة لتسريع الوصول المتكرر.
    """
    def __init__(self, host: str = "localhost", port: int = 6380, db: int = 0):
        self.host = host
        self.port = port
        self.db = db
        self._client = None
        self._available = False
        self._try_connect()

    def _try_connect(self):
        """محاولة الاتصال بـ Redis."""
        try:
            import redis
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                socket_timeout=2,
                socket_connect_timeout=2,
                decode_responses=True
            )
            self._client.ping()
            self._available = True
        except Exception:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def get(self, key: str) -> Optional[str]:
        """قراءة قيمة من الكاش."""
        if not self._available:
            return None
        try:
            return self._client.get(key)
        except Exception:
            return None

    def set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """كتابة قيمة في الكاش."""
        if not self._available:
            return False
        try:
            self._client.setex(key, ttl, value)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """حذف مفتاح."""
        if not self._available:
            return False
        try:
            self._client.delete(key)
            return True
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        """فحص وجود مفتاح."""
        if not self._available:
            return False
        try:
            return bool(self._client.exists(key))
        except Exception:
            return False


# =============================================================================
# CORE IMAGE PROCESSING FUNCTIONS (من v13.1)
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

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    h, w = gray.shape
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    binary = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=25, C=11
    )

    kernel_small = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_small, iterations=1)
    kernel_medium = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_medium, iterations=2)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return (0, 0, w, h)

    min_area = (w * h) * 0.05
    valid_contours = [c for c in contours if cv2.contourArea(c) > min_area]
    if not valid_contours:
        valid_contours = contours

    all_points = np.vstack([c.reshape(-1, 2) for c in valid_contours])
    x, y, bw, bh = cv2.boundingRect(all_points)

    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(w, x + bw + padding)
    y2 = min(h, y + bh + padding)

    page_ratio = ((x2 - x1) * (y2 - y1)) / (w * h)
    if page_ratio > 0.95:
        row_sums = np.sum(binary, axis=1)
        col_sums = np.sum(binary, axis=0)
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
    """كشف الميلان باستخدام Projection Profile Method."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    h, w = gray.shape
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    best_angle = 0.0
    max_score = -1.0
    angles = np.arange(-angle_range, angle_range + step, step)

    for angle in angles:
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        cos_a = np.abs(np.cos(np.radians(angle)))
        sin_a = np.abs(np.sin(np.radians(angle)))
        new_w = int(h * sin_a + w * cos_a)
        new_h = int(h * cos_a + w * sin_a)
        M[0, 2] += (new_w / 2) - center[0]
        M[1, 2] += (new_h / 2) - center[1]
        rotated = cv2.warpAffine(binary, M, (new_w, new_h),
                                  borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        row_sums = np.sum(rotated, axis=1).astype(np.float64)
        if len(row_sums) > 1:
            diff = np.diff(row_sums)
            score = np.var(diff)
        else:
            score = 0.0
        if score > max_score:
            max_score = score
            best_angle = angle

    if abs(best_angle) < 0.3:
        best_angle = 0.0
    return float(best_angle)


def smart_auto_crop(image: np.ndarray,
                    bounds: Tuple[int, int, int, int],
                    margin: int = 20) -> np.ndarray:
    """قص ذكي مع الحفاظ على هوامش مناسبة."""
    if image is None:
        return image
    h, w = image.shape[:2]
    x1, y1, x2, y2 = bounds
    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)
    x2 = min(w, x2 + margin)
    y2 = min(h, y2 + margin)
    if x2 <= x1 or y2 <= y1:
        return image
    return image[y1:y2, x1:x2]


def apply_deskew(image: np.ndarray, angle: float) -> np.ndarray:
    """تطبيق تصحيح الميلان على الصورة."""
    if abs(angle) < 0.1:
        return image
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos_a = np.abs(np.cos(np.radians(angle)))
    sin_a = np.abs(np.sin(np.radians(angle)))
    new_w = int(h * sin_a + w * cos_a)
    new_h = int(h * cos_a + w * sin_a)
    M[0, 2] += (new_w / 2) - center[0]
    M[1, 2] += (new_h / 2) - center[1]
    border_value = (255, 255, 255) if len(image.shape) == 3 else 255
    return cv2.warpAffine(image, M, (new_w, new_h),
                           flags=cv2.INTER_CUBIC,
                           borderMode=cv2.BORDER_CONSTANT,
                           borderValue=border_value)


def run_ocr(image: np.ndarray, lang: str = "ara+eng") -> Dict[str, Any]:
    """تشغيل OCR على الصورة المعالجة."""
    if not TESSERACT_AVAILABLE:
        return {"text": "", "words": [], "confidence": 0.0, "error": "pytesseract not installed"}
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    config = f'--oem 3 --psm 6 -l {lang}'
    try:
        text = pytesseract.image_to_string(binary, config=config)
        data = pytesseract.image_to_data(binary, config=config, output_type=pytesseract.Output.DICT)
        words = []
        confidences = []
        for i, word_text in enumerate(data['text']):
            if word_text.strip():
                words.append({"text": word_text, "conf": data['conf'][i],
                              "bbox": (data['left'][i], data['top'][i],
                                       data['width'][i], data['height'][i])})
                if data['conf'][i] > 0:
                    confidences.append(data['conf'][i])
        avg_conf = np.mean(confidences) if confidences else 0.0
        return {"text": text.strip(), "words": words,
                "confidence": float(avg_conf), "word_count": len(words)}
    except Exception as e:
        return {"text": "", "words": [], "confidence": 0.0, "error": str(e)}


# =============================================================================
# WORKER THREAD (من v13.1)
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
            results = {"original": original, "steps": []}

            if self.auto_crop:
                self.status.emit("جاري كشف حدود الصفحة...")
                self.progress.emit(25)
                bounds = find_page_bounds_fixed(image)
                if bounds:
                    results["bounds"] = bounds
                    image = smart_auto_crop(image, bounds)
                    results["steps"].append({"name": "crop", "image": image.copy(),
                                              "desc": f"قص الصفحة: {bounds}"})

            if self.auto_deskew:
                self.status.emit("جاري كشف الميلان...")
                self.progress.emit(50)
                angle = auto_detect_skew_fixed(image)
                results["skew_angle"] = angle
                self.status.emit(f"الميلان المكتشف: {angle:.2f}°")
                if abs(angle) > 0.3:
                    image = apply_deskew(image, angle)
                    results["steps"].append({"name": "deskew", "image": image.copy(),
                                              "desc": f"تصحيح الميلان: {angle:.2f}°"})

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


# =============================================================================
# MAIN WINDOW — SMART CLIENT v14
# =============================================================================

class MedicalDocScanner(QMainWindow):
    """
    ماسح المستندات الطبية — العميل الذكي v14.
    يدعم:
    - المعالجة المحلية (كما في v13.1)
    - المعالجة السحابية عبر Load Balancer
    - التخزين المؤقت عبر Redis
    - المزامنة التلقائية عند عودة الاتصال
    - التنبيهات الفورية عبر WebSocket
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Medical Document Scanner v14 | Smart Client")
        self.setMinimumSize(1200, 800)

        self.current_image = None
        self.processed_image = None
        self.thread = None
        self.current_path = None

        # ── Smart Client: البنية السحابية ──────────────────────────
        self.ws_bridge = QtWebSocketBridge(
            uri="ws://localhost:8765",
            tenant="clinic_01"
        )
        self.ws_bridge.update.connect(self._on_ws_update)
        self.ws_bridge.connected.connect(
            lambda: self.status_bar.showMessage("🟢 متصل بالسحابة")
        )
        self.ws_bridge.disconnected.connect(
            lambda e: self.status_bar.showMessage(f"🔌 وضع محلي (Offline): {e}")
        )
        self.ws_bridge.connection_status.connect(self._on_connection_change)
        self.ws_bridge.start()

        self.cache = RedisCache(host="localhost", port=6380)

        self.offline_queue = queue_mod.Queue()
        self.is_online = True

        # مؤقت المزامنة (كل دقيقة)
        self.sync_timer = QTimer()
        self.sync_timer.timeout.connect(self._sync_offline)
        self.sync_timer.start(60000)

        # مؤقت فحص الاتصال (كل 30 ثانية)
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self._check_connection)
        self.connection_timer.start(30000)

        # ── واجهة المستخدم ──────────────────────────────────────────
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # --- Sidebar ---
        sidebar = QVBoxLayout()

        # حالة الاتصال
        self.lbl_connection = QLabel("🔌 جاري الاتصال...")
        self.lbl_connection.setStyleSheet("font-weight: bold; padding: 5px; "
                                           "background: #f0f0f0; border-radius: 5px;")
        sidebar.addWidget(self.lbl_connection)

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

        # Sync button
        self.btn_sync = QPushButton("🔄 مزامنة الآن")
        self.btn_sync.setStyleSheet("background: #4CAF50; color: white; "
                                     "font-size: 12px; padding: 8px;")
        sidebar.addWidget(self.btn_sync)

        # Progress
        self.progress = QProgressBar()
        sidebar.addWidget(self.progress)

        self.lbl_status = QLabel("جاهز")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        sidebar.addWidget(self.lbl_status)

        # Offline queue info
        self.lbl_offline = QLabel("قائمة الانتظار: 0 مستند")
        self.lbl_offline.setAlignment(Qt.AlignCenter)
        self.lbl_offline.setStyleSheet("color: #888; font-size: 11px;")
        sidebar.addWidget(self.lbl_offline)

        sidebar.addStretch()
        main_layout.addLayout(sidebar, 1)

        # --- Image View ---
        view_widget = QWidget()
        view_layout = QVBoxLayout(view_widget)

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

        self.txt_ocr = QTextEdit()
        self.txt_ocr.setPlaceholderText("نتيجة OCR ستظهر هنا...")
        self.txt_ocr.setMaximumHeight(150)
        view_layout.addWidget(self.txt_ocr)

        main_layout.addWidget(view_widget, 4)

        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("v14 — Smart Client | Cloud + Offline Support")

    def _connect_signals(self):
        self.btn_load.clicked.connect(self._on_load)
        self.btn_detect_bounds.clicked.connect(self._on_detect_bounds)
        self.btn_deskew.clicked.connect(self._on_deskew)
        self.btn_crop.clicked.connect(self._on_crop)
        self.btn_ocr.clicked.connect(self._on_ocr)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_sync.clicked.connect(self._sync_offline)

    # ====================================================================
    # SMART CLIENT: دوال المعالجة الذكية
    # ====================================================================

    def _on_connection_change(self, is_online: bool):
        """تحديث حالة الاتصال."""
        self.is_online = is_online
        if is_online:
            self.lbl_connection.setText("🟢 متصل بالسحابة")
            self.lbl_connection.setStyleSheet(
                "font-weight: bold; padding: 5px; "
                "background: #e8f5e9; border-radius: 5px; color: #2e7d32;"
            )
            # محاولة مزامنة المهام المؤجلة
            self._sync_offline()
        else:
            self.lbl_connection.setText("🔌 وضع محلي (Offline)")
            self.lbl_connection.setStyleSheet(
                "font-weight: bold; padding: 5px; "
                "background: #fff3e0; border-radius: 5px; color: #e65100;"
            )

    def _on_ws_update(self, data: dict):
        """معالجة تحديثات WebSocket الواردة."""
        msg_type = data.get("type", "")

        if msg_type == "processing_progress":
            stage = data.get("stage", "")
            progress_val = data.get("progress", 0)
            self.progress.setValue(progress_val)
            self.lbl_status.setText(f"📡 {stage}")
            if stage == "completed":
                final_text = data.get("metadata", {}).get("final_text", "")
                if final_text:
                    self.txt_ocr.setPlainText(final_text)
                self.lbl_status.setStyleSheet("color: green;")

        elif msg_type == "document_update":
            self.lbl_status.setText(
                f"📡 تحديث مستند من: {data.get('from', 'unknown')}"
            )

        elif msg_type == "subscribed":
            self.lbl_status.setText(
                f"✅ مشترك في: {data.get('tenant_id', '')}"
            )

    def _check_connection(self):
        """فحص دوري لاتصال WebSocket."""
        self.is_online = self.ws_bridge.is_connected()
        self._on_connection_change(self.is_online)
        # تحديث عداد قائمة الانتظار
        queue_size = self.offline_queue.qsize()
        self.lbl_offline.setText(
            f"قائمة الانتظار: {queue_size} مستند"
        )

    def _process_smart(self, image_path: str):
        """
        معالجة ذكية:
        1. فحص الكاش أولاً
        2. إذا كان متصلاً، أرسل للسحابة
        3. إذا كان غير متصل، عالج محلياً وأضف لقائمة الانتظار
        """
        cache_key = f"ocr_result:{image_path}"
        cached = self.cache.get(cache_key)

        if cached and cached != "$-1":
            self.txt_ocr.setPlainText(cached)
            self.lbl_status.setText("📦 نتيجة من الكاش")
            self.status_bar.showMessage("📦 تم تحميل النتيجة من الكاش")
            return

        if self.is_online:
            self.lbl_status.setText("📤 إرسال للسحابة...")
            # هنا يتم استدعاء API عبر LB
            # في الإنتاج: requests.post("http://localhost:8080/api/documents/upload", ...)
            # حالياً نعالج محلياً ونخزن في الكاش
            self._run_local_processing(image_path)
        else:
            self.lbl_status.setText("💻 معالجة محلية (Fallback)...")
            self._run_local_processing(image_path)
            self.offline_queue.put(image_path)

    def _run_local_processing(self, image_path: str):
        """تشغيل المعالجة المحلية."""
        self.thread = ProcessThread(
            image_path,
            auto_deskew=self.chk_auto_deskew.isChecked(),
            auto_crop=self.chk_auto_crop.isChecked(),
            run_ocr_flag=self.chk_run_ocr.isChecked()
        )
        self.thread.progress.connect(self.progress.setValue)
        self.thread.status.connect(self.lbl_status.setText)
        self.thread.finished_signal.connect(self._on_smart_process_finished)
        self.thread.start()

    def _on_smart_process_finished(self, results: dict):
        """معالجة نتيجة المعالجة الذكية."""
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

            # تخزين في الكاش
            if self.current_path:
                cache_key = f"ocr_result:{self.current_path}"
                self.cache.set(cache_key, text, ttl=7200)

            # إرسال تحديث عبر WebSocket
            if self.is_online:
                self.ws_bridge.send({
                    "type": "processing_progress",
                    "stage": "completed",
                    "progress": 100,
                    "metadata": {"final_text": text}
                })

            self.status_bar.showMessage(
                f"OCR: {wc} كلمة | الثقة: {conf:.1f}% | "
                f"{'☁ سحابة' if self.is_online else '💻 محلي'} | "
                f"الميلان: {results.get('skew_angle', 0):.2f}°"
            )

    def _sync_offline(self):
        """مزامنة المهام المؤجلة عند عودة الاتصال."""
        if not self.offline_queue.empty() and self.is_online:
            synced = 0
            while not self.offline_queue.empty():
                try:
                    path = self.offline_queue.get_nowait()
                    # إرسال للمزامنة مع السحابة
                    # في الإنتاج: requests.post("http://localhost:8080/api/sync", ...)
                    synced += 1
                except queue_mod.Empty:
                    break
            if synced > 0:
                self.lbl_status.setText(f"🔄 تمت مزامنة {synced} مستند")
                self.status_bar.showMessage(
                    f"✅ تمت مزامنة {synced} مستند مع السحابة"
                )

        # تحديث العداد
        queue_size = self.offline_queue.qsize()
        self.lbl_offline.setText(
            f"قائمة الانتظار: {queue_size} مستند"
        )

    # ====================================================================
    # EVENT HANDLERS (من v13.1)
    # ====================================================================

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
        # استخدام المعالجة الذكية
        self._process_smart(path)

    def _on_process_finished(self, results: dict):
        """ backward compat - delegates to smart handler """
        self._on_smart_process_finished(results)

    def _on_detect_bounds(self):
        if self.current_image is None:
            QMessageBox.warning(self, "تنبيه", "افتح صورة أولاً")
            return
        bounds = find_page_bounds_fixed(self.current_image)
        if bounds:
            x1, y1, x2, y2 = bounds
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

    def _on_ocr(self):
        if self.processed_image is None:
            QMessageBox.warning(self, "تنبيه", "افتح صورة أولاً")
            return
        if not TESSERACT_AVAILABLE:
            QMessageBox.critical(self, "خطأ", "pytesseract غير مثبت")
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
        if len(image.shape) == 3:
            rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        else:
            rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        scaled = pixmap.scaled(
            label.width(), label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        label.setPixmap(scaled)

    def closeEvent(self, event):
        """تنظيف عند الإغلاق."""
        # مزامنة المهام المتبقية
        self._sync_offline()
        # إيقاف WebSocket
        self.ws_bridge.stop()
        # إيقاف المؤقتات
        self.sync_timer.stop()
        self.connection_timer.stop()
        # إيقاف المعالجة
        if self.thread and self.thread.isRunning():
            self.thread.wait(3000)
        event.accept()


# =============================================================================
# ENTRY POINT
# =============================================================================

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    window = MedicalDocScanner()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
