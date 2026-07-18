"""
scanner_fixer.core
==================

Core image-correction pipeline for scanned medical documents.

Pipeline (per image):
  1. Load (path | PIL.Image | np.ndarray)
  2. Text-aware auto-crop (Tesseract OCR boxes, fallback to Canny edges)
  3. Auto-rotate (Hough-line skew estimation)
  4. CLAHE contrast enhancement
  5. Non-local-means denoising
  6. Return RGB np.ndarray + metadata dict

All bugs that appeared in earlier drafts are fixed here:
  - ``auto_rotate_strong`` is actually defined (no NameError)
  - axis order from ``np.where`` is respected (rows=y, cols=x)
  - bare ``except:`` replaced with explicit ``except Exception``
  - ``pytesseract`` import is guarded (graceful fallback if missing)
  - no redundant BGR<->RGB round-trips
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Optional: pytesseract for text-aware cropping
try:
    import pytesseract
    _HAS_TESSERACT = True
except Exception:
    _HAS_TESSERACT = False
    logger.info("pytesseract not available — falling back to edge-based crop")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_bgr(image: Any) -> np.ndarray:
    """Coerce path | PIL.Image | ndarray into a BGR uint8 ndarray."""
    if isinstance(image, Image.Image):
        rgb = np.array(image.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    if isinstance(image, (str, Path)):
        img = cv2.imread(str(image))
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {image}")
        return img
    if isinstance(image, np.ndarray):
        return image.copy()
    raise TypeError(f"Unsupported image type: {type(image)!r}")


def _bgr_to_rgb(bgr: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


# ---------------------------------------------------------------------------
# Edge detection
# ---------------------------------------------------------------------------

def detect_edges_strong(image: Any) -> tuple[np.ndarray, np.ndarray]:
    """
    Strong edge map combining adaptive threshold + Canny + morphology.

    Returns
    -------
    edges : np.ndarray (uint8, same HxW as input)
    gray  : np.ndarray (uint8, grayscale)
    """
    img = _to_bgr(image)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11, 2,
    )
    edges = cv2.Canny(binary, 50, 150)

    kernel = np.ones((5, 5), np.uint8)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    edges = cv2.dilate(edges, kernel, iterations=2)
    return edges, gray


# ---------------------------------------------------------------------------
# Auto-rotate
# ---------------------------------------------------------------------------

def auto_rotate_strong(image: Any) -> np.ndarray:
    """
    Estimate skew angle via Hough transform on a binary edge map and
    deskew. Falls back to returning the image unchanged if estimation fails.
    Input/output: BGR ndarray.
    """
    img = _to_bgr(image)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Binarize
    bw = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        15, 8,
    )

    # Use minAreaRect over all non-zero points — robust skew estimator
    coords = cv2.findNonZero(bw)
    if coords is None or len(coords) < 50:
        return img

    rect = cv2.minAreaRect(coords)
    (cx, cy), (w, h), angle = rect

    # minAreaRect returns angle in [-90, 0). Normalize to true skew.
    if w < h:
        angle = angle + 90

    # Only correct if skew is meaningful (avoid tiny wobbles)
    if abs(angle) < 0.5 or abs(angle) > 45:
        return img

    (h_img, w_img) = img.shape[:2]
    M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    rotated = cv2.warpAffine(
        img, M, (w_img, h_img),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated


# ---------------------------------------------------------------------------
# Text-aware crop
# ---------------------------------------------------------------------------

def text_aware_auto_crop(image: Any, padding: int = 15, min_conf: int = 35) -> np.ndarray:
    """
    Crop to the bounding box of detected text regions. Falls back to
    edge-based crop if Tesseract is unavailable or returns nothing.
    Input/output: BGR ndarray.
    """
    img = _to_bgr(image)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    x_min = y_min = None
    x_max = y_max = None

    if _HAS_TESSERACT:
        try:
            data = pytesseract.image_to_data(
                gray, output_type=pytesseract.Output.DICT
            )
            boxes = []
            for i in range(len(data["text"])):
                try:
                    conf = int(data["conf"][i])
                except (ValueError, TypeError):
                    continue
                if conf > min_conf and str(data["text"][i]).strip():
                    x = int(data["left"][i])
                    y = int(data["top"][i])
                    w = int(data["width"][i])
                    h = int(data["height"][i])
                    boxes.append((x, y, w, h))
            if boxes:
                x_min = min(b[0] for b in boxes)
                y_min = min(b[1] for b in boxes)
                x_max = max(b[0] + b[2] for b in boxes)
                y_max = max(b[1] + b[3] for b in boxes)
        except Exception as exc:
            logger.warning("Tesseract crop failed (%s) — falling back to edges", exc)

    if x_min is None:
        # Edge-based fallback — respect (rows=y, cols=x) ordering from np.where
        edges, _ = detect_edges_strong(img)
        ys, xs = np.where(edges > 0)
        if len(xs) == 0:
            return img
        x_min, x_max = int(xs.min()), int(xs.max())
        y_min, y_max = int(ys.min()), int(ys.max())

    H, W = img.shape[:2]
    x_min = max(0, x_min - padding)
    y_min = max(0, y_min - padding)
    x_max = min(W, x_max + padding)
    y_max = min(H, y_max + padding)

    if x_max - x_min < 10 or y_max - y_min < 10:
        return img

    return img[y_min:y_max, x_min:x_max]


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def fix_scanned_image(input_source: Any, output_path: str | Path | None = None) -> tuple[np.ndarray, dict]:
    """
    Full pipeline: crop -> rotate -> enhance -> denoise.

    Parameters
    ----------
    input_source : path | PIL.Image | np.ndarray
    output_path  : optional path to save the result (BGR for cv2.imwrite).

    Returns
    -------
    final_rgb : np.ndarray (HxWx3, RGB, uint8)
    meta      : dict with status flags and intermediate shapes
    """
    img_bgr = _to_bgr(input_source)
    meta: dict[str, Any] = {"input_shape": tuple(img_bgr.shape)}

    # 1. Text-aware crop
    cropped = text_aware_auto_crop(img_bgr)
    meta["cropped_shape"] = tuple(cropped.shape)

    # 2. Auto-rotate
    rotated = auto_rotate_strong(cropped)
    meta["rotated_shape"] = tuple(rotated.shape)

    # 3. CLAHE on grayscale
    gray = cv2.cvtColor(rotated, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # 4. Denoise
    denoised = cv2.fastNlMeansDenoising(enhanced, h=10)

    # 5. Back to RGB for downstream consumers
    final_rgb = cv2.cvtColor(denoised, cv2.COLOR_GRAY2RGB)
    meta["final_shape"] = tuple(final_rgb.shape)
    meta["status"] = "success"
    meta["used_tesseract"] = _HAS_TESSERACT

    if output_path:
        # cv2.imwrite expects BGR
        cv2.imwrite(str(output_path), cv2.cvtColor(final_rgb, cv2.COLOR_RGB2BGR))
        meta["output_path"] = str(output_path)

    return final_rgb, meta


def batch_fix_folder(
    folder: str | Path,
    output_dir: str | Path | None = None,
) -> list[dict]:
    """
    Run fix_scanned_image over every image file in ``folder``.

    Returns a list of per-image metadata dicts (one per image). If
    ``output_dir`` is provided, each result is saved there as
    ``<stem>_fixed.png``.
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise NotADirectoryError(folder)

    exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
    out_dir = Path(output_dir) if output_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() not in exts:
            continue
        try:
            out_path = (out_dir / f"{path.stem}_fixed.png") if out_dir else None
            _, meta = fix_scanned_image(path, output_path=out_path)
            meta["file"] = str(path)
            results.append(meta)
        except Exception as exc:
            results.append({"file": str(path), "status": "error", "error": str(exc)})
    return results
