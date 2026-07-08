"""OmniMedical Suite — Modern PyQt6 Desktop Application.

A unified desktop GUI for medical document OCR, text editing, and
dictionary lookup.  Replaces the legacy PyQt5 ``medical_doc_gui_v18.py``.

Features
--------
- **OCR Scanner** — upload an image, preview it, run Tesseract / PaddleOCR
  / EasyOCR in a background thread, and display RTL Arabic results.
- **Text Editor** — RTL Arabic text editor with find-and-replace and live
  word count.
- **Dictionary** — live-search medical terms loaded from
  ``medical_terms.json``.
- **Settings** — engine selection, language, confidence threshold, and
  dark-mode toggle.

All OCR calls run inside ``QThread`` so the UI stays responsive.  Missing
OCR engines are detected at import-time and disabled gracefully.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Optional engine detection — graceful fallback
# ---------------------------------------------------------------------------

_HAS_TESSERACT = False
_HAS_PADDLEOCR = False
_HAS_EASYOCR = False
_HAS_JAIS = False
_HAS_OCR_ENSEMBLE = False

try:
    import pytesseract  # type: ignore[import-untyped]
    _HAS_TESSERACT = True
except ImportError:
    pass

try:
    from paddleocr import PaddleOCR  # type: ignore[import-untyped]
    _HAS_PADDLEOCR = True
except ImportError:
    pass

try:
    import easyocr  # type: ignore[import-untyped]
    _HAS_EASYOCR = True
except ImportError:
    pass

# Jais LLM proofreader (GPU required)
_proofreader = None
_jais_ner = None
try:
    import torch  # type: ignore[import-untyped]
    if torch.cuda.is_available():
        from src.llm.proofreader import MedicalProofreader
        from src.ner.jais_ner import JaisNER
        _proofreader = MedicalProofreader()
        _jais_ner = JaisNER()
        _HAS_JAIS = True
except Exception:
    pass

# OCR Ensemble (multi-engine orchestrator)
_ocr_ensemble = None
try:
    from src.ocr.ensemble import OCREnsemble
    _ocr_ensemble = OCREnsemble()
    _HAS_OCR_ENSEMBLE = True
except Exception:
    pass

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_MEDICAL_TERMS_PATH = _PROJECT_ROOT / "medical_terms.json"


# ===========================================================================
# OCR Worker Thread
# ===========================================================================


class OCRWorker(QThread):
    """Run an OCR engine in a background thread.

    Emits ``result_ready(str)`` on success and ``error_occurred(str)`` on
    failure so the UI thread can update widgets safely.
    Supports: Tesseract, PaddleOCR, EasyOCR, Ensemble, Jais Proofread.
    """

    result_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    jais_entities_ready = pyqtSignal(dict)

    def __init__(
        self,
        engine: str,
        image_path: str,
        lang: str,
        confidence: int,
        enable_jais: bool = False,
    ) -> None:
        super().__init__()
        self.engine = engine
        self.image_path = image_path
        self.lang = lang
        self.confidence = confidence
        self.enable_jais = enable_jais

    def run(self) -> None:
        try:
            self.progress_updated.emit(10)
            text = self._execute()
            self.progress_updated.emit(90)

            # Optional Jais LLM proofreading
            if self.enable_jais and _HAS_JAIS and _proofreader is not None:
                self.progress_updated.emit(92)
                try:
                    proof_result = _proofreader.proofread(text)
                    text = proof_result["corrected"]
                    entities = proof_result.get("entities", {})
                    self.jais_entities_ready.emit(entities)
                except Exception as exc:
                    text += f"\n\n[WARNING] Jais proofread failed: {exc}"

            self.progress_updated.emit(100)
            self.result_ready.emit(text)
        except Exception as exc:
            self.error_occurred(str(exc))

    # -- engine dispatchers ---------------------------------------------------

    def _execute(self) -> str:
        dispatchers: dict[str, Any] = {
            "Tesseract": self._run_tesseract,
            "PaddleOCR": self._run_paddleocr,
            "EasyOCR": self._run_easyocr,
            "Ensemble (OCREnsemble)": self._run_ensemble,
        }
        handler = dispatchers.get(self.engine)
        if handler is None:
            return f"[Engine '{self.engine}' is not available]"
        return handler()

    def _run_tesseract(self) -> str:
        if not _HAS_TESSERACT:
            return "[Tesseract (pytesseract) is not installed. Install with: pip install pytesseract]"
        self.progress_updated.emit(30)
        lang_map = {"Arabic": "ara", "English": "eng", "Auto": "ara+eng"}
        tesseract_lang = lang_map.get(self.lang, "ara+eng")
        self.progress_updated.emit(60)
        data: dict[str, Any] = pytesseract.image_to_data(
            self.image_path, lang=tesseract_lang, output_type=pytesseract.Output.DICT
        )
        self.progress_updated.emit(80)
        threshold = self.confidence
        lines: list[str] = []
        last_line_num = -1
        for i, conf_val in enumerate(data["conf"]):
            conf = float(conf_val) if conf_val != "-1" else 0.0
            if conf >= threshold:
                word = str(data["text"][i]).strip()
                if word:
                    line_num = int(data["line_num"][i])
                    if line_num != last_line_num:
                        lines.append(word)
                        last_line_num = line_num
                    else:
                        lines[-1] += " " + word
        return "\n".join(lines) if lines else "[No text detected above confidence threshold]"

    def _run_paddleocr(self) -> str:
        if not _HAS_PADDLEOCR:
            return "[PaddleOCR is not installed. Install with: pip install paddleocr]"
        self.progress_updated.emit(30)
        lang_map = {"Arabic": "ar", "English": "en", "Auto": "ch"}
        paddle_lang = lang_map.get(self.lang, "ch")
        ocr = PaddleOCR(use_angle_cls=True, lang=paddle_lang, show_log=False)
        self.progress_updated.emit(60)
        results = ocr.ocr(self.image_path, cls=True)
        self.progress_updated.emit(80)
        lines: list[str] = []
        if results and results[0]:
            for line_data in results[0]:
                text = line_data[1][0] if isinstance(line_data[1], tuple) else str(line_data[1])
                score = line_data[1][1] if isinstance(line_data[1], tuple) else 0.0
                if score * 100 >= self.confidence:
                    lines.append(str(text))
        return "\n".join(lines) if lines else "[No text detected above confidence threshold]"

    def _run_easyocr(self) -> str:
        if not _HAS_EASYOCR:
            return "[EasyOCR is not installed. Install with: pip install easyocr]"
        self.progress_updated.emit(30)
        lang_map = {"Arabic": ["ar"], "English": ["en"], "Auto": ["ar", "en"]}
        reader = easyocr.Reader(lang_map.get(self.lang, ["ar", "en"]), gpu=False)
        self.progress_updated.emit(60)
        results = reader.readtext(self.image_path)
        self.progress_updated.emit(80)
        lines: list[str] = []
        for _bbox, text, score in results:
            if score * 100 >= self.confidence:
                lines.append(str(text))
        return "\n".join(lines) if lines else "[No text detected above confidence threshold]"

    def _run_ensemble(self) -> str:
        """Run the full OCREnsemble pipeline (all engines + fusion)."""
        if not _HAS_OCR_ENSEMBLE or _ocr_ensemble is None:
            return "[OCREnsemble not available — check imports from src.ocr.ensemble]"
        self.progress_updated.emit(30)
        result = _ocr_ensemble.process_image(self.image_path)
        self.progress_updated.emit(80)
        if isinstance(result, dict):
            best_text = result.get("best_text", "")
            if not best_text:
                return "[Ensemble: no text extracted]"
            return best_text
        return str(result) if result else "[Ensemble: no text extracted]"


# ===========================================================================
# Find & Replace Dialog
# ===========================================================================


class FindReplaceDialog(QDialog):
    """Non-modal find-and-replace dialog for the text editor."""

    def __init__(self, editor: QTextEdit, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.editor = editor
        self.setWindowTitle("Find & Replace — البحث والاستبدال")
        self.setMinimumWidth(420)
        layout = QGridLayout(self)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Search text...")
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with...")

        find_btn = QPushButton("Find Next")
        find_btn.clicked.connect(self._find_next)
        replace_btn = QPushButton("Replace")
        replace_btn.clicked.connect(self._replace)
        replace_all_btn = QPushButton("Replace All")
        replace_all_btn.clicked.connect(self._replace_all)

        layout.addWidget(QLabel("Find:"), 0, 0)
        layout.addWidget(self.find_input, 0, 1)
        layout.addWidget(find_btn, 0, 2)
        layout.addWidget(QLabel("Replace:"), 1, 0)
        layout.addWidget(self.replace_input, 1, 1)
        layout.addWidget(replace_btn, 1, 2)
        layout.addWidget(replace_all_btn, 2, 2)

    def _find_next(self) -> None:
        text = self.find_input.text()
        if not text:
            return
        found = self.editor.find(text)
        if not found:
            QMessageBox.information(self, "Not Found", "No more occurrences found.")

    def _replace(self) -> None:
        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == self.find_input.text():
            cursor.insertText(self.replace_input.text())
        self._find_next()

    def _replace_all(self) -> None:
        old_text = self.editor.toPlainText()
        new_text = old_text.replace(self.find_input.text(), self.replace_input.text())
        self.editor.setPlainText(new_text)


# ===========================================================================
# Tab Widgets
# ===========================================================================


class OCRScannerTab(QWidget):
    """Tab 1 — Upload image, preview, run OCR, show results."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.image_path: str | None = None
        self.worker: OCRWorker | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- image preview ---
        self.preview_label = QLabel("No image loaded — لا توجد صورة")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(220)
        self.preview_label.setStyleSheet("border: 2px dashed #aaa; border-radius: 8px; padding: 20px;")
        layout.addWidget(self.preview_label)

        # --- buttons row ---
        btn_row = QHBoxLayout()
        self.upload_btn = QPushButton("Upload Image — رفع صورة")
        self.upload_btn.clicked.connect(self._open_file)
        self.jais_cb = QCheckBox("Jais LLM Proofread (GPU)")
        self.jais_cb.setEnabled(_HAS_JAIS)
        self.jais_cb.setToolTip(
            "Jais LLM proofreading" if _HAS_JAIS
            else "Jais not available — requires GPU + src.llm.proofreader"
        )
        self.run_btn = QPushButton("Run OCR — تشغيل التعرف")
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._run_ocr)
        self.copy_btn = QPushButton("Copy Results — نسخ النتائج")
        self.copy_btn.setEnabled(False)
        self.copy_btn.clicked.connect(self._copy_results)
        btn_row.addWidget(self.upload_btn)
        btn_row.addWidget(self.jais_cb)
        btn_row.addWidget(self.run_btn)
        btn_row.addWidget(self.copy_btn)
        layout.addLayout(btn_row)

        # --- Jais entities display ---
        entities_group = QGroupBox("Jais NER Entities — الكيانات الطبية")
        entities_layout = QVBoxLayout(entities_group)
        self.entities_edit = QTextEdit()
        self.entities_edit.setReadOnly(True)
        self.entities_edit.setMaximumHeight(120)
        self.entities_edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.entities_edit.setPlaceholderText("Medical entities will appear here after Jais proofread...")
        entities_layout.addWidget(self.entities_edit)
        layout.addWidget(entities_group)

        # --- progress bar ---
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # --- results ---
        self.results_edit = QTextEdit()
        self.results_edit.setReadOnly(True)
        self.results_edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.results_edit.setFont(QFont("sans-serif", 12))
        self.results_edit.setPlaceholderText("OCR results will appear here — ستظهر النتائج هنا")
        layout.addWidget(self.results_edit)

    # -- slots --------------------------------------------------------------

    def _open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Image — افتح صورة",
            "",
            "Images & PDF (*.png *.jpg *.jpeg *.bmp *.tiff *.pdf);;All Files (*)",
        )
        if not path:
            return
        self.image_path = path
        pixmap = QPixmap(path)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)
        self.run_btn.setEnabled(True)
        self.statusBar().showMessage(f"Loaded: {path}")  # type: ignore[attr-defined]

    def _run_ocr(self) -> None:
        if not self.image_path:
            return
        main_win = self.window()
        engine = main_win.settings_tab.engine_combo.currentText()  # type: ignore[attr-defined]
        lang = main_win.settings_tab.lang_combo.currentText()  # type: ignore[attr-defined]
        confidence = main_win.settings_tab.confidence_slider.value()  # type: ignore[attr-defined]
        use_jais = self.jais_cb.isChecked()

        self.run_btn.setEnabled(False)
        self.progress.setValue(0)
        self.results_edit.clear()
        self.entities_edit.clear()

        self.worker = OCRWorker(engine, self.image_path, lang, confidence, enable_jais=use_jais)
        self.worker.progress_updated.connect(self.progress.setValue)
        self.worker.result_ready.connect(self._on_result)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.jais_entities_ready.connect(self._on_jais_entities)
        self.worker.finished.connect(lambda: self.run_btn.setEnabled(True))
        self.worker.start()

    def _on_jais_entities(self, entities: dict) -> None:
        """Display extracted medical entities from Jais NER."""
        lines: list[str] = []
        for entity_type, items in entities.items():
            if isinstance(items, list) and items:
                lines.append(f"{entity_type}: {', '.join(str(i) for i in items)}")
        self.entities_edit.setPlainText("\n".join(lines) if lines else "No entities extracted")

    def _on_result(self, text: str) -> None:
        self.results_edit.setPlainText(text)
        self.copy_btn.setEnabled(True)
        self.statusBar().showMessage("OCR complete — تم التعرف بنجاح")  # type: ignore[attr-defined]

    def _on_error(self, msg: str) -> None:
        self.results_edit.setPlainText(f"[Error] {msg}")
        self.statusBar().showMessage(f"OCR error: {msg}")  # type: ignore[attr-defined]

    def _copy_results(self) -> None:
        from PyQt6.QtWidgets import QApplication as _QApp

        clipboard = _QApp.clipboard()
        clipboard.setText(self.results_edit.toPlainText())
        self.statusBar().showMessage("Copied to clipboard — تم النسخ")  # type: ignore[attr-defined]

    def apply_dark_mode(self, enabled: bool) -> None:
        sheet = ""
        if enabled:
            bg, fg = "#2b2b2b", "#e0e0e0"
            sheet = (
                f"QTextEdit {{ background-color: {bg}; color: {fg}; }}"
                f"QLabel {{ color: {fg}; }}"
                f"QProgressBar {{ background: {bg}; }}"
                f"QGroupBox {{ color: {fg}; border: 1px solid #555; }}"
                f"QCheckBox {{ color: {fg}; }}"
            )
        self.results_edit.setStyleSheet(sheet)
        self.entities_edit.setStyleSheet(sheet)
        self.jais_cb.setStyleSheet(sheet)
        self.preview_label.setStyleSheet(
            f"border: 2px dashed #666; border-radius: 8px; padding: 20px;"
            f"background: {'#1e1e1e' if enabled else 'white'};"
            f"color: {'#e0e0e0' if enabled else 'black'};"
        )


class TextEditorTab(QWidget):
    """Tab 2 — RTL Arabic text editor with find & replace and word count."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # toolbar row
        toolbar = QHBoxLayout()
        find_replace_btn = QPushButton("Find & Replace — بحث واستبدال")
        find_replace_btn.clicked.connect(self._open_find_replace)
        clear_btn = QPushButton("Clear — مسح")
        clear_btn.clicked.connect(lambda: self.editor.clear())
        self.word_count_label = QLabel("Words: 0 | Characters: 0 — كلمات: 0 | أحرف: 0")
        toolbar.addWidget(find_replace_btn)
        toolbar.addWidget(clear_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.word_count_label)
        layout.addLayout(toolbar)

        # editor
        self.editor = QTextEdit()
        self.editor.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.editor.setFont(QFont("sans-serif", 13))
        self.editor.setPlaceholderText("Start typing or paste OCR results here — اكتب أو الصق النتائج هنا")
        self.editor.textChanged.connect(self._update_word_count)
        layout.addWidget(self.editor)

    def _open_find_replace(self) -> None:
        dialog = FindReplaceDialog(self.editor, self)
        dialog.show()

    def _update_word_count(self) -> None:
        text = self.editor.toPlainText().strip()
        words = len(text.split()) if text else 0
        chars = len(text)
        self.word_count_label.setText(f"Words: {words} | Characters: {chars} — كلمات: {words} | أحرف: {chars}")
        self.window().statusBar().showMessage(  # type: ignore[attr-defined]
            f"Words: {words} | Characters: {chars}"
        )

    def apply_dark_mode(self, enabled: bool) -> None:
        if enabled:
            self.editor.setStyleSheet("QTextEdit { background-color: #2b2b2b; color: #e0e0e0; }")
        else:
            self.editor.setStyleSheet("")


class DictionaryTab(QWidget):
    """Tab 3 — Live-search medical terms from ``medical_terms.json``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.terms: dict[str, str] = {}
        self._load_terms()
        self._build_ui()

    def _load_terms(self) -> None:
        if _MEDICAL_TERMS_PATH.exists():
            try:
                with open(_MEDICAL_TERMS_PATH, encoding="utf-8") as fh:
                    self.terms = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                self.terms = {"(error)": str(exc)}
        else:
            self.terms = {"(info)": f"File not found: {_MEDICAL_TERMS_PATH}"}

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search medical term — ابحث عن مصطلح طبي...")
        self.search_input.textChanged.connect(self._filter_terms)
        layout.addWidget(self.search_input)

        self.count_label = QLabel(f"Total terms: {len(self.terms)} — إجمالي المصطلحات: {len(self.terms)}")
        layout.addWidget(self.count_label)

        self.results_list = QListWidget()
        self.results_list.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._populate(list(self.terms.keys()))
        layout.addWidget(self.results_list)

    def _populate(self, keys: list[str]) -> None:
        self.results_list.clear()
        for key in keys:
            value = self.terms.get(key, "")
            item = QListWidgetItem(f"{key}  →  {value}")
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.results_list.addItem(item)
        self.count_label.setText(f"Showing: {len(keys)} / {len(self.terms)}")

    def _filter_terms(self, query: str) -> None:
        q = query.strip().lower()
        if not q:
            self._populate(list(self.terms.keys()))
            return
        matched = [k for k in self.terms if q in k.lower() or q in self.terms[k].lower()]
        self._populate(matched)

    def apply_dark_mode(self, enabled: bool) -> None:
        if enabled:
            sheet = "QListWidget { background-color: #2b2b2b; color: #e0e0e0; } QLineEdit { background: #333; color: #e0e0e0; }"
            self.results_list.setStyleSheet(sheet)
            self.search_input.setStyleSheet(sheet)
        else:
            self.results_list.setStyleSheet("")
            self.search_input.setStyleSheet("")


class SettingsTab(QWidget):
    """Tab 4 — Engine selection, language, confidence threshold, dark mode."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # --- OCR Engine ---
        engine_group = QGroupBox("OCR Engine — محرك التعرف")
        engine_layout = QHBoxLayout(engine_group)
        self.engine_combo = QComboBox()
        engines = ["Tesseract", "PaddleOCR", "EasyOCR", "Ensemble (OCREnsemble)"]
        availability: dict[str, bool] = {
            "Tesseract": _HAS_TESSERACT,
            "PaddleOCR": _HAS_PADDLEOCR,
            "EasyOCR": _HAS_EASYOCR,
            "Ensemble (OCREnsemble)": _HAS_OCR_ENSEMBLE,
        }
        for eng in engines:
            status = "✓" if availability[eng] else "✗ (not installed)"
            self.engine_combo.addItem(f"{eng}  {status}")
            idx = self.engine_combo.count() - 1
            if not availability[eng]:
                model = self.engine_combo.model()
                model.item(idx).setEnabled(False)  # type: ignore[union-attr]
        engine_layout.addWidget(self.engine_combo)
        layout.addWidget(engine_group)

        # --- Language ---
        lang_group = QGroupBox("Language — اللغة")
        lang_layout = QHBoxLayout(lang_group)
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["Arabic", "English", "Auto"])
        lang_layout.addWidget(self.lang_combo)
        layout.addWidget(lang_group)

        # --- Confidence ---
        conf_group = QGroupBox("Confidence Threshold — عتبة الثقة")
        conf_layout = QHBoxLayout(conf_group)
        self.confidence_slider = QSlider(Qt.Orientation.Horizontal)
        self.confidence_slider.setRange(0, 100)
        self.confidence_slider.setValue(30)
        self.confidence_label = QLabel("30%")
        self.confidence_slider.valueChanged.connect(lambda v: self.confidence_label.setText(f"{v}%"))
        conf_layout.addWidget(self.confidence_slider)
        conf_layout.addWidget(self.confidence_label)
        layout.addWidget(conf_group)

        # --- Dark Mode ---
        appearance_group = QGroupBox("Appearance — المظهر")
        appearance_layout = QHBoxLayout(appearance_group)
        self.dark_mode_cb = QCheckBox("Dark Mode — الوضع الداكن")
        self.dark_mode_cb.toggled.connect(self._on_dark_mode_toggled)
        appearance_layout.addWidget(self.dark_mode_cb)
        layout.addWidget(appearance_group)

        layout.addStretch()

        # --- Engine availability info ---
        info_lines: list[str] = []
        if _HAS_TESSERACT:
            info_lines.append("Tesseract: available")
        else:
            info_lines.append("Tesseract: NOT installed (pip install pytesseract)")
        if _HAS_PADDLEOCR:
            info_lines.append("PaddleOCR: available")
        else:
            info_lines.append("PaddleOCR: NOT installed (pip install paddleocr)")
        if _HAS_EASYOCR:
            info_lines.append("EasyOCR: available")
        else:
            info_lines.append("EasyOCR: NOT installed (pip install easyocr)")
        if _HAS_OCR_ENSEMBLE:
            info_lines.append("OCREnsemble (src.ocr.ensemble): available")
        else:
            info_lines.append("OCREnsemble: NOT available")
        if _HAS_JAIS:
            info_lines.append("Jais LLM Proofreader (GPU): available")
        else:
            info_lines.append("Jais LLM: NOT available (requires GPU + transformers + torch)")
        info_label = QLabel("\n".join(info_lines))
        info_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(info_label)

    def _on_dark_mode_toggled(self, checked: bool) -> None:
        main_win = self.window()
        if hasattr(main_win, "apply_dark_mode"):
            main_win.apply_dark_mode(checked)  # type: ignore[attr-defined]

    def apply_dark_mode(self, enabled: bool) -> None:
        if enabled:
            self.setStyleSheet("QGroupBox { color: #e0e0e0; } QComboBox { background: #333; color: #e0e0e0; } QCheckBox { color: #e0e0e0; }")
        else:
            self.setStyleSheet("")


# ===========================================================================
# Main Window
# ===========================================================================


class OmniMedicalMainWindow(QMainWindow):
    """Main application window with menu bar, toolbar, tabs, and status bar."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("OmniMedical Suite — سويت الطب الشامل")
        self.setMinimumSize(960, 700)
        self._build_menu_bar()
        self._build_toolbar()
        self._build_tabs()
        self._build_status_bar()

    # -- construction --------------------------------------------------------

    def _build_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File — ملف")
        open_action = QAction("Open Image — فتح صورة", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._menu_open_image)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction("Exit — خروج", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menu_bar.addMenu("Edit — تحرير")
        find_action = QAction("Find & Replace — بحث واستبدال", self)
        find_action.setShortcut("Ctrl+H")
        find_action.triggered.connect(lambda: FindReplaceDialog(self.text_editor_tab.editor, self).show())
        edit_menu.addAction(find_action)

        # View menu
        view_menu = menu_bar.addMenu("View — عرض")
        self.dark_mode_action = QAction("Toggle Dark Mode — تبديل الوضع الداكن", self)
        self.dark_mode_action.setShortcut("Ctrl+D")
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.toggled.connect(self.apply_dark_mode)
        view_menu.addAction(self.dark_mode_action)

        # Help menu
        help_menu = menu_bar.addMenu("Help — مساعدة")
        about_action = QAction("About — حول", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_toolbar(self) -> None:
        toolbar = self.addToolBar("Quick Actions")
        toolbar.setMovable(False)

        open_tool = QPushButton("📂 Open")
        open_tool.clicked.connect(self._menu_open_image)
        toolbar.addWidget(open_tool)

        run_tool = QPushButton("🔍 Run OCR")
        run_tool.clicked.connect(self.ocr_tab._run_ocr if hasattr(self, "ocr_tab") else lambda: None)
        toolbar.addWidget(run_tool)

        copy_tool = QPushButton("📋 Copy")
        copy_tool.clicked.connect(self.ocr_tab._copy_results if hasattr(self, "ocr_tab") else lambda: None)
        toolbar.addWidget(copy_tool)

    def _build_tabs(self) -> None:
        self.tabs = QTabWidget()
        self.ocr_tab = OCRScannerTab()
        self.text_editor_tab = TextEditorTab()
        self.dictionary_tab = DictionaryTab()
        self.settings_tab = SettingsTab()

        self.settings_tab.dark_mode_cb.toggled.connect(self.dark_mode_action.setChecked)  # type: ignore[union-attr]
        self.dark_mode_action.toggled.connect(self.settings_tab.dark_mode_cb.setChecked)  # type: ignore[union-attr]

        self.tabs.addTab(self.ocr_tab, "OCR Scanner — الماسح")
        self.tabs.addTab(self.text_editor_tab, "Text Editor — المحرر")
        self.tabs.addTab(self.dictionary_tab, "Dictionary — القاموس")
        self.tabs.addTab(self.settings_tab, "Settings — الإعدادات")
        self.setCentralWidget(self.tabs)

    def _build_status_bar(self) -> None:
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready — جاهز")

    # -- slots --------------------------------------------------------------

    def _menu_open_image(self) -> None:
        self.tabs.setCurrentIndex(0)
        self.ocr_tab._open_file()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About OmniMedical Suite — حول",
            "OmniMedical Suite v2.0\n"
            "Modern PyQt6 Desktop Application\n\n"
            "OCR Engines:\n"
            f"  • Tesseract: {'✓' if _HAS_TESSERACT else '✗'}\n"
            f"  • PaddleOCR: {'✓' if _HAS_PADDLEOCR else '✗'}\n"
            f"  • EasyOCR:   {'✓' if _HAS_EASYOCR else '✗'}\n"
            f"  • OCREnsemble: {'✓' if _HAS_OCR_ENSEMBLE else '✗'}\n"
            f"  • Jais LLM:  {'✓ (GPU)' if _HAS_JAIS else '✗ (needs GPU)'}\n",
        )

    def apply_dark_mode(self, enabled: bool) -> None:
        """Apply or remove dark mode across all tabs and the main window."""
        if enabled:
            self.setStyleSheet(
                "QMainWindow { background-color: #1e1e1e; }"
                "QTabWidget::pane { border: 1px solid #555; background: #2b2b2b; }"
                "QTabBar::tab { background: #333; color: #ccc; padding: 8px 16px; }"
                "QTabBar::tab:selected { background: #2b2b2b; color: #fff; }"
                "QPushButton { background: #3c3c3c; color: #e0e0e0; border: 1px solid #555; padding: 5px 12px; border-radius: 4px; }"
                "QPushButton:hover { background: #4a4a4a; }"
                "QPushButton:disabled { color: #666; }"
                "QMenuBar { background: #2b2b2b; color: #e0e0e0; }"
                "QMenuBar::item:selected { background: #3c3c3c; }"
                "QMenu { background: #2b2b2b; color: #e0e0e0; }"
                "QMenu::item:selected { background: #3c3c3c; }"
                "QToolBar { background: #2b2b2b; border: none; }"
                "QStatusBar { background: #1e1e1e; color: #aaa; }"
                "QLabel { color: #e0e0e0; }"
                "QGroupBox { color: #e0e0e0; border: 1px solid #555; }"
                "QSlider::groove:horizontal { background: #555; height: 6px; border-radius: 3px; }"
                "QSlider::handle:horizontal { background: #888; width: 14px; margin: -4px 0; border-radius: 7px; }"
            )
        else:
            self.setStyleSheet("")
        self.ocr_tab.apply_dark_mode(enabled)
        self.text_editor_tab.apply_dark_mode(enabled)
        self.dictionary_tab.apply_dark_mode(enabled)
        self.settings_tab.apply_dark_mode(enabled)


# ===========================================================================
# Entry Point
# ===========================================================================


def main() -> None:
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("OmniMedical Suite")
    window = OmniMedicalMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
