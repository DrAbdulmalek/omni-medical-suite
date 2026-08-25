# app/services/ocr_service.py
"""OCR Service — Engine initialization, image preprocessing, and OCR processing.

Encapsulates all OCR engine lifecycle management (PaddleOCR, Tesseract,
ImagePreprocessor, HybridSpellChecker) and the text-extraction pipeline
functions used by the Gradio HITL interface.

Since v1.1.0-rc (P0 hardening): heavy engines are **lazily loaded** via
factory getters. Importing this module no longer triggers PaddleOCR or
Tesseract initialization. Callers should use the getters
``get_paddle_ocr()``, ``get_image_preprocessor()``, ``get_spell_checker()``,
and ``has_tesseract()`` instead of reading the module-level globals
directly. The legacy globals (``paddle_ocr``, ``image_preprocessor``,
``spell_checker``, ``HAS_PREPROCESSOR``, ``HAS_TESSERACT``) are kept as
backward-compatibility shims that delegate to the getters, so existing
imports keep working — but they no longer pay the initialization cost at
import time.
"""

import logging
import re
import threading

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── OCR common misrecognition corrections ─────────────────────────────────────
OCR_CORRECTIONS = {
    "باراسيتبمول": "باراسيتامول", "ايبوروفين": "ايبوبروفين",
    "اموكسيستلين": "اموكسيسيلين", "اموكسيسلين": "اموكسيسيلين",
    "ازيثروميسين": "ازيثرومايسين", "ميتروندازول": "ميترونيدازول",
    "اوجمينتين": "اوجمنتين",
    "اوميبرازول": "اوميبرازول", "سيليبريكس": "سيليبريكس",
    "كاتافلام": "كاتافلام",
    "فلاميكس": "فلاميكس",
    "بنادول": "بنادول", "ادفيل": "ادفيل",
}

# ── Lazy singletons (thread-safe) ────────────────────────────────────────────
# Each heavy resource is constructed on first access via its getter. The
# legacy module-level names are kept as property-like shims for backward
# compatibility (see _LazyGlobal below). Importing this module is now O(1)
# and never triggers network I/O or model loading.

_lock = threading.Lock()
_paddle_ocr_singleton: "object | None" = None
_paddle_ocr_failed: bool = False  # remember failure to avoid retrying on every call
_image_preprocessor_singleton: "object | None" = None
_image_preprocessor_failed: bool = False
_spell_checker_singleton: "object | None" = None
_spell_checker_failed: bool = False
_tesseract_probed: bool = False
_tesseract_available: bool = False


def get_paddle_ocr():
    """Return the singleton PaddleOCR instance, or ``None`` if unavailable.

    Construction happens on first call. Failures are cached so subsequent
    calls don't retry (a missing dep won't recover without a restart).
    """
    global _paddle_ocr_singleton, _paddle_ocr_failed
    if _paddle_ocr_singleton is not None:
        return _paddle_ocr_singleton
    if _paddle_ocr_failed:
        return None
    with _lock:
        # Re-check inside the lock
        if _paddle_ocr_singleton is not None:
            return _paddle_ocr_singleton
        if _paddle_ocr_failed:
            return None
        try:
            from paddleocr import PaddleOCR

            # PaddlePaddle 3.x: `device="cpu"` replaces the deprecated
            # `use_gpu=False` kwarg. Kept in lock-step with hf-space/app.py
            # (see docs/DEPLOYMENT.md §"HF Space drift control").
            _paddle_ocr_singleton = PaddleOCR(
                use_angle_cls=True, lang="ar", show_log=False,
                device="cpu", det_db_thresh=0.3, det_db_box_thresh=0.5,
                det_db_unclip_ratio=1.6, max_text_length=800, use_mp=True,
            )
            logger.info("PaddleOCR initialized successfully (lazy)")
        except Exception as e:
            _paddle_ocr_failed = True
            logger.error("PaddleOCR init failed (cached as unavailable): %s", e)
        return _paddle_ocr_singleton


def get_image_preprocessor():
    """Return the singleton ImagePreprocessor, or ``None`` if unavailable."""
    global _image_preprocessor_singleton, _image_preprocessor_failed
    if _image_preprocessor_singleton is not None:
        return _image_preprocessor_singleton
    if _image_preprocessor_failed:
        return None
    with _lock:
        if _image_preprocessor_singleton is not None:
            return _image_preprocessor_singleton
        if _image_preprocessor_failed:
            return None
        try:
            from packages.vision.image_preprocessor import ImagePreprocessor

            _image_preprocessor_singleton = ImagePreprocessor(
                apply_clahe=True, apply_denoise=True,
                apply_deskew=True, deskew_angle_threshold=5.0,
                apply_binarize=True,
            )
            logger.info("ImagePreprocessor loaded (CLAHE+denoise+deskew+binarize) (lazy)")
        except Exception as e:
            _image_preprocessor_failed = True
            logger.warning("ImagePreprocessor not available (cached): %s", e)
        return _image_preprocessor_singleton


def has_preprocessor() -> bool:
    """True if ``get_image_preprocessor()`` would return a non-None object."""
    return get_image_preprocessor() is not None


def has_tesseract() -> bool:
    """Probe Tesseract availability once; cache the result."""
    global _tesseract_probed, _tesseract_available
    if _tesseract_probed:
        return _tesseract_available
    with _lock:
        if _tesseract_probed:
            return _tesseract_available
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            _tesseract_available = True
            logger.info("Tesseract initialized successfully (lazy)")
        except Exception as e:
            _tesseract_available = False
            logger.warning("Tesseract not available (cached): %s", e)
        _tesseract_probed = True
        return _tesseract_available


def get_spell_checker():
    """Return the singleton HybridSpellChecker, or ``None`` if unavailable."""
    global _spell_checker_singleton, _spell_checker_failed
    if _spell_checker_singleton is not None:
        return _spell_checker_singleton
    if _spell_checker_failed:
        return None
    with _lock:
        if _spell_checker_singleton is not None:
            return _spell_checker_singleton
        if _spell_checker_failed:
            return None
        try:
            from packages.core.spell_checker import HybridSpellChecker

            _spell_checker_singleton = HybridSpellChecker()
            logger.info("HybridSpellChecker loaded (lazy)")
        except Exception as e:
            _spell_checker_failed = True
            logger.warning("Spell checker not available (cached): %s", e)
        return _spell_checker_singleton


def reset_lazy_cache() -> None:
    """Reset all lazy singletons. Intended for tests; do not call in production."""
    global _paddle_ocr_singleton, _paddle_ocr_failed
    global _image_preprocessor_singleton, _image_preprocessor_failed
    global _spell_checker_singleton, _spell_checker_failed
    global _tesseract_probed, _tesseract_available
    with _lock:
        _paddle_ocr_singleton = None
        _paddle_ocr_failed = False
        _image_preprocessor_singleton = None
        _image_preprocessor_failed = False
        _spell_checker_singleton = None
        _spell_checker_failed = False
        _tesseract_probed = False
        _tesseract_available = False


# ── Backward-compatibility shims ─────────────────────────────────────────────
# Pre-P0 callers did `from app.services.ocr_service import paddle_ocr, HAS_TESSERACT, ...`
# These module-level attributes evaluate the getters on access, preserving
# behavior without re-introducing import-time work. They are read-only —
# assigning to them has no effect on the underlying singletons.

class _LazyAttr:
    """Descriptor that delegates attribute access to a getter function.

    Used to keep module-level names like ``paddle_ocr`` working without
    triggering eager initialization at import time.
    """

    def __init__(self, getter):
        self._getter = getter

    def __get__(self, instance, owner=None):
        return self._getter()


# We can't use a descriptor on a module directly, so we expose them as
# plain module-level functions that mimic attribute access via __getattr__.
# Simplest approach: just expose them as functions that return the value,
# and rely on Python's late binding. Callers writing `paddle_ocr.ocr(...)`
# must use `get_paddle_ocr().ocr(...)` instead — but callers writing
# `if paddle_ocr is None:` will see None on first access (good) and the
# instance on subsequent access (good).
#
# To preserve the exact pre-P0 surface, we re-export the getters under
# the old names as properties of a small proxy module.

def __getattr__(name):  # PEP 562 — module-level __getattr__
    if name == "paddle_ocr":
        return get_paddle_ocr()
    if name == "image_preprocessor":
        return get_image_preprocessor()
    if name == "spell_checker":
        return get_spell_checker()
    if name == "HAS_PREPROCESSOR":
        return has_preprocessor()
    if name == "HAS_TESSERACT":
        return has_tesseract()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ── Processing Functions ────────────────────────────────────────────────────

def _preprocess_image(image: np.ndarray) -> tuple[np.ndarray, list[str]]:
    """
    Preprocess image using ImagePreprocessor (582-line module) if available,
    otherwise fallback to basic CLAHE+Otsu. Returns (processed, steps_log).
    """
    steps = []
    cleaned = None

    preprocessor = get_image_preprocessor()
    if preprocessor is not None:
        try:
            cleaned = preprocessor.preprocess(image, return_numpy=True)
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
    paddle = get_paddle_ocr()
    if paddle is None:
        return "", []
    try:
        img_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        result = paddle.ocr(img_bgr, cls=True)
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
    if not has_tesseract():
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

    # Apply spell checker (lazy) — non-fatal
    checker = get_spell_checker()
    if checker is not None:
        try:
            corrected = checker.correct_text(corrected)
        except Exception as e:
            logger.debug("spell_checker.correct_text failed (non-fatal): %s", e)

    return corrected, changes
