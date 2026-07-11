# -*- coding: utf-8 -*-
"""Fusion V3 Lab — side-by-side OCR engine comparison UI.

Launches a Gradio interface that runs Tesseract, EasyOCR, PaddleOCR, and
the Fusion V3 merge on the same document image, then displays four
annotated panels for direct visual comparison along with extracted text
and performance metrics.

All engine imports are wrapped in ``try/except`` so the UI degrades
gracefully when optional dependencies are not available.
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
    import pytesseract

    _HAS_TESSERACT = True
except ImportError:
    pytesseract = None  # type: ignore[assignment,misc]
    _HAS_TESSERACT = False

try:
    from src.vision.fusion_v3_enhanced import FusionV3Enhanced, OCREntry

    _HAS_FUSION = True
except ImportError:
    FusionV3Enhanced = None  # type: ignore[assignment,misc]
    OCREntry = None  # type: ignore[assignment,misc]
    _HAS_FUSION = False

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
# Colour palette per engine
# ---------------------------------------------------------------------------

_ENGINE_COLORS: Dict[str, str] = {
    "tesseract": "#e6194b",
    "easyocr": "#3cb44b",
    "paddleocr": "#4363d8",
    "fusion_v3": "#f58231",
}


# ---------------------------------------------------------------------------
# draw_boxes — overlay bounding boxes with engine labels
# ---------------------------------------------------------------------------

def draw_boxes(
    image: Image.Image,
    entries: List[Any],
    color: str = "#f58231",
    label_prefix: str = "",
) -> Image.Image:
    """Draw coloured bounding boxes with labels on a PIL image.

    Each entry must expose ``.bbox`` as ``(x1, y1, x2, y2)`` and
    ``.text`` / ``.confidence`` attributes.

    Parameters
    ----------
    image:
        Source image to annotate (a copy is returned).
    entries:
        OCR detection entries.
    color:
        Hex colour for box outlines and label text.
    label_prefix:
        Prefix prepended to each label string.

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
        draw.text((x1, max(y1 - 14, 0)), label, fill=color)
    return canvas


# ---------------------------------------------------------------------------
# Per-engine OCR functions
# ---------------------------------------------------------------------------

def _run_tesseract(image_array: np.ndarray) -> Tuple[List[Any], float]:
    """Run Tesseract and return (entries, elapsed_time)."""
    if not _HAS_TESSERACT:
        return [], 0.0
    t0 = time.time()
    pil_img = Image.fromarray(image_array)
    data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
    entries: List[Any] = []
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
    return entries, time.time() - t0


def _run_easyocr(image_array: np.ndarray) -> Tuple[List[Any], float]:
    """Run EasyOCR and return (entries, elapsed_time)."""
    if not _HAS_EASYOCR:
        return [], 0.0
    t0 = time.time()
    reader = easyocr.Reader(["en", "ar"], gpu=False, verbose=False)
    results = reader.readtext(image_array)
    entries: List[Any] = []
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
    return entries, time.time() - t0


def _run_paddleocr(image_array: np.ndarray) -> Tuple[List[Any], float]:
    """Run PaddleOCR and return (entries, elapsed_time)."""
    if not _HAS_PADDLEOCR:
        return [], 0.0
    t0 = time.time()
    ocr_engine = paddleocr.PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    results = ocr_engine.ocr(image_array, cls=True)
    entries: List[Any] = []
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
    return entries, time.time() - t0


# ---------------------------------------------------------------------------
# Main comparison function
# ---------------------------------------------------------------------------

def compare_engines(
    input_image: Image.Image,
    use_iou_clustering: bool,
    iou_threshold: float,
    dynamic_weights: bool,
    show_boxes: bool,
) -> Tuple[
    Optional[Image.Image], Optional[Image.Image],
    Optional[Image.Image], Optional[Image.Image],
    str, str,
]:
    """Run all OCR engines side-by-side and return four annotated panels.

    Parameters
    ----------
    input_image:
        Uploaded PIL image.
    use_iou_clustering:
        Enable IOU-based spatial clustering in Fusion V3.
    iou_threshold:
        Minimum IOU for merging overlapping detections.
    dynamic_weights:
        Use image-feature-driven per-engine weights.
    show_boxes:
        When *False*, return plain images without bounding boxes.

    Returns
    -------
    tuple
        ``(img_tesseract, img_easyocr, img_paddleocr, img_fusion_v3,
        extracted_text, performance_metrics)``
    """
    if input_image is None:
        return None, None, None, None, "No image provided.", ""

    image_array: np.ndarray = np.array(input_image.convert("RGB"))
    pil_base: Image.Image = input_image.convert("RGB")
    metrics: Dict[str, Any] = {}

    # -- Run each engine ----------------------------------------------------
    tesseract_entries, t_time = _run_tesseract(image_array)
    easyocr_entries, e_time = _run_easyocr(image_array)
    paddleocr_entries, p_time = _run_paddleocr(image_array)

    metrics["tesseract"] = {"tokens": len(tesseract_entries), "time_ms": round(t_time * 1000, 1)}
    metrics["easyocr"] = {"tokens": len(easyocr_entries), "time_ms": round(e_time * 1000, 1)}
    metrics["paddleocr"] = {"tokens": len(paddleocr_entries), "time_ms": round(p_time * 1000, 1)}

    # -- Fusion V3 ----------------------------------------------------------
    fused_entries: List[Any] = []
    if _HAS_FUSION:
        engine_results = [
            ("tesseract", tesseract_entries),
            ("easyocr", easyocr_entries),
            ("paddleocr", paddleocr_entries),
        ]
        fusion = FusionV3Enhanced(
            iou_threshold=iou_threshold if use_iou_clustering else 0.0,
            use_dynamic_weights=dynamic_weights,
            min_confidence=0.0,
        )
        f0 = time.time()
        fused_entries = fusion.fuse(
            engine_results,
            image=image_array if dynamic_weights else None,
        )
        f_time = time.time() - f0
        metrics["fusion_v3"] = {"tokens": len(fused_entries), "time_ms": round(f_time * 1000, 1)}

    # -- Build annotated images ---------------------------------------------
    annotate = show_boxes
    img_tess: Optional[Image.Image] = (
        draw_boxes(pil_base, tesseract_entries, _ENGINE_COLORS["tesseract"], "T: ")
        if annotate and tesseract_entries else pil_base
    )
    img_easy: Optional[Image.Image] = (
        draw_boxes(pil_base, easyocr_entries, _ENGINE_COLORS["easyocr"], "E: ")
        if annotate and easyocr_entries else pil_base
    )
    img_pad: Optional[Image.Image] = (
        draw_boxes(pil_base, paddleocr_entries, _ENGINE_COLORS["paddleocr"], "P: ")
        if annotate and paddleocr_entries else pil_base
    )
    img_fusion: Optional[Image.Image] = (
        draw_boxes(pil_base, fused_entries, _ENGINE_COLORS["fusion_v3"], "FV3: ")
        if annotate and fused_entries else pil_base
    )

    # -- Extracted text from fusion -----------------------------------------
    extracted = "\n".join(
        getattr(e, "text", "") for e in fused_entries if getattr(e, "text", "")
    )

    # -- Format metrics string ----------------------------------------------
    metrics_lines = [
        f"Engine       | Tokens | Time (ms)",
        f"{'-' * 35}",
    ]
    for name in ("tesseract", "easyocr", "paddleocr", "fusion_v3"):
        m = metrics.get(name, {})
        metrics_lines.append(f"{name:<13}| {m.get('tokens', 0):>6} | {m.get('time_ms', 0):>9}")
    metrics_str = "\n".join(metrics_lines)

    return img_tess, img_easy, img_pad, img_fusion, extracted, metrics_str


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------

def launch() -> None:
    """Build and launch the Fusion V3 Lab interface on port 7861."""
    if not _HAS_GRADIO:
        logger.error("Gradio is not installed. Run: pip install gradio")
        return

    with gr.Blocks(
        title="OmniMedical — Fusion V3 Lab",
        theme=gr.themes.Soft(primary_hue="orange"),
    ) as demo:
        gr.Markdown("# 🔬 Fusion V3 Lab — Side-by-Side OCR Comparison")

        with gr.Row():
            input_image = gr.Image(type="pil", label="Upload Document")

            with gr.Column():
                use_iou_clustering = gr.Checkbox(value=True, label="IOU Clustering")
                iou_threshold = gr.Slider(
                    minimum=0.0, maximum=1.0, step=0.05, value=0.3,
                    label="IOU Threshold",
                )
                dynamic_weights = gr.Checkbox(value=True, label="Dynamic Weights")
                show_boxes = gr.Checkbox(value=True, label="Show Bounding Boxes")
                compare_btn = gr.Button("Compare Engines", variant="primary")

        gr.Markdown("### Annotated Results")

        with gr.Row(equal_height=True):
            img_tess = gr.Image(type="pil", label="Tesseract", show_label=True)
            img_easy = gr.Image(type="pil", label="EasyOCR", show_label=True)
            img_pad = gr.Image(type="pil", label="PaddleOCR", show_label=True)
            img_fusion = gr.Image(type="pil", label="Fusion V3", show_label=True)

        with gr.Row():
            output_text = gr.Textbox(label="Fusion V3 — Extracted Text", lines=8)
            output_metrics = gr.Textbox(label="Performance Metrics", lines=8)

        compare_btn.click(
            fn=compare_engines,
            inputs=[input_image, use_iou_clustering, iou_threshold, dynamic_weights, show_boxes],
            outputs=[img_tess, img_easy, img_pad, img_fusion, output_text, output_metrics],
        )

    demo.launch(server_name="0.0.0.0", server_port=7861)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    launch()
