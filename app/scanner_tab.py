"""Scanner fixer Gradio tab — interactive crop + advanced edge detection.

This module backs Tab 1 ("🔬 معالج الصور") in app/advanced_review_app.py.
It is intentionally Gradio-free at module level so it can be unit-tested
with plain numpy arrays.

Public API:
    apply_manual_crop(image_bgr, crop_box) -> np.ndarray
    apply_advanced_edges(image_bgr, **opts) -> np.ndarray
    process_with_options(image_rgb, crop_box, **opts) -> tuple[PIL, PIL, str]
    save_processed_image(image_bgr, output_dir, filename) -> str
    pick_random_from_gallery(paths) -> tuple[np.ndarray, str]

All image inputs/outputs are BGR numpy arrays (OpenCV convention) unless
noted. Gradio RGB conversion is done at the boundary in process_with_options.
"""

from __future__ import annotations

import os
import random
import time
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Optional scanner_fixer import (graceful fallback)
# ---------------------------------------------------------------------------
try:
    from scanner_fixer.pipeline import fix_scan as _fix_scan  # type: ignore
    from scanner_fixer.crop import auto_crop as _auto_crop  # type: ignore
    from scanner_fixer.deskew import deskew as _deskew  # type: ignore
    from scanner_fixer.enhance import enhance_for_ocr as _enhance_for_ocr  # type: ignore

    SCANNER_FIXER_AVAILABLE = True
except ImportError:
    SCANNER_FIXER_AVAILABLE = False
    _fix_scan = None  # type: ignore
    _auto_crop = None  # type: ignore
    _deskew = None  # type: ignore
    _enhance_for_ocr = None  # type: ignore


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


# ---------------------------------------------------------------------------
# Manual crop (interactive gr.Image tool="select" support)
# ---------------------------------------------------------------------------
def apply_manual_crop(
    image_bgr: np.ndarray,
    crop_box: Optional[Any],
) -> np.ndarray:
    """Apply manual crop using a selection box.

    Supports two crop_box formats:
    - dict:  {"x": int, "y": int, "width": int, "height": int}
             (Gradio's tool="select" returns this)
    - tuple/list: (x, y, w, h)

    Returns the original image unchanged if crop_box is None or has zero area.
    """
    if crop_box is None:
        return image_bgr
    if image_bgr is None or image_bgr.size == 0:
        return image_bgr

    # Parse crop_box
    if isinstance(crop_box, dict):
        x = int(crop_box.get("x", 0))
        y = int(crop_box.get("y", 0))
        w = int(crop_box.get("width", 0))
        h = int(crop_box.get("height", 0))
    elif isinstance(crop_box, (list, tuple)):
        if len(crop_box) < 4:
            return image_bgr
        x, y, w, h = [int(v) for v in crop_box[:4]]
    else:
        return image_bgr

    if w <= 0 or h <= 0:
        return image_bgr

    H, W = image_bgr.shape[:2]
    x1 = max(0, min(x, W))
    y1 = max(0, min(y, H))
    x2 = max(0, min(x + w, W))
    y2 = max(0, min(y + h, H))

    if x2 <= x1 or y2 <= y1:
        return image_bgr

    return image_bgr[y1:y2, x1:x2].copy()


# ---------------------------------------------------------------------------
# Advanced edge detection (composable)
# ---------------------------------------------------------------------------
def apply_canny_edges(
    image_bgr: np.ndarray,
    low: int = 50,
    high: int = 150,
) -> np.ndarray:
    """Apply Canny edge detection, return BGR image with edges highlighted."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr
    edges = cv2.Canny(gray, low, high, apertureSize=3)
    return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)


def apply_adaptive_threshold(
    image_bgr: np.ndarray,
    block_size: int = 15,
    c_const: int = 5,
) -> np.ndarray:
    """Apply adaptive thresholding for uneven lighting documents."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr
    block_size = max(3, block_size | 1)  # must be odd, >=3
    result = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, block_size, c_const,
    )
    return cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)


def apply_morphology(
    image_bgr: np.ndarray,
    operation: str = "close",
    kernel_size: int = 5,
) -> np.ndarray:
    """Apply morphological operation (close/open/erode/dilate)."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))

    ops = {
        "close": cv2.MORPH_CLOSE,
        "open": cv2.MORPH_OPEN,
        "erode": cv2.MORPH_ERODE,
        "dilate": cv2.MORPH_DILATE,
    }
    op = ops.get(operation, cv2.MORPH_CLOSE)
    result = cv2.morphologyEx(gray, op, kernel) if op != cv2.MORPH_ERODE and op != cv2.MORPH_DILATE else cv2.morphologyEx(gray, op, kernel)
    if op == cv2.MORPH_ERODE:
        result = cv2.erode(gray, kernel)
    elif op == cv2.MORPH_DILATE:
        result = cv2.dilate(gray, kernel)
    return cv2.cvtColor(result, cv2.COLOR_GRAY2BGR)


def detect_hough_lines(
    image_bgr: np.ndarray,
    threshold: int = 100,
) -> tuple[np.ndarray, list[float]]:
    """Detect lines via Hough transform; return (annotated image, list of angles)."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if len(image_bgr.shape) == 3 else image_bgr
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold)

    annotated = image_bgr.copy()
    angles: list[float] = []

    if lines is not None:
        for line in lines:
            rho, theta = line[0]
            angles.append(float(np.degrees(theta)))
            a = np.cos(theta)
            b = np.sin(theta)
            x0 = a * rho
            y0 = b * rho
            x1 = int(x0 + 1000 * (-b))
            y1 = int(y0 + 1000 * (a))
            x2 = int(x0 - 1000 * (-b))
            y2 = int(y0 - 1000 * (a))
            cv2.line(annotated, (x1, y1), (x2, y2), (0, 0, 255), 1)

    return annotated, angles


def apply_advanced_edges(
    image_bgr: np.ndarray,
    use_canny: bool = False,
    use_adaptive: bool = False,
    use_morphology: bool = False,
    use_hough: bool = False,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Apply selected edge-detection operations in sequence.

    Returns (processed_image, metadata_dict).
    """
    if image_bgr is None or image_bgr.size == 0:
        return image_bgr, {"error": "empty image"}

    result = image_bgr.copy()
    meta: dict[str, Any] = {"operations": []}

    if use_canny:
        result = apply_canny_edges(result)
        meta["operations"].append("canny")
    if use_adaptive:
        result = apply_adaptive_threshold(result)
        meta["operations"].append("adaptive_threshold")
    if use_morphology:
        result = apply_morphology(result, operation="close", kernel_size=5)
        meta["operations"].append("morphology")
    if use_hough:
        result, angles = detect_hough_lines(result)
        meta["hough_angles_count"] = len(angles)
        if angles:
            meta["hough_dominant_angle"] = float(np.median(angles))
        meta["operations"].append("hough")

    return result, meta


# ---------------------------------------------------------------------------
# Save processed image
# ---------------------------------------------------------------------------
def save_processed_image(
    image_bgr: np.ndarray,
    output_dir: str,
    filename: Optional[str] = None,
) -> str:
    """Save a BGR numpy image to output_dir/filename.

    If filename is None, generates a timestamp-based name.
    Creates output_dir if it does not exist.
    Returns the absolute path to the saved file.
    """
    if image_bgr is None or image_bgr.size == 0:
        raise ValueError("Cannot save empty image")

    out_path = Path(output_dir).expanduser().resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    if filename is None:
        filename = f"scan_{int(time.time() * 1000)}.png"
    else:
        # Sanitize filename
        filename = Path(filename).name

    if not Path(filename).suffix:
        filename = f"{filename}.png"

    file_path = out_path / filename
    ok, buf = cv2.imencode(Path(filename).suffix, image_bgr)
    if not ok:
        raise RuntimeError(f"Failed to encode image as {Path(filename).suffix}")
    file_path.write_bytes(buf.tobytes())
    return str(file_path)


# ---------------------------------------------------------------------------
# Pick random preview from gallery (used by batch tab)
# ---------------------------------------------------------------------------
def pick_random_from_gallery(
    gallery_paths: list[str],
) -> tuple[Optional[np.ndarray], str]:
    """Pick a random image path from the list, return (RGB numpy, label)."""
    if not gallery_paths:
        return None, "⚠️ لا توجد صور في المعرض"
    chosen = random.choice(gallery_paths)
    img = cv2.imread(chosen)
    if img is None:
        return None, f"⚠️ تعذر قراءة: {chosen}"
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return rgb, f"🔍 معاينة عشوائية: `{Path(chosen).name}`"


# ---------------------------------------------------------------------------
# Full pipeline: process with manual crop + advanced options
# ---------------------------------------------------------------------------
def process_with_options(
    input_image_rgb: Optional[np.ndarray],
    crop_box: Optional[Any] = None,
    do_crop: bool = True,
    do_deskew: bool = True,
    do_enhance: bool = True,
    do_rotate: bool = False,
    binarize: bool = False,
    crop_padding: int = 10,
    use_canny: bool = False,
    use_adaptive: bool = False,
    use_morphology: bool = False,
    use_hough: bool = False,
) -> tuple[Optional[Image.Image], Optional[Image.Image], str]:
    """Process an image with manual crop + scanner_fixer + advanced edges.

    Returns (before_pil, after_pil, report_markdown).
    """
    if input_image_rgb is None:
        return None, None, "⚠️ لم يتم تحميل صورة"

    # Convert RGB (from Gradio) → BGR (for OpenCV)
    bgr = cv2.cvtColor(input_image_rgb, cv2.COLOR_RGB2BGR)
    before_pil = Image.fromarray(input_image_rgb)

    # 1. Apply manual crop first (if provided)
    manual_cropped = False
    if crop_box is not None:
        bgr = apply_manual_crop(bgr, crop_box)
        manual_cropped = True

    # 2. Run scanner_fixer pipeline
    fix_report: dict[str, Any] = {}
    if SCANNER_FIXER_AVAILABLE:
        try:
            result = _fix_scan(
                bgr,
                do_crop=do_crop,
                do_deskew=do_deskew,
                do_enhance=do_enhance,
                do_rotate=do_rotate,
                binarize=binarize,
                crop_padding=crop_padding,
            )
            fixed_bgr = result.get("image", bgr)
            fix_report = result.get("report", {})
            fix_steps = list(result.get("steps", {}).keys())
        except Exception as exc:
            return before_pil, None, f"❌ خطأ في scanner_fixer: {exc}"
    else:
        # Fallback: just apply advanced edges
        fixed_bgr = bgr.copy()
        fix_steps = []

    # 3. Apply advanced edge detection on top
    edge_meta: dict[str, Any] = {}
    if use_canny or use_adaptive or use_morphology or use_hough:
        fixed_bgr, edge_meta = apply_advanced_edges(
            fixed_bgr,
            use_canny=use_canny,
            use_adaptive=use_adaptive,
            use_morphology=use_morphology,
            use_hough=use_hough,
        )

    after_rgb = cv2.cvtColor(fixed_bgr, cv2.COLOR_BGR2RGB)
    after_pil = Image.fromarray(after_rgb)

    # 4. Build report
    lines = [
        "## 📊 تقرير المعالجة",
        f"- **الحجم الأصلي:** {input_image_rgb.shape[1]}×{input_image_rgb.shape[0]}",
        f"- **الحجم بعد المعالجة:** {fixed_bgr.shape[1]}×{fixed_bgr.shape[0]}",
    ]
    if manual_cropped:
        lines.append("- ✂️ **قص يدوي مُطبَّق**")
    if fix_steps:
        lines.append(f"- **خطوات scanner_fixer:** {', '.join(fix_steps)}")
    if edge_meta.get("operations"):
        lines.append(f"- **كشف الحواف:** {', '.join(edge_meta['operations'])}")
        if "hough_dominant_angle" in edge_meta:
            lines.append(
                f"- **زاوية Hough المهيمنة:** {edge_meta['hough_dominant_angle']:.2f}°"
            )
    if "skew_angle" in fix_report:
        lines.append(f"- **زاوية الميل:** {fix_report['skew_angle']:.2f}°")
    if "crop_box" in fix_report:
        l, t, r, b = fix_report["crop_box"]
        lines.append(f"- **حدود القص التلقائي:** يسار={l}, أعلى={t}, يمين={r}, أسفل={b}")

    return before_pil, after_pil, "\n".join(lines)


# ---------------------------------------------------------------------------
# Convenience: build a "save all as ZIP" helper
# ---------------------------------------------------------------------------
def build_zip_from_dir(
    image_dir: str,
    zip_path: Optional[str] = None,
) -> str:
    """Zip all image files in image_dir into a single .zip.

    If zip_path is None, writes alongside image_dir as <dir>.zip.
    Returns the absolute path to the created ZIP file.
    """
    import zipfile

    src = Path(image_dir).expanduser().resolve()
    if not src.is_dir():
        raise FileNotFoundError(f"Directory not found: {src}")

    if zip_path is None:
        zip_path = str(src.parent / f"{src.name}.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(src.rglob("*")):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS:
                arcname = p.relative_to(src)
                zf.write(str(p), str(arcname))
    return zip_path
