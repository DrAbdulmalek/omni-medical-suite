# gradio_scanner_app.py
"""
Scanner Fixer Pro v2.0 - Gradio Web Interface
Web alternative to the Tkinter desktop app.
Provides the same image processing pipeline via browser.

Processing: shadow removal, deskew, perspective correction,
denoise, CLAHE contrast enhancement, auto-crop.
"""

import os
import time
import tempfile
import logging

import cv2
import numpy as np
from PIL import Image
import gradio as gr

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ── Image Processing Engine ──────────────────────────────────────────────────
class AdvancedScannerFixer:
    """Image enhancement pipeline (same logic as desktop_scanner_fixer_pro_v2.py)."""

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
        return image[y:y + h, x:x + w]

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
        rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)
        return rotated, float(angle)

    def perspective_correction(self, image):
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
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
        dst = np.array([[0, 0], [maxWidth - 1, 0],
                        [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]],
                       dtype="float32")
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
        """Run the full processing pipeline and return (result_image, metrics)."""
        if options is None:
            options = {
                'shadow_removal': True, 'deskew': True, 'perspective': True,
                'denoise': True, 'enhance_contrast': True, 'auto_crop': True,
            }
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

        metrics = {
            "deskew_angle": round(deskew_angle, 2),
            "perspective_fixed": perspective_fixed,
            "shadow_removed": options.get('shadow_removal', False),
            "denoise_applied": options.get('denoise', False),
            "contrast_enhanced": options.get('enhance_contrast', False),
            "auto_crop_applied": options.get('auto_crop', False),
        }
        return result, metrics


# ── Global engine ─────────────────────────────────────────────────────────────
fixer = AdvancedScannerFixer()


# ── Gradio Processing Function ────────────────────────────────────────────────
def process_image(
    input_image,
    shadow_removal,
    deskew,
    perspective,
    denoise,
    enhance_contrast,
    auto_crop,
):
    """
    Main Gradio processing callback.
    Accepts a PIL Image, returns (processed PIL Image, metrics JSON string).
    """
    if input_image is None:
        return None, "No image provided."

    options = {
        'shadow_removal': shadow_removal,
        'deskew': deskew,
        'perspective': perspective,
        'denoise': denoise,
        'enhance_contrast': enhance_contrast,
        'auto_crop': auto_crop,
    }

    start_time = time.time()

    # Convert PIL -> OpenCV BGR
    img_array = np.array(input_image)
    if img_array.ndim == 2:
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
    elif img_array.shape[2] == 4:
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
    else:
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

    # Process
    result_bgr, metrics = fixer.process(img_bgr, options)

    elapsed_ms = round((time.time() - start_time) * 1000, 1)
    metrics["processing_time_ms"] = elapsed_ms

    # Convert back to PIL RGB
    result_rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
    result_pil = Image.fromarray(result_rgb)

    # Format metrics
    metrics_text = "\n".join(f"  {k}: {v}" for k, v in metrics.items())
    status = "Done" if elapsed_ms < 5000 else "Slow"
    output = f"Status: {status}\n\nMetrics:\n{metrics_text}"

    return result_pil, output


# ── Build Gradio UI ───────────────────────────────────────────────────────────
def create_interface():
    with gr.Blocks(
        title="Scanner Fixer Pro v2.0",
        theme=gr.themes.Soft(),
    ) as demo:
        gr.Markdown(
            "# Scanner Fixer Pro v2.0\n"
            "Advanced scanned document image enhancement. "
            "Upload an image and choose processing options."
        )

        with gr.Row():
            with gr.Column(scale=1):
                input_image = gr.Image(
                    type="pil",
                    label="Original Image",
                )

            with gr.Column(scale=1):
                output_image = gr.Image(
                    type="pil",
                    label="Processed Image",
                )

        with gr.Row():
            shadow_removal = gr.Checkbox(label="Shadow Removal", value=True)
            deskew = gr.Checkbox(label="Deskew", value=True)
            perspective = gr.Checkbox(label="Perspective Correction", value=True)
            denoise = gr.Checkbox(label="Denoise", value=True)
            enhance_contrast = gr.Checkbox(label="Contrast Enhancement (CLAHE)", value=True)
            auto_crop = gr.Checkbox(label="Auto Crop", value=True)

        process_btn = gr.Button("Process Image", variant="primary")

        with gr.Row():
            metrics_output = gr.Textbox(
                label="Processing Metrics",
                lines=8,
                interactive=False,
            )

        # Wire up
        process_btn.click(
            fn=process_image,
            inputs=[
                input_image,
                shadow_removal, deskew, perspective,
                denoise, enhance_contrast, auto_crop,
            ],
            outputs=[output_image, metrics_output],
        )

        gr.Examples(
            examples=[],
            inputs=input_image,
            label="Examples",
        )

    return demo


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    demo = create_interface()
    demo.launch(
        server_name=os.getenv("GRADIO_SERVER_NAME", "0.0.0.0"),
        server_port=int(os.getenv("GRADIO_SERVER_PORT", "7860")),
    )