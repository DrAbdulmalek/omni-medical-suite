# -*- coding: utf-8 -*-
"""Gradio Phase 2 Enhanced — interactive OCR testing UI.

Provides a browser-based interface for experimenting with the Phase 2
document processing pipeline.  Users can upload an image, select a
deskew strategy, crop method, IOU threshold, and engine weights before
running Tesseract OCR fused with the Fusion V3 merge strategy.

All engine imports are wrapped in ``try/except`` so the UI degrades
gracefully when optional dependencies (OpenCV, EasyOCR, PaddleOCR) are
not installed.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Optional engine imports — graceful degradation
# ---------------------------------------------------------------------------

try:
    import cv2

    _HAS_CV2 = True
except ImportError:
    cv2 = None  # type: ignore[assignment]
    _HAS_CV2 = False

try:
    import pytesseract

    _HAS_TESSERACT = True
except ImportError:
    pytesseract = None  # type: ignore[assignment]
    _HAS_TESSERACT = False

try:
    from src.vision.fusion_v3_enhanced import FusionV3Enhanced, OCREntry

    _HAS_FUSION = True
except ImportError:
    FusionV3Enhanced = None  # type: ignore[assignment,misc]
    OCREntry = None  # type: ignore[assignment,misc]
    _HAS_FUSION = False

try:
    from src.vision.deskew_advanced import AdvancedDeskew

    _HAS_DESKEW = True
except ImportError:
    AdvancedDeskew = None  # type: ignore[assignment,misc]
    _HAS_DESKEW = False

try:
    import easyocr

    _HAS_EASYOCR = True
except ImportError:
    easyocr = None  # type: ignore[assignment,misc]
    _HAS_EASYOCR = False

try:
    import paddleocr

    _HAS_PADDLEOCR = True
except ImportError:
    paddleocr = None  # type: ignore[assignment,misc]
    _HAS_PADDLEOCR = False

try:
    import gradio as gr

    _HAS_GRADIO = True
except ImportError:
    gr = None  # type: ignore[assignment,misc]
    _HAS_GRADIO = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette for bounding boxes per engine
# ---------------------------------------------------------------------------

_ENGINE_COLORS: Dict[str, str] = {
    "tesseract": "#e6194b",
    "easyocr": "#3cb44b",
    "paddleocr": "#4363d8",
    "fusion_v3": "#f58231",
}


# ---------------------------------------------------------------------------
# Helper: draw bounding boxes on a PIL image
# ---------------------------------------------------------------------------

def _draw_boxes(
    image: Image.Image,
    entries: List[Any],
    color: str = "#f58231",
    label_prefix: str = "",
) -> Image.Image:
    """Overlay coloured bounding boxes with text labels on a PIL image.

    Parameters
    ----------
    image:
        Source PIL image (modified in-place copy).
    entries:
        List of objects with ``bbox`` (x1,y1,x2,y2) and ``text`` / ``confidence``.
    color:
        Hex colour string for box outlines and labels.
    label_prefix:
        Optional prefix shown on each label.

    Returns
    -------
    PIL.Image.Image
        Annotated image copy.
    """
    canvas = image.copy().convert("RGB")
    draw = ImageDraw.Draw(canvas)
    for entry in entries:
        x1, y1, x2, y2 = entry.bbox
        draw.rectangle([x1, y1, x2, y2], outline=color, width=2)
        text = getattr(entry, "text", "")
        conf = getattr(entry, "confidence", 0.0)
        label = f"{label_prefix}{text} ({conf:.0%})" if text else label_prefix
        draw.text((x1, y1 - 14), label, fill=color)
    return canvas


# ---------------------------------------------------------------------------
# Core processing function
# ---------------------------------------------------------------------------

def process_document(
    input_image: Image.Image,
    deskew_method: str,
    crop_method: str,
    iou_threshold: float,
    dynamic_weights: bool,
    use_tesseract: bool,
    use_easyocr: bool,
    use_paddleocr: bool,
    min_confidence: float,
) -> Tuple[Optional[Image.Image], str, str]:
    """Run the full Phase 2 pipeline on a single document image.

    Steps:
        1. Convert PIL → OpenCV array and optionally deskew.
        2. Smart crop (noop / centre-crop / margin-trim).
        3. Run selected OCR engines.
        4. Fuse results with Fusion V3 (IOU clustering).
        5. Draw bounding boxes and collect extracted text.

    Parameters
    ----------
    input_image:
        Uploaded PIL image.
    deskew_method:
        One of ``"none"``, ``"hybrid"``, ``"hough"``, ``"projection"``.
    crop_method:
        One of ``"none"``, ``"centre"``, ``"margin"``.
    iou_threshold:
        Minimum IOU for merging overlapping detections (0–1).
    dynamic_weights:
        Enable image-feature-driven engine weights.
    use_tesseract / use_easyocr / use_paddleocr:
        Toggle individual OCR engines.
    min_confidence:
        Discard tokens with fused confidence below this value.

    Returns
    -------
    tuple
        ``(annotated_image, processing_log, extracted_text)``
    """
    log_lines: List[str] = []
    start = time.time()

    if input_image is None:
        return None, "No image provided.", ""

    # -- Convert PIL → NumPy -----------------------------------------------
    img_array = np.array(input_image.convert("RGB"))
    current: np.ndarray = img_array.copy()

    # -- Step 1: Deskew -----------------------------------------------------
    if deskew_method != "none":
        if not _HAS_CV2 or not _HAS_DESKEW:
            log_lines.append("[WARN] Deskew skipped — opencv or deskew module unavailable.")
        else:
            bgr = cv2.cvtColor(current, cv2.COLOR_RGB2BGR)
            deskewer = AdvancedDeskew()
            corrected, angle = deskewer.auto_deskew(bgr, method=deskew_method)
            current = cv2.cvtColor(corrected, cv2.COLOR_BGR2RGB)
            log_lines.append(f"[Deskew] method={deskew_method}, angle={angle:.2f}°")

    # -- Step 2: Smart crop -------------------------------------------------
    h, w = current.shape[:2]
    if crop_method == "centre":
        side = min(h, w)
        cy, cx = h // 2, w // 2
        current = current[cy - side // 2 : cy + side // 2, cx - side // 2 : cx + side // 2]
        log_lines.append(f"[Crop] centre crop → {current.shape[1]}×{current.shape[0]}")
    elif crop_method == "margin":
        margin = int(min(h, w) * 0.05)
        current = current[margin : h - margin, margin : w - margin]
        log_lines.append(f"[Crop] margin trim (5%) → {current.shape[1]}×{current.shape[0]}")

    # -- Step 3: Run OCR engines --------------------------------------------
    engine_results: List[Any] = []

    # Tesseract
    if use_tesseract and _HAS_TESSERACT:
        try:
            pil_img = Image.fromarray(current)
            data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
            entries = []
            for i in range(len(data["text"])):
                if int(data["conf"][i]) > 0:
                    entries.append(
                        type("E", (), {
                            "text": data["text"][i],
                            "confidence": int(data["conf"][i]) / 100.0,
                            "bbox": (
                                data["left"][i], data["top"][i],
                                data["left"][i] + data["width"][i],
                                data["top"][i] + data["height"][i],
                            ),
                            "engine_name": "tesseract",
                            "language": "en",
                        })()
                    )
            engine_results.append(("tesseract", entries))
            log_lines.append(f"[Tesseract] {len(entries)} tokens")
        except Exception as exc:
            log_lines.append(f"[Tesseract] ERROR: {exc}")
    else:
        log_lines.append("[Tesseract] skipped (disabled or unavailable)")

    # EasyOCR
    if use_easyocr and _HAS_EASYOCR:
        try:
            reader = easyocr.Reader(["en", "ar"], gpu=False, verbose=False)
            results = reader.readtext(current)
            entries = []
            for bbox, text, conf in results:
                pts = np.array(bbox, dtype=int)
                entries.append(
                    type("E", (), {
                        "text": text,
                        "confidence": float(conf),
                        "bbox": (pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()),
                        "engine_name": "easyocr",
                        "language": "en",
                    })()
                )
            engine_results.append(("easyocr", entries))
            log_lines.append(f"[EasyOCR] {len(entries)} tokens")
        except Exception as exc:
            log_lines.append(f"[EasyOCR] ERROR: {exc}")
    else:
        log_lines.append("[EasyOCR] skipped (disabled or unavailable)")

    # PaddleOCR
    if use_paddleocr and _HAS_PADDLEOCR:
        try:
            ocr_paddle = paddleocr.PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            results = ocr_paddle.ocr(current, cls=True)
            entries = []
            for line in (results or []):
                if line:
                    for word_info in line:
                        bbox_pts = word_info[0]
                        text, conf = word_info[1]
                        pts = np.array(bbox_pts, dtype=int)
                        entries.append(
                            type("E", (), {
                                "text": text,
                                "confidence": float(conf),
                                "bbox": (pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()),
                                "engine_name": "paddleocr",
                                "language": "en",
                            })()
                        )
            engine_results.append(("paddleocr", entries))
            log_lines.append(f"[PaddleOCR] {len(entries)} tokens")
        except Exception as exc:
            log_lines.append(f"[PaddleOCR] ERROR: {exc}")
    else:
        log_lines.append("[PaddleOCR] skipped (disabled or unavailable)")

    # -- Step 4: Fusion V3 --------------------------------------------------
    fused_entries: List[Any] = []
    if _HAS_FUSION and engine_results:
        try:
            fusion = FusionV3Enhanced(
                iou_threshold=iou_threshold,
                use_dynamic_weights=dynamic_weights,
                min_confidence=min_confidence,
            )
            fused_entries = fusion.fuse(engine_results, image=current)
            log_lines.append(
                f"[Fusion V3] {len(fused_entries)} fused blocks "
                f"(iou={iou_threshold}, dynamic={dynamic_weights})"
            )
        except Exception as exc:
            log_lines.append(f"[Fusion V3] ERROR: {exc}")
    else:
        log_lines.append("[Fusion V3] skipped — no engines or module unavailable")

    # -- Step 5: Build outputs -----------------------------------------------
    elapsed = time.time() - start
    log_lines.append(f"[Total] {elapsed:.2f}s")

    annotated: Optional[Image.Image] = None
    if fused_entries:
        pil_current = Image.fromarray(current)
        annotated = _draw_boxes(pil_current, fused_entries, "#f58231", "FV3: ")
    elif engine_results:
        pil_current = Image.fromarray(current)
        for name, entries in engine_results:
            color = _ENGINE_COLORS.get(name, "#ffffff")
            annotated = _draw_boxes(annotated or pil_current, entries, color, f"{name}: ")

    extracted_text = "\n".join(
        getattr(e, "text", "") for e in fused_entries if getattr(e, "text", "")
    )

    return annotated, "\n".join(log_lines), extracted_text


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

def launch() -> None:
    """Build and launch the Gradio Blocks interface on port 7860."""
    if not _HAS_GRADIO:
        logger.error("Gradio is not installed. Run: pip install gradio")
        return

    with gr.Blocks(
        title="OmniMedical — Phase 2 Enhanced OCR",
        theme=gr.themes.Soft(primary_hue="orange"),
    ) as demo:
        gr.Markdown("# 🏥 OmniMedical Suite — Phase 2 Enhanced OCR")

        with gr.Row():
            with gr.Column(scale=1):
                input_image = gr.Image(type="pil", label="Document Image")

                deskew_method = gr.Radio(
                    choices=["none", "hybrid", "hough", "projection"],
                    value="none",
                    label="Deskew Method",
                )
                crop_method = gr.Radio(
                    choices=["none", "centre", "margin"],
                    value="none",
                    label="Smart Crop",
                )
                iou_threshold = gr.Slider(
                    minimum=0.0, maximum=1.0, step=0.05, value=0.3,
                    label="IOU Threshold",
                )
                dynamic_weights = gr.Checkbox(
                    value=True, label="Dynamic Weights",
                )
                min_confidence = gr.Slider(
                    minimum=0.0, maximum=1.0, step=0.05, value=0.3,
                    label="Min Confidence",
                )

                with gr.Accordion("Engine Selection", open=True):
                    use_tesseract = gr.Checkbox(value=True, label="Tesseract")
                    use_easyocr = gr.Checkbox(value=False, label="EasyOCR")
                    use_paddleocr = gr.Checkbox(value=False, label="PaddleOCR")

                process_btn = gr.Button("Process Document", variant="primary")

            with gr.Column(scale=2):
                output_image = gr.Image(type="pil", label="Processed (Annotated)")
                output_log = gr.Textbox(label="Processing Log", lines=8)
                output_text = gr.Textbox(label="Extracted Text", lines=10)

        process_btn.click(
            fn=process_document,
            inputs=[
                input_image, deskew_method, crop_method, iou_threshold,
                dynamic_weights, use_tesseract, use_easyocr, use_paddleocr,
                min_confidence,
            ],
            outputs=[output_image, output_log, output_text],
        )

    demo.launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    launch()
