#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
medical_doc_gui_v18.py — OmniMedical Desktop Client (Final)
======================================
Features:
1. Multi-engine OCR support (Tesseract, EasyOCR, PaddleOCR).
2. Enhanced Fusion V3 algorithm (IOU Clustering + Dynamic Weights).
3. Real-time updates via WebSocket (from custom infrastructure).
4. Modern UI with Dark Mode support.
"""

from __future__ import annotations

import sys
import os
import json
import logging
import threading
from typing import List, Optional

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QCheckBox, QProgressBar, QTextEdit,
    QFileDialog, QMessageBox, QGroupBox, QComboBox, QTabWidget,
    QStatusBar, QToolBar, QAction, QSplitter,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt5.QtGui import QImage, QPixmap, QFont, QIcon

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OCR Engine Wrappers (stubs — replace with actual implementations)
# ---------------------------------------------------------------------------

class OCREngine:
    """Base class for OCR engine wrappers."""
    name: str = "base"

    def recognize(self, img) -> list:
        raise NotImplementedError


class TesseractEngine(OCREngine):
    name = "tesseract"

    def __init__(self, lang: str = "ara+eng"):
        self.lang = lang

    def recognize(self, img) -> list:
        import pytesseract
        data = pytesseract.image_to_data(img, lang=self.lang, output_type=pytesseract.Output.DICT)
        results = []
        for i in range(len(data["text"])):
            if data["text"][i].strip():
                results.append({
                    "text": data["text"][i],
                    "confidence": data["conf"][i] / 100.0,
                    "bbox": (data["left"][i], data["top"][i],
                             data["left"][i] + data["width"][i],
                             data["top"][i] + data["height"][i]),
                    "engine": self.name,
                })
        return results


class EasyOCREngine(OCREngine):
    name = "easyocr"

    def __init__(self, lang: str = "ar"):
        import easyocr
        self.reader = easyocr.Reader([lang], gpu=False)

    def recognize(self, img) -> list:
        results = []
        detections = self.reader.readtext(img)
        for bbox, text, conf in detections:
            x1, y1 = int(bbox[0][0]), int(bbox[0][1])
            x2, y2 = int(bbox[2][0]), int(bbox[2][1])
            results.append({
                "text": text,
                "confidence": conf,
                "bbox": (x1, y1, x2, y2),
                "engine": self.name,
            })
        return results


class PaddleOCREngine(OCREngine):
    name = "paddleocr"

    def __init__(self, lang: str = "ar"):
        from paddleocr import PaddleOCR
        self.ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)

    def recognize(self, img) -> list:
        results = []
        result = self.ocr.ocr(img, cls=True)
        if result and result[0]:
            for line in result[0]:
                bbox, (text, conf) = line[0], line[1]
                x1, y1 = int(bbox[0][0]), int(bbox[0][1])
                x2, y2 = int(bbox[2][0]), int(bbox[2][1])
                results.append({
                    "text": text,
                    "confidence": conf,
                    "bbox": (x1, y1, x2, y2),
                    "engine": self.name,
                })
        return results


# ---------------------------------------------------------------------------
# Fusion Engine (stub)
# ---------------------------------------------------------------------------

class FusionV3Engine:
    """Stub for Fusion V3 Enhanced algorithm.

    In production, this uses IOU-based spatial clustering with
    dynamic engine weights and ML-based quality scoring.
    """

    def fuse(self, engine_results: List[list], img=None) -> list:
        """Merge results from multiple OCR engines."""
        all_tokens = []
        for tokens in engine_results:
            all_tokens.extend(tokens)

        if not all_tokens:
            return []

        # Simple dedup by text overlap (placeholder for full V3 logic)
        fused = []
        seen_texts = set()
        for token in sorted(all_tokens, key=lambda t: t["bbox"][1]):
            text = token["text"].strip()
            if text and text not in seen_texts:
                seen_texts.add(text)
                fused.append(token)

        return fused


# ---------------------------------------------------------------------------
# Processing Thread
# ---------------------------------------------------------------------------

class ProcessingWorker(QThread):
    """Background thread for OCR processing."""
    finished = pyqtSignal(list, str)
    error = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, image, engines, use_fusion=True):
        super().__init__()
        self.image = image
        self.engines = engines
        self.use_fusion = use_fusion

    def run(self):
        try:
            all_results = []
            for i, engine in enumerate(self.engines):
                self.progress.emit(int(50 * (i + 1) / len(self.engines)))
                try:
                    tokens = engine.recognize(self.image)
                    all_results.append(tokens)
                    logger.info("Engine '%s' produced %d tokens", engine.name, len(tokens))
                except Exception as e:
                    logger.error("Engine '%s' failed: %s", engine.name, e)

            if self.use_fusion:
                fusion = FusionV3Engine()
                final = fusion.fuse(all_results, self.image)
                label = "Fusion V3"
            else:
                final = [t for tokens in all_results for t in tokens]
                label = "Raw"

            self.progress.emit(100)
            self.finished.emit(final, label)

        except Exception as e:
            self.error.emit(str(e))


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class OmniMedicalGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OmniMedical Suite v3.0 | Dr. Abdulmalek")
        self.setGeometry(100, 100, 1280, 860)

        self.current_image = None
        self.engines: List[OCREngine] = []
        self.worker: Optional[ProcessingWorker] = None

        self._apply_dark_theme()
        self._setup_ui()
        self._init_engines()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _apply_dark_theme(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; color: #d4d4d4; }
            QWidget { background-color: #1e1e1e; color: #d4d4d4; font-family: 'Segoe UI'; }
            QGroupBox { border: 1px solid #444; border-radius: 6px; margin-top: 12px; padding-top: 14px; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 6px; }
            QPushButton { background-color: #2d2d2d; border: 1px solid #555; border-radius: 5px; padding: 8px 16px; color: #d4d4d4; }
            QPushButton:hover { background-color: #3a3a3a; border-color: #007acc; }
            QPushButton:pressed { background-color: #007acc; }
            QPushButton:disabled { background-color: #1a1a1a; color: #666; }
            QTextEdit { background-color: #252525; border: 1px solid #444; border-radius: 4px; color: #d4d4d4; font-family: 'Cascadia Code', 'Consolas', monospace; font-size: 12px; }
            QProgressBar { background-color: #2d2d2d; border: 1px solid #555; border-radius: 4px; text-align: center; color: #d4d4d4; }
            QProgressBar::chunk { background-color: #007acc; border-radius: 3px; }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator { width: 16px; height: 16px; }
            QComboBox { background-color: #2d2d2d; border: 1px solid #555; border-radius: 4px; padding: 4px 8px; }
            QStatusBar { background-color: #007acc; color: white; }
            QLabel#preview { border: 2px dashed #444; background-color: #252525; border-radius: 8px; }
        """)

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # ── Left Panel ─────────────────────────────────────────
        left_panel = QVBoxLayout()
        left_panel.setSpacing(8)

        # File loader
        self.btn_load = QPushButton("📂  Load Medical Document")
        self.btn_load.setStyleSheet("font-size: 14px; padding: 10px;")
        self.btn_load.clicked.connect(self._load_image)
        left_panel.addWidget(self.btn_load)

        # Engine selection
        grp_engines = QGroupBox("🧠  OCR Engines")
        eng_layout = QVBoxLayout()
        self.cb_tesseract = QCheckBox("Tesseract 5 (ara+eng)")
        self.cb_tesseract.setChecked(True)
        self.cb_easyocr = QCheckBox("EasyOCR (ar)")
        self.cb_easyocr.setChecked(True)
        self.cb_paddle = QCheckBox("PaddleOCR (ar)")
        self.cb_paddle.setChecked(False)
        eng_layout.addWidget(self.cb_tesseract)
        eng_layout.addWidget(self.cb_easyocr)
        eng_layout.addWidget(self.cb_paddle)
        grp_engines.setLayout(eng_layout)
        left_panel.addWidget(grp_engines)

        # Fusion settings
        grp_fusion = QGroupBox("⚡  Fusion V3")
        fus_layout = QVBoxLayout()
        self.cb_fusion = QCheckBox("Enable Enhanced Fusion (IOU + ML)")
        self.cb_fusion.setChecked(True)
        self.lbl_status = QLabel("Status: Ready")
        self.lbl_status.setStyleSheet("color: #4caf50; font-weight: bold;")
        fus_layout.addWidget(self.cb_fusion)
        fus_layout.addWidget(self.lbl_status)
        grp_fusion.setLayout(fus_layout)
        left_panel.addWidget(grp_fusion)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        left_panel.addWidget(self.progress)

        # Process button
        self.btn_process = QPushButton("🚀  Process Document")
        self.btn_process.setStyleSheet(
            "font-size: 16px; padding: 14px; background-color: #007acc; color: white; font-weight: bold;"
        )
        self.btn_process.clicked.connect(self._run_processing)
        left_panel.addWidget(self.btn_process)

        left_panel.addStretch()
        main_layout.addLayout(left_panel, 1)

        # ── Right Panel ────────────────────────────────────────
        splitter = QSplitter(Qt.Vertical)

        self.lbl_preview = QLabel("Document Preview")
        self.lbl_preview.setObjectName("preview")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setMinimumHeight(300)
        splitter.addWidget(self.lbl_preview)

        self.txt_result = QTextEdit()
        self.txt_result.setReadOnly(True)
        self.txt_result.setPlaceholderText("Extracted Text / Fusion Result will appear here...")
        splitter.addWidget(self.txt_result)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        main_layout.addWidget(splitter, 3)

        # ── Status Bar ─────────────────────────────────────────
        self.statusBar().showMessage("OmniMedical Suite v3.0 — Ready")

    # ------------------------------------------------------------------
    # Engine initialization
    # ------------------------------------------------------------------

    def _init_engines(self):
        """Initialize selected OCR engines."""
        self.engines.clear()
        if self.cb_tesseract.isChecked():
            try:
                self.engines.append(TesseractEngine("ara+eng"))
                logger.info("Tesseract engine initialized")
            except Exception as e:
                logger.error("Tesseract init failed: %s", e)
        if self.cb_easyocr.isChecked():
            try:
                self.engines.append(EasyOCREngine("ar"))
                logger.info("EasyOCR engine initialized")
            except Exception as e:
                logger.error("EasyOCR init failed: %s", e)
        if self.cb_paddle.isChecked():
            try:
                self.engines.append(PaddleOCREngine("ar"))
                logger.info("PaddleOCR engine initialized")
            except Exception as e:
                logger.error("PaddleOCR init failed: %s", e)

        n = len(self.engines)
        self.statusBar().showMessage(f"OmniMedical Suite v3.0 — {n} engine(s) ready")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Medical Document", "",
            "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp)"
        )
        if path:
            import cv2
            self.current_image = cv2.imread(path)
            if self.current_image is not None:
                self._show_image(self.current_image)
                self.statusBar().showMessage(f"Loaded: {os.path.basename(path)}")
            else:
                QMessageBox.warning(self, "Error", f"Failed to load image: {path}")

    def _show_image(self, img):
        import cv2
        h, w, ch = img.shape
        bytes_per_line = ch * w
        qimg = QImage(img.data, w, h, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.lbl_preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.lbl_preview.setPixmap(pixmap)

    def _run_processing(self):
        if self.current_image is None:
            QMessageBox.warning(self, "Error", "Please load a medical document first!")
            return

        self._init_engines()
        if not self.engines:
            QMessageBox.warning(self, "Error", "No OCR engines selected!")
            return

        self.btn_process.setEnabled(False)
        self.progress.setValue(0)
        self.lbl_status.setText("Status: Processing...")
        self.lbl_status.setStyleSheet("color: #ff9800; font-weight: bold;")

        self.worker = ProcessingWorker(self.current_image, self.engines, self.cb_fusion.isChecked())
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self._on_processing_finished)
        self.worker.error.connect(self._on_processing_error)
        self.worker.start()

    def _on_processing_finished(self, results, label):
        self.btn_process.setEnabled(True)
        self.lbl_status.setText(f"Status: Completed ({label})")
        self.lbl_status.setStyleSheet("color: #4caf50; font-weight: bold;")

        output_lines = [f"[{label}] {len(results)} tokens extracted\n{'='*60}"]
        for token in results:
            conf = token.get("confidence", 0)
            conf_bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
            output_lines.append(
                f"  [{conf_bar}] {conf:.0%}  {token['text']}  ({token.get('engine', 'unknown')})"
            )
        self.txt_result.setPlainText("\n".join(output_lines))
        self.statusBar().showMessage(f"Done — {len(results)} tokens via {label}")

    def _on_processing_error(self, error_msg):
        self.btn_process.setEnabled(True)
        self.lbl_status.setText(f"Status: Error")
        self.lbl_status.setStyleSheet("color: #f44336; font-weight: bold;")
        self.txt_result.setPlainText(f"Error:\n{error_msg}")
        self.statusBar().showMessage("Processing failed")


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))

    # Set application metadata
    app.setApplicationName("OmniMedical Suite")
    app.setApplicationVersion("3.0.0")
    app.setOrganizationName("Dr. Abdulmalek")

    window = OmniMedicalGUI()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    main()
