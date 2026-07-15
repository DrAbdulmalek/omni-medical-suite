# app/services/ocr_service.py
"""OCR Service — Engine initialization, image preprocessing, and OCR processing.

Encapsulates all OCR engine lifecycle management (PaddleOCR, Tesseract,
ImagePreprocessor, HybridSpellChecker) and the text-extraction pipeline
functions used by the Gradio HITL interface.

Module-level globals are initialised at import time so that downstream
consumers can simply ``from app.services.ocr_service import paddle_ocr``.
"""

import logging
import re

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── OCR common misrecognition corrections ─────────────────────────────────────
OCR_CORRECTIONS = {
    "باراسيتبمول": "باراسيتامول", "ايبوروفين": "ايبوبروفين",
    "اموكسيستلين": "اموكسيسيلين", "اموكسيسلين": "اموكسيسيلين",
    "ازيثروميسين": "ازيثرومايسين", "ميتروندازول": "ميترونيدازول",
    "ديكلوفيناك ": "ديكلوفيناك", "اوجمينتين": "اوجمنتين",
    "اوميبرازول ": "اوميبرازول", "سيليبريكس ": "سيليبريكس",
    "ترامادول ": "ترامادول", "كاتافلام ": "كاتافلام",
    "نوفافين ": "نوفافين", "فلاميكس ": "فلاميكس",
    "بنادول ": "بنادول", "ادفيل ": "ادفيل",
}

# ── Initialize OCR Engines ──────────────────────────────────────────────────
logger.info("Initializing OCR engines...")

# ImagePreprocessor (582-line module in packages/vision/)
image_preprocessor = None
HAS_PREPROCESSOR = False
try:
    from packages.vision.image_preprocessor import ImagePreprocessor
    image_preprocessor = ImagePreprocessor(
        apply_clahe=True, apply_denoise=True,
        apply_deskew=True, deskew_angle_threshold=5.0,
        apply_binarize=True,
    )
    HAS_PREPROCESSOR = True
    logger.info("ImagePreprocessor loaded (CLAHE+denoise+deskew+binarize)")
except Exception as e:
    logger.warning(f"ImagePreprocessor not available, will use fallback: {e}")

# PaddleOCR (primary — best Arabic support)
paddle_ocr = None
try:
    from paddleocr import PaddleOCR
    paddle_ocr = PaddleOCR(
        use_angle_cls=True, lang="ar", show_log=False,
        use_gpu=False, det_db_thresh=0.3, det_db_box_thresh=0.5,
        det_db_unclip_ratio=1.6, max_text_length=800, use_mp=True,
    )
    logger.info("PaddleOCR initialized successfully")
except Exception as e:
    logger.error(f"PaddleOCR init failed: {e}")

# Tesseract (secondary — always-on safety net)
HAS_TESSERACT = False
try:
    import pytesseract
    pytesseract.get_tesseract_version()
    HAS_TESSERACT = True
    logger.info("Tesseract initialized successfully")
except Exception as e:
    logger.warning(f"Tesseract not available: {e}")

# Spell Checker (tested v7.1 module)
spell_checker = None
try:
    from packages.core.spell_checker import HybridSpellChecker
    spell_checker = HybridSpellChecker()
    logger.info("HybridSpellChecker v7.1 loaded")
except Exception as e:
    logger.warning(f"Spell checker not available: {e}")


# ── Processing Functions ────────────────────────────────────────────────────

def _preprocess_image(image: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """
    Preprocess image using ImagePreprocessor (582-line module) if available,
    otherwise fallback to basic CLAHE+Otsu. Returns (processed, steps_log).
    """
    steps = []
    cleaned = None

    # Full preprocessor (CLAHE + denoise + deskew 5°+ + binarize)
    if HAS_PREPROCESSOR and image_preprocessor is not None:
        try:
            cleaned = image_preprocessor.preprocess(image, return_numpy=True)
            if cleaned.ndim == 2:  # grayscale → RGB for Gradio display
                cleaned = cv2.cvtColor(cleaned, cv2.COLOR_GRAY2RGB)
            steps.append("ImagePreprocessor (CLAHE+denoise+deskew+binarize)")
        except Exception as e:
            logger.warning(f"ImagePreprocessor failed, falling back: {e}")
            cleaned = None

    # Fallback: CLAHE + Otsu
    if cleaned is None:
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            cleaned = cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)
            steps.append("Fallback CLAHE+Otsu")
        except Exception as e:
            logger.debug(f"Basic preprocessing fallback failed: {e}")
            cleaned = image
            steps.append("No preprocessing")

    return cleaned, steps


def _run_paddle_ocr(image: np.ndarray) -> tuple[str, list[dict]]:
    """Run PaddleOCR. Returns (full_text, line_details)."""
    if paddle_ocr is None:
        return "", []
    try:
        img_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        result = paddle_ocr.ocr(img_bgr, cls=True)
        lines, details = [], []
        if result and result[0]:
            for idx, line in enumerate(result[0]):
                text = line[1][0].strip()
                conf = line[1][1]
                if text:
                    lines.append(text)
                    details.append({"line": idx+1, "text": text,
                                   "confidence": round(float(conf), 4)})
        return "\n".join(lines), details
    except Exception as e:
        logger.error(f"PaddleOCR error: {e}")
        return "", []


def _run_tesseract(image: np.ndarray) -> tuple[str, float]:
    """Run Tesseract. Returns (text, avg_confidence)."""
    if not HAS_TESSERACT:
        return "", 0.0
    try:
        import pytesseract
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        text = pytesseract.image_to_string(gray, lang="ara+eng", config="--psm 6")
        try:
            data = pytesseract.image_to_data(gray, lang="ara+eng", output_type=pytesseract.Output.DICT)
            confs = [int(c) for c in data["conf"] if int(c) > 0]
            avg_conf = sum(confs) / len(confs) if confs else 0.0
        except Exception:
            avg_conf = 0.0
        return text.strip(), round(avg_conf, 2)
    except Exception as e:
        logger.error(f"Tesseract error: {e}")
        return "", 0.0


def _auto_correct_ocr(text: str) -> tuple[str, list[dict]]:
    """Apply OCR corrections + spell checker. Returns (corrected, changes)."""
    changes = []
    corrected = text
    for wrong, right in OCR_CORRECTIONS.items():
        if wrong in corrected:
            count = corrected.count(wrong)
            corrected = corrected.replace(wrong, right)
            changes.append({"type": "ocr_fix", "from": wrong, "to": right, "count": count})
    # Normalize whitespace
    corrected = re.sub(r'[ \t]+', ' ', corrected)
    corrected = re.sub(r'\n{3,}', '\n\n', corrected).strip()
    return corrected, changes