"""
medical_doc_gui_final_v2.py
===========================

PySide6 desktop GUI for scanner_fixer v2.1.

Features
--------
- Drag & drop image loading
- Side-by-side before/after preview
- Single-image processing
- Batch folder processing with JSON report
- ZIP export of batch results
- Manual save dialog

Run:
    python packages/desktop/medical_doc_gui_final_v2.py
"""

from __future__ import annotations

import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

# Make the scanner_fixer package importable when running from repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "packages" / "scanner_fixer" / "src"))

from scanner_fixer import batch_fix_folder, fix_scanned_image  # noqa: E402


IMAGE_FILTER = "Images (*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp);;All Files (*)"


class ScannerFixerApp(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Scanner Fixer v2.1 — OmniMedical")
        self.resize(1400, 900)

        self.original_pixmap: QPixmap | None = None
        self.fixed_pixmap: QPixmap | None = None
        self.batch_results: list[dict] = []

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QVBoxLayout(central)

        # Preview row
        previews = QHBoxLayout()
        self.before_view = QLabel("قبل المعالجة")
        self.after_view = QLabel("بعد المعالجة")
        for lbl in (self.before_view, self.after_view):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(
                "border: 1px dashed #888; background: #f8f8f8; min-width: 600px; min-height: 500px;"
            )
        previews.addWidget(self.before_view)
        previews.addWidget(self.after_view)
        root.addLayout(previews, stretch=1)

        # Buttons
        btn_row = QHBoxLayout()
        load_btn = QPushButton("📂 تحميل صورة")
        process_btn = QPushButton("🔄 معالجة")
        save_btn = QPushButton("💾 حفظ")
        batch_btn = QPushButton("📁 Batch Mode")
        zip_btn = QPushButton("📦 ZIP من آخر Batch")

        load_btn.clicked.connect(self.load_image)
        process_btn.clicked.connect(self.process_image)
        save_btn.clicked.connect(self.save_image)
        batch_btn.clicked.connect(self.batch_mode)
        zip_btn.clicked.connect(self.zip_last_batch)

        for b in (load_btn, process_btn, save_btn, batch_btn, zip_btn):
            btn_row.addWidget(b)
        root.addLayout(btn_row)

        # Progress + status
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.setStatusBar(QStatusBar())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_pixmap(self, target: QLabel, pixmap: QPixmap | None) -> None:
        if pixmap is None:
            target.clear()
            return
        scaled = pixmap.scaled(
            target.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        target.setPixmap(scaled)

    def _pil_to_qpixmap(self, pil_img: Image.Image) -> QPixmap:
        # Pillow >=9: use ImageQt
        qimg = ImageQt.ImageQt(pil_img)
        return QPixmap.fromImage(qimg)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def load_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "اختر صورة", "", IMAGE_FILTER)
        if not path:
            return
        self.original_pixmap = QPixmap(path)
        self._set_pixmap(self.before_view, self.original_pixmap)
        self.after_view.clear()
        self.fixed_pixmap = None
        self.statusBar().showMessage(f"Loaded: {path}", 4000)

    def process_image(self) -> None:
        if self.original_pixmap is None:
            QMessageBox.warning(self, "تنبيه", "حمّل صورة أولاً.")
            return

        # Convert QPixmap -> PIL.Image (no deprecated Image.fromqpixmap)
        qimg = self.original_pixmap.toImage()
        pil_in = ImageQt.fromqimage(qimg).convert("RGB")

        try:
            fixed_rgb, meta = fix_scanned_image(pil_in)
        except Exception as exc:
            QMessageBox.critical(self, "خطأ", f"فشلت المعالجة:\n{exc}")
            return

        pil_out = Image.fromarray(fixed_rgb, mode="RGB")
        self.fixed_pixmap = self._pil_to_qpixmap(pil_out)
        self._set_pixmap(self.after_view, self.fixed_pixmap)
        self.statusBar().showMessage(f"تم التصحيح — {meta}", 6000)

    def save_image(self) -> None:
        if self.fixed_pixmap is None:
            QMessageBox.warning(self, "تنبيه", "لا توجد نتيجة للحفظ.")
            return
        default = f"fixed_{datetime.now():%Y%m%d_%H%M%S}.png"
        path, _ = QFileDialog.getSaveFileName(self, "حفظ الصورة", default, "PNG (*.png);;JPEG (*.jpg)")
        if not path:
            return
        if self.fixed_pixmap.save(path):
            QMessageBox.information(self, "نجح", f"تم الحفظ:\n{path}")
        else:
            QMessageBox.critical(self, "خطأ", f"تعذّر الحفظ:\n{path}")

    def batch_mode(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "اختر مجلد صور")
        if not folder:
            return

        out_dir = Path(folder) / "_fixed"
        self.progress.setVisible(True)
        self.progress.setRange(0, 0)  # indeterminate

        try:
            self.batch_results = batch_fix_folder(folder, output_dir=out_dir)
        except Exception as exc:
            QMessageBox.critical(self, "خطأ", f"Batch failed:\n{exc}")
            return
        finally:
            self.progress.setVisible(False)

        # Save JSON report next to the folder
        report_path = Path(folder) / f"batch_report_{datetime.now():%Y%m%d_%H%M%S}.json"
        report_path.write_text(json.dumps(self.batch_results, indent=2, ensure_ascii=False), encoding="utf-8")

        n_ok = sum(1 for r in self.batch_results if r.get("status") == "success")
        self.statusBar().showMessage(
            f"Batch: {n_ok}/{len(self.batch_results)} نجح — تقرير: {report_path}", 8000
        )
        QMessageBox.information(
            self, "Batch",
            f"تم معالجة {len(self.batch_results)} صورة ({n_ok} نجح).\nالنتائج: {out_dir}\nالتقرير: {report_path}",
        )

    def zip_last_batch(self) -> None:
        if not self.batch_results:
            QMessageBox.warning(self, "تنبيه", "لا يوجد batch سابق.")
            return
        # Find the _fixed dir referenced by any result's output_path
        fixed_dirs: set[Path] = set()
        for r in self.batch_results:
            op = r.get("output_path")
            if op:
                fixed_dirs.add(Path(op).parent)
        if not fixed_dirs:
            QMessageBox.warning(self, "تنبيه", "لا توجد ملفات مُصحَّحة لتنظيمها في ZIP.")
            return

        default = f"batch_fixed_{datetime.now():%Y%m%d_%H%M%S}.zip"
        zip_path, _ = QFileDialog.getSaveFileName(self, "حفظ ZIP", default, "ZIP (*.zip)")
        if not zip_path:
            return

        count = 0
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for d in fixed_dirs:
                for f in d.iterdir():
                    if f.is_file():
                        z.write(f, arcname=f.name)
                        count += 1
        QMessageBox.information(self, "ZIP", f"تم إنشاء:\n{zip_path}\n({count} ملف)")


def main() -> int:
    app = QApplication(sys.argv)
    win = ScannerFixerApp()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
