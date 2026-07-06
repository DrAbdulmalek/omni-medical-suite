# desktop/app.py
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QPushButton, QLabel, QFileDialog, QTextEdit, QProgressBar)
from PyQt6.QtCore import Qt
from src.core.ocr_processor import OCRProcessor
from PIL import Image
import cv2

class MedicalOCRApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🩺 Omni Medical OCR Desktop")
        self.setGeometry(100, 100, 1200, 800)
        self.processor = OCRProcessor()
        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.btn_load = QPushButton("📂 تحميل صورة أو PDF")
        self.btn_load.clicked.connect(self.load_file)
        layout.addWidget(self.btn_load)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        self.result = QTextEdit()
        self.result.setReadOnly(True)
        layout.addWidget(self.result)

        self.btn_process = QPushButton("🚀 معالجة")
        self.btn_process.clicked.connect(self.process)
        layout.addWidget(self.btn_process)

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "اختر صورة", "", "Images (*.jpg *.png *.pdf)")
        self.current_path = path

    def process(self):
        if not hasattr(self, 'current_path'):
            return
        self.progress.setValue(50)
        text, entities = self.processor.process(self.current_path)
        self.result.setText(f"النص المصحح:\n{text}\n\nالكيانات:\n{entities}")
        self.progress.setValue(100)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MedicalOCRApp()
    window.show()
    sys.exit(app.exec())