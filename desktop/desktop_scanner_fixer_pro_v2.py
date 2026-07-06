# desktop_scanner_fixer_pro_v2.py
"""
Scanner Fixer Pro v2.0 - مع دمج كامل مع HF
يتضمن: معالجة الصور + OCR + Dataset Manager
"""

import cv2
import numpy as np
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import threading
import tempfile
import json
import time

# استيراد المكونات
try:
    from hf_connector import HFConnector, DesktopHFIntegration
    from hf_auto_dataset import HFAutoDatasetManager
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False


class AdvancedScannerFixer:
    """معالج الصور المتقدم (متوافق مع scanner-fixer repo)"""

    def __init__(self):
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    def remove_shadows(self, image):
        rgb_planes = cv2.split(image)
        result_planes = []
        for plane in rgb_planes:
            dilated = cv2.dilate(plane, np.ones((7, 7), np.uint8))
            bg = cv2.medianBlur(dilated, 21)
            diff = 255 - cv2.subtract(bg, plane)
            result_planes.append(diff)
        return cv2.merge(result_planes)

    def auto_crop(self, image, padding=10):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
        coords = cv2.findNonZero(thresh)
        if coords is None:
            return image
        x, y, w, h = cv2.boundingRect(coords)
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(image.shape[1] - x, w + 2 * padding)
        h = min(image.shape[0] - y, h + 2 * padding)
        return image[y:y+h, x:x+w]

    def deskew(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.bitwise_not(gray)
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(thresh > 0))
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) < 0.5:
            return image, 0.0
        (h, w) = image.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated, float(angle)

    def perspective_correction(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return image, False
        largest = max(contours, key=cv2.contourArea)
        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, 0.02 * peri, True)
        if len(approx) != 4:
            return image, False
        pts = np.array([p[0] for p in approx], dtype="float32")
        rect = np.zeros((4, 2), dtype="float32")
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        (tl, tr, br, bl) = rect
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        dst = np.array([[0, 0], [maxWidth - 1, 0], [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
        return warped, True

    def denoise(self, image):
        return cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)

    def enhance_contrast(self, image):
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        cl = self.clahe.apply(l)
        enhanced = cv2.merge([cl, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    def process(self, image, options=None):
        if options is None:
            options = {'shadow_removal': True, 'deskew': True, 'perspective': True, 'denoise': True, 'enhance_contrast': True, 'auto_crop': True}
        result = image.copy()
        deskew_angle = 0.0
        perspective_fixed = False

        if options.get('shadow_removal'):
            result = self.remove_shadows(result)
        if options.get('deskew'):
            result, deskew_angle = self.deskew(result)
        if options.get('perspective'):
            result, perspective_fixed = self.perspective_correction(result)
        if options.get('denoise'):
            result = self.denoise(result)
        if options.get('enhance_contrast'):
            result = self.enhance_contrast(result)
        if options.get('auto_crop'):
            result = self.auto_crop(result)

        return result, {
            "deskew_angle": deskew_angle,
            "perspective_fixed": perspective_fixed,
            "shadow_removed": options.get('shadow_removal', False),
            "denoise_applied": options.get('denoise', False),
            "contrast_enhanced": options.get('enhance_contrast', False),
            "auto_crop_applied": options.get('auto_crop', False),
        }


class ScannerFixerProV2App:
    """تطبيق سطح مكتب متكامل v2 مع HF Dataset Manager"""

    def __init__(self):
        self.preprocessor = AdvancedScannerFixer()
        self.hf_connector = None
        self.hf_integration = None
        self.dataset_manager = None
        self.root = tk.Tk()
        self.root.title("Scanner Fixer Pro v2.0 + HF Integration")
        self.root.geometry("1400x900")
        self.root.configure(bg="#f0f0f0")

        self.image = None
        self.cleaned = None
        self.processing_metrics = {}
        self.current_image_path = None

        self.setup_ui()
        self.init_hf()

    def init_hf(self):
        """تهيئة الاتصال بـ HF"""
        if not HF_AVAILABLE:
            self.hf_status.config(text="HF: Not installed", fg="#e74c3c")
            return

        try:
            self.hf_connector = HFConnector()
            self.hf_integration = DesktopHFIntegration(self.hf_connector)
            self.hf_status.config(text="HF: Ready (not connected)", fg="#f39c12")
        except Exception as e:
            self.hf_status.config(text=f"HF Error: {e}", fg="#e74c3c")

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#2c3e50", height=80)
        header.pack(fill=tk.X)
        tk.Label(header, text="Scanner Fixer Pro v2.0 + Hugging Face", 
                font=("Arial", 24, "bold"), fg="white", bg="#2c3e50").pack(pady=15)

        self.hf_status = tk.Label(header, text="HF: Initializing...", 
                                 font=("Arial", 11), fg="#3498db", bg="#2c3e50")
        self.hf_status.pack()

        # Main Container
        main = tk.Frame(self.root, bg="#f0f0f0")
        main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left Panel
        left_panel = tk.Frame(main, bg="#ecf0f1", width=350)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        left_panel.pack_propagate(False)

        # === HF Connection & Dataset ===
        hf_frame = tk.LabelFrame(left_panel, text=" Hugging Face", 
                                font=("Arial", 12, "bold"), bg="#ecf0f1", fg="#2c3e50")
        hf_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(hf_frame, text="Space:", bg="#ecf0f1", font=("Arial", 10)).pack(anchor=tk.W, padx=5)
        self.space_entry = tk.Entry(hf_frame, width=40, font=("Arial", 10))
        self.space_entry.insert(0, "DrAbdulmalek/medical-ocr-demo")
        self.space_entry.pack(padx=5, pady=2)

        tk.Label(hf_frame, text="HF Token:", bg="#ecf0f1", font=("Arial", 10)).pack(anchor=tk.W, padx=5)
        self.token_entry = tk.Entry(hf_frame, width=40, font=("Arial", 10), show="*")
        self.token_entry.pack(padx=5, pady=2)

        tk.Button(hf_frame, text="Connect to HF", command=self.connect_hf,
                 bg="#3498db", fg="white", font=("Arial", 10, "bold"), width=20).pack(pady=5)

        # Dataset Management
        ds_frame = tk.LabelFrame(hf_frame, text=" Dataset Manager", 
                                font=("Arial", 10, "bold"), bg="#ecf0f1")
        ds_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Button(ds_frame, text="Create Dataset", command=self.create_hf_dataset,
                 bg="#9b59b6", fg="white", font=("Arial", 9), width=18).pack(pady=2)
        tk.Button(ds_frame, text="View Stats", command=self.view_dataset_stats,
                 bg="#1abc9c", fg="white", font=("Arial", 9), width=18).pack(pady=2)
        tk.Button(ds_frame, text="Export Dataset", command=self.export_dataset,
                 bg="#e67e22", fg="white", font=("Arial", 9), width=18).pack(pady=2)

        # === Processing Options ===
        options_frame = tk.LabelFrame(left_panel, text=" Processing Options", 
                                     font=("Arial", 12, "bold"), bg="#ecf0f1", fg="#2c3e50")
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        self.options = {}
        opts = [('shadow_removal', 'Remove Shadows', True), 
                ('deskew', 'Deskew', True),
                ('perspective', 'Perspective Correction', True),
                ('denoise', 'Denoise', True),
                ('enhance_contrast', 'Enhance Contrast', True),
                ('auto_crop', 'Auto Crop', True)]
        for key, text, default in opts:
            var = tk.BooleanVar(value=default)
            self.options[key] = var
            tk.Checkbutton(options_frame, text=text, variable=var, 
                          bg="#ecf0f1", font=("Arial", 10)).pack(anchor=tk.W, padx=5)

        # === Mode Selection ===
        mode_frame = tk.LabelFrame(left_panel, text=" Processing Mode", 
                                  font=("Arial", 12, "bold"), bg="#ecf0f1", fg="#2c3e50")
        mode_frame.pack(fill=tk.X, padx=10, pady=5)

        self.process_mode = tk.StringVar(value="local")
        tk.Radiobutton(mode_frame, text="Local Only", variable=self.process_mode, 
                      value="local", bg="#ecf0f1", font=("Arial", 10)).pack(anchor=tk.W, padx=5)
        tk.Radiobutton(mode_frame, text="Local + HF OCR", variable=self.process_mode, 
                      value="hybrid", bg="#ecf0f1", font=("Arial", 10)).pack(anchor=tk.W, padx=5)
        tk.Radiobutton(mode_frame, text="HF Direct", variable=self.process_mode, 
                      value="hf_only", bg="#ecf0f1", font=("Arial", 10)).pack(anchor=tk.W, padx=5)

        # === Action Buttons ===
        btn_frame = tk.LabelFrame(left_panel, text=" Actions", 
                                font=("Arial", 12, "bold"), bg="#ecf0f1", fg="#2c3e50")
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Button(btn_frame, text=" Load Image", command=self.load_image,
                 bg="#3498db", fg="white", font=("Arial", 11, "bold"), width=25, height=2).pack(pady=3)
        tk.Button(btn_frame, text=" Batch Process", command=self.batch_process,
                 bg="#9b59b6", fg="white", font=("Arial", 11, "bold"), width=25, height=2).pack(pady=3)
        tk.Button(btn_frame, text=" Process + OCR", command=self.process_with_ocr,
                 bg="#27ae60", fg="white", font=("Arial", 11, "bold"), width=25, height=2).pack(pady=3)
        tk.Button(btn_frame, text=" Save Image", command=self.save_image,
                 bg="#e74c3c", fg="white", font=("Arial", 11, "bold"), width=25, height=2).pack(pady=3)
        tk.Button(btn_frame, text=" Send Correction to HF", command=self.send_correction,
                 bg="#f39c12", fg="white", font=("Arial", 11, "bold"), width=25, height=2).pack(pady=3)
        tk.Button(btn_frame, text=" Log to HF Dataset", command=self.log_to_hf_dataset,
                 bg="#1abc9c", fg="white", font=("Arial", 11, "bold"), width=25, height=2).pack(pady=3)

        # Status & Progress
        self.status = tk.Label(left_panel, text="Ready", fg="#27ae60", 
                              bg="#ecf0f1", font=("Arial", 11, "bold"))
        self.status.pack(pady=5)
        self.progress = ttk.Progressbar(left_panel, orient=tk.HORIZONTAL, length=300, mode='determinate')
        self.progress.pack(pady=5)

        # === Right Panel ===
        right_panel = tk.Frame(main, bg="#bdc3c7")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5)

        # Images
        img_frame = tk.Frame(right_panel, bg="#bdc3c7")
        img_frame.pack(fill=tk.X, pady=5)
        tk.Label(img_frame, text="Original", font=("Arial", 12, "bold"), 
                bg="#bdc3c7", fg="#2c3e50").pack(side=tk.LEFT, padx=200)
        tk.Label(img_frame, text="Processed", font=("Arial", 12, "bold"), 
                bg="#bdc3c7", fg="#2c3e50").pack(side=tk.RIGHT, padx=200)

        canvases_frame = tk.Frame(right_panel, bg="#bdc3c7")
        canvases_frame.pack(fill=tk.X)
        self.canvas_before = tk.Canvas(canvases_frame, width=450, height=400, bg="gray")
        self.canvas_before.pack(side=tk.LEFT, padx=10, pady=5)
        self.canvas_after = tk.Canvas(canvases_frame, width=450, height=400, bg="gray")
        self.canvas_after.pack(side=tk.RIGHT, padx=10, pady=5)

        # OCR Results
        ocr_frame = tk.LabelFrame(right_panel, text=" OCR Results", 
                                 font=("Arial", 12, "bold"), bg="#ecf0f1", fg="#2c3e50")
        ocr_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(ocr_frame, text="Raw Text:", bg="#ecf0f1", font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=5)
        self.raw_text_box = tk.Text(ocr_frame, height=3, width=100, font=("Arial", 10))
        self.raw_text_box.pack(padx=5, pady=2)

        tk.Label(ocr_frame, text="Corrected Text:", bg="#ecf0f1", font=("Arial", 10, "bold")).pack(anchor=tk.W, padx=5)
        self.corrected_text_box = tk.Text(ocr_frame, height=3, width=100, font=("Arial", 10))
        self.corrected_text_box.pack(padx=5, pady=2)

        # Category & Correction
        corr_frame = tk.Frame(ocr_frame, bg="#ecf0f1")
        corr_frame.pack(fill=tk.X, padx=5, pady=5)

        tk.Label(corr_frame, text="Category:", bg="#ecf0f1", font=("Arial", 10)).pack(side=tk.LEFT)
        self.category_var = tk.StringVar(value="prescription")
        tk.OptionMenu(corr_frame, self.category_var, "prescription", "report", "handwriting", "lab").pack(side=tk.LEFT, padx=5)

        tk.Button(corr_frame, text="Manual Correct", command=self.manual_correct,
                 bg="#e67e22", fg="white", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=10)

        # Metrics Display
        metrics_frame = tk.LabelFrame(right_panel, text=" Processing Metrics", 
                                     font=("Arial", 11, "bold"), bg="#ecf0f1", fg="#2c3e50")
        metrics_frame.pack(fill=tk.X, padx=10, pady=5)
        self.metrics_text = tk.Text(metrics_frame, height=4, width=100, font=("Arial", 9))
        self.metrics_text.pack(padx=5, pady=2)

        # Batch Log
        self.batch_text = tk.Text(right_panel, height=4, width=100, font=("Arial", 9))
        self.batch_text.pack(pady=5)

    def connect_hf(self):
        """الاتصال بـ HF"""
        if not HF_AVAILABLE:
            messagebox.showerror("Error", "HF libraries not installed!")
            return

        space = self.space_entry.get()
        token = self.token_entry.get() or None

        self.status.config(text="Connecting to HF...", fg="#f39c12")
        self.root.update()

        try:
            self.hf_connector = HFConnector(space_name=space, hf_token=token)
            if self.hf_connector.connect_to_space():
                self.hf_integration = DesktopHFIntegration(self.hf_connector)
                self.dataset_manager = HFAutoDatasetManager(hf_token=token)
                self.hf_status.config(text=f"HF: Connected to {space}", fg="#27ae60")
                self.status.config(text="Connected to HF", fg="#27ae60")
            else:
                self.status.config(text="Connection failed", fg="#e74c3c")
        except Exception as e:
            messagebox.showerror("Error", f"Connection failed: {e}")
            self.status.config(text="Connection failed", fg="#e74c3c")

    def create_hf_dataset(self):
        """إنشاء Dataset جديد على HF"""
        if not self.dataset_manager:
            messagebox.showwarning("Warning", "Connect to HF first!")
            return

        try:
            dataset_name = self.dataset_manager.create_dataset("corrections", private=False)
            messagebox.showinfo("Success", f"Dataset created: {dataset_name}")
            self.status.config(text=f"Dataset created: {dataset_name}", fg="#27ae60")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create dataset: {e}")

    def view_dataset_stats(self):
        """عرض إحصائيات Dataset"""
        if not self.dataset_manager:
            messagebox.showwarning("Warning", "Connect to HF first!")
            return

        try:
            dataset_name = f"DrAbdulmalek/arabic-medical-ocr-corrections"
            stats = self.dataset_manager.get_dataset_stats(dataset_name)

            stats_str = json.dumps(stats, indent=2, ensure_ascii=False)
            self.metrics_text.delete(1.0, tk.END)
            self.metrics_text.insert(1.0, stats_str)
            self.status.config(text="Stats loaded", fg="#27ae60")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to get stats: {e}")

    def export_dataset(self):
        """تصدير Dataset"""
        if not self.dataset_manager:
            messagebox.showwarning("Warning", "Connect to HF first!")
            return

        folder = filedialog.askdirectory()
        if not folder:
            return

        try:
            dataset_name = f"DrAbdulmalek/arabic-medical-ocr-corrections"
            output_file = self.dataset_manager.export_dataset(dataset_name, folder, "json")
            messagebox.showinfo("Success", f"Exported to: {output_file}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    def load_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff")])
        if file_path:
            self.image = cv2.imread(file_path)
            self.show_image(self.image, self.canvas_before)
            self.status.config(text=f"Loaded: {Path(file_path).name}")
            self.current_image_path = file_path

    def show_image(self, img, canvas):
        canvas.delete("all")
        if img is None:
            return
        h, w = img.shape[:2]
        scale = min(450 / w, 400 / h)
        new_w, new_h = int(w * scale), int(h * scale)
        resized = cv2.resize(img, (new_w, new_h))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        photo = ImageTk.PhotoImage(pil_img)
        canvas.create_image(225, 200, anchor=tk.CENTER, image=photo)
        canvas.image = photo

    def process_with_ocr(self):
        """معالجة + OCR"""
        if self.image is None:
            messagebox.showwarning("Warning", "No image loaded!")
            return

        mode = self.process_mode.get()
        self.status.config(text=f"Processing ({mode})...", fg="#f39c12")
        self.root.update()

        start_time = time.time()

        try:
            if mode == "local":
                opts = {k: v.get() for k, v in self.options.items()}
                self.cleaned, self.processing_metrics = self.preprocessor.process(self.image, opts)
                self.show_image(self.cleaned, self.canvas_after)

                elapsed = (time.time() - start_time) * 1000
                self.processing_metrics["processing_time_ms"] = elapsed
                self.update_metrics_display()
                self.status.config(text="Local processing done", fg="#27ae60")

            elif mode == "hybrid":
                opts = {k: v.get() for k, v in self.options.items()}
                self.cleaned, self.processing_metrics = self.preprocessor.process(self.image, opts)
                self.show_image(self.cleaned, self.canvas_after)

                if self.hf_connector and self.hf_connector.client:
                    temp_path = Path(tempfile.gettempdir()) / "temp_for_hf.jpg"
                    cv2.imwrite(str(temp_path), self.cleaned)

                    result = self.hf_connector.process_image_via_hf(str(temp_path), "standard")
                    if result.get("success"):
                        self.raw_text_box.delete(1.0, tk.END)
                        self.raw_text_box.insert(1.0, result.get("raw_text", ""))
                        self.corrected_text_box.delete(1.0, tk.END)
                        self.corrected_text_box.insert(1.0, result.get("corrected_text", ""))
                        self.status.config(text="Processing + OCR done", fg="#27ae60")
                else:
                    self.status.config(text="HF not connected", fg="#e74c3c")

            elif mode == "hf_only":
                if self.hf_connector and self.hf_connector.client:
                    temp_path = Path(tempfile.gettempdir()) / "temp_for_hf.jpg"
                    cv2.imwrite(str(temp_path), self.image)

                    result = self.hf_connector.process_image_via_hf(str(temp_path), "standard")
                    if result.get("success"):
                        if result.get("cleaned_image"):
                            cleaned = cv2.imread(result["cleaned_image"])
                            if cleaned is not None:
                                self.cleaned = cleaned
                                self.show_image(cleaned, self.canvas_after)

                        self.raw_text_box.delete(1.0, tk.END)
                        self.raw_text_box.insert(1.0, result.get("raw_text", ""))
                        self.corrected_text_box.delete(1.0, tk.END)
                        self.corrected_text_box.insert(1.0, result.get("corrected_text", ""))
                        self.status.config(text="HF processing done", fg="#27ae60")
                else:
                    messagebox.showwarning("Warning", "Connect to HF first!")
                    self.status.config(text="HF not connected", fg="#e74c3c")

        except Exception as e:
            messagebox.showerror("Error", f"Processing failed: {e}")
            self.status.config(text="Failed", fg="#e74c3c")

    def update_metrics_display(self):
        """تحديث عرض المقاييس"""
        metrics_str = json.dumps(self.processing_metrics, indent=2, ensure_ascii=False)
        self.metrics_text.delete(1.0, tk.END)
        self.metrics_text.insert(1.0, metrics_str)

    def save_image(self):
        if self.cleaned is None:
            messagebox.showwarning("Warning", "No processed image!")
            return
        file_path = filedialog.asksaveasfilename(defaultextension=".jpg", 
                                                filetypes=[("JPEG", "*.jpg"), ("PNG", "*.png"), ("TIFF", "*.tiff")])
        if file_path:
            cv2.imwrite(file_path, self.cleaned)
            messagebox.showinfo("Success", f"Saved to: {file_path}")
            self.status.config(text=f"Saved: {Path(file_path).name}")

    def send_correction(self):
        """إرسال تصحيح إلى HF Dataset"""
        if not self.dataset_manager:
            messagebox.showwarning("Warning", "Connect to HF first!")
            return

        raw = self.raw_text_box.get(1.0, tk.END).strip()
        corrected = self.corrected_text_box.get(1.0, tk.END).strip()
        category = self.category_var.get()

        if not raw or not corrected:
            messagebox.showwarning("Warning", "Please enter raw and corrected text!")
            return

        image_path = getattr(self, 'current_image_path', 'unknown')
        dataset_name = f"DrAbdulmalek/arabic-medical-ocr-corrections"

        try:
            success = self.dataset_manager.add_correction_record(
                dataset_name=dataset_name,
                image_path=image_path,
                incorrect_text=raw,
                correct_text=corrected,
                category=category,
                source="desktop_app_v2"
            )

            if success:
                self.status.config(text="Correction sent to HF", fg="#27ae60")
                messagebox.showinfo("Success", "Correction added to HF Dataset!")
            else:
                self.status.config(text="Saved locally (HF failed)", fg="#f39c12")
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {e}")

    def log_to_hf_dataset(self):
        """تسجيل معالجة Scanner في HF Dataset"""
        if not self.dataset_manager or not self.cleaned is not None:
            messagebox.showwarning("Warning", "Process an image and connect to HF first!")
            return

        try:
            # حفظ الصور المؤقتة
            temp_dir = Path(tempfile.gettempdir())
            original_temp = temp_dir / "original_temp.jpg"
            processed_temp = temp_dir / "processed_temp.jpg"

            cv2.imwrite(str(original_temp), self.image)
            cv2.imwrite(str(processed_temp), self.cleaned)

            dataset_name = f"DrAbdulmalek/scanner-fixer-logs"

            success = self.dataset_manager.add_scanner_log(
                dataset_name=dataset_name,
                original_image_path=str(original_temp),
                processed_image_path=str(processed_temp),
                processing_options={k: v.get() for k, v in self.options.items()},
                processing_time_ms=self.processing_metrics.get("processing_time_ms", 0),
                deskew_angle=self.processing_metrics.get("deskew_angle", 0.0)
            )

            if success:
                self.status.config(text="Scanner log sent to HF", fg="#27ae60")
                messagebox.showinfo("Success", "Processing log added to HF Dataset!")
            else:
                self.status.config(text="Log saved locally", fg="#f39c12")
        except Exception as e:
            messagebox.showerror("Error", f"Failed: {e}")

    def batch_process(self):
        """معالجة مجلد كامل"""
        folder = filedialog.askdirectory()
        if not folder:
            return
        files = list(Path(folder).glob("*.jpg")) + list(Path(folder).glob("*.png")) +                 list(Path(folder).glob("*.jpeg")) + list(Path(folder).glob("*.bmp"))
        if not files:
            messagebox.showwarning("Warning", "No images found!")
            return

        output_dir = Path(folder) / "processed"
        output_dir.mkdir(exist_ok=True)
        self.progress['maximum'] = len(files)
        self.progress['value'] = 0
        self.batch_text.delete(1.0, tk.END)

        opts = {k: v.get() for k, v in self.options.items()}
        mode = self.process_mode.get()

        def process_batch():
            for i, file in enumerate(files):
                try:
                    img = cv2.imread(str(file))
                    if img is None:
                        continue

                    cleaned, metrics = self.preprocessor.process(img, opts)
                    cv2.imwrite(str(output_dir / f"fixed_{file.name}"), cleaned)

                    self.progress['value'] = i + 1
                    self.batch_text.insert(tk.END, f" {file.name} | deskew: {metrics['deskew_angle']:.1f}°\n")
                    self.root.update_idletasks()
                except Exception as e:
                    self.batch_text.insert(tk.END, f" {file.name}: {e}\n")

            self.status.config(text=f"Batch complete: {len(files)} images")
            messagebox.showinfo("Success", f"Processed {len(files)} images to:\n{output_dir}")

        threading.Thread(target=process_batch, daemon=True).start()

    def manual_correct(self):
        """تصحيح يدوي"""
        corr_window = tk.Toplevel(self.root)
        corr_window.title("Manual Correction")
        corr_window.geometry("700x400")

        tk.Label(corr_window, text="Corrected Text:", font=("Arial", 12, "bold")).pack(pady=5)
        text_box = tk.Text(corr_window, height=10, width=80, font=("Arial", 12))
        text_box.pack(padx=10, pady=5)
        text_box.insert(1.0, self.corrected_text_box.get(1.0, tk.END))

        def save_manual():
            corrected = text_box.get(1.0, tk.END).strip()
            self.corrected_text_box.delete(1.0, tk.END)
            self.corrected_text_box.insert(1.0, corrected)
            corr_window.destroy()
            self.status.config(text="Manual correction saved", fg="#27ae60")

        tk.Button(corr_window, text="Save Correction", command=save_manual,
                 bg="#27ae60", fg="white", font=("Arial", 12, "bold")).pack(pady=10)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ScannerFixerProV2App()
    app.run()
