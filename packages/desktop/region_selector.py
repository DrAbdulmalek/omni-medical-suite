#!/usr/bin/env python3
# region_selector.py — محدد منطقة رقم الصفحة

from PyQt5.QtWidgets import (
    QLabel, QRubberBand, QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal, QSize
from PyQt5.QtGui import QPainter, QPen, QColor


class RegionSelectorLabel(QLabel):
    """QLabel يدعم رسم مربع تحديد بالماوس."""
    
    region_selected = pyqtSignal(QRect)  # يُرسل QRect بالبكسل
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rubber = QRubberBand(QRubberBand.Rectangle, self)
        self._origin = QPoint()
        self._current_region = None
        self._active = False
        
    def start_selection(self):
        """تفعيل وضع التحديد."""
        self._active = True
        self.setCursor(Qt.CrossCursor)
        self._rubber.hide()
        self._current_region = None
        
    def cancel_selection(self):
        """إلغاء وضع التحديد."""
        self._active = False
        self.setCursor(Qt.ArrowCursor)
        self._rubber.hide()
        
    def get_region(self):
        """الحصول على المنطقة المحددة."""
        return self._current_region
        
    def paintEvent(self, event):
        """رسم المستطيل الأحمر إذا كانت هناك منطقة محددة."""
        super().paintEvent(event)
        if self._current_region and not self._active:
            painter = QPainter(self)
            pen = QPen(QColor(239, 68, 68), 3, Qt.SolidLine)
            painter.setPen(pen)
            painter.drawRect(self._current_region)
            painter.end()
            
    def mousePressEvent(self, event):
        if not self._active:
            super().mousePressEvent(event)
            return
        self._origin = event.pos()
        self._rubber.setGeometry(QRect(self._origin, QSize()))
        self._rubber.show()
        
    def mouseMoveEvent(self, event):
        if not self._active or not self._rubber.isVisible():
            super().mouseMoveEvent(event)
            return
        self._rubber.setGeometry(QRect(self._origin, event.pos()).normalized())
        
    def mouseReleaseEvent(self, event):
        if not self._active:
            super().mouseReleaseEvent(event)
            return
        self._rubber.hide()
        rect = QRect(self._origin, event.pos()).normalized()
        if rect.width() > 20 and rect.height() > 10:
            self._current_region = rect
            self._active = False
            self.setCursor(Qt.ArrowCursor)
            self.region_selected.emit(rect)
            self.update()  # إعادة الرسم لإظهار المستطيل الأحمر
        else:
            QMessageBox.warning(self, "منطقة صغيرة", "المنطقة صغيرة جداً. حاول مرة أخرى.")


class RegionSelectorDialog(QDialog):
    """حوار لتحديد منطقة رقم الصفحة."""
    
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📍 تحديد منطقة رقم الصفحة")
        self.resize(900, 700)
        
        layout = QVBoxLayout(self)
        
        self.label = RegionSelectorLabel()
        self.label.setPixmap(pixmap)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.region_selected.connect(self._on_region)
        layout.addWidget(self.label)
        
        btn_layout = QHBoxLayout()
        self.btn_select = QPushButton("✚ ابدأ التحديد")
        self.btn_select.setStyleSheet("background:#16a34a;color:white;font-weight:bold;padding:8px;")
        self.btn_select.clicked.connect(self._start)
        
        self.btn_test = QPushButton("🧪 اختبار OCR")
        self.btn_test.setEnabled(False)
        self.btn_test.clicked.connect(self._test_ocr)
        
        self.btn_ok = QPushButton("✅ حفظ المنطقة")
        self.btn_ok.setEnabled(False)
        self.btn_ok.clicked.connect(self.accept)
        
        self.btn_cancel = QPushButton("❌ إلغاء")
        self.btn_cancel.clicked.connect(self.reject)
        
        for b in [self.btn_select, self.btn_test, self.btn_ok, self.btn_cancel]:
            btn_layout.addWidget(b)
        layout.addLayout(btn_layout)
        
        self._region = None
        self._test_result = None
        
    def _start(self):
        self.label.start_selection()
        self.btn_select.setText("⏳ ارسم المربع...")
        self.btn_select.setEnabled(False)
        
    def _on_region(self, rect):
        self._region = rect
        self.btn_select.setText("✚ إعادة التحديد")
        self.btn_select.setEnabled(True)
        self.btn_test.setEnabled(True)
        self.btn_ok.setEnabled(True)
        
    def _test_ocr(self):
        if not self._region:
            return
        # هذا سيُنفذ من الخارج — نرسل إشارة فقط
        self._test_result = self._region
        QMessageBox.information(self, "منطقة محددة", 
            f"المنطقة: x={self._region.x()}, y={self._region.y()}, "
            f"w={self._region.width()}, h={self._region.height()}\n\n"
            f"اضغط 'حفظ المنطقة' للتأكيد.")
        
    def get_region(self):
        """الحصول على المنطقة المحددة كنسب من أبعاد الصورة."""
        return self._region
