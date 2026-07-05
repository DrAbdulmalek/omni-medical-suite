# app/gradio_ui.py
"""
Simplified Gradio UI for Omni Medical OCR.
Uses direct function calls (no internal HTTP).
Integrates scanner-fixer preprocessing + Tesseract OCR.

Based on Kimi Code review — fixed API_URL issue and added RTL support.
"""
import os
import gradio as gr
import cv2
import numpy as np
from pathlib import Path

# Optional imports with fallback
try:
    from src.scanner_fixer.enhanced_preprocessor import DocumentPreprocessor
    HAS_PREPROCESSOR = True
except ImportError:
    HAS_PREPROCESSOR = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

# Initialize preprocessor
preprocessor = DocumentPreprocessor() if HAS_PREPROCESSOR else None


def preprocess_image(image: np.ndarray) -> np.ndarray:
    """Preprocess image using scanner-fixer pipeline."""
    if preprocessor is not None:
        return preprocessor.process_array(image)
    return image


def extract_text_from_image(image: np.ndarray) -> str:
    """Extract text using available OCR engines."""
    if HAS_TESSERACT:
        # Try Arabic + English
        text_ar = pytesseract.image_to_string(image, lang='ara+eng')
        return text_ar.strip()
    return "[OCR engine not available. Install pytesseract]"


def process_image(image):
    """Full pipeline: preprocess → OCR → output."""
    if image is None:
        return "Please upload an image."

    try:
        # Convert to numpy if needed
        if isinstance(image, str):
            img = cv2.imread(image)
        elif isinstance(image, np.ndarray):
            img = image
        else:
            return "Unsupported image format."

        if img is None:
            return "Could not read image."

        # Step 1: Preprocess
        processed = preprocess_image(img)

        # Step 2: OCR
        text = extract_text_from_image(processed)

        return text if text else "No text detected."
    except Exception as e:
        return f"Error: {str(e)}"


def process_and_show(image):
    """Process and return both cleaned image and text."""
    if image is None:
        return None, "Please upload an image."

    try:
        if isinstance(image, str):
            img = cv2.imread(image)
        else:
            img = image

        processed = preprocess_image(img)
        text = extract_text_from_image(processed)

        # Convert BGR to RGB for Gradio display
        if processed is not None:
            processed_rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
        else:
            processed_rgb = None

        return processed_rgb, text if text else "No text detected."
    except Exception as e:
        return None, f"Error: {str(e)}"


# Build examples
examples = []
samples_dir = Path("samples")
if samples_dir.exists():
    for ext in ["*.jpg", "*.jpeg", "*.png"]:
        for f in samples_dir.glob(ext):
            examples.append([str(f)])

# Custom CSS for Arabic RTL support
css = """
.gradio-container { direction: rtl; }
.output-text { direction: rtl; text-align: right; font-size: 16px; line-height: 2; }
"""

# Gradio Interface
with gr.Blocks(
    title="Omni Medical OCR",
    theme=gr.themes.Soft(),
    css=css
) as demo:
    gr.Markdown("# Omni Medical OCR\n**Arabic Medical Text Extraction from Images**")

    with gr.Row():
        input_image = gr.Image(
            type="numpy",
            label="Upload Medical Prescription/Report"
        )
        process_btn = gr.Button("Process", variant="primary", size="lg")

    with gr.Row():
        with gr.Column(scale=1):
            cleaned_img = gr.Image(label="Preprocessed Image")
        with gr.Column(scale=2):
            output_text = gr.Textbox(
                label="Extracted Text",
                lines=10,
                show_copy_button=True,
                elem_classes=["output-text"]
            )

    if examples:
        gr.Examples(examples=examples, inputs=[input_image])

    process_btn.click(
        fn=process_and_show,
        inputs=[input_image],
        outputs=[cleaned_img, output_text]
    )


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)