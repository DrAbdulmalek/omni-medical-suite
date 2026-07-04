#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🏥 معالج الوثائق الطبية الذكي V8 - الإصدار المستقر
المميزات:
✅ نظام تعلم آلي متكامل يحفظ كل إجراء
✅ ضبط تلقائي دقيق للميلان عند فتح كل صورة
✅ أزرار + و - للضبط الدقيق
✅ خوارزمية قص ذكي محسنة
✅ حفظ تلقائي لجميع الإجراءات في JSON/CSV
✅ أداء محسن وسريع
"""
import sys, os, json, csv, time
from pathlib import Path
from datetime import datetime
from collections import deque
import cv2
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QImage, QFont, QKeySequence, QColor, QIcon
from PyQt5.QtWidgets import QShortcut

# الثوابت
IMG_EXT = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".webp"}
LOG_FILE = Path("processing_log.txt")
LEARN_DB = Path("learning_database.json")
ACTION_LOG = Path("action_history.csv")
MAX_PREVIEW = 1200  # حد أقصى للمعاينة
UNDO_LIMIT = 20

# ═══════════════════════════════════════════════
# 1. نظام التعلم الآلي المتقدم
# ═══════════════════════════════════════════════
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
            except: self.database = []
    
    def save(self):
        with open(LEARN_DB, 'w', encoding='utf-8') as f:
            json.dump(self.database, f, ensure_ascii=False, indent=2)
    
    def extract_features(self, img):
        """استخراج ميزات الصورة للتعلم"""
        if img is None: return {}
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
        if len(self.database) < 3: return None, 0.0
        
        current_features = self.extract_features(current_img)
        best_sim, best_params = 0.0, None
        
        # البحث في السجلات الناجحة فقط من نفس نوع الإجراء
        for rec in self.database:
            if not rec.get('success', True): continue
            if rec.get('action') != action_type: continue
            
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
    
    def export_csv(self, path):
        """تصدير قاعدة البيانات لـ CSV"""
        if not self.database: return
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=self.database[0].keys())
            writer.writeheader()
            writer.writerows(self.database)

# ═══════════════════════════════════════════════
# 2. دوال معالجة الصور المحسنة
# ═══════════════════════════════════════════════
def auto_detect_skew_fast(img, max_angle=10, step=0.5):
    """كشف سريع ودقيق للميلان"""
    if img is None: return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    # تصغير الصورة للسرعة
    h, w = gray.shape
    if w > 800:
        scale = 800 / w
        gray = cv2.resize(gray, (int(w*scale), int(h*scale)))
    
    gray = cv2.equalizeHist(gray)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    best_score, best_angle = -1.0, 0.0
    h, w = binary.shape
    center = (w//2, h//2)
    
    for angle in np.arange(-max_angle, max_angle + step, step):
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rot = cv2.warpAffine(binary, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        # حساب التباين في الإسقاط الأفقي
        score = float(np.var(np.sum(rot, axis=1)))
        if score > best_score:
            best_score, best_angle = score, float(angle)
    
    return best_angle

def smart_crop_v2(img, padding=10, dark_threshold=200):
    """قص ذكي محسن يكتشف حدود النص بدقة"""
    if img is None: return (0, 0, 0, 0)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    h, w = gray.shape
    
    # عتبة ذكية
    _, binary = cv2.threshold(gray, dark_threshold, 255, cv2.THRESH_BINARY_INV)
    
    # إزالة الضوضاء
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    # إيجاد إحداثيات النص
    coords = cv2.findNonZero(binary)
    if coords is None: return (0, 0, 0, 0)
    
    x, y, cw, ch = cv2.boundingRect(coords)
    
    # إضافة هوامش آمنة
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(w, x + cw + padding)
    y2 = min(h, y + ch + padding)
    
    # تحويل إلى هوامش قص
    return (x1, y1, w - x2, h - y2)

def apply_all_corrections(img, params):
    """تطبيق جميع التصحيحات دفعة واحدة"""
    if img is None: return img
    out = img.copy()
    h, w = out.shape[:2]
    
    # 1. تطبيق الميلان
    angle = params.get('skew_angle', 0.0)
    if abs(angle) > 0.1:
        M = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
        out = cv2.warpAffine(out, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(255,255,255))
    
    # 2. تطبيق القص
    crop = params.get('crop', (0,0,0,0))
    if any(crop):
        l, t, r, b = crop
        h2, w2 = out.shape[:2]
        out = out[t:h2-b, l:w2-r]
    
    # 3. القلب الأفقي
    if params.get('flip_h', False):
        out = cv2.flip(out, 1)
    
    # 4. تحسين الوضوح
    if params.get('sharpen', False):
        kernel = np.array([[0,-1,0],[-1,5,-1],[0,-1,0]], dtype=np.float32)
        out = cv2.filter2D(out, -1, kernel)
    
    return out

# ═══════════════════════════════════════════════
# 3. خيوط المعالجة الخلفية
# ═══════════════════════════════════════════════
class ProcessingWorker(QThread):
    """خيط معالجة غير متزامن"""
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, int)
    
    def __init__(self, images, params, learner):
        super().__init__()
        self.images = images
        self.params = params
        self.learner = learner
        self._stop = False
    
    def stop(self):
        self._stop = True
    
    def run(self):
        for i, img_path in enumerate(self.images):
            if self._stop: break
            try:
                img = cv2.imread(str(img_path))
                if img is None: continue
                
                # تطبيق التصحيحات
                processed = apply_all_corrections(img, self.params)
                
                # حساب الجودة
                quality = float(cv2.Laplacian(
                    cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY), cv2.CV_64F
                ).var())
                
                # حفظ في قاعدة التعلم
                self.learner.add_action(img, 'batch_process', self.params, quality)
                
                # حفظ النتيجة
                out_path = Path('processed') / f"doc_{i+1:04d}.png"
                out_path.parent.mkdir(exist_ok=True)
                cv2.imwrite(str(out_path), processed)
                
                self.progress.emit(i+1, len(self.images))
                
            except Exception as e:
                print(f"Error processing {img_path}: {e}")

# ═══════════════════════════════════════════════
# 4. الواجهة الرئيسية
# ═══════════════════════════════════════════════
class MedicalDocAppV8(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🏥 معالج الوثائق الطبية الذكي V8")
        self.resize(1300, 800)
        self.setFont(QFont("Noto Sans Arabic", 10))
        self.setAcceptDrops(True)
        
        # الحالة
        self.images = []
        self.current_idx = 0
        self.current_img = None
        self.params = {
            'skew_angle': 0.0,
            'crop': (0, 0, 0, 0),
            'flip_h': False,
            'sharpen': False
        }
        self.learner = SmartLearner()
        self.action_history = []
        self.processed_count = 0
        self.skipped_count = 0
        
        self._build_ui()
        self._connect_signals()
        self._auto_correct_skew_enabled = True
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0

        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0

        
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        # الشريط العلوي
        top_bar = QHBoxLayout()
        self.lbl_status = QLabel("📁 افتح مجلداً أو اسحب ملفات هنا")
        self.lbl_index = QLabel("0 / 0")
        self.lbl_index.setStyleSheet("font-weight:bold;font-size:11pt;")
        self.btn_open = QPushButton("📂 فتح")
        self.btn_export_csv = QPushButton("📤 تصدير CSV")
        self.btn_export_learn = QPushButton("💾 تصدير تعلّم")
        self.btn_import_learn = QPushButton("📥 استيراد تعلّم")
        
        for w in [self.lbl_status, None, self.lbl_index, self.btn_open, 
                  self.btn_export_csv, self.btn_export_learn, self.btn_import_learn]:
            if w is None: top_bar.addStretch()
            else: top_bar.addWidget(w)
        main_layout.addLayout(top_bar)
        
        # المنطقة الوسطى
        mid_splitter = QSplitter(Qt.Horizontal)
        
        # اللوحة اليسرى - المعاينة
        left_w = QWidget()
        left_layout = QVBoxLayout(left_w)
        
        # منطقة المعاينة القابلة للتمرير
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setAlignment(Qt.AlignCenter)
        self.preview_scroll.setStyleSheet("QScrollArea{border:2px dashed #94a3b8;border-radius:8px;background:#f0f4f8;}")
        
        self.lbl_preview = QLabel("⏳ بانتظار التحميل...")
        self.lbl_preview.setAlignment(Qt.AlignCenter)
        self.lbl_preview.setMinimumSize(400, 300)
        self.preview_scroll.setWidget(self.lbl_preview)
        left_layout.addWidget(self.preview_scroll)
        
        # أزرار التحكم الرئيسية
        ctrl_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 تحديث")
        self.btn_crop = QPushButton("✂️ قص ذكي")
        self.btn_compare = QPushButton("🔍 مقارنة")
        self.btn_save = QPushButton("✅ حفظ")
        self.btn_skip = QPushButton("⏭️ تخطي")
        self.btn_batch = QPushButton("🤖 معالجة دفعة")
        
        for b in [self.btn_refresh, self.btn_crop, self.btn_compare, 
                  self.btn_save, self.btn_skip, self.btn_batch]:
            ctrl_layout.addWidget(b)
        left_layout.addLayout(ctrl_layout)
        
        # أزرار الضبط الدقيق + و -
        precision_layout = QHBoxLayout()
        precision_layout.addWidget(QLabel("📐 ضبط دقيق:"))
        
        self.btn_skew_minus = QPushButton("➖")
        self.btn_skew_minus.setFixedWidth(40)
        self.lbl_skew = QLabel("0.0°")
        self.lbl_skew.setFixedWidth(50)
        self.lbl_skew.setAlignment(Qt.AlignCenter)
        self.btn_skew_plus = QPushButton("➕")
        self.btn_zoom_out = QPushButton("🔍-")
        self.btn_zoom_out.setFixedSize(35, 32)
        self.btn_zoom_in = QPushButton("🔍+")
        self.btn_zoom_in.setFixedSize(35, 32)
        self.btn_zoom_fit = QPushButton("⛶ ملاءمة")
        self.btn_zoom_fit.setFixedHeight(32)
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(45)
        self.lbl_zoom.setAlignment(Qt.AlignCenter)

        # أزرار التكبير والتصغير
        self.btn_zoom_out = QPushButton("🔍-")
        self.btn_zoom_out.setFixedSize(35, 32)
        self.btn_zoom_in = QPushButton("🔍+")
        self.btn_zoom_in.setFixedSize(35, 32)
        self.btn_zoom_fit = QPushButton("⛶ ملاءمة")
        self.btn_zoom_fit.setFixedHeight(32)
        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(45)
        self.lbl_zoom.setAlignment(Qt.AlignCenter)

        self.btn_skew_plus.setFixedWidth(40)
        
        precision_layout.addWidget(self.btn_skew_minus)
        precision_layout.addWidget(self.lbl_skew)
        precision_layout.addWidget(self.btn_skew_plus)
        precision_layout.addStretch()
        
        self.chk_auto_skew = QCheckBox("🔄 تصحيح تلقائي عند الفتح")
        self.chk_auto_skew.setChecked(True)
        precision_layout.addWidget(self.chk_auto_skew)
        left_layout.addLayout(precision_layout)
        
        # اللوحة اليمنى - الإعدادات والسجل
        right_w = QWidget()
        right_w.setFixedWidth(420)
        right_layout = QVBoxLayout(right_w)
        
        tabs = QTabWidget()
        
        # تبويب الإعدادات
        settings_tab = QWidget()
        settings_layout = QVBoxLayout(settings_tab)
        
        # إعدادات القص
        crop_group = QGroupBox("✂️ هوامش القص (بكسل)")
        crop_form = QFormLayout()
        self.sp_crop_t = QSpinBox(); self.sp_crop_t.setRange(0, 2000); self.sp_crop_t.setValue(20)
        self.sp_crop_b = QSpinBox(); self.sp_crop_b.setRange(0, 2000); self.sp_crop_b.setValue(20)
        self.sp_crop_l = QSpinBox(); self.sp_crop_l.setRange(0, 2000); self.sp_crop_l.setValue(20)
        self.sp_crop_r = QSpinBox(); self.sp_crop_r.setRange(0, 2000); self.sp_crop_r.setValue(20)
        crop_form.addRow("علوي:", self.sp_crop_t)
        crop_form.addRow("سفلي:", self.sp_crop_b)
        crop_form.addRow("أيسر:", self.sp_crop_l)
        crop_form.addRow("أيمن:", self.sp_crop_r)
        crop_group.setLayout(crop_form)
        settings_layout.addWidget(crop_group)
        
        # إعدادات إضافية
        extras_group = QGroupBox("⚙️ إعدادات إضافية")
        extras_layout = QVBoxLayout(extras_group)
        self.chk_flip = QCheckBox("↔️ قلب أفقي")
        self.chk_sharpen = QCheckBox("🔆 تحسين الوضوح")
        extras_layout.addWidget(self.chk_flip)
        extras_layout.addWidget(self.chk_sharpen)
        settings_layout.addWidget(extras_group)
        settings_layout.addStretch()
        
        # تبويب السجل والإحصائيات
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        
        stats_group = QGroupBox("📊 إحصائيات")
        stats_layout = QFormLayout()
        self.lbl_total = QLabel("0")
        self.lbl_processed = QLabel("0")
        self.lbl_skipped = QLabel("0")
        self.lbl_learned = QLabel("0")
        stats_layout.addRow("إجمالي:", self.lbl_total)
        stats_layout.addRow("معالجة:", self.lbl_processed)
        stats_layout.addRow("تخطي:", self.lbl_skipped)
        stats_layout.addRow("سجلات تعلّم:", self.lbl_learned)
        stats_group.setLayout(stats_layout)
        log_layout.addWidget(stats_group)
        
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        self.txt_log.setStyleSheet("background:#0f172a;color:#94a3b8;font-family:monospace;font-size:9pt;")
        log_layout.addWidget(QLabel("📝 سجل العمليات:"))
        log_layout.addWidget(self.txt_log)
        
        tabs.addTab(settings_tab, "⚙️ الإعدادات")
        tabs.addTab(log_tab, "📝 السجل")
        right_layout.addWidget(tabs)
        
        mid_splitter.addWidget(left_w)
        mid_splitter.addWidget(right_w)
        mid_splitter.setSizes([880, 420])
        main_layout.addWidget(mid_splitter, stretch=1)
        
        # شريط التقدم
        self.progress = QProgressBar()
        self.progress.setTextVisible(True)
        self.progress.setFixedHeight(18)
        main_layout.addWidget(self.progress)
    
    def _connect_signals(self):
        self.btn_open.clicked.connect(self._open_folder)
        self.btn_refresh.clicked.connect(self._update_preview)
        self.btn_crop.clicked.connect(self._smart_crop)
        self.btn_compare.clicked.connect(self._show_compare)
        self.btn_save.clicked.connect(self._save_current)
        self.btn_skip.clicked.connect(self._skip_current)
        self.btn_batch.clicked.connect(self._batch_process)
        self.btn_export_csv.clicked.connect(self._export_csv)
        self.btn_export_learn.clicked.connect(self._export_learn)
        self.btn_import_learn.clicked.connect(self._import_learn)
        
        # أزرار الضبط الدقيق
        self.btn_skew_plus.clicked.connect(lambda: self._adjust_skew(0.5))
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_fit.clicked.connect(self.zoom_fit)

        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_fit.clicked.connect(self.zoom_fit)

        self.btn_skew_minus.clicked.connect(lambda: self._adjust_skew(-0.5))
        
        # ربط عناصر الإعدادات
        for w in [self.sp_crop_t, self.sp_crop_b, self.sp_crop_l, self.sp_crop_r]:
            w.valueChanged.connect(self._on_param_change)
        self.chk_flip.toggled.connect(self._on_param_change)
        self.chk_sharpen.toggled.connect(self._on_param_change)
        
    def _adjust_skew(self, delta):
        """ضبط دقيق للميلان"""
        self.params['skew_angle'] = round(self.params['skew_angle'] + delta, 1)
        self.lbl_skew.setText(f"{self.params['skew_angle']:+.1f}°")
        self._update_preview()
        self._log_action(f"ضبط ميلان: {delta:+.1f}°")
    
    def _on_param_change(self):
        """تحديث المعاينة عند تغيير أي معلمة"""
        self.params['crop'] = (
            self.sp_crop_l.value(),
            self.sp_crop_t.value(),
            self.sp_crop_r.value(),
            self.sp_crop_b.value()
        )
        self.params['flip_h'] = self.chk_flip.isChecked()
        self.params['sharpen'] = self.chk_sharpen.isChecked()
        QTimer.singleShot(200, self._update_preview)
    
    def _update_preview(self):
        """تحديث منطقة المعاينة"""
        if self.current_img is None: return
        
        processed = apply_all_corrections(self.current_img, self.params)
        h, w = processed.shape[:2]
        
        # تحجيم للمعاينة
        scale = min(MAX_PREVIEW/max(w,1), MAX_PREVIEW/max(h,1))
        nw, nh = int(w*scale), int(h*scale)
        preview = cv2.resize(processed, (nw, nh), interpolation=cv2.INTER_AREA)
        
        rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, nw, nh, nw*3, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg)
        
        self.lbl_preview.setPixmap(pix)
        self.lbl_preview.setText("")
        self.lbl_preview.adjustSize()
    
    def _smart_crop(self):
        """تنفيذ القص الذكي"""
        if self.current_img is None: return
        crop = smart_crop_v2(self.current_img, padding=10)
        self.sp_crop_l.setValue(crop[0])
        self.sp_crop_t.setValue(crop[1])
        self.sp_crop_r.setValue(crop[2])
        self.sp_crop_b.setValue(crop[3])
        self.params['crop'] = crop
        self._update_preview()
        self._log_action(f"قص ذكي: {crop}")
        
        # حفظ في قاعدة التعلم
        quality = float(cv2.Laplacian(
            cv2.cvtColor(self.current_img, cv2.COLOR_BGR2GRAY), cv2.CV_64F
        ).var())
        self.learner.add_action(self.current_img, 'smart_crop', {'crop': crop}, quality)
    
    def _auto_correct_skew(self):
        """تصحيح تلقائي للميلان عند فتح الصورة"""
        if not self.chk_auto_skew.isChecked() or self.current_img is None: return
        
        self.lbl_status.setText("⏳ جاري تصحيح الميلان تلقائياً...")
        QApplication.processEvents()
        
        angle = auto_detect_skew_fast(self.current_img)
        self.params['skew_angle'] = angle
        self.lbl_skew.setText(f"{angle:+.1f}°")
        
        self._update_preview()
        self._log_action(f"تصحيح تلقائي للميلان: {angle:+.2f}°")
        
        # حفظ في قاعدة التعلم
        quality = float(cv2.Laplacian(
            cv2.cvtColor(self.current_img, cv2.COLOR_BGR2GRAY), cv2.CV_64F
        ).var())
        self.learner.add_action(self.current_img, 'auto_skew', {'angle': angle}, quality)
    
    def _open_folder(self):
        """فتح مجلد صور"""
        folder = QFileDialog.getExistingDirectory(self, "اختر مجلد الصور")
        if not folder: return
        
        self.images = sorted([
            Path(folder) / f for f in os.listdir(folder)
            if Path(f).suffix.lower() in IMG_EXT
        ])
        
        if not self.images:
            QMessageBox.warning(self, "تنبيه", "لم يتم العثور على صور صالحة")
            return
        
        self.current_idx = 0
        self.processed_count = 0
        self.skipped_count = 0
        self.progress.setMaximum(len(self.images))
        self.lbl_total.setText(str(len(self.images)))
        self._load_current()
    
    def _load_current(self):
        """تحميل الصورة الحالية"""
        if not self.images or self.current_idx >= len(self.images): return
        
        path = self.images[self.current_idx]
        self.current_img = cv2.imread(str(path))
        
        if self.current_img is None:
            self._log_action(f"❌ فشل قراءة: {path.name}")
            return
        
        self.lbl_index.setText(f"{self.current_idx+1} / {len(self.images)}")
        self.progress.setValue(self.current_idx)
        
        # اقتراح من قاعدة التعلم
        suggested, sim = self.learner.suggest_params(self.current_img, 'load')
        if suggested and sim > 0.9:
            self.params.update(suggested)
            self._log_action(f"🤖 اقتراح مستفاد ({sim*100:.0f}%)")
        
        # تحديث الواجهة
        self.sp_crop_l.setValue(self.params['crop'][0])
        self.sp_crop_t.setValue(self.params['crop'][1])
        self.sp_crop_r.setValue(self.params['crop'][2])
        self.sp_crop_b.setValue(self.params['crop'][3])
        self.lbl_skew.setText(f"{self.params['skew_angle']:+.1f}°")
        self.chk_flip.setChecked(self.params['flip_h'])
        self.chk_sharpen.setChecked(self.params['sharpen'])
        
        # تصحيح تلقائي للميلان
        self._auto_correct_skew()
        self._update_preview()
    
    def _save_current(self):
        """حفظ الصورة الحالية مع جميع التصحيحات"""
        if self.current_img is None: return
        
        processed = apply_all_corrections(self.current_img, self.params)
        out_path = Path('processed') / f"doc_{self.current_idx+1:04d}.png"
        out_path.parent.mkdir(exist_ok=True)
        cv2.imwrite(str(out_path), processed)
        
        self.processed_count += 1
        self.lbl_processed.setText(str(self.processed_count))
        
        # حساب الجودة وحفظ في التعلم
        quality = float(cv2.Laplacian(
            cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY), cv2.CV_64F
        ).var())
        self.learner.add_action(self.current_img, 'save', self.params, quality)
        
        self._log_action(f"✅ حفظ: {out_path.name} (جودة: {quality:.0f})")
        self._next_image()
    
    def _skip_current(self):
        """تخطي الصورة الحالية"""
        if self.current_img is None: return
        
        out_path = Path('skipped') / f"skip_{self.current_idx+1:04d}.png"
        out_path.parent.mkdir(exist_ok=True)
        cv2.imwrite(str(out_path), self.current_img)
        
        self.skipped_count += 1
        self.lbl_skipped.setText(str(self.skipped_count))
        self._log_action(f"⏭️ تخطي: {out_path.name}")
        self._next_image()
    
    def _batch_process(self):
        """معالجة جميع الصور المتبقية دفعة واحدة"""
        if not self.images or self.current_idx >= len(self.images): return
        
        reply = QMessageBox.question(
            self, "تأكيد", 
            f"هل تريد معالجة {len(self.images)-self.current_idx} صورة متبقية بالإعدادات الحالية؟",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.No: return
        
        # بدء المعالجة في الخيط الخلفي
        self.worker = ProcessingWorker(
            self.images[self.current_idx:], 
            self.params, 
            self.learner
        )
        self.worker.progress.connect(self._on_batch_progress)
        self.worker.finished.connect(self._on_batch_finished)
        self.worker.start()
        self.btn_batch.setEnabled(False)
        self.lbl_status.setText("⏳ جاري المعالجة...")
    
    def _on_batch_progress(self, current, total):
        self.progress.setValue(self.current_idx + current)
        self.lbl_status.setText(f"⏳ معالجة {current}/{total}...")
    
    def _on_batch_finished(self):
        self.processed_count += len(self.images) - self.current_idx
        self.lbl_processed.setText(str(self.processed_count))
        self.current_idx = len(self.images)
        self.btn_batch.setEnabled(True)
        self.lbl_status.setText("✅ اكتملت المعالجة")
        QMessageBox.information(self, "اكتمل", f"تمت معالجة {len(self.images)-self.current_idx} صورة بنجاح")
    
    def _show_compare(self):
        """عرض مقارنة قبل/بعد"""
        if self.current_img is None: return
        
        processed = apply_all_corrections(self.current_img, self.params)
        
        # تحويل للعرض
        def img_to_pixmap(img, max_size=600):
            h, w = img.shape[:2]
            scale = min(max_size/max(w,1), max_size/max(h,1))
            nw, nh = int(w*scale), int(h*scale)
            small = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, nw, nh, nw*3, QImage.Format_RGB888)
            return QPixmap.fromImage(qimg)
        
        orig_pix = img_to_pixmap(self.current_img)
        proc_pix = img_to_pixmap(processed)
        
        dialog = QDialog(self)
        dialog.setWindowTitle("🔍 مقارنة قبل/بعد")
        dialog.resize(1000, 500)
        layout = QHBoxLayout(dialog)
        
        orig_box = QVBoxLayout()
        orig_box.addWidget(QLabel("الأصلية"))
        orig_lbl = QLabel()
        orig_lbl.setPixmap(orig_pix)
        orig_box.addWidget(orig_lbl)
        layout.addLayout(orig_box)
        
        proc_box = QVBoxLayout()
        proc_box.addWidget(QLabel("بعد المعالجة"))
        proc_lbl = QLabel()
        proc_lbl.setPixmap(proc_pix)
        proc_box.addWidget(proc_lbl)
        layout.addLayout(proc_box)
        
        btn = QPushButton("إغلاق")
        btn.clicked.connect(dialog.accept)
        layout.addWidget(btn)
        
        dialog.exec_()
    
    def _export_csv(self):
        """تصدير سجل الإجراءات لـ CSV"""
        path, _ = QFileDialog.getSaveFileName(self, "تصدير CSV", "actions.csv", "CSV (*.csv)")
        if path:
            self.learner.export_csv(path)
            self._log_action(f"📤 تم تصدير CSV إلى {path}")
    
    def _export_learn(self):
        """تصدير قاعدة التعلم"""
        path, _ = QFileDialog.getSaveFileName(self, "تصدير تعلّم", "learning_db.json", "JSON (*.json)")
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.learner.database, f, ensure_ascii=False, indent=2)
            self._log_action(f"💾 تم تصدير قاعدة التعلم")
    
    def _import_learn(self):
        """استيراد قاعدة تعلم"""
        path, _ = QFileDialog.getOpenFileName(self, "استيراد تعلّم", "", "JSON (*.json)")
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.learner.database = json.load(f)
                self.lbl_learned.setText(str(len(self.learner.database)))
                self._log_action(f"📥 تم استيراد {len(self.learner.database)} سجل تعلّم")
            except Exception as e:
                QMessageBox.critical(self, "خطأ", f"فشل الاستيراد: {e}")
    
    def _next_image(self):
        """الانتقال للصورة التالية"""
        if self.current_idx < len(self.images) - 1:
            self.current_idx += 1
            self._load_current()
        else:
            QMessageBox.information(self, "اكتمل", f"✅ انتهت جميع الصور!\nمعالجة: {self.processed_count} | تخطي: {self.skipped_count}")
    
    def _log_action(self, msg):
        """تسجيل إجراء في السجل"""
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.txt_log.append(line)
        self.txt_log.verticalScrollBar().setValue(self.txt_log.verticalScrollBar().maximum())
        
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    
    def _update_stats(self):
        """تحديث الإحصائيات"""
        self.lbl_learned.setText(str(len(self.learner.database)))
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    
    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        self.images = sorted([Path(p) for p in paths if Path(p).suffix.lower() in IMG_EXT])
        if self.images:
            self.current_idx = 0
            self.progress.setMaximum(len(self.images))
            self.lbl_total.setText(str(len(self.images)))
            self._load_current()
    
    
    # ---------- Zoom ----------
    def zoom_in(self):
        self.zoom_factor = min(self.max_zoom, self.zoom_factor * 1.2)
        self._update_preview()
        self._update_zoom_label()

    def zoom_out(self):
        self.zoom_factor = max(self.min_zoom, self.zoom_factor / 1.2)
        self._update_preview()
        self._update_zoom_label()

    def zoom_fit(self):
        if self.current_img is None:
            return
        h, w = self.current_img.shape[:2]
        # الحصول على الحجم المتاح لمنطقة المعاينة (QScrollArea)
        view_size = self.preview_scroll.viewport().size()
        fit_w = view_size.width() / w
        fit_h = view_size.height() / h
        self.zoom_factor = max(self.min_zoom, min(self.max_zoom, min(fit_w, fit_h)))
        self._update_preview()
        self._update_zoom_label()

    def _update_zoom_label(self):
        self.lbl_zoom.setText(f"{int(self.zoom_factor * 100)}%")

    def zoom_in(self):
        self.zoom_factor = min(self.max_zoom, self.zoom_factor * 1.2)
        self._update_preview()
        self._update_zoom_label()

    def zoom_out(self):
        self.zoom_factor = max(self.min_zoom, self.zoom_factor / 1.2)
        self._update_preview()
        self._update_zoom_label()

    def zoom_fit(self):
        if self.current_img is None: return
        h, w = self.current_img.shape[:2]
        view_size = self.preview_scroll.viewport().size()
        self.zoom_factor = max(self.min_zoom, min(self.max_zoom, min(view_size.width()/w, view_size.height()/h)))
        self._update_preview()
        self._update_zoom_label()

    def _update_zoom_label(self):
        self.lbl_zoom.setText(f"{int(self.zoom_factor * 100)}%")

    def closeEvent(self, event):
        self.learner.save()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setStyle("Fusion")
    window = MedicalDocAppV8()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()