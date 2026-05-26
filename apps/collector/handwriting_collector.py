#!/usr/bin/env python3
"""Handwriting Data Collector Application.

A PyQt5 desktop application for collecting and annotating training data
for Arabic handwriting OCR models. Supports image loading, word segmentation,
quality assessment, manual transcription, and export to HuggingFace-compatible
dataset formats.

Usage:
    python handwriting_collector.py
"""

import base64
import csv
import json
import logging
import os
import sys
from dataclasses import dataclass, field, asdict
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

import cv2
import numpy as np
from PIL import Image, ImageQt
from PyQt5.QtCore import (
    Qt, QSize, QThread, pyqtSignal, QAbstractTableModel, QModelIndex
)
from PyQt5.QtGui import QImage, QPixmap, QIcon, QFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QLineEdit, QFileDialog,
    QScrollArea, QProgressBar, QStatusBar, QGroupBox, QCheckBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QSplitter, QMessageBox,
    QTableView, QHeaderView, QAction, QToolBar, QMenu, QSizePolicy
)

# ---------------------------------------------------------------------------
# Logging configuration
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclass
class WordCrop:
    """Represents a single segmented word crop extracted from a document image.

    Attributes:
        image: The cropped word image as a NumPy BGR array.
        bbox: Bounding box ``(x, y, w, h)`` in the original image coordinates.
        quality_score: Overall quality score in [0, 1] where 1 is best.
        blur_score: Perceptual blur score in [0, 1].
        contrast_score: Contrast quality score in [0, 1].
        transcription: Ground-truth Arabic text entered by the user.
        source: File path or identifier of the source document.
        confidence: OCR confidence for the auto-detected transcription.
        page_index: Zero-based page index (for multi-page sources).
    """

    image: np.ndarray
    bbox: Tuple[int, int, int, int] = (0, 0, 0, 0)
    quality_score: float = 0.0
    blur_score: float = 0.0
    contrast_score: float = 0.0
    transcription: str = ""
    source: str = ""
    confidence: float = 0.0
    page_index: int = 0

    # ------------------------------------------------------------------
    def to_base64(self) -> str:
        """Encode the crop image as a base-64 PNG string.

        Returns:
            Base-64 encoded PNG representation of the word image.
        """
        _, buf = cv2.imencode(".png", self.image)
        return base64.b64encode(buf).decode("utf-8")

    # ------------------------------------------------------------------
    def to_qimage(self) -> QImage:
        """Convert the BGR NumPy image to a :class:`QImage`.

        Returns:
            RGB :class:`QImage` suitable for displaying in Qt widgets.
        """
        rgb = cv2.cvtColor(self.image, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        return QImage(rgb.data.tobytes(), w, h, ch * w, QImage.Format_RGB888)

    # ------------------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        """Serialise the crop to a JSON-serialisable dictionary.

        Returns:
            Dictionary with ``image_base64``, ``text``, ``source``,
            ``confidence``, ``quality_score``, ``blur_score``,
            ``contrast_score`` keys.
        """
        return {
            "image_base64": self.to_base64(),
            "text": self.transcription,
            "source": self.source,
            "confidence": self.confidence,
            "quality_score": self.quality_score,
            "blur_score": self.blur_score,
            "contrast_score": self.contrast_score,
            "bbox": list(self.bbox),
            "page_index": self.page_index,
        }


# ---------------------------------------------------------------------------
# Word Segmenter
# ---------------------------------------------------------------------------
class WordSegmenter:
    """Extract individual word crops from a document image using contour detection.

    The segmenter binarises the input image, detects text contours via
    OpenCV's ``findContours``, and crops each word bounding rectangle.
    """

    def __init__(self, min_area: int = 100, padding: int = 4) -> None:
        """Initialise the segmenter.

        Args:
            min_area: Minimum contour area (in pixels) to consider as a word.
            padding: Pixel padding around each detected bounding box.
        """
        self.min_area = min_area
        self.padding = padding

    # ------------------------------------------------------------------
    def segment(self, image: np.ndarray) -> List[Tuple[np.ndarray, Tuple[int, int, int, int]]]:
        """Segment a document image into word crops.

        Args:
            image: Input document image as BGR NumPy array.

        Returns:
            List of ``(crop_image, bbox)`` tuples sorted left-to-right
            by the x-coordinate of the bounding box.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        _, thresh = cv2.threshold(
            blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
        contours, _ = cv2.findContours(
            thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        h_img, w_img = image.shape[:2]
        crops: List[Tuple[np.ndarray, Tuple[int, int, int, int]]] = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            # Enforce reasonable aspect ratio (reject very tall/wide noise)
            aspect = bw / max(bh, 1)
            if aspect > 30 or aspect < 0.05:
                continue
            # Apply padding while staying inside image bounds
            x1 = max(x - self.padding, 0)
            y1 = max(y - self.padding, 0)
            x2 = min(x + bw + self.padding, w_img)
            y2 = min(y + bh + self.padding, h_img)
            crop = image[y1:y2, x1:x2].copy()
            crops.append((crop, (x, y, bw, bh)))

        # Sort left-to-right (Arabic reads right-to-left but we process L→R)
        crops.sort(key=lambda c: c[1][0])
        return crops


# ---------------------------------------------------------------------------
# Quality Assessor
# ---------------------------------------------------------------------------
class QualityAssessor:
    """Assess the quality of word crop images for OCR training suitability.

    Combines blur detection (Laplacian variance) and contrast analysis
    into a single quality score.
    """

    # ------------------------------------------------------------------
    @staticmethod
    def compute_blur_score(image: np.ndarray) -> float:
        """Compute a perceptual blur score in [0, 1].

        Uses the variance of the Laplacian. A higher variance indicates
        sharper (less blurry) images.

        Args:
            image: BGR word crop image.

        Returns:
            Blur quality score where 1.0 means very sharp.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        # Empirically, values > 500 are sharp; < 50 are very blurry
        score = min(lap_var / 500.0, 1.0)
        return float(score)

    # ------------------------------------------------------------------
    @staticmethod
    def compute_contrast_score(image: np.ndarray) -> float:
        """Compute a contrast quality score in [0, 1].

        Args:
            image: BGR word crop image.

        Returns:
            Contrast score where 1.0 means high contrast (ideal for OCR).
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        std = float(np.std(gray))
        score = min(std / 80.0, 1.0)
        return float(score)

    # ------------------------------------------------------------------
    @classmethod
    def assess(cls, crop: WordCrop) -> WordCrop:
        """Assess and annotate a :class:`WordCrop` with quality metrics.

        Updates ``blur_score``, ``contrast_score``, and ``quality_score``
        in-place on the *crop* object.

        Args:
            crop: The word crop to assess.

        Returns:
            The same crop object with updated quality fields.
        """
        crop.blur_score = cls.compute_blur_score(crop.image)
        crop.contrast_score = cls.compute_contrast_score(crop.image)
        crop.quality_score = 0.6 * crop.blur_score + 0.4 * crop.contrast_score
        return crop


# ---------------------------------------------------------------------------
# Training Data Exporter
# ---------------------------------------------------------------------------
class TrainingDataExporter:
    """Export annotated word crops to various training dataset formats.

    Supported formats:
    * ``jsonl`` — one JSON object per line (default).
    * ``csv``  — comma-separated values.
    * ``huggingface`` — directory with ``metadata.jsonl`` and images,
      compatible with HuggingFace ``datasets.ImageFolder`` loading.
    """

    # ------------------------------------------------------------------
    @staticmethod
    def to_jsonl(crops: List[WordCrop], path: str) -> int:
        """Write crops to a JSONL file.

        Args:
            crops: List of annotated word crops.
            path: Destination file path.

        Returns:
            Number of records written.
        """
        count = 0
        with open(path, "w", encoding="utf-8") as fh:
            for crop in crops:
                if not crop.transcription.strip():
                    continue
                record = crop.to_dict()
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
        logger.info("Exported %d records to %s", count, path)
        return count

    # ------------------------------------------------------------------
    @staticmethod
    def to_csv(crops: List[WordCrop], path: str) -> int:
        """Write crops to a CSV file.

        Args:
            crops: List of annotated word crops.
            path: Destination file path.

        Returns:
            Number of records written.
        """
        fields = [
            "text", "source", "confidence", "quality_score",
            "blur_score", "contrast_score", "image_base64",
        ]
        count = 0
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for crop in crops:
                if not crop.transcription.strip():
                    continue
                record = crop.to_dict()
                writer.writerow({k: record[k] for k in fields})
                count += 1
        logger.info("Exported %d records to %s", count, path)
        return count

    # ------------------------------------------------------------------
    @staticmethod
    def to_huggingface(
        crops: List[WordCrop], output_dir: str
    ) -> Dict[str, int]:
        """Export crops to HuggingFace datasets compatible format.

        Creates ``<output_dir>/images/<idx>.png`` for each crop and a
        ``<output_dir>/metadata.jsonl`` with the corresponding labels.

        Args:
            crops: List of annotated word crops.
            output_dir: Root directory for the dataset.

        Returns:
            Dictionary with ``"annotated"`` and ``"skipped"`` counts.
        """
        img_dir = os.path.join(output_dir, "images")
        os.makedirs(img_dir, exist_ok=True)

        annotated = 0
        skipped = 0
        meta_path = os.path.join(output_dir, "metadata.jsonl")
        with open(meta_path, "w", encoding="utf-8") as fh:
            for idx, crop in enumerate(crops):
                if not crop.transcription.strip():
                    skipped += 1
                    continue
                img_path = os.path.join(img_dir, f"{idx:06d}.png")
                cv2.imwrite(img_path, crop.image)
                meta = {
                    "file_name": f"images/{idx:06d}.png",
                    "text": crop.transcription,
                    "source": crop.source,
                    "confidence": crop.confidence,
                    "quality_score": crop.quality_score,
                }
                fh.write(json.dumps(meta, ensure_ascii=False) + "\n")
                annotated += 1

        logger.info(
            "HuggingFace export complete: %d annotated, %d skipped → %s",
            annotated, skipped, output_dir,
        )
        return {"annotated": annotated, "skipped": skipped}


# ---------------------------------------------------------------------------
# Background Worker Thread
# ---------------------------------------------------------------------------
class SegmentationWorker(QThread):
    """Background thread that performs image segmentation and quality
    assessment to keep the UI responsive.

    Signals:
        finished_signal: Emitted with a list of :class:`WordCrop` objects.
        progress_signal: Emitted with ``(current, total)`` progress ints.
        error_signal: Emitted with an error message string.
    """

    finished_signal = pyqtSignal(list)
    progress_signal = pyqtSignal(int, int)
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        images: List[np.ndarray],
        source: str = "",
        start_page: int = 0,
        parent: Optional[QWidget] = None,
    ) -> None:
        """Initialise the worker.

        Args:
            images: List of document page images (BGR NumPy arrays).
            source: Source identifier / file path.
            start_page: First page index number.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self.images = images
        self.source = source
        self.start_page = start_page

    # ------------------------------------------------------------------
    def run(self) -> None:
        """Execute segmentation on all images."""
        try:
            segmenter = WordSegmenter()
            all_crops: List[WordCrop] = []
            total = len(self.images)

            for i, img in enumerate(self.images):
                raw_crops = segmenter.segment(img)
                for crop_img, bbox in raw_crops:
                    wc = WordCrop(
                        image=crop_img,
                        bbox=bbox,
                        source=self.source,
                        page_index=self.start_page + i,
                    )
                    QualityAssessor.assess(wc)
                    all_crops.append(wc)
                self.progress_signal.emit(i + 1, total)

            self.finished_signal.emit(all_crops)
        except Exception as exc:
            logger.exception("Segmentation failed")
            self.error_signal.emit(str(exc))


# ---------------------------------------------------------------------------
# Word Crop Table Model
# ---------------------------------------------------------------------------
class WordCropTableModel(QAbstractTableModel):
    """Table model that backs the :class:`QTableView` displaying word crops.

    Columns:
        0 — Thumbnail (empty, rendered by delegate)
        1 — Index
        2 — Transcription (editable)
        3 — Quality score
        4 — Blur score
        5 — Contrast score
        6 — Source
    """

    COLUMNS = [
        "الصورة",  # Image
        "#",
        "النص",  # Text
        "الجودة",  # Quality
        "الوضوح",  # Blur
        "التباين",  # Contrast
        "المصدر",  # Source
    ]
    EDITABLE_COLS = {2}  # only transcription column is editable

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._crops: List[WordCrop] = []

    # ------------------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of rows."""
        return len(self._crops)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of columns."""
        return len(self.COLUMNS)

    # ------------------------------------------------------------------
    def data(
        self, index: QModelIndex, role: int = Qt.DisplayRole
    ) -> Any:
        """Return data for the given model index."""
        if not index.isValid() or index.row() >= len(self._crops):
            return None
        col = index.column()
        crop = self._crops[index.row()]
        if role == Qt.DisplayRole or role == Qt.EditRole:
            if col == 0:
                return ""  # Thumbnail rendered via delegate
            if col == 1:
                return index.row() + 1
            if col == 2:
                return crop.transcription
            if col == 3:
                return f"{crop.quality_score:.2f}"
            if col == 4:
                return f"{crop.blur_score:.2f}"
            if col == 5:
                return f"{crop.contrast_score:.2f}"
            if col == 6:
                return os.path.basename(crop.source)
        if role == Qt.TextAlignmentRole and col != 0 and col != 2:
            return Qt.AlignCenter
        return None

    # ------------------------------------------------------------------
    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole
    ) -> Any:
        """Return header labels."""
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.COLUMNS[section]
        return None

    # ------------------------------------------------------------------
    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        """Return item flags — transcription column is editable."""
        default = super().flags(index)
        if index.column() in self.EDITABLE_COLS:
            return default | Qt.ItemIsEditable
        return default

    # ------------------------------------------------------------------
    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        """Set transcription text from the editor."""
        if (
            index.isValid()
            and index.column() in self.EDITABLE_COLS
            and role == Qt.EditRole
        ):
            self._crops[index.row()].transcription = str(value)
            self.dataChanged.emit(index, index, [role])
            return True
        return False

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def set_crops(self, crops: List[WordCrop]) -> None:
        """Replace all crops and reset the model."""
        self.beginResetModel()
        self._crops = crops
        self.endResetModel()

    def add_crops(self, crops: List[WordCrop]) -> None:
        """Append new crops to the end of the list."""
        self.beginInsertRows(
            QModelIndex(), len(self._crops), len(self._crops) + len(crops) - 1
        )
        self._crops.extend(crops)
        self.endInsertRows()

    def get_crops(self) -> List[WordCrop]:
        """Return the full list of crops."""
        return self._crops

    def annotated_count(self) -> int:
        """Return the number of crops with non-empty transcription."""
        return sum(1 for c in self._crops if c.transcription.strip())

    def sort_by_quality(self, ascending: bool = False) -> None:
        """Sort crops by quality score."""
        self.beginResetModel()
        self._crops.sort(key=lambda c: c.quality_score, reverse=not ascending)
        self.endResetModel()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class HandwritingCollectorApp(QMainWindow):
    """Main application window for the Handwriting Data Collector.

    Provides an RTL Arabic interface for loading document images,
    segmenting words, annotating transcriptions, assessing quality,
    and exporting training data.
    """

    def __init__(self) -> None:
        """Set up the UI, layout, and connections."""
        super().__init__()
        self.setWindowTitle("جامع بيانات الخط العربي — Arabic Handwriting Collector")
        self.setMinimumSize(QSize(1200, 800))
        self._apply_rtl_style()

        # State
        self._all_crops: List[WordCrop] = []
        self._worker: Optional[SegmentationWorker] = None
        self._batch_mode = False

        # Build UI
        self._build_toolbar()
        self._build_central_widget()
        self._build_status_bar()
        self._retranslate_ui()

        logger.info("Application initialised.")

    # ==================================================================
    # UI Construction
    # ==================================================================
    def _apply_rtl_style(self) -> None:
        """Apply RTL-aware stylesheet and layout direction."""
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet("""
            QMainWindow { background: #f5f5f5; }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ccc;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                right: 10px;
                padding: 0 4px;
            }
            QPushButton {
                padding: 6px 16px;
                border-radius: 4px;
                border: 1px solid #0078d4;
                background: #0078d4;
                color: #fff;
                font-family: 'Segoe UI', Tahoma, sans-serif;
            }
            QPushButton:hover { background: #106ebe; }
            QPushButton:pressed { background: #005a9e; }
            QPushButton:disabled { background: #ccc; border-color: #aaa; }
            QTableView {
                gridline-color: #ddd;
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 13px;
                alternatingRowColors: true;
            }
            QTableView::item { padding: 4px; }
            QHeaderView::section {
                background: #e8e8e8;
                padding: 4px;
                border: 1px solid #ccc;
                font-weight: bold;
            }
            QLineEdit {
                font-family: 'Segoe UI', Tahoma, sans-serif;
                font-size: 13px;
                padding: 4px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            QProgressBar {
                border: 1px solid #ccc;
                border-radius: 3px;
                text-align: center;
                height: 20px;
            }
            QProgressBar::chunk { background: #0078d4; }
            QComboBox, QSpinBox, QDoubleSpinBox {
                padding: 3px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)

    # ------------------------------------------------------------------
    def _build_toolbar(self) -> None:
        """Construct the top toolbar with action buttons."""
        toolbar = QToolBar("شريط الأدوات")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)

        # Load single image
        self._act_load_image = QAction("📥 فتح صورة", self)
        self._act_load_image.setShortcut("Ctrl+O")
        self._act_load_image.triggered.connect(self._on_load_image)
        toolbar.addAction(self._act_load_image)

        # Load batch
        self._act_load_batch = QAction("📂 فتح مجموعة", self)
        self._act_load_batch.setShortcut("Ctrl+Shift+O")
        self._act_load_batch.triggered.connect(self._on_load_batch)
        toolbar.addAction(self._act_load_batch)

        # Load PDF
        self._act_load_pdf = QAction("📄 فتح PDF", self)
        self._act_load_pdf.triggered.connect(self._on_load_pdf)
        toolbar.addAction(self._act_load_pdf)

        toolbar.addSeparator()

        # Batch correction mode toggle
        self._act_batch_mode = QAction("✏️ وضع التصحيح الجماعي", self)
        self._act_batch_mode.setCheckable(True)
        self._act_batch_mode.setChecked(False)
        self._act_batch_mode.toggled.connect(self._on_toggle_batch_mode)
        toolbar.addAction(self._act_batch_mode)

        toolbar.addSeparator()

        # Sort / filter
        self._act_sort_quality = QAction("🔝 ترتيب بالجودة", self)
        self._act_sort_quality.triggered.connect(self._on_sort_by_quality)
        toolbar.addAction(self._act_sort_quality)

        self._act_filter_low = QAction("⚠️ إخفاء منخفض الجودة", self)
        self._act_filter_low.setCheckable(True)
        self._act_filter_low.setChecked(False)
        self._act_filter_low.toggled.connect(self._on_filter_low_quality)
        toolbar.addAction(self._act_filter_low)

        toolbar.addSeparator()

        # Export actions
        self._act_export_jsonl = QAction("💾 تصدير JSONL", self)
        self._act_export_jsonl.triggered.connect(lambda: self._on_export("jsonl"))
        toolbar.addAction(self._act_export_jsonl)

        self._act_export_csv = QAction("📊 تصدير CSV", self)
        self._act_export_csv.triggered.connect(lambda: self._on_export("csv"))
        toolbar.addAction(self._act_export_csv)

        self._act_export_hf = QAction("🤗 تصدير HuggingFace", self)
        self._act_export_hf.triggered.connect(
            lambda: self._on_export("huggingface")
        )
        toolbar.addAction(self._act_export_hf)

    # ------------------------------------------------------------------
    def _build_central_widget(self) -> None:
        """Construct the central widget layout."""
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)

        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter)

        # --- Left: Word crop table ---
        self._model = WordCropTableModel(self)
        self._table_view = QTableView()
        self._table_view.setModel(self._model)
        self._table_view.setAlternatingRowColors(True)
        self._table_view.setSelectionBehavior(QTableView.SelectRows)
        self._table_view.setEditTriggers(QTableView.DoubleClicked | QTableView.EditKeyPressed)
        self._table_view.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Fixed
        )
        self._table_view.setColumnWidth(0, 120)
        self._table_view.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        self._table_view.verticalHeader().setDefaultSectionSize(64)
        splitter.addWidget(self._table_view)

        # --- Right panel ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        # Quality overview
        quality_group = QGroupBox("📊 إحصائيات الجودة")
        qg_layout = QGridLayout(quality_group)

        self._lbl_total = QLabel("0")
        self._lbl_annotated = QLabel("0")
        self._lbl_avg_quality = QLabel("0.00")
        self._lbl_avg_blur = QLabel("0.00")
        self._lbl_avg_contrast = QLabel("0.00")

        labels = [
            ("إجمالي الكلمات:", self._lbl_total),
            ("المُعَلَّمة:", self._lbl_annotated),
            ("متوسط الجودة:", self._lbl_avg_quality),
            ("متوسط الوضوح:", self._lbl_avg_blur),
            ("متوسط التباين:", self._lbl_avg_contrast),
        ]
        for row, (label_text, value_widget) in enumerate(labels):
            lbl = QLabel(label_text)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value_widget.setAlignment(Qt.AlignCenter)
            qg_layout.addWidget(lbl, row, 0)
            qg_layout.addWidget(value_widget, row, 1)

        right_layout.addWidget(quality_group)

        # Quality threshold slider
        thresh_group = QGroupBox("⚙️ إعدادات الفلترة")
        tg_layout = QVBoxLayout(thresh_group)

        thresh_row = QHBoxLayout()
        thresh_row.addWidget(QLabel("حد أدنى للجودة:"))
        self._spin_quality_min = QDoubleSpinBox()
        self._spin_quality_min.setRange(0.0, 1.0)
        self._spin_quality_min.setSingleStep(0.05)
        self._spin_quality_min.setValue(0.30)
        self._spin_quality_min.valueChanged.connect(self._on_filter_low_quality)
        thresh_row.addWidget(self._spin_quality_min)
        tg_layout.addLayout(thresh_row)

        btn_apply_filter = QPushButton("تطبيق الفلتر")
        btn_apply_filter.clicked.connect(self._apply_quality_filter)
        tg_layout.addWidget(btn_apply_filter)

        right_layout.addWidget(thresh_group)

        # Batch correction panel
        self._batch_group = QGroupBox("✏️ التصحيح الجماعي")
        bg_layout = QVBoxLayout(self._batch_group)

        bg_row = QHBoxLayout()
        bg_row.addWidget(QLabel("نص التصحيح:"))
        self._line_batch_text = QLineEdit()
        self._line_batch_text.setPlaceholderText("أدخل النص الصحيح...")
        bg_row.addWidget(self._line_batch_text)
        bg_layout.addLayout(bg_row)

        btn_apply_batch = QPushButton("تطبيق على المحدد")
        btn_apply_batch.clicked.connect(self._on_batch_correct)
        bg_layout.addWidget(btn_apply_batch)

        self._batch_group.setVisible(False)
        right_layout.addWidget(self._batch_group)

        # Preview area
        preview_group = QGroupBox("🔍 معاينة الكلمة")
        pg_layout = QVBoxLayout(preview_group)
        self._lbl_preview = QLabel("لا يوجد تحديد")
        self._lbl_preview.setAlignment(Qt.AlignCenter)
        self._lbl_preview.setMinimumSize(200, 80)
        self._lbl_preview.setStyleSheet(
            "border: 1px solid #ccc; border-radius: 4px; background: #fff;"
        )
        pg_layout.addWidget(self._lbl_preview)

        preview_info = QHBoxLayout()
        preview_info.addWidget(QLabel("النص:"))
        self._line_preview_text = QLineEdit()
        self._line_preview_text.textChanged.connect(self._on_preview_text_changed)
        preview_info.addWidget(self._line_preview_text)
        pg_layout.addLayout(preview_info)

        right_layout.addWidget(preview_group)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(True)
        right_layout.addWidget(self._progress_bar)

        right_layout.addStretch()
        splitter.addWidget(right_panel)
        splitter.setSizes([800, 350])

        # Signals
        self._table_view.selectionModel().currentRowChanged.connect(
            self._on_row_changed
        )

    # ------------------------------------------------------------------
    def _build_status_bar(self) -> None:
        """Construct the status bar."""
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("جاهز — افتح صورة أو مجموعة صور للبدء")

    # ------------------------------------------------------------------
    def _retranslate_ui(self) -> None:
        """Set Arabic-friendly font on key widgets."""
        font = QFont("Segoe UI", 10)
        self.setFont(font)

    # ==================================================================
    # File Loading
    # ==================================================================
    def _load_image_file(self, path: str) -> Optional[np.ndarray]:
        """Read an image file into a BGR NumPy array.

        Args:
            path: File path to the image.

        Returns:
            BGR NumPy array or ``None`` on failure.
        """
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        if img is None:
            logger.error("Could not read image: %s", path)
            QMessageBox.warning(self, "خطأ", f"لم يتم فتح الصورة:\n{path}")
            return None
        return img

    # ------------------------------------------------------------------
    def _on_load_image(self) -> None:
        """Handle single image loading."""
        path, _ = QFileDialog.getOpenFileName(
            self, "فتح صورة", "",
            "صور (*.png *.jpg *.jpeg *.bmp *.tiff *.webp);;كل الملفات (*)"
        )
        if not path:
            return
        img = self._load_image_file(path)
        if img is None:
            return
        self._start_segmentation([img], source=path)

    # ------------------------------------------------------------------
    def _on_load_batch(self) -> None:
        """Handle batch image loading."""
        paths, _ = QFileDialog.getOpenFileNames(
            self, "فتح مجموعة صور", "",
            "صور (*.png *.jpg *.jpeg *.bmp *.tiff *.webp);;كل الملفات (*)"
        )
        if not paths:
            return
        images: List[np.ndarray] = []
        source_name = os.path.basename(os.path.dirname(paths[0]))
        for p in paths:
            img = self._load_image_file(p)
            if img is not None:
                images.append(img)
        if images:
            self._start_segmentation(images, source=source_name)

    # ------------------------------------------------------------------
    def _on_load_pdf(self) -> None:
        """Handle PDF loading by converting pages to images."""
        path, _ = QFileDialog.getOpenFileName(
            self, "فتح ملف PDF", "", "PDF (*.pdf)"
        )
        if not path:
            return
        images = self._pdf_to_images(path)
        if images:
            self._start_segmentation(images, source=path)

    # ------------------------------------------------------------------
    def _pdf_to_images(self, path: str, dpi: int = 200) -> List[np.ndarray]:
        """Convert a PDF file to a list of page images.

        Falls back gracefully if ``pdf2image`` is not installed.

        Args:
            path: Path to the PDF file.
            dpi: Rendering resolution in dots per inch.

        Returns:
            List of BGR page images.
        """
        try:
            from pdf2image import convert_from_path  # type: ignore
            pil_pages = convert_from_path(path, dpi=dpi)
            images = []
            for page in pil_pages:
                arr = np.array(page)
                bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                images.append(bgr)
            logger.info("Loaded %d pages from %s", len(images), path)
            return images
        except ImportError:
            logger.warning("pdf2image not installed; PDF loading unavailable")
            QMessageBox.information(
                self, "مكتبة مفقودة",
                "لتشغيل PDF، ثبّت المكتبة:\npip install pdf2image\n"
                "وتأكد من تثبيت poppler على النظام.",
            )
            return []

    # ==================================================================
    # Segmentation Pipeline
    # ==================================================================
    def _start_segmentation(
        self, images: List[np.ndarray], source: str = ""
    ) -> None:
        """Kick off background segmentation.

        Args:
            images: List of document page images.
            source: Source file identifier.
        """
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.warning(self, "انتباه", "عملية المعالجة جارية بالفعل.")
            return

        self._progress_bar.setValue(0)
        self._status_bar.showMessage("جارٍ تقسيم الصور إلى كلمات...")
        self._act_load_image.setEnabled(False)
        self._act_load_batch.setEnabled(False)
        self._act_load_pdf.setEnabled(False)

        start_page = len(self._all_crops)
        self._worker = SegmentationWorker(
            images, source=source, start_page=start_page, parent=self
        )
        self._worker.finished_signal.connect(self._on_segmentation_done)
        self._worker.progress_signal.connect(self._on_segmentation_progress)
        self._worker.error_signal.connect(self._on_segmentation_error)
        self._worker.start()

    # ------------------------------------------------------------------
    def _on_segmentation_done(self, crops: List[WordCrop]) -> None:
        """Handle completed segmentation.

        Args:
            crops: List of newly segmented word crops.
        """
        self._all_crops.extend(crops)
        self._model.add_crops(crops)
        self._update_stats()

        self._act_load_image.setEnabled(True)
        self._act_load_batch.setEnabled(True)
        self._act_load_pdf.setEnabled(True)
        self._progress_bar.setValue(100)
        self._status_bar.showMessage(
            f"تم تقسيم {len(crops)} كلمة — الإجمالي: {len(self._all_crops)}"
        )
        logger.info(
            "Segmentation complete: %d new crops, %d total",
            len(crops), len(self._all_crops),
        )

    # ------------------------------------------------------------------
    def _on_segmentation_progress(self, current: int, total: int) -> None:
        """Update progress bar during segmentation.

        Args:
            current: Current page index (1-based).
            total: Total number of pages.
        """
        pct = int(current / max(total, 1) * 100)
        self._progress_bar.setValue(pct)

    # ------------------------------------------------------------------
    def _on_segmentation_error(self, message: str) -> None:
        """Handle segmentation error.

        Args:
            message: Human-readable error description.
        """
        self._act_load_image.setEnabled(True)
        self._act_load_batch.setEnabled(True)
        self._act_load_pdf.setEnabled(True)
        self._status_bar.showMessage("حدث خطأ أثناء التقسيم")
        QMessageBox.critical(self, "خطأ", f"فشل التقسيم:\n{message}")
        logger.error("Segmentation error: %s", message)

    # ==================================================================
    # Table Interaction
    # ==================================================================
    def _on_row_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        """Update the preview panel when the selected row changes.

        Args:
            current: Newly selected model index.
            _previous: Previously selected model index (unused).
        """
        if not current.isValid():
            self._lbl_preview.setText("لا يوجد تحديد")
            self._line_preview_text.clear()
            return

        crops = self._model.get_crops()
        row = current.row()
        if row >= len(crops):
            return

        crop = crops[row]
        pixmap = QPixmap.fromImage(crop.to_qimage())
        scaled = pixmap.scaled(
            200, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._lbl_preview.setPixmap(scaled)
        self._line_preview_text.blockSignals(True)
        self._line_preview_text.setText(crop.transcription)
        self._line_preview_text.blockSignals(False)

    # ------------------------------------------------------------------
    def _on_preview_text_changed(self, text: str) -> None:
        """Propagate preview text changes back to the crop and model.

        Args:
            text: New transcription text.
        """
        idx = self._table_view.currentIndex()
        if not idx.isValid():
            return
        self._model.setData(idx, text, Qt.EditRole)
        self._update_stats()

    # ==================================================================
    # Sorting / Filtering
    # ==================================================================
    def _on_sort_by_quality(self) -> None:
        """Sort all crops by quality score (descending)."""
        self._model.sort_by_quality(ascending=False)
        self._update_stats()
        self._status_bar.showMessage("تم الترتيب حسب الجودة (الأعلى أولاً)")

    # ------------------------------------------------------------------
    def _on_toggle_batch_mode(self, checked: bool) -> None:
        """Toggle batch correction mode visibility.

        Args:
            checked: Whether batch mode is active.
        """
        self._batch_mode = checked
        self._batch_group.setVisible(checked)

    # ------------------------------------------------------------------
    def _on_filter_low_quality(self) -> None:
        """Toggle the low-quality filter."""
        self._apply_quality_filter()

    # ------------------------------------------------------------------
    def _apply_quality_filter(self) -> None:
        """Apply quality threshold filter to the table model."""
        threshold = self._spin_quality_min.value()
        if self._act_filter_low.isChecked():
            filtered = [
                c for c in self._all_crops if c.quality_score >= threshold
            ]
            self._model.set_crops(filtered)
            self._status_bar.showMessage(
                f"عرض {len(filtered)} من {len(self._all_crops)} "
                f"(جودة ≥ {threshold:.2f})"
            )
        else:
            self._model.set_crops(self._all_crops)
            self._status_bar.showMessage(
                f"عرض جميع الكلمات ({len(self._all_crops)})"
            )

    # ------------------------------------------------------------------
    def _on_batch_correct(self) -> None:
        """Apply the batch correction text to all selected rows."""
        text = self._line_batch_text.text().strip()
        if not text:
            QMessageBox.information(self, "تنبيه", "أدخل نص التصحيح أولاً.")
            return
        indexes = self._table_view.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.information(self, "تنبيه", "حدد صفوفاً من الجدول أولاً.")
            return
        for idx in indexes:
            self._model.setData(idx, text, Qt.EditRole)
        self._update_stats()
        self._status_bar.showMessage(
            f"تم تعديل {len(indexes)} كلمة بـ «{text}»"
        )

    # ==================================================================
    # Statistics
    # ==================================================================
    def _update_stats(self) -> None:
        """Recalculate and display quality statistics."""
        crops = self._model.get_crops()
        total = len(crops)
        annotated = sum(1 for c in crops if c.transcription.strip())
        avg_q = np.mean([c.quality_score for c in crops]) if crops else 0
        avg_b = np.mean([c.blur_score for c in crops]) if crops else 0
        avg_c = np.mean([c.contrast_score for c in crops]) if crops else 0

        self._lbl_total.setText(str(total))
        self._lbl_annotated.setText(str(annotated))
        self._lbl_avg_quality.setText(f"{avg_q:.2f}")
        self._lbl_avg_blur.setText(f"{avg_b:.2f}")
        self._lbl_avg_contrast.setText(f"{avg_c:.2f}")

    # ==================================================================
    # Export
    # ==================================================================
    def _on_export(self, fmt: str) -> None:
        """Handle dataset export in the specified format.

        Args:
            fmt: One of ``"jsonl"``, ``"csv"``, ``"huggingface"``.
        """
        crops = self._all_crops
        annotated = [c for c in crops if c.transcription.strip()]
        if not annotated:
            QMessageBox.warning(
                self, "تنبيه",
                "لا توجد كلمات مُعلَّمة للتصدير.\n"
                "قم بتعبئة عمود النص أولاً.",
            )
            return

        exporter = TrainingDataExporter()

        if fmt == "jsonl":
            path, _ = QFileDialog.getSaveFileName(
                self, "حفظ JSONL", "training_data.jsonl",
                "JSONL (*.jsonl);;كل الملفات (*)"
            )
            if not path:
                return
            count = exporter.to_jsonl(annotated, path)
            self._status_bar.showMessage(f"تم تصدير {count} سجل → {path}")

        elif fmt == "csv":
            path, _ = QFileDialog.getSaveFileName(
                self, "حفظ CSV", "training_data.csv",
                "CSV (*.csv);;كل الملفات (*)"
            )
            if not path:
                return
            count = exporter.to_csv(annotated, path)
            self._status_bar.showMessage(f"تم تصدير {count} سجل → {path}")

        elif fmt == "huggingface":
            path = QFileDialog.getExistingDirectory(
                self, "اختر مجلد التصدير"
            )
            if not path:
                return
            result = exporter.to_huggingface(annotated, path)
            self._status_bar.showMessage(
                f"تم تصدير {result['annotated']} سجل إلى {path} "
                f"(تم تخطي {result['skipped']})"
            )
        else:
            logger.warning("Unknown export format: %s", fmt)

    # ==================================================================
    # Cleanup
    # ==================================================================
    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Clean up background threads on window close.

        Args:
            event: Close event.
        """
        if self._worker is not None and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(3000)
        event.accept()


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------
def main() -> None:
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("جامع بيانات الخط العربي")
    app.setOrganizationName("Omni Medical Suite")

    window = HandwritingCollectorApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
